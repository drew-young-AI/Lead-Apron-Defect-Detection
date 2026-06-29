#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Med-Research PDF Auto-Downloader (v12.5 - Browser Automation Edition)
Integrates PMC API, Unpaywall, Sci-Hub, and Playwright Browser Automation for maximum bypass rate.
"""

import os
import sys
import urllib.request
import urllib.parse
import re
import json
import time

SCIHUB_MIRRORS = [
    "https://sci-hub.ru",
    "https://sci-hub.st",
    "https://sci-hub.ee"
]

def download_file(url, output_path, timeout=20):
    """Utility to download a file from a URL with custom user-agent."""
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            with open(output_path, 'wb') as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"      Direct download failed: {e}")
        return False

def try_pmc_direct_download(doi, output_path, timeout=15):
    """Queries NCBI Translation Tool to resolve DOI to PMCID and downloads from PMC."""
    doi_clean = doi.replace("https://doi.org/", "").strip()
    encoded_doi = urllib.parse.quote(doi_clean)
    url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={encoded_doi}&idtype=doi&format=json&tool=med-research-agent&email=agent@localhost.org"
    print("  Querying PubMed Central (PMC) Converter API...")
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Med-Research-Agent/12.5'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8'))
            records = data.get("records", [])
            if records:
                pmcid = records[0].get("pmcid")
                if pmcid:
                    print(f"    Found PMCID: {pmcid}")
                    pmc_pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
                    print(f"    Attempting direct PMC PDF download: {pmc_pdf_url}")
                    if download_file(pmc_pdf_url, output_path, timeout):
                        return True
    except Exception as e:
        print(f"    PMC API download failed: {e}")
    return False

def try_unpaywall(doi, output_path, timeout=15):
    """Attempts to find a free PDF URL via Unpaywall API."""
    doi_clean = doi.replace("https://doi.org/", "").strip()
    url = f"https://api.unpaywall.org/v2/{doi_clean}?email=unpaywall_agent@localhost.org"
    print(f"  Querying Unpaywall API for Open Access PDF...")
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Med-Research-Agent/12.5'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8'))
            is_oa = data.get("is_oa", False)
            if not is_oa:
                print("    Unpaywall: Article is not flagged as Open Access.")
                return False
                
            oa_locations = data.get("oa_locations", [])
            for loc in oa_locations:
                pdf_url = loc.get("url_for_pdf")
                if pdf_url:
                    print(f"    Unpaywall found Open Access PDF: {pdf_url}")
                    if download_file(pdf_url, output_path, timeout):
                        return True
    except Exception as e:
        print(f"    Unpaywall API query failed: {e}")
    return False

def try_playwright_scihub_bypass(doi, output_path, timeout=30):
    """
    Ladder 4: Uses Playwright Browser Automation to bypass Cloudflare Turnstile,
    resolve dynamic frames on Sci-Hub, and retrieve the full PDF.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [Warning] Playwright library not found in Python. Skipping Browser Automation.")
        return False

    doi_clean = doi.replace("https://doi.org/", "").strip()
    print("  [Browser Automation] Launching headless browser to bypass cloudflare/frames...")
    
    success = False
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use stealthy context settings
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        for mirror in SCIHUB_MIRRORS:
            url = f"{mirror}/{doi_clean}"
            print(f"    Navigating to: {url}")
            try:
                page.goto(url, wait_until="load", timeout=timeout*1000)
                time.sleep(3) # Wait for Turnstile or scripts to execute
                
                # Check for dynamic embed or iframe sources
                iframe = page.locator("iframe#pdf")
                pdf_url = ""
                if iframe.count() > 0:
                    pdf_url = iframe.get_attribute("src")
                else:
                    embed = page.locator("embed[type='application/pdf']")
                    if embed.count() > 0:
                        pdf_url = embed.get_attribute("src")
                        
                if not pdf_url:
                    # Fallback lookup in page elements
                    links = page.locator("a[href$='.pdf']")
                    if links.count() > 0:
                        pdf_url = links.first.get_attribute("href")
                
                if pdf_url:
                    if pdf_url.startswith('//'):
                        pdf_url = 'https:' + pdf_url
                    elif not pdf_url.startswith('http'):
                        pdf_url = mirror + pdf_url
                        
                    print(f"    [Browser Automation] Resolved direct PDF: {pdf_url}")
                    
                    # Read the PDF content via browser fetch to carry session cookies
                    response = page.request.get(pdf_url)
                    if response.status == 200 and b"%PDF" in response.body()[:1024]:
                        with open(output_path, "wb") as f:
                            f.write(response.body())
                        print("    [Success] Browser download complete.")
                        success = True
                        break
            except Exception as e:
                print(f"    Playwright path failed on mirror {mirror}: {e}")
                
        browser.close()
    return success

def download_pdf_from_scihub(doi, output_path, timeout=15):
    """Attempts standard urllib download from Sci-Hub mirrors."""
    doi_clean = doi.replace("https://doi.org/", "").strip()
    
    for mirror in SCIHUB_MIRRORS:
        url = f"{mirror}/{doi_clean}"
        print(f"  Trying standard Sci-Hub: {url}")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                html = response.read().decode('utf-8', errors='ignore')
                pdf_match = re.search(r'iframe\s+src="([^"]+\.pdf[^"]*)"', html, re.IGNORECASE)
                if not pdf_match:
                    pdf_match = re.search(r'embed\s+src="([^"]+\.pdf[^"]*)"', html, re.IGNORECASE)
                if not pdf_match:
                    pdf_match = re.search(r'location\.href=\'([^\']+\.pdf[^\']*)\'', html, re.IGNORECASE)
                if not pdf_match:
                    pdf_match = re.search(r'href="([^"]+\.pdf[^"]*)"', html, re.IGNORECASE)

                if pdf_match:
                    pdf_url = pdf_match.group(1)
                    if pdf_url.startswith('//'):
                        pdf_url = 'https:' + pdf_url
                    elif not pdf_url.startswith('http'):
                        pdf_url = mirror + pdf_url
                    if download_file(pdf_url, output_path, timeout):
                        return True
        except Exception as e:
            print(f"    Standard Sci-Hub path failed: {e}")
    return False

def batch_download_for_report(report_path, papers_dir):
    """Parses markdown table and runs 4-ladder download checks."""
    if not os.path.exists(report_path):
        print(f"Report not found: {report_path}")
        return
        
    os.makedirs(papers_dir, exist_ok=True)
    
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    dois = re.findall(r'https://doi.org/[0-9\.]+\/[^\s\)\|]+', content)
    dois = list(set([d.replace(')', '').strip() for d in dois]))
    
    print(f"Found {len(dois)} unique DOIs in report. Initiating 4-ladder download attempts...")
    
    for doi in dois:
        doi_clean = doi.replace("https://doi.org/", "")
        safe_name = doi_clean.replace("/", "_").replace(".", "_") + ".pdf"
        output_path = os.path.join(papers_dir, safe_name)
        
        if os.path.exists(output_path):
            print(f"\n[Skip] PDF already exists for DOI {doi}: {safe_name}")
            continue
            
        print(f"\n[Attempting Download] DOI: {doi}")
        
        # Ladder 1: PMC Direct
        success = try_pmc_direct_download(doi, output_path)
        
        # Ladder 2: Unpaywall
        if not success:
            success = try_unpaywall(doi, output_path)
            
        # Ladder 3: Standard Sci-Hub
        if not success:
            print("  Falling back to standard Sci-Hub...")
            success = download_pdf_from_scihub(doi, output_path)
            
        # Ladder 4: Playwright Browser Automation Bypass (Cloudflare challenge bypass)
        if not success:
            success = try_playwright_scihub_bypass(doi, output_path)
            
        if not success:
            print(f"  [Failure] Could not fetch PDF for DOI: {doi}")
        else:
            print(f"  [Success] Saved PDF as: {safe_name}")
            
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python download_papers.py [report_path] [papers_dir]")
        sys.exit(1)
    batch_download_for_report(sys.argv[1], sys.argv[2])
