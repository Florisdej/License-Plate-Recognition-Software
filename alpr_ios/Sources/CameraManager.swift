import AVFoundation
import CoreVideo
import Combine
import UIKit

/// Beheert de AVCaptureSession, frameverwerking en systeemintegratie.
/// Detectie start NIET automatisch — roep startDetection() aan na requestPermissionAndStart().
final class CameraManager: NSObject, ObservableObject {

    // MARK: - Gepubliceerde state

    @Published var detectedPlates: [PlateResult] = []   // Huidige sessie (uniek per tekst)
    @Published var fullHistory:    [PlateResult] = []   // Alle detecties inclusief duplicaten
    @Published var devLogs:        [String]      = []   // Dev mode console regels
    @Published var debugStatus:    String = "Gereed"
    @Published var isRunning:      Bool = false         // Camera preview actief
    @Published var isDetecting:    Bool = false         // YOLO/OCR verwerking actief
    @Published var isTorchOn:      Bool = false         // Flitser staat aan
    @Published var permissionDenied: Bool = false

    let session = AVCaptureSession()

    private let videoOutput   = AVCaptureVideoDataOutput()
    private let processingQueue = DispatchQueue(label: "nl.alpr.camera", qos: .userInitiated)
    private let detector      = PlateDetector()
    private let haptics       = UIImpactFeedbackGenerator(style: .medium)

    private var isProcessingFrame = false
    private var frameCounter      = 0
    private var captureDevice:  AVCaptureDevice?

    private static let maxLogs    = 100
    private static let maxHistory = 500

    // MARK: - Init

    override init() {
        super.init()
        detector.logCallback = { [weak self] msg in self?.addLog(msg) }
        haptics.prepare()
    }

    // MARK: - Camera levenscyclus

    /// Zet camera preview op en vraag permissie. Detectie start NIET automatisch.
    func requestPermissionAndStart() {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            setupSession()
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .video) { [weak self] granted in
                DispatchQueue.main.async {
                    if granted { self?.setupSession() }
                    else { self?.permissionDenied = true }
                }
            }
        default:
            DispatchQueue.main.async { self.permissionDenied = true }
        }
    }

    /// Stop alles — camera preview + detectie + flitser.
    func stop() {
        isDetecting = false
        turnOffTorch()
        processingQueue.async { [weak self] in self?.session.stopRunning() }
        DispatchQueue.main.async {
            self.isRunning   = false
            self.debugStatus = "Gestopt"
        }
    }

    // MARK: - Detectie aan/uit

    func startDetection() {
        guard isRunning else { return }
        frameCounter = 0
        DispatchQueue.main.async {
            self.isDetecting  = true
            self.debugStatus  = "Detectie actief..."
        }
        addLog("[Camera] ▶ Detectie gestart")
    }

    func stopDetection() {
        DispatchQueue.main.async {
            self.isDetecting  = false
            self.debugStatus  = "Detectie gestopt"
        }
        addLog("[Camera] ■ Detectie gestopt")
    }

    // MARK: - Flitser

    @discardableResult
    func toggleTorch() -> Bool {
        guard let device = captureDevice, device.hasTorch else { return false }
        do {
            try device.lockForConfiguration()
            isTorchOn ? device.torchMode = .off : (try? device.setTorchModeOn(level: 1.0))
            isTorchOn = device.torchMode == .on
            device.unlockForConfiguration()
            return true
        } catch {
            addLog("[Camera] Flitser fout: \(error)")
            return false
        }
    }

    private func turnOffTorch() {
        guard let device = captureDevice, device.hasTorch, device.torchMode == .on else { return }
        try? device.lockForConfiguration()
        device.torchMode = .off
        device.unlockForConfiguration()
        DispatchQueue.main.async { self.isTorchOn = false }
    }

    // MARK: - Resultaten beheren

    func clearSessionResults() {
        DispatchQueue.main.async { self.detectedPlates = [] }
    }

    func clearHistory() {
        DispatchQueue.main.async { self.fullHistory = [] }
    }

    func clearLogs() {
        DispatchQueue.main.async { self.devLogs = [] }
    }

    func deleteHistoryItem(_ result: PlateResult) {
        DispatchQueue.main.async {
            self.fullHistory.removeAll { $0.id == result.id }
        }
    }

    // MARK: - Logging

    func addLog(_ msg: String) {
        let line = "[\(Self.timeStr())] \(msg)"
        DispatchQueue.main.async {
            self.devLogs.insert(line, at: 0)
            if self.devLogs.count > Self.maxLogs {
                self.devLogs = Array(self.devLogs.prefix(Self.maxLogs))
            }
        }
    }

    private static func timeStr() -> String {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss.SSS"
        return f.string(from: Date())
    }

    // MARK: - Sessie opzetten

    private func setupSession() {
        addLog("[Camera] Sessie opzetten...")
        session.beginConfiguration()
        session.sessionPreset = .hd1280x720

        guard let device = AVCaptureDevice.default(
            .builtInWideAngleCamera, for: .video, position: .back
        ) else {
            addLog("[Camera] ✗ Geen achtercamera")
            session.commitConfiguration()
            return
        }
        captureDevice = device

        guard let input = try? AVCaptureDeviceInput(device: device),
              session.canAddInput(input) else {
            addLog("[Camera] ✗ Kan input niet toevoegen")
            session.commitConfiguration()
            return
        }
        session.addInput(input)

        try? device.lockForConfiguration()
        if device.isFocusModeSupported(.continuousAutoFocus) {
            device.focusMode = .continuousAutoFocus
        }
        device.unlockForConfiguration()

        videoOutput.alwaysDiscardsLateVideoFrames = true
        videoOutput.videoSettings = [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA
        ]
        videoOutput.setSampleBufferDelegate(self, queue: processingQueue)

        guard session.canAddOutput(videoOutput) else {
            addLog("[Camera] ✗ Kan output niet toevoegen")
            session.commitConfiguration()
            return
        }
        session.addOutput(videoOutput)

        if let conn = videoOutput.connection(with: .video),
           conn.isVideoRotationAngleSupported(0) {
            conn.videoRotationAngle = 0
        }

        session.commitConfiguration()

        processingQueue.async { [weak self] in
            self?.session.startRunning()
            DispatchQueue.main.async {
                self?.isRunning   = true
                self?.debugStatus = "Camera gereed — druk Start"
                self?.addLog("[Camera] ✓ Camera preview actief")
            }
        }
    }
}

// MARK: - AVCaptureVideoDataOutputSampleBufferDelegate

extension CameraManager: AVCaptureVideoDataOutputSampleBufferDelegate {

    func captureOutput(
        _ output: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard isDetecting, !isProcessingFrame else { return }

        // Frame skip: verwerk alleen elke Nth frame
        frameCounter += 1
        let skip = AppSettings.shared.frameSkipRate
        guard frameCounter % skip == 0 else { return }

        isProcessingFrame = true
        defer { isProcessingFrame = false }

        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }

        // Lees instellingen — thread-safe snapshot
        let threshold  = AppSettings.shared.detectionThreshold
        let nlRequired = AppSettings.shared.requireNLPattern
        let textHeight = AppSettings.shared.minOCRTextHeight

        detector.requireNLPattern = nlRequired
        detector.minTextHeight    = textHeight

        let results = detector.detect(pixelBuffer: pixelBuffer, confidenceThreshold: threshold)

        let status = results.isEmpty
            ? "Scannen... (geen plaat)"
            : "\(results.count) kenteken(s) herkend"

        DispatchQueue.main.async { [weak self] in
            guard let self else { return }

            self.debugStatus = status

            if !results.isEmpty {
                // Haptische feedback
                if AppSettings.shared.hapticFeedback {
                    self.haptics.impactOccurred()
                }

                // Dedupliceer binnen een tijdvenster: voeg dezelfde plaat niet toe
                // aan de geschiedenis als hij al binnen de laatste 10 seconden gezien is.
                let recentCutoff = Date().addingTimeInterval(-10)

                for result in results {
                    let alreadyInHistory = self.fullHistory.contains {
                        $0.plateText == result.plateText && $0.timestamp > recentCutoff
                    }
                    if !alreadyInHistory {
                        self.fullHistory.insert(result, at: 0)
                    }

                    if !self.detectedPlates.contains(where: { $0.plateText == result.plateText }) {
                        self.detectedPlates.insert(result, at: 0)
                    }
                }

                let maxH = AppSettings.shared.maxHistory
                if self.fullHistory.count > maxH {
                    self.fullHistory = Array(self.fullHistory.prefix(maxH))
                }
                if self.detectedPlates.count > 50 {
                    self.detectedPlates = Array(self.detectedPlates.prefix(50))
                }
            }
        }
    }
}
