#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Med-Research Library Genesis (LibGen) PDF Downloader (v1.0)
Specifically searches LibGen Sci-Mag databases for DOIs, parses download gateways,
and retrieves full PDF binaries bypassing Sci-Hub mirrors.
"""

import os
import sys
import urllib.request
import urllib.parse
import re
import time

LIBGEN_SCIMAG_MIRRORS = [
    "https://libgen.is/scimag",
    "https://libgen.rs/scimag",
    "https://libgen.st/scimag"
]

def download_pdf(url, output_path, timeout=30):
    """Downloads a file from a URL with browser emulation headers."""
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read()
            if b"%PDF" in content[:1024]:
                with open(output_path, 'wb') as f:
                    f.write(content)
                return True
    except Exception as e:
        print(f"      Fetch failed: {e}")
    return False

def harvest_from_libgen(doi, output_path):
    print(f"\n[LibGen Engine] Target DOI: {doi}")
    doi_clean = doi.replace("https://doi.org/", "").strip()
    
    # 1. Search LibGen Sci-Mag for the DOI
    search_query = urllib.parse.quote(doi_clean)
    success = False
    
    for mirror in LIBGEN_SCIMAG_MIRRORS:
        search_url = f"{mirror}/?q={search_query}"
        print(f"  Querying LibGen Sci-Mag index: {search_url}...")
        
        req = urllib.request.Request(
            search_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                html = r.read().decode('utf-8', errors='ignore')
                
                # LibGen Sci-Mag search page lists download links in the table.
                # Standard pattern is links pointing to library.lol/scimag/xxxx or gen.lib.rus.ec
                download_gateways = re.findall(r'href="([^"]+library\.lol/scimag/[^"]+)"', html)
                if not download_gateways:
                    download_gateways = re.findall(r'href="([^"]+libgen\.lc/scimag/[^"]+)"', html)
                if not download_gateways:
                    download_gateways = re.findall(r'href="([^"]+sci-hub[^"]+)"', html)
                    
                # De-duplicate links
                download_gateways = list(set(download_gateways))
                if download_gateways:
                    print(f"    Found {len(download_gateways)} potential LibGen download gateway(s):")
                    for gateway in download_gateways:
                        # Normalize gateway protocol
                        if gateway.startswith("//"):
                            gateway = "https:" + gateway
                            
                        print(f"    Navigating gateway: {gateway}...")
                        # 2. Open the gateway page and find the direct download link
                        # The gateway page (library.lol) has a direct link pointing to the PDF
                        gateway_req = urllib.request.Request(
                            gateway, 
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                        )
                        try:
                            with urllib.request.urlopen(gateway_req, timeout=15) as gw_resp:
                                gw_html = gw_resp.read().decode('utf-8', errors='ignore')
                                # Direct download URL is usually under <h2><a href="direct_link">GET</a></h2>
                                direct_match = re.search(r'href="([^"]+\.pdf[^"]*)"', gw_html, re.IGNORECASE)
                                if not direct_match:
                                    direct_match = re.search(r'href="([^"]+)"[^\>]*\>GET\<\/a\>', gw_html, re.IGNORECASE)
                                    
                                if direct_match:
                                    direct_pdf_url = direct_match.group(1)
                                    if direct_pdf_url.startswith("//"):
                                        direct_pdf_url = "https:" + direct_pdf_url
                                        
                                    print(f"      Resolved LibGen Direct PDF URL: {direct_pdf_url}")
                                    if download_pdf(direct_pdf_url, output_path):
                                        print(f"      [Success] Saved PDF from LibGen: {os.path.basename(output_path)}")
                                        success = True
                                        break
                        except Exception as e:
                            print(f"      Gateway navigation failed: {e}")
                    if success:
                        break
                else:
                    print("    No LibGen download gateways resolved in HTML response.")
        except Exception as e:
            print(f"    Search mirror failed: {e}")
            
    return success

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python libgen_downloader.py [DOI] [Output_Path]")
        sys.exit(1)
    harvest_from_libgen(sys.argv[1], sys.argv[2])
