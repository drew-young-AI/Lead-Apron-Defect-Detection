#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Med-Research Dynamic Repository PDF Crawler (v1.0)
Uses Playwright to crawl Google Search, institutional repositories, and ResearchGate for public preprints/PDFs.
"""

import os
import sys
import time
import urllib.parse
import urllib.request
import re
from playwright.sync_api import sync_playwright

def get_google_pdf_links(query):
    """Searches DuckDuckGo HTML using urllib and regex for maximum stability."""
    search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    print(f"Searching DuckDuckGo for: '{query}'...")
    
    pdf_links = []
    req = urllib.request.Request(
        search_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8', errors='ignore')
            # Extract all hrefs
            hrefs = re.findall(r'href="([^"]+)"', html)
            for h in hrefs:
                # Clean duckduckgo outgoing redirect wrapping if present
                if "uddg=" in h:
                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(h).query)
                    uddg = parsed.get("uddg")
                    if uddg:
                        h = uddg[0]
                
                if h.startswith("http"):
                    h_lower = h.lower()
                    if ".pdf" in h_lower or "pdf" in h_lower or "researchgate.net/publication" in h_lower or "core.ac.uk" in h_lower or "sci-hub" in h_lower or "europepmc.org/article" in h_lower:
                        pdf_links.append(h)
    except Exception as e:
        print(f"Error searching DuckDuckGo: {e}")
        
    return list(set(pdf_links))

def download_pdf_via_browser(url, output_path):
    """Attempts to download PDF from a dynamic page/link by intercepting network traffic."""
    print(f"  Attempting browser download from: {url}")
    success = False
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Intercept network responses to catch the PDF content stream
        pdf_data = None
        
        def handle_response(response):
            nonlocal pdf_data
            try:
                headers = response.headers
                content_type = headers.get("content-type", "").lower()
                if "application/pdf" in content_type or response.url.endswith(".pdf"):
                    print(f"    [Intercepted PDF] url={response.url} type={content_type}")
                    pdf_data = response.body()
            except Exception:
                pass
                
        page.on("response", handle_response)
        
        try:
            # Navigate and wait for load
            page.goto(url, wait_until="load", timeout=25000)
            time.sleep(4)
            
            # If it's a ResearchGate publication page, try to click the Download button
            if "researchgate.net/publication" in url:
                print("    Targeting ResearchGate publication page. Locating download links...")
                download_btn = page.locator("a:has-text('Download'), a[href*='download'], button:has-text('Download')")
                if download_btn.count() > 0:
                    print("    Clicking Download button on ResearchGate page...")
                    download_btn.first.click()
                    time.sleep(5)
            
            # Save intercepted PDF if found
            if pdf_data and b"%PDF" in pdf_data[:1024]:
                with open(output_path, "wb") as f:
                    f.write(pdf_data)
                print(f"    [Success] Intercepted and saved PDF to {os.path.basename(output_path)}")
                success = True
            else:
                # Fallback: check if the final URL is a direct PDF download
                final_url = page.url
                if final_url.endswith(".pdf") or "pdf" in final_url.lower():
                    # Attempt simple HTTP request fetch if no cookies/tokens required
                    response = page.request.get(final_url)
                    if response.status == 200 and b"%PDF" in response.body()[:1024]:
                        with open(output_path, "wb") as f:
                            f.write(response.body())
                        print(f"    [Success] Downloaded direct PDF from final URL: {os.path.basename(output_path)}")
                        success = True
        except Exception as e:
            print(f"    Browser navigation/action failed: {e}")
            
        browser.close()
        
    return success

def run_deep_harvest(doi, title, output_path):
    """Runs a multi-pronged search and harvest for a specific closed paper."""
    print(f"\n[Deep Harvest] Starting search for: '{title}' (DOI: {doi})")
    
    # Setup search queries
    queries = [
        f'\"{title}\" pdf',
        f'\"{title}\" filetype:pdf',
        f'{doi} pdf'
    ]
    
    candidate_urls = []
    for query in queries:
        links = get_google_pdf_links(query)
        candidate_urls.extend(links)
        time.sleep(2)
        
    candidate_urls = list(set(candidate_urls))
    print(f"Found {len(candidate_urls)} potential open PDF download URLs.")
    
    # Try downloading from each candidate URL
    for url in candidate_urls:
        # Ignore main publisher portals that are known to be strictly paid/CF-walled
        if any(domain in url for domain in ["link.springer.com", "journals.lww.com", "doi.org"]):
            continue
            
        success = download_pdf_via_browser(url, output_path)
        if success:
            return True
            
    return False

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python search_and_download_deep.py [DOI] [Title] [Output_Path]")
        sys.exit(1)
    run_deep_harvest(sys.argv[1], sys.argv[2], sys.argv[3])
