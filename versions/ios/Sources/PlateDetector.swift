import Vision
import CoreML
import CoreImage
import CoreVideo

/// Kentekendetector op basis van het YOLOv8 Core ML model.
final class PlateDetector {

    var logCallback: ((String) -> Void)? {
        didSet { ocr.logCallback = logCallback }
    }

    private let ocr = PlateOCR()
    private let ciContext = CIContext(options: [.useSoftwareRenderer: false])
    private var visionModel: VNCoreMLModel?

    /// Scherptedrempel uitgeschakeld (0.0): iOS buffert al automatisch via alwaysDiscardsLateVideoFrames
    private let sharpnessThreshold: Double = 0.0

    /// Geeft aan of OCR alleen geldige NL-kentekenpatronen mag accepteren.
    var requireNLPattern: Bool = true

    /// Minimale teksthoogte die aan VNRecognizeTextRequest wordt doorgegeven.
    var minTextHeight: Float = 0.05

    init() {
        loadModel()
    }

    private func log(_ msg: String) {
        logCallback?(msg)
        print(msg)
    }

    private func loadModel() {
        // best.mlpackage wordt door Xcode gecompileerd naar best.mlmodelc in de app bundle
        guard let modelURL = Bundle.main.url(forResource: "best", withExtension: "mlmodelc") else {
            log("[Detector] ⚠️ best.mlmodelc niet gevonden in bundle.")
            log("[Detector]   Voer convert_model.py uit en voeg best.mlpackage toe aan Xcode.")
            return
        }

        do {
            let config = MLModelConfiguration()
            config.computeUnits = .cpuAndNeuralEngine
            let mlModel = try MLModel(contentsOf: modelURL, configuration: config)
            self.visionModel = try VNCoreMLModel(for: mlModel)
            log("[Detector] ✓ Model geladen")
        } catch {
            log("[Detector] ✗ Model laden mislukt: \(error)")
        }
    }

    /// Verwerk een cameraframe en geef gedetecteerde kentekens terug.
    func detect(pixelBuffer: CVPixelBuffer, confidenceThreshold: Float) -> [PlateResult] {
        guard let model = visionModel else {
            log("[Detector] Model niet beschikbaar — sla frame over")
            return []
        }

        var results: [PlateResult] = []

        let ciImage = CIImage(cvPixelBuffer: pixelBuffer)
        let imageWidth = CVPixelBufferGetWidth(pixelBuffer)
        let imageHeight = CVPixelBufferGetHeight(pixelBuffer)

        let request = VNCoreMLRequest(model: model) { [weak self] req, error in
            guard let self else { return }
            if let error { self.log("[Detector] Request fout: \(error)"); return }

            guard let observations = req.results as? [VNRecognizedObjectObservation] else {
                self.log("[Detector] Geen VNRecognizedObjectObservation resultaten")
                return
            }

            self.log("[Detector] \(observations.count) kandidaat(en), drempel: \(confidenceThreshold)")

            for obs in observations {
                let confStr = String(format: "%.2f", obs.confidence)
                guard obs.confidence >= confidenceThreshold else {
                    self.log("[Detector] Skip conf=\(confStr) < \(confidenceThreshold)")
                    continue
                }

                // Vision Y-as is omgekeerd t.o.v. UIKit
                let bbox = obs.boundingBox
                let cropRect = CGRect(
                    x: bbox.minX * CGFloat(imageWidth),
                    y: (1.0 - bbox.maxY) * CGFloat(imageHeight),
                    width: bbox.width * CGFloat(imageWidth),
                    height: bbox.height * CGFloat(imageHeight)
                )

                let croppedCI = ciImage.cropped(to: cropRect)
                guard let cgCrop = self.ciContext.createCGImage(croppedCI, from: croppedCI.extent) else {
                    self.log("[Detector] Crop mislukt")
                    continue
                }

                self.log("[Detector] Plaat conf=\(confStr), crop \(Int(cropRect.width))x\(Int(cropRect.height))px")

                // Scherptecheck (uitgeschakeld als threshold == 0)
                if self.sharpnessThreshold > 0 {
                    let sharpness = PlatePreprocessor.measureSharpness(cgCrop)
                    guard sharpness >= self.sharpnessThreshold else {
                        self.log("[Detector] Overgeslagen (scherp=\(String(format:"%.1f",sharpness)) < \(self.sharpnessThreshold))")
                        continue
                    }
                }

                guard let processed = PlatePreprocessor.process(cgCrop) else {
                    self.log("[Detector] Preprocessing mislukt")
                    continue
                }

                guard let (plateText, ocrConf) = self.ocr.recognize(
                    cgImage: processed,
                    requireNLPattern: self.requireNLPattern,
                    minTextHeight: self.minTextHeight
                ) else {
                    continue
                }

                results.append(PlateResult(
                    plateText: plateText,
                    detectionConfidence: obs.confidence,
                    ocrConfidence: ocrConf,
                    boundingBox: obs.boundingBox,
                    timestamp: Date()
                ))
            }
        }

        // .scaleFit preserves the 16:9 aspect ratio with letterboxing — matches how
        // YOLOv8 was trained (ultralytics uses letterbox by default, not stretch-fill)
        request.imageCropAndScaleOption = .scaleFit

        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, options: [:])
        try? handler.perform([request])

        return results
    }
}
