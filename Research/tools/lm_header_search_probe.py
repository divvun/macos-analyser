#!/usr/bin/env python3
"""
2r: Header/Prototype Search Probe

Systematically search for LMLanguageModelCreate prototypes and related headers.

Search locations:
1. LanguageModeling private framework (runtime + SDK)
2. .tbd export file for symbol-level hints
3. Binary DWARF/debug metadata availability
4. Inferred prototype from prior 2n-2q evidence
"""

import subprocess
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from typing import Optional, List

@dataclass
class FindingItem:
    category: str
    location: str
    content_preview: Optional[str] = None
    notes: str = ""

def run_cmd(cmd: str) -> str:
    """Run shell command safely."""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return f"ERROR: {str(e)}"

def search_system_headers() -> List[FindingItem]:
    """Search for LM/LanguageModeling headers in relevant framework roots only."""
    findings = []

    paths_to_check = [
        "/System/Library/PrivateFrameworks/LanguageModeling.framework",
        "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/PrivateFrameworks/LanguageModeling.framework",
    ]

    header_name_pattern = re.compile(r"(languagemodeling|lmlanguage|lmvocabulary).*(\.h|\.hpp)$", re.IGNORECASE)

    for base_path in paths_to_check:
        if not os.path.exists(base_path):
            continue

        # List candidate header files and then filter by strict filename patterns.
        cmd = f"find '{base_path}' -type f \\( -name '*.h' -o -name '*.hpp' \\) 2>/dev/null"
        result = run_cmd(cmd)
        if not result:
            findings.append(FindingItem(
                category="header_search",
                location=base_path,
                content_preview="(no header files found)",
                notes="No headers shipped in this framework path"
            ))
            continue

        candidates = [line.strip() for line in result.splitlines() if line.strip()]
        relevant = [p for p in candidates if header_name_pattern.search(os.path.basename(p))]

        if relevant:
            findings.append(FindingItem(
                category="header_search",
                location=base_path,
                content_preview="\n".join(relevant[:20]),
                notes=f"Found relevant headers: {len(relevant)}"
            ))
        else:
            findings.append(FindingItem(
                category="header_search",
                location=base_path,
                content_preview="(headers exist, none matched LM/LanguageModeling naming)",
                notes=f"Total headers scanned: {len(candidates)}"
            ))

    return findings

def analyze_tbd_symbols() -> List[FindingItem]:
    """Analyze .tbd file for symbol hints about Create function."""
    findings = []
    
    tbd_path = "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk/System/Library/PrivateFrameworks/LanguageModeling.framework/Versions/A/LanguageModeling.tbd"
    
    if not os.path.exists(tbd_path):
        return findings
    
    try:
        with open(tbd_path, 'r') as f:
            content = f.read()
        
        # Extract _LMLanguageModelCreate and related symbols
        create_symbols = re.findall(r'_LMLanguageModel[A-Za-z0-9_]*', content)
        create_symbols = sorted(set(create_symbols))
        
        findings.append(FindingItem(
            category="tbd_symbols",
            location=tbd_path,
            content_preview=f"Found {len(create_symbols)} LMLanguageModel* symbols",
            notes=f"Create function present: {'_LMLanguageModelCreate' in create_symbols}"
        ))
        
        # Document key symbols
        key_symbols = [s for s in create_symbols if 'Create' in s or 'GetToken' in s or 'Release' in s]
        if key_symbols:
            findings.append(FindingItem(
                category="tbd_key_symbols",
                location="symbol_analysis",
                content_preview="\n".join(key_symbols[:15]),
                notes=f"Total key symbols: {len(key_symbols)}"
            ))
        
    except Exception as e:
        findings.append(FindingItem(
            category="tbd_error",
            location=tbd_path,
            notes=f"Error reading: {str(e)}"
        ))
    
    return findings

def check_dwarf_debug_info() -> List[FindingItem]:
    """Check if binary has DWARF debug info."""
    findings = []
    
    binary_path = "/System/Library/PrivateFrameworks/LanguageModeling.framework/Versions/A/LanguageModeling"

    if not os.path.exists(binary_path):
        findings.append(FindingItem(
            category="dwarf_info",
            location=binary_path,
            content_preview="Runtime binary not present as standalone file",
            notes="Likely stored in dyld shared cache on this macOS build"
        ))
        return findings
    
    cmd = f"dwarfdump -F '{binary_path}' 2>&1 | head -20"
    result = run_cmd(cmd)
    
    if "DW_TAG" in result or "DW_AT" in result:
        findings.append(FindingItem(
            category="dwarf_info",
            location=binary_path,
            content_preview="DWARF debug info present",
            notes="Could extract type info with dwarfdump"
        ))
    elif result:
        findings.append(FindingItem(
            category="dwarf_info",
            location=binary_path,
            content_preview="No DWARF type metadata detected",
            notes=result.splitlines()[0][:200]
        ))
    
    return findings

def check_xcode_documentation() -> List[FindingItem]:
    """Check Xcode documentation paths."""
    findings = []
    
    doc_paths = [
        "/Applications/Xcode.app/Contents/Developer/Documentation",
        "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/Documentation",
    ]
    
    for doc_path in doc_paths:
        if os.path.exists(doc_path):
            cmd = f"find '{doc_path}' -type f \\( -name '*LanguageModeling*' -o -name '*LM*' \\) 2>/dev/null | head -5"
            result = run_cmd(cmd)
            if result:
                findings.append(FindingItem(
                    category="xcode_docs",
                    location=doc_path,
                    content_preview=result,
                    notes="Found documentation references"
                ))
    
    return findings

def infer_create_prototype() -> List[FindingItem]:
    """Infer Create function prototype from available evidence."""
    findings = []
    
    # Evidence from previous probes:
    # 1. 2n-2q show create returns void* (model_ptr)
    # 2. 2o shows NSInvalidArgumentException on dict access
    # 3. 2p/2q show dict keys: locale, appContext, adaptationEnabled, isSiriModel
    # 4. Call site expects NSDictionary or CFDictionary
    
    inferred_proto = """
// Inferred from 2n-2q probe evidence:
typedef void* LMLanguageModelRef;

// Most likely signature (based on crashes and key recovery):
LMLanguageModelRef _LMLanguageModelCreate(
    CFDictionaryRef options  // or NSDictionary*
);

// Dictionary keys (from dyld imports):
- kLMLanguageModelLocaleKey          (CFStringRef)
- kLMLanguageModelAppContextKey      (CFStringRef or nil)
- kLMLanguageModelAdaptationEnabledKey (CFBooleanRef)
- kLMLanguageModelIsSiriModelKey     (CFBooleanRef)

// Possible alternative signatures:
// 1. _LMLanguageModelCreate(locale, options)
// 2. _LMLanguageModelCreate(options, callbacks)
// 3. _LMLanguageModelCreate(dictionary) + setters
"""
    
    findings.append(FindingItem(
        category="inferred_prototype",
        location="evidence_synthesis",
        content_preview=inferred_proto.strip(),
        notes="Based on 2n-2q blocking signals and dyld key recovery"
    ))
    
    return findings

def main():
    """Run comprehensive header search."""
    
    findings = []
    
    # 1. System header search
    findings.extend(search_system_headers())
    
    # 2. .tbd symbol analysis
    findings.extend(analyze_tbd_symbols())
    
    # 3. DWARF debug info check
    findings.extend(check_dwarf_debug_info())
    
    # 4. Xcode documentation
    findings.extend(check_xcode_documentation())
    
    # 5. Inferred prototype
    findings.extend(infer_create_prototype())
    
    # Prepare report
    result = {
        "probe_type": "header_search",
        "phase": "2r",
        "step_name": "Header/Prototype Search",
        "total_findings": len(findings),
        "findings": [asdict(f) for f in findings],
        "observed_result": "HEADER_SEARCH_COMPLETE",
    }

    # Determine if successful (only count relevant LanguageModeling headers or usable DWARF).
    has_headers = any(
        f["category"] == "header_search" and "found relevant headers" in (f.get("notes") or "").lower()
        for f in result["findings"]
    )
    has_dwarf = any(
        f["category"] == "dwarf_info" and (f.get("content_preview") or "").strip().lower() == "dwarf debug info present"
        for f in result["findings"]
    )

    if has_headers or has_dwarf:
        result["observed_result"] = "HEADERS_OR_DWARF_FOUND"
    else:
        result["observed_result"] = "NO_PUBLIC_HEADERS_FOUND_USING_INFERRED_PROTOTYPE"
        result["next_steps"] = [
            "Consider 2r alt: disassembly-based extraction",
            "Or proceed with 2s: enum/constant probe with inferred prototype",
            "Or test inferred prototype directly"
        ]
    
    return result

if __name__ == "__main__":
    result = main()
    print(json.dumps(result, indent=2, ensure_ascii=False))
