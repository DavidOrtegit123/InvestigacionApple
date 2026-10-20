import SwiftUI
import UIKit

/// Wraps `UIActivityViewController` so feedback JSON files can be shared
/// (e.g. saved to Files or attached to a Feedback Assistant report).
struct ActivityView: UIViewControllerRepresentable {
    let activityItems: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: activityItems, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
