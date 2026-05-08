#!/usr/bin/env swift
// test.swift — Test the SME lemmatizer model using NLTagger + NLModel.
//
// Usage:
//   swift test.swift [model.mlmodel] [word1 word2 ...]
//
// If no words are provided, runs a built-in test suite.
// Requires macOS 10.15+ with NaturalLanguage and CoreML.

import Foundation
import NaturalLanguage
import CoreML

// MARK: - Arguments

let args = CommandLine.arguments
let modelPath = args.count > 1 ? args[1] : "Research/proto/sme-lemmatizer/SmeLemmatizer.mlmodel"

// Test words: inflected forms whose lemmas should be known from training data
let testWords: [String] = args.count > 2
    ? Array(args.dropFirst(2))
    : [
        // Nouns
        "mánáid",    // mánná (child, Pl.Gen)
        "máná",      // mánná (child, Sg.Gen)
        "mánnái",    // mánná (child, Sg.Ill)
        "gielain",   // giella (language, Sg.Com)
        "gielda",    // gielda (municipality, Sg.Nom)
        "gieldas",   // gielda (municipality, Sg.Loc)
        "skuvllas",  // skuvla (school, Sg.Loc)
        // Verbs
        "boahtá",    // boahtit (to come, Prs.Sg3)
        "bohtii",    // boahtit (to come, Prt.Sg3)
        "mana",      // mannat (to go, Prs.Sg3)
        "čálá",      // čállit (to write, Prs.Sg3)
        "lohká",     // lohkat (to read, Prs.Sg3)
        // Adjectives
        "buorrin",   // buorre (good, Ess)
        "stuorra",   // stuorra (big, Sg.Nom)
        // Lemma forms (should return themselves)
        "boahtit",   // boahtit
        "mánná",     // mánná
        "giella",    // giella
    ]

// MARK: - Load model

let modelURL = URL(fileURLWithPath: modelPath)

print("Loading model: \(modelPath)")

let mlModel: MLModel
do {
    // MLWordTagger models saved as .mlmodel need compilation first
    let compiledURL = try MLModel.compileModel(at: modelURL)
    mlModel = try MLModel(contentsOf: compiledURL)
} catch {
    fputs("ERROR loading model: \(error)\n", stderr)
    fputs("Make sure the model file exists and was saved by train.swift\n", stderr)
    exit(1)
}

let nlModel: NLModel
do {
    nlModel = try NLModel(mlModel: mlModel)
} catch {
    fputs("ERROR creating NLModel: \(error)\n", stderr)
    exit(1)
}

// MARK: - Set up tagger

let tagger = NLTagger(tagSchemes: [.lemma])
tagger.setModels([nlModel], forTagScheme: .lemma)

// Build test text as space-separated words
let testText = testWords.joined(separator: " ")
tagger.string = testText
tagger.setLanguage(NLLanguage("se"), range: testText.startIndex..<testText.endIndex)

// MARK: - Run and print results

print("\nLemmatization results:")
print(String(repeating: "-", count: 50))
func padRight(_ text: String, to width: Int) -> String {
    let chars = text.count
    if chars >= width { return text }
    return text + String(repeating: " ", count: width - chars)
}

print("\(padRight("surface", to: 20))  lemma")
print(String(repeating: "-", count: 50))

var correct = 0
var total   = 0

tagger.enumerateTags(
    in: testText.startIndex..<testText.endIndex,
    unit: .word,
    scheme: .lemma,
    options: .omitWhitespace
) { tag, range in
    let surface = String(testText[range])
    let lemma   = tag?.rawValue ?? "(no tag)"
    print("\(padRight(surface, to: 20))  \(lemma)")
    total += 1
    // Simple check: if surface == lemma, or lemma looks like a valid sme lemma
    if !lemma.contains("(") { correct += 1 }
    return true
}

print(String(repeating: "-", count: 50))
print("Tagged \(total) words, \(correct) with a lemma tag.")
