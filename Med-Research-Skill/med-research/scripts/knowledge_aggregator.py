#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Med-Research Knowledge Aggregator (v11.0)
Extracts key technical equations and engineering parameters from local PDF papers.
"""

import os
import re
import sys

def search_text_for_patterns(text):
    """Scans raw text for medical physics formulas, metrics, or sample sizes."""
    findings = []
    
    # 1. Look for equation-like patterns (e.g., PVR = ..., Formula = ..., sensitivity = ...)
    formula_patterns = [
        r'[A-Za-z_]+\s*=\s*[\w\s\/\+\-\*\(\)\{\}\[\]\.\$\_]+', # e.g. PVR = PI_apron / PI_2mmPb
        r'\b(?:PVR|Sensitivity|Specificity|F1-score|Accuracy)\b\s*:\s*\d+[\.\d]*%?',
        r'\b\d+\s*kVp\b',
        r'\b\d+\s*mm\s*Pb\b',
        r'\bn\s*=\s*\d+[\d,]*\b' # sample size
    ]
    
    for pattern in formula_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            if m.strip() and len(m.strip()) > 3:
                findings.append(m.strip())
                
    return list(set(findings))

def extract_from_file(file_path):
    """Reads local text files, HTML files, or extracts metadata summary as fallback."""
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return []
        
    ext = os.path.splitext(file_path)[1].lower()
    
    # Text, markdown, HTML fallback extraction
    if ext in ['.txt', '.html', '.md', '.xml']:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return search_text_for_patterns(content)
        except Exception as e:
            print(f"Failed to read file: {e}")
    
    elif ext == '.pdf':
        # If PyPDF2 is installed, try extracting text. Otherwise flag dependency.
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                # Scan first 5 pages (usually contains methods/formulas)
                max_pages = min(5, len(reader.pages))
                for i in range(max_pages):
                    text += reader.pages[i].extract_text()
                return search_text_for_patterns(text)
        except ImportError:
            # Fallback to metadata / name pattern search
            basename = os.path.basename(file_path)
            print(f"[Warning] PyPDF2 not installed. Unable to parse PDF text for {basename}.")
            return [f"Filename Reference: {basename}"]
        except Exception as e:
            print(f"Error parsing PDF: {e}")
            
    return []

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python knowledge_aggregator.py [path_to_paper_or_directory]")
        sys.exit(1)
        
    target = sys.argv[1]
    if os.path.isdir(target):
        for f in os.listdir(target):
            p = os.path.join(target, f)
            if os.path.isfile(p) and f.endswith(('.pdf', '.txt', '.html')):
                print(f"\nScanning: {f}")
                results = extract_from_file(p)
                for r in results[:10]: # Print top 10 formulas found
                    print(f"  - Extracted parameter/formula: {r}")
    else:
        results = extract_from_file(target)
        print(f"\nResults for {os.path.basename(target)}:")
        for r in results:
            print(f"  - Extracted parameter/formula: {r}")
