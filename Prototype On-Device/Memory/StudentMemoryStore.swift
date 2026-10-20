import Foundation
import Combine

/// Persists a single student's memory as JSON in the app's Documents
/// directory. No cloud sync — everything stays on-device.
@MainActor
final class StudentMemoryStore: ObservableObject {
    @Published private(set) var memory: StudentMemory

    private let fileURL: URL

    init(studentId: String = "default_student") {
        let documentsDirectory = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        fileURL = documentsDirectory.appendingPathComponent("student_memory_\(studentId).json")

        if let data = try? Data(contentsOf: fileURL),
           let decoded = try? JSONDecoder().decode(StudentMemory.self, from: data) {
            memory = decoded
        } else {
            memory = StudentMemory(studentId: studentId)
        }
    }

    func update(_ transform: (inout StudentMemory) -> Void) {
        transform(&memory)
        save()
    }

    /// Clears the saved name, level, and topic history back to a blank profile.
    func reset() {
        update { memory in
            memory = StudentMemory(studentId: memory.studentId)
        }
    }

    private func save() {
        guard let data = try? JSONEncoder().encode(memory) else { return }
        try? data.write(to: fileURL, options: .atomic)
    }
}
