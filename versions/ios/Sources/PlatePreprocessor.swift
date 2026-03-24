import CoreImage
import CoreGraphics

/// Beeldvoorverwerking voor gecropte kentekenregio's.
/// Equivalent van de Python PlatePreprocessor, gebouwd op CoreImage.
///
/// Pipeline: grayscale → contrast → sharpening
/// (Binarisatie weggelaten — Vision's VNRecognizeTextRequest werkt beter op grayscale)
struct PlatePreprocessor {

    private static let context = CIContext(options: [.useSoftwareRenderer: false])

    // MARK: - Scherptemeting

    /// Meet de scherpte van een afbeelding via Edge Intensity als proxy voor Laplacian-variantie.
    /// Hogere waarde = scherper beeld. Drempel: 80 (zelfde als Python SHARPNESS_MIN_VARIANCE).
    static func measureSharpness(_ cgImage: CGImage) -> Double {
        let ciImage = CIImage(cgImage: cgImage)

        guard let edgeFilter = CIFilter(name: "CIEdges") else { return 0 }
        edgeFilter.setValue(ciImage, forKey: kCIInputImageKey)
        edgeFilter.setValue(5.0, forKey: kCIInputIntensityKey)

        guard let edgeOutput = edgeFilter.outputImage,
              let rendered = context.createCGImage(edgeOutput, from: edgeOutput.extent)
        else { return 0 }

        // Bereken gemiddelde helderheid van de edge-map als scherptemaat
        let width = rendered.width
        let height = rendered.height
        let totalPixels = width * height
        guard totalPixels > 0 else { return 0 }

        let bytesPerPixel = rendered.bitsPerPixel / 8
        guard let dataProvider = rendered.dataProvider,
              let data = dataProvider.data,
              let bytes = CFDataGetBytePtr(data)
        else { return 0 }

        var sum: Double = 0
        for i in 0..<totalPixels {
            let offset = i * bytesPerPixel
            let r = Double(bytes[offset])
            let g = Double(bytes[offset + 1])
            let b = Double(bytes[offset + 2])
            sum += (r + g + b) / 3.0
        }

        return sum / Double(totalPixels)
    }

    // MARK: - Voorverwerking

    /// Pas de volledige preprocessing-pipeline toe op een gecropte kentekenafbeelding.
    /// Geeft een voorverwerkt CGImage terug, klaar voor Vision OCR.
    static func process(_ cgImage: CGImage) -> CGImage? {
        var image = CIImage(cgImage: cgImage)

        // Stap 1: Grayscale
        if let mono = CIFilter(name: "CIColorMonochrome") {
            mono.setValue(image, forKey: kCIInputImageKey)
            mono.setValue(CIColor.gray, forKey: kCIInputColorKey)
            mono.setValue(1.0, forKey: kCIInputIntensityKey)
            if let out = mono.outputImage { image = out }
        }

        // Stap 2: Contrast verhoging (equivalent van CLAHE clipLimit=2.0)
        if let controls = CIFilter(name: "CIColorControls") {
            controls.setValue(image, forKey: kCIInputImageKey)
            controls.setValue(1.5, forKey: kCIInputContrastKey)
            controls.setValue(0.05, forKey: kCIInputBrightnessKey)
            if let out = controls.outputImage { image = out }
        }

        // Stap 3: Verscherping (equivalent van Python sharpen_kernel)
        if let sharpen = CIFilter(name: "CIUnsharpMask") {
            sharpen.setValue(image, forKey: kCIInputImageKey)
            sharpen.setValue(2.5, forKey: kCIInputRadiusKey)
            sharpen.setValue(0.7, forKey: kCIInputIntensityKey)
            if let out = sharpen.outputImage { image = out }
        }

        return context.createCGImage(image, from: image.extent)
    }
}
