import Foundation
import CoreGraphics

/// Eindresultaat van één kentekenherkenning.
struct PlateResult: Identifiable, Equatable {
    let id = UUID()
    let plateText: String
    let detectionConfidence: Float  // YOLO detectie confidence (0-1)
    let ocrConfidence: Float        // OCR herkennings confidence (0-1)
    let boundingBox: CGRect         // Genormaliseerde bbox (0-1) in Vision-coördinaten
    let timestamp: Date

    static func == (lhs: PlateResult, rhs: PlateResult) -> Bool {
        lhs.id == rhs.id
    }
}
