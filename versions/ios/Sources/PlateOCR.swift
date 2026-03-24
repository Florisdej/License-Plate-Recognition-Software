import Vision
import CoreGraphics

/// OCR-engine voor kentekenherkenning op iOS.
/// Gebruikt Apple's Vision framework (VNRecognizeTextRequest) als vervanging voor EasyOCR.
final class PlateOCR {

    /// Optionele log-callback voor dev mode (anders gaat output naar print)
    var logCallback: ((String) -> Void)?

    private func log(_ msg: String) {
        logCallback?(msg)
        print(msg)
    }

    // MARK: - NL Kentekenpatronen (sidecodes 1–9 + oudere formaten)
    private static let nlPatterns: [NSRegularExpression] = [
        "^[A-Z]{2}\\d{3}[A-Z]$",     // XX-999-X  (sidecode 9)
        "^[A-Z]\\d{3}[A-Z]{2}$",     // X-999-XX  (sidecode 8)
        "^\\d[A-Z]{3}\\d{2}$",       // 9-XXX-99  (sidecode 7)
        "^\\d{2}[A-Z]{3}\\d$",       // 99-XXX-9  (sidecode 6)
        "^[A-Z]{3}\\d{2}[A-Z]$",     // XXX-99-X
        "^[A-Z]\\d{2}[A-Z]{3}$",     // X-99-XXX
        "^\\d{2}[A-Z]{2}\\d{2}$",    // 99-XX-99
        "^[A-Z]{2}\\d{2}[A-Z]{2}$",  // XX-99-XX
        "^\\d{4}[A-Z]{2}$",          // 99-99-XX
        "^[A-Z]{2}\\d{4}$",          // XX-99-99
        "^\\d{2}[A-Z]{4}$",          // 99-XX-XX
        "^[A-Z]{4}\\d{2}$",          // XX-XX-99
    ].compactMap { try? NSRegularExpression(pattern: $0) }

    private static let formatMap: [String: (Int, Int, Int)] = [
        "LLDDDD": (2, 2, 2), "DDDDLL": (2, 2, 2), "DDLLDD": (2, 2, 2),
        "LLDDLL": (2, 2, 2), "LLLLDD": (2, 2, 2), "DDLLLL": (2, 2, 2),
        "DLLLDL": (1, 3, 2), "DLLLDD": (1, 3, 2), "DDLLLD": (2, 3, 1),
        "LDDDLL": (1, 3, 2), "LLDDDL": (2, 3, 1), "LLLDDL": (3, 2, 1),
        "LDDLLL": (1, 2, 3),
    ]

    // MARK: - Herkenning

    /// Herken kentekentext in een voorverwerkte afbeelding.
    /// - Parameters:
    ///   - cgImage: Voorverwerkte plaatafbeelding.
    ///   - requireNLPattern: Wanneer true, wordt de tekst gevalideerd en opgemaakt als NL-kenteken.
    ///     Wanneer false, wordt de ruwe (opgemaakte) tekst teruggegeven zonder patrooncheck.
    ///   - minTextHeight: Minimale relatieve teksthoogte voor VNRecognizeTextRequest (0.02–0.15).
    /// - Returns: (tekst, confidence) of nil als er niets bruikbaars is herkend.
    func recognize(cgImage: CGImage, requireNLPattern: Bool = true, minTextHeight: Float = 0.05) -> (String, Float)? {
        var resultText: String?
        var resultConf: Float = 0

        let request = VNRecognizeTextRequest { [weak self] req, error in
            guard let self else { return }
            if let error { self.log("[OCR] Fout: \(error.localizedDescription)"); return }
            guard let observations = req.results as? [VNRecognizedTextObservation] else { return }

            var pieces: [(text: String, conf: Float, x: Float)] = []

            for obs in observations {
                guard let candidate = obs.topCandidates(1).first else { continue }
                guard candidate.confidence >= 0.1 else { continue }

                let cleaned = candidate.string
                    .uppercased()
                    .filter { $0.isLetter || $0.isNumber }

                if cleaned.count >= 2 {
                    let centerX = Float((obs.boundingBox.minX + obs.boundingBox.maxX) / 2)
                    pieces.append((cleaned, candidate.confidence, centerX))
                }
            }

            guard !pieces.isEmpty else {
                self.log("[OCR] Geen tekst herkend in crop")
                return
            }

            pieces.sort { $0.x < $1.x }
            let combined = pieces.map(\.text).joined()
            let avgConf = pieces.map(\.conf).reduce(0, +) / Float(pieces.count)

            self.log("[OCR] Ruw: '\(combined)' (conf: \(String(format: "%.2f", avgConf)))")

            if requireNLPattern {
                guard let formatted = self.formatNLPlate(combined) else {
                    self.log("[OCR] '\(combined)' verworpen: geen geldig NL-patroon")
                    return
                }
                resultText = formatted
            } else {
                // Geen patroonvalidatie — geef de ruwe opgemaakte tekst terug
                let raw = combined.uppercased().filter { $0.isLetter || $0.isNumber }
                resultText = raw
            }

            resultConf = avgConf
        }

        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        request.minimumTextHeight = minTextHeight

        let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
        try? handler.perform([request])
        // perform() is synchroon — resultText is nu gezet

        guard let text = resultText else { return nil }
        log("[OCR] Geldig kenteken: \(text)")
        return (text, resultConf)
    }

    // MARK: - NL Patroonvalidatie

    func matchesNLPattern(_ clean: String) -> Bool {
        let stripped = clean.filter { $0.isLetter || $0.isNumber }
        let range = NSRange(stripped.startIndex..., in: stripped)
        return PlateOCR.nlPatterns.contains {
            $0.firstMatch(in: stripped, range: range) != nil
        }
    }

    // MARK: - Formattering

    private func formatNLPlate(_ raw: String) -> String? {
        let clean = raw.filter { $0.isLetter || $0.isNumber }.uppercased()
        guard clean.count == 6 else { return nil }
        guard matchesNLPattern(clean) else { return nil }

        let pattern = clean.map { $0.isLetter ? "L" : "D" }.joined()
        let chars = Array(clean)

        if let (g1, g2, g3) = PlateOCR.formatMap[pattern], g3 > 0 {
            return "\(String(chars[0..<g1]))-\(String(chars[g1..<(g1+g2)]))-\(String(chars[(g1+g2)...]))"
        }

        return "\(String(chars[0..<2]))-\(String(chars[2..<4]))-\(String(chars[4...]))"
    }
}
