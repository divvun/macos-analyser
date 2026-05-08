import CoreML
import Foundation

func pad(_ value: String, _ width: Int) -> String {
    if value.count >= width { return value }
    return value + String(repeating: " ", count: width - value.count)
}

func charNgrams(_ word: String, nRange: ClosedRange<Int> = 2...4) -> [String: Double] {
    let wrapped = "^" + word + "$"
    let chars = Array(wrapped)
    var feats: [String: Double] = [:]

    for n in nRange {
        guard chars.count >= n else { continue }
        for i in 0...(chars.count - n) {
            let gram = String(chars[i..<(i + n)])
            let key = "c\(n)=\(gram)"
            feats[key, default: 0.0] += 1.0
        }
    }

    return feats
}

func applyEdit(_ label: String, to surface: String) -> String {
    let parts = label.split(separator: ":", maxSplits: 1, omittingEmptySubsequences: false)
    guard let strip = Int(parts.first ?? "") else {
        return surface
    }

    let suffix = parts.count > 1 ? String(parts[1]) : ""
    let chars = Array(surface)
    let safeStrip = max(0, min(strip, chars.count))
    let stem = String(chars.prefix(chars.count - safeStrip))
    return stem + suffix
}

func findPredictedLabel(from prediction: MLFeatureProvider, preferredName: String) -> String? {
    if let preferred = prediction.featureValue(for: preferredName)?.stringValue {
        return preferred
    }

    for name in prediction.featureNames.sorted() {
        if let value = prediction.featureValue(for: name)?.stringValue {
            return value
        }
    }

    return nil
}

func evaluate(modelPath: String, words: [String]) throws {
    let modelURL = URL(fileURLWithPath: modelPath)
    let compiledURL = try MLModel.compileModel(at: modelURL)
    let model = try MLModel(contentsOf: compiledURL)

    let inputNames = model.modelDescription.inputDescriptionsByName.keys.sorted()
    guard let inputName = inputNames.first else {
        throw NSError(domain: "test_coreml", code: 1, userInfo: [NSLocalizedDescriptionKey: "Model has no inputs"])
    }

    let outputNames = model.modelDescription.outputDescriptionsByName.keys.sorted()
    let preferredOutput = outputNames.contains("editLabel") ? "editLabel" : (outputNames.first ?? "")

    print("Input feature: \(inputName)")
    print("Output features: \(outputNames)")
    print("")
    print("\(pad("SURFACE", 16)) \(pad("EDIT", 16)) \(pad("LEMMA", 24))")
    print(String(repeating: "-", count: 58))

    for word in words {
        let feats = charNgrams(word)
        let nsFeats: [AnyHashable: NSNumber] = feats.reduce(into: [:]) { acc, item in
            acc[item.key] = NSNumber(value: item.value)
        }
        let featureValue = try MLFeatureValue(dictionary: nsFeats)
        let fp = try MLDictionaryFeatureProvider(dictionary: [inputName: featureValue])
        let pred = try model.prediction(from: fp)

        let edit = findPredictedLabel(from: pred, preferredName: preferredOutput) ?? "0:"
        let lemma = applyEdit(edit, to: word)

        print("\(pad(word, 16)) \(pad(edit, 16)) \(pad(lemma, 24))")
    }
}

let args = CommandLine.arguments
if args.count < 2 {
    fputs("Usage: test_coreml.swift <model.mlmodel|model.mlpackage> [word ...]\n", stderr)
    exit(1)
}

let modelPath = args[1]
let words: [String]
if args.count > 2 {
    words = Array(args.dropFirst(2))
} else {
    words = [
        "mánáid",
        "mánnái",
        "vuođđun",
        "oidnen",
        "boahtán",
        "ruovttus",
        "dego",
        "du"
    ]
}

do {
    try evaluate(modelPath: modelPath, words: words)
} catch {
    fputs("ERROR: \(error)\n", stderr)
    exit(2)
}
