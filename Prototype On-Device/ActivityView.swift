import SwiftUI
import UIKit

/// A file to hand to the share sheet. Present it with `.sheet(item:)`, so the
/// sheet can't open before the file's URL is set (with `isPresented:` plus a
/// separate URL, the first presentation could read a stale nil and show an
/// empty sheet).
struct ShareableFile: Identifiable {
    let url: URL
    var id: URL { url }
}

/// Wraps `UIActivityViewController` to share exported files (transcripts,
/// Feedback Assistant attachments) to Files, AirDrop, etc.
struct ActivityView: UIViewControllerRepresentable {
    let activityItems: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: activityItems, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
