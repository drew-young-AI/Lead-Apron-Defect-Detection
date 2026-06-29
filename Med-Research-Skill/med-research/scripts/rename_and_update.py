#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Med-Research PDF Rename and Report Link Updater (v1.0)
Renames physical PDF files to their clean Windows-compatible paper titles and updates the markdown report.
"""

import os
import re

def clean_filename(title):
    # Remove Windows invalid characters: \ / : * ? " < > |
    cleaned = re.sub(r'[\x00-\x1f\\/:*?\"<>|]', '', title)
    return cleaned.strip()

def run_rename_and_update(report_path, papers_dir):
    print("--- Starting PDF Rename and Report Updater ---")
    if not os.path.exists(report_path):
        print(f"Report not found: {report_path}")
        return
        
    # Read the markdown report
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Define mapping of old files (already existing) to their official paper titles
    mapping = {
        # Row 03: A simple quality control tool for assessing integrity of lead equivalent aprons
        'A simple quality control tool for assessing integrity of lead equivalent aprons': [
            '10_4103_ijri_IJRI_374_17.pdf',
            'Livingstone_2018_PVR_Integrity.pdf'
        ],
        # Row 05: Development of a Model for Predicting Defects in Radiation Shielding Aprons Using Machine Learning
        'Development of a Model for Predicting Defects in Radiation Shielding Aprons Using Machine Learning': [
            '10_30699_fhi_v13i7_1284.pdf',
            '10_30699_fhi.v13i7_1284.pdf',
            '2024_Lead_Apron_ML_Kim.pdf'
        ]
    }
    
    # 1. Rename physical files on disk
    renamed_files = {} # maps original target path to new clean title name
    
    for title, sources in mapping.items():
        clean_name = clean_filename(title) + ".pdf"
        target_path = os.path.join(papers_dir, clean_name)
        
        # Check if target already exists, if so we don't need to rename unless it's missing
        target_exists = os.path.exists(target_path)
        
        for src_name in sources:
            src_path = os.path.join(papers_dir, src_name)
            if os.path.exists(src_path):
                if src_path == target_path:
                    continue
                # If target exists, delete the source to keep it clean, otherwise rename
                if os.path.exists(target_path):
                    os.remove(src_path)
                    print(f"  Removed duplicate file to clean workspace: {src_name}")
                else:
                    os.rename(src_path, target_path)
                    print(f"  Renamed {src_name} -> {clean_name}")
                    target_exists = True
        
        if target_exists:
            renamed_files[title] = clean_name
            
    # 2. Update links in the Markdown Report content
    # Replace relative PDF links with the new paper title PDF links
    lines = content.split("\n")
    updated_lines = []
    
    for line in lines:
        if "|" in line:
            # Check if this row matches any of our titles
            for title, clean_name in renamed_files.items():
                # Locate if the line contains the title
                if title in line:
                    # Find any relative PDF link inside this row and replace it with the clean title PDF name
                    # Matches [PDF](../papers/xxx.pdf)
                    match = re.search(r'\[PDF\]\(\.\./papers/[^\)]+\)', line)
                    if match:
                        old_link = match.group(0)
                        new_link = f"[PDF](../papers/{urllib.parse.quote(clean_name)})"
                        # Make sure not to double-encode or break, standard relative URL:
                        new_link = f"[PDF](../papers/{clean_name})"
                        line = line.replace(old_link, new_link)
                        print(f"  Updated link in report for title: '{title[:30]}...' -> {clean_name}")
        updated_lines.append(line)
        
    # Write back the updated report
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(updated_lines))
        
    print("--- Completed Rename and Report Update successfully! ---")

if __name__ == "__main__":
    import urllib.parse
    report_file = "D:/project/Med Deep Research/reports/v12.0_LeadApron_DICOM_Master.md"
    papers_directory = "D:/project/Med Deep Research/papers"
    run_rename_and_update(report_file, papers_directory)
