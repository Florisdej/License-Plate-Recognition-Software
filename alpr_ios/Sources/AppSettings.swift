import Foundation
import Combine

/// Centralised app settings backed by UserDefaults.
/// Use `AppSettings.shared` for the singleton instance.
final class AppSettings: ObservableObject {

    static let shared = AppSettings()

    // MARK: - Keys

    private enum Key {
        static let detectionThreshold  = "detectionThreshold"
        static let requireNLPattern    = "requireNLPattern"
        static let minOCRTextHeight    = "minOCRTextHeight"
        static let frameSkipRate       = "frameSkipRate"
        static let hapticFeedback      = "hapticFeedback"
        static let soundOnDetection    = "soundOnDetection"
        static let devMode             = "devMode"
        static let maxHistory          = "maxHistory"
    }

    // MARK: - Defaults

    private enum Default {
        static let detectionThreshold: Float  = 0.2
        static let requireNLPattern: Bool     = true
        static let minOCRTextHeight: Float    = 0.02
        static let frameSkipRate: Int         = 2
        static let hapticFeedback: Bool       = true
        static let soundOnDetection: Bool     = false
        static let devMode: Bool              = false
        static let maxHistory: Int            = 200
    }

    // MARK: - Published properties

    /// YOLO confidence threshold (0.1–0.9).
    @Published var detectionThreshold: Float {
        didSet { UserDefaults.standard.set(detectionThreshold, forKey: Key.detectionThreshold) }
    }

    /// When true, only accept plates matching Dutch NL patterns.
    @Published var requireNLPattern: Bool {
        didSet { UserDefaults.standard.set(requireNLPattern, forKey: Key.requireNLPattern) }
    }

    /// Vision minimum text height passed to VNRecognizeTextRequest (0.02–0.15).
    @Published var minOCRTextHeight: Float {
        didSet { UserDefaults.standard.set(minOCRTextHeight, forKey: Key.minOCRTextHeight) }
    }

    /// Process every Nth camera frame (1–10).
    @Published var frameSkipRate: Int {
        didSet { UserDefaults.standard.set(frameSkipRate, forKey: Key.frameSkipRate) }
    }

    /// Trigger haptic feedback when a plate is detected.
    @Published var hapticFeedback: Bool {
        didSet { UserDefaults.standard.set(hapticFeedback, forKey: Key.hapticFeedback) }
    }

    /// Play an audio beep when a plate is detected.
    @Published var soundOnDetection: Bool {
        didSet { UserDefaults.standard.set(soundOnDetection, forKey: Key.soundOnDetection) }
    }

    /// Developer / debug mode — shows extra logging in the UI.
    @Published var devMode: Bool {
        didSet { UserDefaults.standard.set(devMode, forKey: Key.devMode) }
    }

    /// Maximum number of entries kept in the detection history (50–500).
    @Published var maxHistory: Int {
        didSet { UserDefaults.standard.set(maxHistory, forKey: Key.maxHistory) }
    }

    // MARK: - Init

    private init() {
        let ud = UserDefaults.standard

        detectionThreshold = ud.object(forKey: Key.detectionThreshold) as? Float
            ?? Default.detectionThreshold

        requireNLPattern = ud.object(forKey: Key.requireNLPattern) as? Bool
            ?? Default.requireNLPattern

        minOCRTextHeight = ud.object(forKey: Key.minOCRTextHeight) as? Float
            ?? Default.minOCRTextHeight

        frameSkipRate = ud.object(forKey: Key.frameSkipRate) as? Int
            ?? Default.frameSkipRate

        hapticFeedback = ud.object(forKey: Key.hapticFeedback) as? Bool
            ?? Default.hapticFeedback

        soundOnDetection = ud.object(forKey: Key.soundOnDetection) as? Bool
            ?? Default.soundOnDetection

        devMode = ud.object(forKey: Key.devMode) as? Bool
            ?? Default.devMode

        maxHistory = ud.object(forKey: Key.maxHistory) as? Int
            ?? Default.maxHistory
    }

    // MARK: - Reset

    /// Reset all settings to their compile-time defaults.
    func reset() {
        detectionThreshold  = Default.detectionThreshold
        requireNLPattern    = Default.requireNLPattern
        minOCRTextHeight    = Default.minOCRTextHeight
        frameSkipRate       = Default.frameSkipRate
        hapticFeedback      = Default.hapticFeedback
        soundOnDetection    = Default.soundOnDetection
        devMode             = Default.devMode
        maxHistory          = Default.maxHistory
    }
}
