import Foundation
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

/// OCRs an imported photo into plain text for an `ImportedMaterial`. PDFs are
/// read by OnDeviceRAG instead (see `MaterialReviewSheet.extract()`).
enum DocumentTextExtractor {
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
