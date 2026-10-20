import Foundation

// Stage 1 retrieval harness (evaluation/rag_stage1_design.md).
// Usage: swift run -c release --package-path evaluation/rag/RetrievalHarness \
//            RetrievalHarness <corpus.json> <queries.json> <output-directory>

nonisolated struct Manual: Decodable {
    let id: String
    let title: String
    let content: String
}

nonisolated struct Corpus: Decodable {
    let manuals: [Manual]
}

nonisolated struct RetrievalQuery: Decodable {
    let taskID: String
    let variant: String
    let query: String

    enum CodingKeys: String, CodingKey {
        case variant, query
        case taskID = "task_id"
    }
}

nonisolated struct PassageRecord: Encodable {
    let id: String
    let documentID: String
    let sectionTitle: String
    let sectionIndex: Int
    let passageIndex: Int
    let text: String

    enum CodingKeys: String, CodingKey {
        case id, text
        case documentID = "document_id"
        case sectionTitle = "section_title"
        case sectionIndex = "section_index"
        case passageIndex = "passage_index"
    }
}

nonisolated struct PassageList: Encodable {
    let passagesWithoutVector: Int
    let passages: [PassageRecord]

    enum CodingKeys: String, CodingKey {
        case passages
        case passagesWithoutVector = "passages_without_vector"
    }
}

nonisolated struct PipelineAResult: Encodable {
    let taskID: String
    let variant: String
    let retrievedManualIDs: [String]

    enum CodingKeys: String, CodingKey {
        case variant
        case taskID = "task_id"
        case retrievedManualIDs = "retrieved_manual_ids"
    }
}

nonisolated struct PipelineBResult: Encodable {
    let taskID: String
    let variant: String
    let ranking: [String]

    enum CodingKeys: String, CodingKey {
        case variant, ranking
        case taskID = "task_id"
    }
}

nonisolated struct RetrievalResults: Encodable {
    let pipelineA: [PipelineAResult]
    let pipelineB: [PipelineBResult]

    enum CodingKeys: String, CodingKey {
        case pipelineA = "pipeline_a"
        case pipelineB = "pipeline_b"
    }
}

nonisolated struct BatchTaskRecord: Decodable {
    let category: String
    let prompt: String
    let referenceDocTitle: String
    let referenceDocContent: String
}

let arguments = CommandLine.arguments

// Stage 2: `RetrievalHarness export-vectors <BatchTasks.json> <RetrievalVectors.json>`
// embeds every passage of the app's corpus and every task prompt with the
// live English NLEmbedding, for bundling (see PrecomputedEmbedding).
if arguments.count == 4, arguments[1] == "export-vectors" {
    let taskDecoder = JSONDecoder()
    taskDecoder.keyDecodingStrategy = .convertFromSnakeCase
    let tasks = try taskDecoder.decode([BatchTaskRecord].self, from: Data(contentsOf: URL(fileURLWithPath: arguments[2])))
    let manuals = RetrievalCorpus.manuals(from: tasks.map {
        RetrievalCorpus.Spec(category: $0.category, title: $0.referenceDocTitle, content: $0.referenceDocContent)
    })
    let passageTexts = manuals.flatMap { PassageChunker.passages(for: $0) }.map(\.indexedText)
    guard let precomputed = PrecomputedEmbedding.compute(for: passageTexts + tasks.map(\.prompt)) else {
        print("English sentence embedding unavailable, or a text got no vector")
        exit(1)
    }
    let vectorEncoder = JSONEncoder()
    vectorEncoder.outputFormatting = [.sortedKeys]
    try vectorEncoder.encode(precomputed).write(to: URL(fileURLWithPath: arguments[3]))
    print("\(precomputed.vectors.count) vectors (\(passageTexts.count) passages, \(tasks.count) prompts), revision \(precomputed.revision), dimension \(precomputed.dimension) -> \(arguments[3])")
    exit(0)
}

guard arguments.count == 4 else {
    print("usage: RetrievalHarness <corpus.json> <queries.json> <output-directory>")
    print("       RetrievalHarness export-vectors <BatchTasks.json> <RetrievalVectors.json>")
    exit(2)
}

let decoder = JSONDecoder()
let corpus = try decoder.decode(Corpus.self, from: Data(contentsOf: URL(fileURLWithPath: arguments[1])))
let queries = try decoder.decode([RetrievalQuery].self, from: Data(contentsOf: URL(fileURLWithPath: arguments[2])))
let outputDirectory = URL(fileURLWithPath: arguments[3], isDirectory: true)

let documents = corpus.manuals.map {
    KnowledgeDocument(id: $0.id, title: $0.title, topic: $0.id, difficulty: .beginner, keywords: [], content: $0.content)
}
let pipelineA = KnowledgeRetriever(documents: documents)
let pipelineB = HybridRetriever(documents: documents)

let results = RetrievalResults(
    pipelineA: queries.map { query in
        PipelineAResult(
            taskID: query.taskID,
            variant: query.variant,
            retrievedManualIDs: pipelineA.retrieve(for: query.query, topK: documents.count).map(\.id)
        )
    },
    pipelineB: queries.map { query in
        PipelineBResult(
            taskID: query.taskID,
            variant: query.variant,
            ranking: pipelineB.rankAll(for: query.query).map(\.passage.id)
        )
    }
)
let passageList = PassageList(
    passagesWithoutVector: pipelineB.passagesWithoutVector,
    passages: pipelineB.passages.map {
        PassageRecord(id: $0.id, documentID: $0.documentID, sectionTitle: $0.sectionTitle,
                      sectionIndex: $0.sectionIndex, passageIndex: $0.passageIndex, text: $0.text)
    }
)

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
try FileManager.default.createDirectory(at: outputDirectory, withIntermediateDirectories: true)
try encoder.encode(passageList).write(to: outputDirectory.appendingPathComponent("passages.json"))
try encoder.encode(results).write(to: outputDirectory.appendingPathComponent("retrieval_results.json"))
print("\(queries.count) queries, \(pipelineB.passages.count) passages (\(pipelineB.passagesWithoutVector) without vector) -> \(outputDirectory.path)")
