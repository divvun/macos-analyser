// DivvunNLResearch – research tool for investigating Apple's private NLP pipeline.
//
// Subcommands:
//   phase1-coverage   Map NLTagger tag scheme availability for all languages.
//   phase1-assets     Inspect Apple LinguisticData asset bundles on this machine.
//   phase1-symbols    Enumerate private symbols from NL-related frameworks.
//   phase2-build      Build a minimal 'se' LinguisticData asset bundle.
//   phase2-inject     Attempt various asset injection strategies and report results.
//
// Usage:
//   swift run DivvunNLResearch <subcommand> [options]
//
// All findings are printed to stdout in a structured, human-readable format
// suitable for inclusion in research reports and Apple Feedback Assistant submissions.

import Foundation

let args = CommandLine.arguments.dropFirst()

guard let subcommand = args.first else {
    printHelp()
    exit(0)
}

switch subcommand {
case "phase1-coverage":
    LanguageCoverage.run()
case "phase1-assets":
    AssetCatalog.run()
case "phase1-symbols":
    PrivateSymbols.run()
case "phase2-build":
    let outputDir = args.dropFirst().first ?? "Research/assets/se"
    AssetBuilder.run(outputDir: outputDir)
case "phase2-inject":
    let assetDir = args.dropFirst().first ?? "Research/assets/se"
    InjectionTester.run(assetDir: assetDir)
default:
    fputs("Unknown subcommand: \(subcommand)\n", stderr)
    printHelp()
    exit(1)
}

func printHelp() {
    print("""
    DivvunNLResearch – Apple NL private pipeline research tool
    ==========================================================
    Usage: DivvunNLResearch <subcommand>

    Subcommands:
      phase1-coverage          Map NLTagger scheme coverage for 80+ languages
      phase1-assets            Inspect system LinguisticData asset bundles
      phase1-symbols           Enumerate private symbols in NL-related frameworks
      phase2-build [outdir]    Build a minimal 'se' LinguisticData test asset
      phase2-inject [assetdir] Attempt injection strategies and report results

    Research goal:
      Document the technical barriers preventing minority language support
      in Apple's NLTagger/Dictionary/Spotlight pipeline, and demonstrate
      what a third-party language provider would need to do to integrate.
    """)
}
