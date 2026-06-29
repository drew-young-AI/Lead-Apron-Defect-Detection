#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Med-Research Verification Engine (v11.0)
Auto-checks DOI validity, physical PDF file existence, and report matrix formatting.
"""

import os
import re
import sys
import urllib.request
import json
from urllib.error import URLError, HTTPError

def check_pdf_exists(pdf_path, base_dir):
    """Checks if a PDF file actually exists on disk."""
    # Resolve relative path
    abs_path = os.path.abspath(os.path.join(base_dir, pdf_path))
    res = os.path.exists(abs_path)
    print(f"    [Debug Path Check] path={abs_path} exists={res}")
    return res

def verify_doi_title(doi, expected_title, timeout=5):
    """Uses CrossRef API to verify if DOI matches the expected title."""
    if not doi:
        return False, "No DOI"
    
    # Strip url prefix if present
    doi_clean = doi.replace("https://doi.org/", "").strip()
    url = f"https://api.crossref.org/works/{doi_clean}"
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Med-Research-Agent/11.0 (mailto:agent@localhost)'}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8'))
            message = data.get("message", {})
            titles = message.get("title", [])
            if not titles:
                return False, "No title found in DOI metadata"
            
            actual_title = titles[0].lower().strip()
            expected = expected_title.lower().strip()
            
            # Basic validation: check if major keywords exist or edit distance is small
            # For simplicity, check if the first 4 words of the expected title match keywords in the actual title
            expected_words = [w for w in re.findall(r'\b\w+\b', expected) if len(w) > 3]
            actual_words = [w for w in re.findall(r'\b\w+\b', actual_title) if len(w) > 3]
            
            match_count = sum(1 for w in expected_words[:4] if w in actual_words)
            if match_count >= min(2, len(expected_words)):
                return True, "Verified Match"
            else:
                return False, f"Title mismatch. CrossRef: '{titles[0]}'"
    except HTTPError as e:
        if e.code == 404:
            return False, "DOI not found on CrossRef (404)"
        return False, f"HTTP Error {e.code}"
    except Exception as e:
        return False, f"Verification failed due to error: {str(e)}"

def verify_markdown_report(report_path, papers_dir):
    """Parses markdown table and verifies each row."""
    if not os.path.exists(report_path):
        print(f"[Error] Report file not found: {report_path}")
        return False

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    updated_lines = []
    in_table = False
    table_headers = []
    
    # Regex to find markdown links [text](url)
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

    print(f"\n--- Starting Audit for: {os.path.basename(report_path)} ---")
    
    base_dir = os.path.dirname(report_path)
    modified = False

    for line in lines:
        if "|" in line:
            # Check if this is a table row using negative lookbehind for escaped pipes
            parts = [p.strip() for p in re.split(r'(?<!\\)\|', line)]
            # Skip divider line (e.g. |---|---|)
            if not in_table:
                if len(parts) > 3:
                    in_table = True
                    table_headers = parts
                    updated_lines.append(line)
                    continue
            
            if in_table and len(parts) > 3 and not all(c in "-:" for c in parts[1]):
                # Process row
                row_no = parts[1] # e.g. **01** or 1
                title_col = parts[2]
                ref_col = parts[-2] # REF is usually the last column before the final |
                
                # Extracted parameters
                title = title_col.replace("**", "").replace("`", "").strip()
                
                # Parse DOI from column 1 or 7
                doi = ""
                doi_match = re.search(r'https://doi.org/[^\s\)]+', line)
                if doi_match:
                    doi = doi_match.group(0)

                print(f"\nRow {row_no}: Checking '{title[:40].encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')}...'")
                
                # 1. DOI Validation
                updated_parts = list(parts)
                if doi:
                    doi_ok, doi_msg = verify_doi_title(doi, title)
                    # Protect print from Windows encoding crashes
                    safe_msg = doi_msg.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
                    print(f"  [DOI Verification] {safe_msg}")
                    if not doi_ok:
                        # Append the warning outside the Markdown link in the first column (parts[1])
                        # E.g. **01** / [10.xxx](url) / JCR -> **01** / [10.xxx](url) **(REF recovery pending)** / JCR
                        if "(REF recovery pending)" not in updated_parts[1]:
                            updated_parts[1] = updated_parts[1] + " **(REF recovery pending)**"
                            modified = True
                
                # 2. Local PDF vs Web Link Validation in REF column
                links = link_pattern.findall(ref_col)
                updated_ref_col = ref_col
                
                for label, url in links:
                    if label.lower() == "pdf":
                        # Verify physical file existence
                        exists = check_pdf_exists(url, base_dir)
                        if not exists:
                            # Protect print from encoding crash
                            safe_url = url.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
                            print(f"  [PDF ERROR] File does not exist: {safe_url}")
                            # Replace [PDF](path) with [PENDING](web_url) or fallback
                            web_url = doi if doi else "https://pubmed.ncbi.nlm.nih.gov/"
                            for l2, u2 in links:
                                if l2.lower() == "web":
                                    web_url = u2
                            
                            updated_ref_col = updated_ref_col.replace(f"[PDF]({url})", f"[PENDING]({web_url})")
                            modified = True
                        else:
                            safe_url = url.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8')
                            print(f"  [PDF OK] Verified: {safe_url}")
                            # Keep relative path unchanged for portability (do not convert to file:///)
                            
                if modified:
                    # Assign updated ref column
                    updated_parts[-2] = updated_ref_col
                    # Reconstruct row line from updated_parts ensuring correct Markdown format:
                    # | Column 1 | Column 2 | ... | Column 8 |
                    cleaned_parts = [p.strip() for p in updated_parts]
                    if cleaned_parts[0] == "":
                        cleaned_parts = cleaned_parts[1:]
                    if cleaned_parts[-1] == "":
                        cleaned_parts = cleaned_parts[:-1]
                    line = "| " + " | ".join(cleaned_parts) + " |"
            
            updated_lines.append(line)
        else:
            in_table = False
            updated_lines.append(line)

    if modified:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(updated_lines))
        print("\n[Audit Status] Completed: Report updated with corrections.")
    else:
        print("\n[Audit Status] Completed: All links and titles are valid. No changes needed.")
        
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_integrity.py [path_to_markdown_report]")
        sys.exit(1)
        
    report = sys.argv[1]
    # Standard output directory mapping
    papers_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Med Deep Research/papers/"))
    verify_markdown_report(report, papers_directory)
