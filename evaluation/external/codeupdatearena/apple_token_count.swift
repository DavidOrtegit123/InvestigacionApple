// Counts each full prompt with Apple's on-device tokenizer (design.md §3.2, context-fit rule).
// Usage: swift apple_token_count.swift fit_prompts.json apple_tokens.json
// Needs Apple Intelligence on this Mac; exits with an error rather than estimating.
import Foundation
import FoundationModels

let arguments = CommandLine.arguments
guard arguments.count == 3 else {
    FileHandle.standardError.write("usage: apple_token_count.swift <prompts.json> <out.json>\n".data(using: .utf8)!)
    exit(2)
}
let prompts = try JSONDecoder().decode([String: String].self, from: Data(contentsOf: URL(fileURLWithPath: arguments[1])))
let model = SystemLanguageModel.default
guard case .available = model.availability else {
    FileHandle.standardError.write("Apple Intelligence is not available: \(model.availability)\n".data(using: .utf8)!)
    exit(1)
}

var tokens: [String: Int] = [:]
for (id, text) in prompts.sorted(by: { $0.key < $1.key }) {
    tokens[id] = try await model.tokenCount(for: text)
}
let output: [String: Any] = ["contextSize": model.contextSize, "tokens": tokens]
let data = try JSONSerialization.data(withJSONObject: output, options: [.prettyPrinted, .sortedKeys])
try data.write(to: URL(fileURLWithPath: arguments[2]))
print("\(tokens.count) prompts counted; largest \(tokens.values.max() ?? 0) of \(model.contextSize)")
