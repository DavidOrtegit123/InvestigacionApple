import SwiftUI

struct OnboardingView: View {
    @ObservedObject var memoryStore: StudentMemoryStore
    @Environment(\.colorScheme) private var colorScheme
    @State private var name = ""
    @State private var selectedLevel: DifficultyLevel = .beginner

    private var trimmedName: String {
        name.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var body: some View {
        NavigationStack {
            ZStack {
                TutorPalette.backgroundGradient(for: colorScheme)
                    .ignoresSafeArea()

                VStack(spacing: 28) {
                    VStack(spacing: 12) {
                        Image(systemName: "graduationcap.fill")
                            .font(.system(size: 44))
                            .foregroundStyle(.white)
                            .padding(24)
                            .background(
                                Circle().fill(
                                    LinearGradient(
                                        colors: [TutorPalette.purple, TutorPalette.pink],
                                        startPoint: .topLeading,
                                        endPoint: .bottomTrailing
                                    )
                                )
                            )

                        Text("Welcome to Swift Tutor")
                            .font(.title2.bold())

                        Text("Let's get to know you before you start.")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, 24)

                    VStack(alignment: .leading, spacing: 8) {
                        Text("What's your name?")
                            .font(.headline)
                        TextField("Your name", text: $name)
                            .textFieldStyle(.roundedBorder)
                            .autocorrectionDisabled()
                            .textInputAutocapitalization(.words)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text("How much do you know about programming or Apple devices?")
                            .font(.headline)
                            .fixedSize(horizontal: false, vertical: true)

                        Picker("Knowledge level", selection: $selectedLevel) {
                            ForEach(DifficultyLevel.allCases, id: \.self) { level in
                                Text(level.onboardingDescription).tag(level)
                            }
                        }
                        .pickerStyle(.segmented)
                        .tint(TutorPalette.purple)
                    }

                    Spacer()

                    Button {
                        memoryStore.update { memory in
                            memory.name = trimmedName
                            memory.currentLevel = selectedLevel
                        }
                    } label: {
                        Text("Get Started")
                            .font(.headline)
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(TutorPalette.purple)
                    .disabled(trimmedName.isEmpty)
                }
                .padding()
            }
            .navigationTitle("Get Started")
            .navigationBarTitleDisplayMode(.inline)
        }
    }
}
