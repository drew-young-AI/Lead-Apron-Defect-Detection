#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Med-Research Stealth Browser PDF Downloader (v1.0)
Uses Playwright with cookies, custom headers, and browser-native fetch to bypass CF 403 blocks.
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

SCIHUB_MIRRORS = [
    "https://sci-hub.se.swab.top",
    "https://sci-hub.st.swab.top",
    "https://sci-hub.hk.cn",
    "https://sci-hub.st",
    "https://sci-hub.ru"
]

def stealth_download(doi, output_path):
    print(f"\n[Stealth Downloader] Targeting DOI: {doi}")
    success = False
    
    with sync_playwright() as p:
        # Launch Chromium in headed mode to pass Cloudflare Turnstile verification
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--use-fake-device-for-media-stream",
                "--disable-web-security"
            ]
        )
        
        # Create context with realistic desktop parameters
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="zh-TW",
            timezone_id="Asia/Taipei"
        )
        
        # Inject stealth scripts to erase playwright automation flags
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        for mirror in SCIHUB_MIRRORS:
            target_url = f"{mirror}/{doi}"
            print(f"  Navigating to mirror: {target_url}...")
            
            try:
                # Go to Sci-Hub page
                response = page.goto(target_url, wait_until="commit", timeout=25000)
                if not response:
                    print("    Failed to get response (timeout/abort).")
                    continue
                    
                print(f"    Page loaded with status: {response.status}")
                if response.status == 403:
                    print("    Encountered 403 Forbidden. Trying next mirror.")
                    continue
                    
                time.sleep(4) # Let page evaluate dynamic scripts
                
                # Check for PDF embed/iframe source
                pdf_url = ""
                iframe = page.locator("iframe#pdf")
                if iframe.count() > 0:
                    pdf_url = iframe.get_attribute("src")
                else:
                    embed = page.locator("embed[type='application/pdf']")
                    if embed.count() > 0:
                        pdf_url = embed.get_attribute("src")
                        
                if not pdf_url:
                    # Look for any pdf dynamic download button/link
                    download_link = page.locator("a[onclick*='download']")
                    if download_link.count() > 0:
                        onclick = download_link.get_attribute("onclick")
                        # Extract href from onclick location.href='url'
                        match = re.search(r"href='([^']+)'", onclick or "")
                        if match:
                            pdf_url = match.group(1)
                            
                if not pdf_url:
                    # Generic lookup
                    links = page.locator("a:has-text('download'), a[href$='.pdf']")
                    if links.count() > 0:
                        pdf_url = links.first.get_attribute("href")
                        
                if pdf_url:
                    if pdf_url.startswith('//'):
                        pdf_url = 'https:' + pdf_url
                    elif not pdf_url.startswith('http'):
                        pdf_url = mirror + pdf_url
                        
                    print(f"    Resolved PDF URL: {pdf_url}")
                    
                    # Bypassing 403 on download: Evaluate a native fetch in the browser context!
                    # This ensures the download carries all cookies and the EXACT browser TLS fingerprint.
                    print("    Downloading PDF via browser-native fetch execution...")
                    js_download_script = """
                        async (url) => {
                            const response = await fetch(url);
                            const blob = await response.blob();
                            return new Promise((resolve) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result);
                                reader.readAsDataURL(blob);
                            });
                        }
                    """
                    
                    # Execute fetch and get base64 encoded data URI
                    data_uri = page.evaluate(js_download_script, pdf_url)
                    
                    if data_uri and "," in data_uri:
                        base64_data = data_uri.split(",")[1]
                        import base64
                        pdf_bytes = base64.b64decode(base64_data)
                        
                        if b"%PDF" in pdf_bytes[:1024]:
                            with open(output_path, "wb") as f:
                                f.write(pdf_bytes)
                            print(f"    [Success] Bypassed paywall and saved PDF: {os.path.basename(output_path)}")
                            success = True
                            break
                        else:
                            print("    [Error] Downloaded content is not a valid PDF.")
                    else:
                        print("    [Error] Native browser fetch did not return data.")
            except Exception as e:
                print(f"    Mirror failed due to: {e}")
                
        browser.close()
    return success

if __name__ == "__main__":
    import re
    if len(sys.argv) < 3:
        print("Usage: python stealth_scihub_downloader.py [DOI] [Output_Path]")
        sys.exit(1)
    stealth_download(sys.argv[1], sys.argv[2])
