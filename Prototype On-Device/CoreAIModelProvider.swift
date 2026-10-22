//
//  CoreAIModelProvider.swift
//  Prototype On-Device
//

import Foundation
import FoundationModels
import CoreAILanguageModels

enum CoreAIModelProviderError: LocalizedError {
    case resourceNotFound

    var errorDescription: String? {
        "The Core AI model resource could not be found in the app bundle."
    }
}

/// Describes one exported Core AI model that can back System B. Only one is
/// bundled at a time: every export's tokenizer/metadata files share the same
/// names, so two models in the app target would collide once Xcode flattens
/// them (see `reconstructedResourceDirectory()`). Swapping models means
/// changing `CoreAIModelProvider.activeModel` and the bundled folder together.
struct CoreAIModelDescriptor {
    /// The export's folder name, which is also its `.aimodel` file name.
    let resourceName: String
    /// Short name shown in the UI and written to exported transcripts.
    let displayName: String
    /// Whether the model runs in "thinking mode" by default and needs Qwen3's
    /// ` /no_think` prompt switch to answer directly.
    let needsNoThinkSwitch: Bool

    static let qwen3_0_6b = CoreAIModelDescriptor(
        resourceName: "qwen3_0_6b_mixed_4bit_8bit_static",
        displayName: "Qwen3-0.6B",
        needsNoThinkSwitch: true
    )

    // Qwen2.5 has no thinking mode (its chat template has no think/no_think
    // handling), so `/no_think` would just be read as literal prompt text.
    static let qwen2_5_1_5b = CoreAIModelDescriptor(
        resourceName: "qwen2_5_1_5b_instruct_4bit_weight_palettized_group8_static",
        displayName: "Qwen2.5-1.5B",
        needsNoThinkSwitch: false
    )

    // Size-matched comparison with Apple's model (~3B). Same Qwen3 chat
    // template as the 0.6B model, so thinking mode is on by default.
    static let qwen3_4b = CoreAIModelDescriptor(
        resourceName: "qwen3_4b_mixed_4bit_8bit_static",
        displayName: "Qwen3-4B",
        needsNoThinkSwitch: true
    )

    // Exploratory: same Qwen3 generation as the 4B model at roughly Qwen2.5-1.5B's
    // size, to separate generation from size. Its chat template has
    // `enable_thinking`, so thinking mode is on by default.
    static let qwen3_1_7b = CoreAIModelDescriptor(
        resourceName: "qwen3_1_7b_6bit_static",
        displayName: "Qwen3-1.7B",
        needsNoThinkSwitch: true
    )
}

/// Lazily loads and caches the bundled Core AI model (System B), so its
/// async load cost (tokenizer + bundle parsing) is paid once rather than on
/// every message. `unload()` releases it when the student switches back to
/// System A, since keeping both backends resident is too much for the
/// device's memory.
final class CoreAIModelProvider {
    static let shared = CoreAIModelProvider()

    /// The model currently bundled as System B.
    static let activeModel = CoreAIModelDescriptor.qwen3_4b

    private var cached: CoreAILanguageModel?

    private init() {}

    func model() async throws -> CoreAILanguageModel {
        if let cached {
            return cached
        }
        let url = try Self.reconstructedResourceDirectory()
        let model = try await CoreAILanguageModel(resourcesAt: url)
        cached = model
        return model
    }

    /// `CoreAILanguageModel` loads its inference engine lazily on the first
    /// request; this forces that load now instead.
    func preload() async throws {
        try await model().load()
    }

    func unload() {
        cached?.unload()
        cached = nil
    }

    /// Xcode's resource-copy step flattens the exported model folder — the
    /// `.aimodel` package, `metadata.json`, and the three tokenizer files all
    /// land loose at the bundle root instead of nested under a `tokenizer/`
    /// subfolder. `CoreAILanguageModel` requires that nesting, so this
    /// rebuilds it once into Caches from the flattened bundle resources,
    /// regardless of how Xcode chose to copy them in.
    private static func reconstructedResourceDirectory() throws -> URL {
        let fileManager = FileManager.default
        let cachesDirectory = try fileManager.url(for: .cachesDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
        let resourceName = activeModel.resourceName
        let destination = cachesDirectory.appendingPathComponent(resourceName, isDirectory: true)

        // Reuse a previous reconstruction rather than re-copying the model on every launch.
        if fileManager.fileExists(atPath: destination.path) {
            return destination
        }

        guard let aimodelURL = Bundle.main.url(forResource: resourceName, withExtension: "aimodel"),
              let metadataURL = Bundle.main.url(forResource: "metadata", withExtension: "json"),
              let tokenizerJSONURL = Bundle.main.url(forResource: "tokenizer", withExtension: "json"),
              let tokenizerConfigURL = Bundle.main.url(forResource: "tokenizer_config", withExtension: "json"),
              let chatTemplateURL = Bundle.main.url(forResource: "chat_template", withExtension: "jinja")
        else {
            throw CoreAIModelProviderError.resourceNotFound
        }

        // Build into a staging directory first so a failure partway through
        // (e.g. low disk space) can't leave a half-copied folder that a
        // later launch would mistake for a complete, cached reconstruction.
        let staging = cachesDirectory.appendingPathComponent("\(resourceName)-staging-\(UUID().uuidString)", isDirectory: true)
        do {
            let tokenizerDirectory = staging.appendingPathComponent("tokenizer", isDirectory: true)
            try fileManager.createDirectory(at: tokenizerDirectory, withIntermediateDirectories: true)
            try fileManager.copyItem(at: aimodelURL, to: staging.appendingPathComponent(aimodelURL.lastPathComponent))
            try fileManager.copyItem(at: metadataURL, to: staging.appendingPathComponent("metadata.json"))
            try fileManager.copyItem(at: tokenizerJSONURL, to: tokenizerDirectory.appendingPathComponent("tokenizer.json"))
            try fileManager.copyItem(at: tokenizerConfigURL, to: tokenizerDirectory.appendingPathComponent("tokenizer_config.json"))
            try fileManager.copyItem(at: chatTemplateURL, to: tokenizerDirectory.appendingPathComponent("chat_template.jinja"))
            try fileManager.moveItem(at: staging, to: destination)
        } catch {
            try? fileManager.removeItem(at: staging)
            throw error
        }

        return destination
    }
}
