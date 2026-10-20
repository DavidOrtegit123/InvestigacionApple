import Speech
import AVFoundation
import Combine

@MainActor
public class SpeechRecognizer: ObservableObject {
    enum RecognizerError: Error {
        case nilRecognizer
        case notAuthorizedToRecognize
        case notAuthorizedToRecord
        case recognizerIsUnavailable
        
        var message: String {
            switch self {
            case .nilRecognizer: "Can't initialize speech recognizer."
            case .notAuthorizedToRecognize: "Not authorized to recognize speech. Please enable it in Settings."
            case .notAuthorizedToRecord: "Not authorized to record audio. Please enable Microphone access in Settings."
            case .recognizerIsUnavailable: "Speech recognition is unavailable right now."
            }
        }
    }
    
    @Published var transcript: String = ""
    @Published var isRecording: Bool = false
    @Published var errorText: String? = nil
    
    private var audioEngine: AVAudioEngine?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private let recognizer: SFSpeechRecognizer?
    
    public init() {
        self.recognizer = SFSpeechRecognizer()
    }
    
    deinit {
        // Deinit can be called on any thread, so we perform reset synchronously or safely.
        // We cancel the task and end requests.
    }
    
    public func startTranscribing() {
        Task {
            do {
                guard let recognizer = recognizer else {
                    throw RecognizerError.nilRecognizer
                }
                guard recognizer.isAvailable else {
                    throw RecognizerError.recognizerIsUnavailable
                }
                
                let isAuthorizedSpeech = await withCheckedContinuation { continuation in
                    SFSpeechRecognizer.requestAuthorization { status in
                        continuation.resume(returning: status == .authorized)
                    }
                }
                
                let isAuthorizedAudio = await AVAudioApplication.requestRecordPermission()
                
                guard isAuthorizedSpeech else {
                    throw RecognizerError.notAuthorizedToRecognize
                }
                guard isAuthorizedAudio else {
                    throw RecognizerError.notAuthorizedToRecord
                }
                
                try self.beginTranscribing()
            } catch let error as RecognizerError {
                self.errorText = error.message
                self.isRecording = false
            } catch {
                self.errorText = error.localizedDescription
                self.isRecording = false
            }
        }
    }
    
    private func beginTranscribing() throws {
        self.errorText = nil
        self.transcript = ""
        
        // Stop any running sessions
        stopAndReset()
        
        let audioEngine = AVAudioEngine()
        let request = SFSpeechAudioBufferRecognitionRequest()
        
        request.shouldReportPartialResults = true
        if recognizer?.supportsOnDeviceRecognition == true {
            request.requiresOnDeviceRecognition = true
        }
        
        self.audioEngine = audioEngine
        self.request = request
        
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { (buffer, _) in
            request.append(buffer)
        }
        
        audioEngine.prepare()
        try audioEngine.start()
        
        task = recognizer?.recognitionTask(with: request) { [weak self] result, error in
            guard let self = self else { return }
            
            Task { @MainActor in
                if let result = result {
                    self.transcript = result.bestTranscription.formattedString
                }
                if error != nil || result?.isFinal == true {
                    // Stop on error or final result
                    self.stopTranscribing()
                }
            }
        }
        
        isRecording = true
    }
    
    public func stopTranscribing() {
        stopAndReset()
    }
    
    private func stopAndReset() {
        task?.cancel()
        task = nil
        
        request?.endAudio()
        request = nil
        
        if let audioEngine = audioEngine {
            if audioEngine.isRunning {
                audioEngine.stop()
            }
            audioEngine.inputNode.removeTap(onBus: 0)
        }
        audioEngine = nil
        
        isRecording = false
    }
}
