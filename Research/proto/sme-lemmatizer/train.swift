#!/usr/bin/env swift
// train.swift — Train an MLWordTagger lemmatizer from FST-generated data.
//
// Usage:
//   swift train.swift [training_data.json] [output.mlmodel]
//
// Requires macOS 10.15+ with CreateML framework.
// Run from the repo root or the sme-lemmatizer directory.

import Foundation
import CreateML

// MARK: - Paths

let args = CommandLine.arguments
let trainingDataPath = args.count > 1 ? args[1] : "Research/proto/sme-lemmatizer/training_data.json"
let modelOutputPath  = args.count > 2 ? args[2] : "Research/proto/sme-lemmatizer/SmeLemmatizer.mlmodel"

let trainingDataURL = URL(fileURLWithPath: trainingDataPath)
let modelOutputURL  = URL(fileURLWithPath: modelOutputPath)

// MARK: - Load data

print("Loading training data from: \(trainingDataPath)")

guard let data = try? MLDataTable(contentsOf: trainingDataURL) else {
    fputs("ERROR: Cannot load training data from \(trainingDataPath)\n", stderr)
    exit(1)
}

print("Loaded \(data.rows.count) training sentences.")

// 80/20 split
let (trainingData, testData) = data.randomSplit(by: 0.8, seed: 42)
print("Split: \(trainingData.rows.count) train / \(testData.rows.count) test")

// MARK: - Train

print("\nTraining MLWordTagger...")

let wordTagger: MLWordTagger
do {
    wordTagger = try MLWordTagger(
        trainingData: trainingData,
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

// MARK: - Evaluate

print("\nEvaluating on held-out test data...")
let evalMetrics = wordTagger.evaluation(on: testData, tokenColumn: "tokens", labelColumn: "labels")
let evalAcc = (1.0 - evalMetrics.taggingError) * 100
print(String(format: "Test accuracy: %.1f%%", evalAcc))

// MARK: - Save

let metadata = MLModelMetadata(
    author: "Divvun",
    shortDescription: "North Sami (sme) lemmatizer — prototype trained from FST-generated paradigms",
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
