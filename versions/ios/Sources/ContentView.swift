import SwiftUI
import AVFoundation

// MARK: - Root view met TabView

struct ContentView: View {
    @StateObject private var camera = CameraManager()
    @ObservedObject private var settings = AppSettings.shared
    @State private var showSettings = false
    @Environment(\.scenePhase) private var scenePhase
    @State private var wasRunning = false

    var body: some View {
        TabView {
            CameraTab(camera: camera, settings: settings, showSettings: $showSettings)
                .tabItem {
                    Label("Camera", systemImage: "camera.fill")
                }

            HistoryTab(camera: camera)
                .tabItem {
                    Label("Geschiedenis", systemImage: "clock.fill")
                }
                .badge(camera.fullHistory.count > 0 ? camera.fullHistory.count : 0)
        }
        .sheet(isPresented: $showSettings) {
            SettingsSheet(camera: camera, settings: settings)
        }
        .onAppear {
            camera.requestPermissionAndStart()
            wasRunning = true
        }
        .onChange(of: scenePhase) { newPhase in
            switch newPhase {
            case .background:
                wasRunning = camera.isRunning
                camera.stop()
            case .active:
                if wasRunning {
                    camera.requestPermissionAndStart()
                }
            default:
                break
            }
        }
    }
}

// MARK: - Camera Tab

struct CameraTab: View {
    @ObservedObject var camera: CameraManager
    @ObservedObject var settings: AppSettings
    @Binding var showSettings: Bool
    @State private var copiedToast = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            CameraPreviewView(session: camera.session)
                .ignoresSafeArea()

            if camera.permissionDenied {
                permissionView
            } else {
                VStack(spacing: 0) {
                    header
                    Spacer()
                    if settings.devMode {
                        devConsole
                    }
                    if camera.isDetecting && camera.detectedPlates.isEmpty {
                        scanHint
                    }
                    if !camera.detectedPlates.isEmpty {
                        detectionList
                    }
                    startStopButton
                }
            }

            if copiedToast {
                VStack {
                    Spacer()
                    Text("Gekopieerd!")
                        .font(.subheadline.bold())
                        .foregroundColor(.white)
                        .padding(.horizontal, 20)
                        .padding(.vertical, 10)
                        .background(Color.green.opacity(0.9))
                        .clipShape(Capsule())
                        .transition(.opacity.combined(with: .scale))
                    Spacer().frame(height: 160)
                }
                .animation(.easeInOut(duration: 0.2), value: copiedToast)
            }
        }
    }

    // MARK: Header

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("ALPR")
                    .font(.title2.bold())
                    .foregroundColor(.white)
                Text("NL Kentekenherkenning")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.75))
            }

            Spacer()

            if camera.isRunning {
                Button {
                    _ = camera.toggleTorch()
                } label: {
                    Image(systemName: camera.isTorchOn ? "flashlight.on.fill" : "flashlight.off.fill")
                        .font(.title3)
                        .foregroundColor(camera.isTorchOn ? .yellow : .white)
                        .padding(10)
                        .background(Color.white.opacity(0.15))
                        .clipShape(Circle())
                }
                .padding(.trailing, 8)
            }

            Button {
                showSettings = true
            } label: {
                Image(systemName: "gearshape.fill")
                    .font(.title3)
                    .foregroundColor(.white)
                    .padding(10)
                    .background(Color.white.opacity(0.15))
                    .clipShape(Circle())
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 60)
        .padding(.bottom, 16)
        .background(
            LinearGradient(
                colors: [.black.opacity(0.75), .clear],
                startPoint: .top, endPoint: .bottom
            )
        )
    }

    // MARK: Dev Console

    private var devConsole: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("DEV CONSOLE")
                    .font(.system(size: 10, weight: .bold, design: .monospaced))
                    .foregroundColor(.green)
                Spacer()
                Text(camera.debugStatus)
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.yellow)
                    .lineLimit(1)
                Button {
                    camera.clearLogs()
                } label: {
                    Text("CLR")
                        .font(.system(size: 10, weight: .bold, design: .monospaced))
                        .foregroundColor(.red)
                }
                .padding(.leading, 8)
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 5)

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 1) {
                    ForEach(Array(camera.devLogs.prefix(30).enumerated()), id: \.offset) { _, line in
                        Text(line)
                            .font(.system(size: 9, design: .monospaced))
                            .foregroundColor(logColor(line))
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(.horizontal, 10)
                .padding(.bottom, 6)
            }
            .frame(height: 140)
        }
        .background(Color.black.opacity(0.85))
    }

    private func logColor(_ line: String) -> Color {
        if line.contains("✓") || line.contains("Geldig") { return .green }
        if line.contains("✗") || line.contains("Fout") || line.contains("mislukt") { return .red }
        if line.contains("verworpen") || line.contains("overgeslagen") { return .orange }
        if line.contains("[OCR]") { return .cyan }
        if line.contains("[Detector]") { return .yellow }
        return Color(white: 0.7)
    }

    // MARK: Scan Hint

    private var scanHint: some View {
        VStack(spacing: 6) {
            HStack(spacing: 8) {
                Image(systemName: "viewfinder")
                    .foregroundColor(.white.opacity(0.7))
                Text("Houd een kenteken voor de camera")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 10)
            .background(Color.black.opacity(0.5))
            .clipShape(Capsule())
        }
        .padding(.bottom, 12)
    }

    // MARK: Detection List

    private var detectionList: some View {
        VStack(spacing: 0) {
            HStack {
                Text("\(camera.detectedPlates.count) uniek — sessie")
                    .font(.caption.bold())
                    .foregroundColor(.secondary)
                Spacer()
                Button("Wissen") { camera.clearSessionResults() }
                    .font(.caption)
                    .foregroundColor(.accentColor)
            }
            .padding(.horizontal, 16)
            .padding(.top, 10)
            .padding(.bottom, 4)

            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(camera.detectedPlates) { plate in
                        PlateCardView(result: plate, onCopy: {
                            copyToClipboard(plate.plateText)
                        })
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 12)
            }
            .frame(maxHeight: 220)
        }
        .background(.ultraThinMaterial)
    }

    // MARK: Start/Stop Detection Button

    private var startStopButton: some View {
        HStack {
            Spacer()
            Button {
                if camera.isDetecting {
                    camera.stopDetection()
                } else {
                    camera.startDetection()
                }
            } label: {
                HStack(spacing: 10) {
                    Image(systemName: camera.isDetecting ? "stop.fill" : "qrcode.viewfinder")
                        .font(.system(size: 20, weight: .bold))
                    Text(camera.isDetecting ? "Stop" : "Start Scannen")
                        .font(.system(size: 17, weight: .bold))
                }
                .foregroundColor(.white)
                .frame(height: 56)
                .padding(.horizontal, 36)
                .background(camera.isDetecting ? Color.red : Color.green)
                .clipShape(Capsule())
                .shadow(color: (camera.isDetecting ? Color.red : Color.green).opacity(0.5), radius: 8, x: 0, y: 4)
            }
            Spacer()
        }
        .padding(.bottom, 36)
        .padding(.top, 12)
        .background(
            LinearGradient(
                colors: [.clear, .black.opacity(0.6)],
                startPoint: .top, endPoint: .bottom
            )
        )
    }

    // MARK: Permission Denied View

    private var permissionView: some View {
        VStack(spacing: 12) {
            Spacer()
            Image(systemName: "camera.slash")
                .font(.system(size: 52))
                .foregroundColor(.secondary)
            Text("Camera-toegang vereist")
                .font(.headline)
                .foregroundColor(.white)
            Text("Ga naar Instellingen → Privacy & Beveiliging → Camera om toegang te verlenen.")
                .font(.caption)
                .multilineTextAlignment(.center)
                .foregroundColor(.white.opacity(0.7))
                .padding(.horizontal, 32)
            Button {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            } label: {
                Text("Open Instellingen")
                    .font(.subheadline.bold())
                    .foregroundColor(.white)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(Color.accentColor)
                    .clipShape(Capsule())
            }
            .padding(.top, 8)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.black.opacity(0.8))
    }

    // MARK: Helpers

    private func copyToClipboard(_ text: String) {
        UIPasteboard.general.string = text
        if settings.hapticFeedback {
            let generator = UIImpactFeedbackGenerator(style: .light)
            generator.impactOccurred()
        }
        withAnimation(.easeInOut(duration: 0.2)) {
            copiedToast = true
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            withAnimation(.easeInOut(duration: 0.2)) {
                copiedToast = false
            }
        }
    }
}

// MARK: - History Tab

struct HistoryTab: View {
    @ObservedObject var camera: CameraManager
    @State private var copiedToast = false
    @State private var toastText = ""

    var body: some View {
        NavigationView {
            Group {
                if camera.fullHistory.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "clock")
                            .font(.system(size: 48))
                            .foregroundColor(.secondary)
                        Text("Nog geen kentekens gescand")
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                } else {
                    ZStack {
                        List {
                            ForEach(camera.fullHistory) { plate in
                                HistoryRow(result: plate) {
                                    copyToClipboard(plate.plateText)
                                }
                                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                                    Button(role: .destructive) {
                                        if let idx = camera.fullHistory.firstIndex(where: { $0.id == plate.id }) {
                                            camera.fullHistory.remove(at: idx)
                                        }
                                    } label: {
                                        Label("Verwijder", systemImage: "trash")
                                    }
                                }
                                .contextMenu {
                                    Button {
                                        let text = plate.plateText
                                        let av = UIActivityViewController(activityItems: [text], applicationActivities: nil)
                                        if let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
                                           let root = scene.windows.first?.rootViewController {
                                            root.present(av, animated: true)
                                        }
                                    } label: {
                                        Label("Deel", systemImage: "square.and.arrow.up")
                                    }
                                    Button {
                                        copyToClipboard(plate.plateText)
                                    } label: {
                                        Label("Kopieer", systemImage: "doc.on.doc")
                                    }
                                }
                            }
                        }
                        .listStyle(.plain)

                        if copiedToast {
                            VStack {
                                Spacer()
                                Text(toastText)
                                    .font(.subheadline.bold())
                                    .foregroundColor(.white)
                                    .padding(.horizontal, 20)
                                    .padding(.vertical, 10)
                                    .background(Color.green.opacity(0.9))
                                    .clipShape(Capsule())
                                    .transition(.opacity.combined(with: .scale))
                                    .padding(.bottom, 32)
                            }
                            .animation(.easeInOut(duration: 0.2), value: copiedToast)
                        }
                    }
                }
            }
            .navigationTitle("Geschiedenis (\(camera.fullHistory.count))")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if !camera.fullHistory.isEmpty {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button("Wissen", role: .destructive) {
                            camera.clearHistory()
                        }
                        .foregroundColor(.red)
                    }
                }
            }
        }
    }

    private func copyToClipboard(_ text: String) {
        UIPasteboard.general.string = text
        toastText = "Gekopieerd!"
        withAnimation(.easeInOut(duration: 0.2)) {
            copiedToast = true
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            withAnimation(.easeInOut(duration: 0.2)) {
                copiedToast = false
            }
        }
    }
}

struct HistoryRow: View {
    let result: PlateResult
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: 12) {
                Text(result.plateText)
                    .font(.system(.body, design: .monospaced).bold())
                    .foregroundColor(.black)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(Color.yellow)
                    .cornerRadius(6)

                VStack(alignment: .leading, spacing: 2) {
                    Text("Det: \(Int(result.detectionConfidence * 100))%  OCR: \(Int(result.ocrConfidence * 100))%")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(result.timestamp, style: .time)
                        .font(.caption2)
                        .foregroundColor(.secondary)
                }

                Spacer()

                Image(systemName: "doc.on.doc")
                    .font(.caption)
                    .foregroundColor(.secondary.opacity(0.5))
            }
            .padding(.vertical, 4)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Settings Sheet

struct SettingsSheet: View {
    @ObservedObject var camera: CameraManager
    @ObservedObject var settings: AppSettings
    @Environment(\.dismiss) private var dismiss
    @State private var showResetConfirm = false
    @State private var showClearHistoryConfirm = false

    var body: some View {
        NavigationView {
            Form {
                // MARK: Detectie
                Section {
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text("Drempelwaarde")
                            Spacer()
                            Text("\(Int(settings.detectionThreshold * 100))%")
                                .foregroundColor(.secondary)
                                .monospacedDigit()
                        }
                        Slider(value: $settings.detectionThreshold, in: 0.1...0.9, step: 0.05)
                        Text("Lagere waarde = meer detecties")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .padding(.vertical, 4)

                    Toggle(isOn: $settings.requireNLPattern) {
                        Label("Alleen geldige NL-kentekens", systemImage: "checkmark.shield")
                    }
                } header: {
                    Text("Detectie")
                }

                // MARK: Verwerking
                Section {
                    Stepper(value: $settings.frameSkipRate, in: 1...10) {
                        HStack {
                            Text("Frame skip")
                            Spacer()
                            Text("elke \(settings.frameSkipRate)e frame")
                                .foregroundColor(.secondary)
                                .font(.subheadline)
                        }
                    }

                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text("Min. tekst hoogte")
                            Spacer()
                            Text("\(Int(settings.minOCRTextHeight * 100))%")
                                .foregroundColor(.secondary)
                                .monospacedDigit()
                        }
                        Slider(value: $settings.minOCRTextHeight, in: 0.02...0.15, step: 0.01)
                    }
                    .padding(.vertical, 4)
                } header: {
                    Text("Verwerking")
                }

                // MARK: Meldingen
                Section {
                    Toggle(isOn: $settings.hapticFeedback) {
                        Label("Trillen bij detectie", systemImage: "iphone.radiowaves.left.and.right")
                    }
                    Toggle(isOn: $settings.soundOnDetection) {
                        Label("Geluid bij detectie", systemImage: "speaker.wave.2")
                    }
                } header: {
                    Text("Meldingen")
                }

                // MARK: Developer
                Section {
                    Toggle(isOn: $settings.devMode) {
                        Label("Dev Mode", systemImage: "terminal")
                    }
                    if settings.devMode {
                        Text("Toont een live console onderaan het camerascherm met YOLO/OCR logs.")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                } header: {
                    Text("Developer")
                }

                // MARK: Data
                Section {
                    Stepper(value: $settings.maxHistory, in: 50...500, step: 50) {
                        HStack {
                            Text("Max geschiedenis")
                            Spacer()
                            Text("\(settings.maxHistory)")
                                .foregroundColor(.secondary)
                                .monospacedDigit()
                        }
                    }

                    Button("Sessie wissen") {
                        camera.clearSessionResults()
                    }

                    Button("Geschiedenis wissen", role: .destructive) {
                        showClearHistoryConfirm = true
                    }

                    Button("Opnieuw instellen", role: .destructive) {
                        showResetConfirm = true
                    }
                } header: {
                    Text("Data")
                }

                // MARK: Status
                Section {
                    LabeledContent("Camera", value: camera.isRunning ? "Actief" : "Gestopt")
                    LabeledContent("Frames", value: camera.debugStatus)
                        .font(.caption)
                    LabeledContent("Sessie", value: "\(camera.detectedPlates.count) uniek")
                    LabeledContent("Geschiedenis", value: "\(camera.fullHistory.count) totaal")
                } header: {
                    Text("Status")
                }
            }
            .navigationTitle("Instellingen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Klaar") { dismiss() }
                }
            }
            .confirmationDialog(
                "Geschiedenis wissen?",
                isPresented: $showClearHistoryConfirm,
                titleVisibility: .visible
            ) {
                Button("Wissen", role: .destructive) { camera.clearHistory() }
                Button("Annuleer", role: .cancel) {}
            } message: {
                Text("Alle \(camera.fullHistory.count) items worden permanent verwijderd.")
            }
            .confirmationDialog(
                "Alle instellingen resetten?",
                isPresented: $showResetConfirm,
                titleVisibility: .visible
            ) {
                Button("Opnieuw instellen", role: .destructive) { settings.reset() }
                Button("Annuleer", role: .cancel) {}
            } message: {
                Text("Alle instellingen worden teruggezet naar de standaardwaarden.")
            }
        }
    }
}

// MARK: - Camera Preview

struct CameraPreviewView: UIViewRepresentable {
    let session: AVCaptureSession

    func makeUIView(context: Context) -> PreviewView {
        let view = PreviewView()
        view.previewLayer.session = session
        view.previewLayer.videoGravity = .resizeAspectFill
        return view
    }

    func updateUIView(_ uiView: PreviewView, context: Context) {}

    class PreviewView: UIView {
        override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
        var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
    }
}

// MARK: - Plate Card (live sessie)

struct PlateCardView: View {
    let result: PlateResult
    var onCopy: (() -> Void)? = nil

    var body: some View {
        Button {
            onCopy?()
        } label: {
            HStack(spacing: 12) {
                Text(result.plateText)
                    .font(.system(.body, design: .monospaced).bold())
                    .foregroundColor(.black)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(Color.yellow)
                    .cornerRadius(6)
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(Color.black.opacity(0.15), lineWidth: 1)
                    )

                VStack(alignment: .leading, spacing: 3) {
                    confidenceRow(label: "Detectie", value: result.detectionConfidence)
                    confidenceRow(label: "OCR", value: result.ocrConfidence)
                }

                Spacer()

                Text(result.timestamp, style: .time)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
            .padding(12)
            .background(Color(.systemBackground).opacity(0.95))
            .cornerRadius(12)
        }
        .buttonStyle(.plain)
    }

    private func confidenceRow(label: String, value: Float) -> some View {
        HStack(spacing: 4) {
            Text(label)
                .font(.caption2)
                .foregroundColor(.secondary)
                .frame(width: 48, alignment: .leading)
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(Color.secondary.opacity(0.15))
                    Capsule()
                        .fill(value >= 0.7 ? Color.green : value >= 0.4 ? Color.orange : Color.red)
                        .frame(width: geo.size.width * CGFloat(min(value, 1.0)))
                }
            }
            .frame(height: 5)
            Text("\(Int(value * 100))%")
                .font(.caption2.monospacedDigit())
                .foregroundColor(.secondary)
                .frame(width: 28, alignment: .trailing)
        }
    }
}
