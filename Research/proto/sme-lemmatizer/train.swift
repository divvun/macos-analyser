#!/usr/bin/env swift
// train.swift — Train an MLWordTagger lemmatizer from FST-generated data.
//
// Usage (interpreted — handy for small datasets):
//   swift train.swift [training_data.json] [output.mlmodel]
//
// Usage (compiled — recommended for full ~116k-lemma runs):
//   swiftc -O -o train_bin train.swift && ./train_bin [data.json] [out.mlmodel]
//
// Requires macOS 13+ (Ventura) for TabularData.DataFrame + modern CreateML.

import CreateML
import Foundation
import TabularData

// MARK: - Paths

let cliArgs = CommandLine.arguments
let trainingDataPath = cliArgs.count > 1
    ? cliArgs[1]
    : "Research/proto/sme-lemmatizer/training_data.json"
let modelOutputPath = cliArgs.count > 2
    ? cliArgs[2]
    : "Research/proto/sme-lemmatizer/SmeLemmatizer.mlmodel"

let trainingDataURL = URL(fileURLWithPath: trainingDataPath)
let modelOutputURL  = URL(fileURLWithPath: modelOutputPath)

// MARK: - Load data

print("Loading training data from: \(trainingDataPath)")

let fullTable: DataFrame
do {
    fullTable = try DataFrame(contentsOfJSONFile: trainingDataURL)
} catch {
    fputs("ERROR: Cannot load \(trainingDataPath): \(error)\n", stderr)
    exit(1)
}

print("Loaded \(fullTable.rows.count) training sentences.")

// MARK: - Train

print("\nTraining MLWordTagger...")

// MLWordTagger.ModelParameters defaults:
//   - algorithm: CRF (only available option)
//   - validation: .split(strategy: .automatic) — handled internally
let wordTagger: MLWordTagger
do {
    wordTagger = try MLWordTagger(
        trainingData: fullTable,
        tokenColumn: "tokens",
        labelColumn: "labels"
    )
} catch {
    fputs("ERROR during training: \(error)\n", stderr)
    exit(1)
}

let trainAcc = (1.0 - wordTagger.trainingMetrics.taggingError) * 100
let valAcc   = (1.0 - wordTagger.validationMetrics.taggingError) * 100
print(String(format: "Training accuracy:   %.1f%%", trainAcc))
print(String(format: "Validation accuracy: %.1f%%", valAcc))

// MARK: - Save

let metadata = MLModelMetadata(
    author: "Divvun",
    shortDescription: "North Sami (sme) lemmatizer — trained from FST-generated paradigms",
    license: nil,
    version: "0.1",
    additional: ["language": "se", "source": "FST generator-gt-norm (lang-sme)"]
)

do {
    try wordTagger.write(to: modelOutputURL, metadata: metadata)
    print("\nModel saved: \(modelOutputPath)")
} catch {
    fputs("ERROR saving model: \(error)\n", stderr)
    exit(1)
}
