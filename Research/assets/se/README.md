# North Sami (se) LinguisticData Research Bundle

This directory contains a research/placeholder LinguisticData asset bundle
for North Sami (se), constructed by reverse-engineering Apple's existing
language bundles as part of the Divvun macOS Analyser project.

## Purpose

This bundle documents the file structure and format that Apple uses internally
for language assets consumed by NLTagger, Dictionary.app, and Spotlight.
It is evidence of what a third-party language provider would need to produce
in order to add a minority language to Apple's NLP pipeline — currently
impossible via any public or documented API.

## Bundle Structure

  Info.plist            Bundle metadata: language, locale, content type registry
  se.lm/                Language model bundle subdirectory
    fst.dat             OpenFST const-format transducer (tokenizer/morphology)
    pos.dat             POS tagger data (proprietary Apple format)
    lm.dat              N-gram language model data (format TBD)
  Lemmatizer-se.dat     Lemmatizer binary (proprietary Apple format)

## File Formats

### fst.dat
Magic bytes: d6 fd b2 7e (= little-endian 0x7eb2fdd6, OpenFST file magic)
Followed by FST type string "const" and arc type "standard".

This is the **OpenFST constant/compact FST format**, the same family as HFST.
Divvun's North Sami analyser (se.zhfst / se.hfst) is built with HFST and uses
a compatible transducer format. The conversion path is:

  se.hfst → fstconvert --fst_type=const → fst.dat

This is our highest-confidence lead for producing functional content.

### Lemmatizer-se.dat
Magic bytes: 24 31 12 00 (proprietary Apple format)
This file provides lemma forms via a lookup mechanism separate from fst.dat.
The format is not yet understood. Options:
  - Further disassembly of LinguisticData.framework
  - Differential analysis of multiple language files to find structure patterns
  - Attempting to use only fst.dat (skipping Lemmatizer-se.dat) to see if
    NLTagger's .lemma scheme can be satisfied by the LanguageModel alone

### pos.dat
Magic bytes: 64 00 00 00 (= decimal 100 in LE, unknown format)
POS tagger data. Not required for basic lemma lookup.

## What Apple Would Need to Provide

For Divvun (and other minority language providers) to integrate with the
standard macOS NLP pipeline, Apple would need to provide ONE of:

1. A documented AssetType registration API so third parties can register
   language bundles at a user-level path (e.g. ~/Library/Application Support/Apple/NLP/).
2. Documentation of the fst.dat and Lemmatizer-*.dat formats so the community
   can produce compatible assets.
3. A public NLTagger extension point that allows overriding .lemma for new locales
   (similar to how App Extensions work for custom tag schemes, but system-level).

## Context

As of macOS 14, NLTagger's .lemma scheme is only available for:
  en, fr, de, pt, ru, sv

All Sami languages (se, smn, sms, sma, smj, etc.), along with hundreds of
other minority and indigenous languages, receive only the lowest tier of
support: Language, Script, and TokenType detection only.

This technical gap means that Dictionary.app and Spotlight cannot perform
morphology-aware lookup for these languages, putting them at a systematic
disadvantage in Apple's software ecosystem.

## References

- Divvun Group: https://divvun.no
- HFST: https://hfst.github.io
- OpenFST: https://openfst.org
- macos-analyser: https://github.com/divvun/macos-analyser