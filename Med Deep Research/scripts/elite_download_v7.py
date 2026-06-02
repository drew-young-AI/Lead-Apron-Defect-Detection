import asyncio
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

def download_paper(url, output):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        stealth_sync(page)
        page.goto(url)
        # 簡單等待以防渲染
        page.wait_for_timeout(5000)
        page.pdf(path=output)
        browser.close()

if __name__ == " __main__\:
 import argparse
 parser = argparse.ArgumentParser()
 parser.add_argument(\--url\)
 parser.add_argument(\--output\)
 args = parser.parse_args()
 download_paper(args.url, args.output)
