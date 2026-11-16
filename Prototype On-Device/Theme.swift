import SwiftUI

/// The app's bright color palette.
enum TutorPalette {
    static let purple = Color(red: 0.45, green: 0.32, blue: 0.98)
    static let pink = Color(red: 1.0, green: 0.35, blue: 0.62)
    static let orange = Color(red: 1.0, green: 0.60, blue: 0.20)
    static let yellow = Color(red: 1.0, green: 0.78, blue: 0.15)
    static let green = Color(red: 0.20, green: 0.80, blue: 0.55)
    static let teal = Color(red: 0.15, green: 0.72, blue: 0.80)
    static let blue = Color(red: 0.25, green: 0.55, blue: 1.0)

    static let chipColors: [Color] = [purple, pink, orange, teal, green, blue]

    /// The accent tint used throughout the UI.
    static let accent = green

    /// A soft background gradient that adapts to light/dark mode.
    static func backgroundGradient(for colorScheme: ColorScheme) -> LinearGradient {
        if colorScheme == .dark {
            LinearGradient(
                colors: [
                    Color(red: 0.09, green: 0.08, blue: 0.16),
                    Color(red: 0.06, green: 0.09, blue: 0.14)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
        } else {
            LinearGradient(
                colors: [
                    Color(red: 0.92, green: 0.89, blue: 0.97),
                    Color(red: 0.87, green: 0.93, blue: 0.96)
                ],
                startPoint: .top,
                endPoint: .bottom
            )
        }
    }
}
