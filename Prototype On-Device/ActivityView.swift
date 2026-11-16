import SwiftUI
import UIKit

/// Wraps `UIActivityViewController` to share exported files (transcripts,
/// Feedback Assistant attachments) to Files, AirDrop, etc.
struct ActivityView: UIViewControllerRepresentable {
    let activityItems: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: activityItems, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
