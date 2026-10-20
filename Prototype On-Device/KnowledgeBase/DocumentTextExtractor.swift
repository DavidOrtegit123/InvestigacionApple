import Foundation
import PDFKit
import Vision
import UIKit

enum DocumentTextExtractionError: LocalizedError {
    case unreadablePDF
    case unreadableImage
    case noTextFound

    var errorDescription: String? {
        switch self {
        case .unreadablePDF: "Could not open this PDF."
        case .unreadableImage: "Could not read this image."
        case .noTextFound: "No readable text was found in this document."
        }
    }
}

/// Pulls plain text out of an imported PDF or image so it can be stored as
/// an `ImportedMaterial` and used like any other knowledge base document.
enum DocumentTextExtractor {
    static func extractText(fromPDFAt url: URL) throws -> String {
        guard let pdf = PDFDocument(url: url) else { throw DocumentTextExtractionError.unreadablePDF }

        var pages: [String] = []
        for index in 0..<pdf.pageCount {
            if let page = pdf.page(at: index), let text = page.string,
               !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                pages.append(text)
            }
        }

        let joined = pages.joined(separator: "\n\n").trimmingCharacters(in: .whitespacesAndNewlines)
        guard !joined.isEmpty else { throw DocumentTextExtractionError.noTextFound }
        return joined
    }

    static func extractText(fromImageAt url: URL) async throws -> String {
        guard let data = try? Data(contentsOf: url), let image = UIImage(data: data), let cgImage = image.cgImage else {
            throw DocumentTextExtractionError.unreadableImage
        }

        return try await withCheckedThrowingContinuation { continuation in
            let request = VNRecognizeTextRequest { request, error in
                if let error {
                    continuation.resume(throwing: error)
                    return
                }

                let observations = request.results as? [VNRecognizedTextObservation] ?? []
                let text = observations
                    .compactMap { $0.topCandidates(1).first?.string }
                    .joined(separator: "\n")
                    .trimmingCharacters(in: .whitespacesAndNewlines)

                if text.isEmpty {
                    continuation.resume(throwing: DocumentTextExtractionError.noTextFound)
                } else {
                    continuation.resume(returning: text)
                }
            }
            request.recognitionLevel = .accurate
            request.usesLanguageCorrection = true

            do {
                try VNImageRequestHandler(cgImage: cgImage, options: [:]).perform([request])
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }
}
