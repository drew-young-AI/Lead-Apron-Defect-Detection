#!/usr/bin/env python3
"""
Playwright test for Batch Upload (Sub-directories) and Bulk Delete functionality.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

def log_test(title, status):
    icon = "✅" if status else "❌"
    color = GREEN if status else RED
    print(f"{color}{icon} {title}{RESET}")

async def main():
    print("Testing Batch Upload and Bulk Delete...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            await page.goto('http://localhost:8005', wait_until='networkidle')
            await page.wait_for_timeout(1000)
            
            # Setup a temporary directory with files to simulate batch upload
            data_dir = Path('/Users/drew/ENV/lead_protection/dicom_annotator/data')
            if not data_dir.exists():
                print("Data dir not found.")
                return
                
            # We will upload a directory that contains two identical DICOM files
            test_batch_dir = data_dir / 'test_batch'
            if not test_batch_dir.exists():
                print("test_batch dir not found.")
                return
            
            # 1. Batch Upload Directory
            print("\n[Step 1] Uploading Directory (Batch Upload)...")
            upload_input = page.locator('input[type="file"]')
            
            await upload_input.set_input_files(str(test_batch_dir))
            await page.wait_for_timeout(2000)
            
            # Verify file count
            # Since both files are the same, they should trigger the "duplicate" logic
            # One will be uploaded, the other detected as duplicate.
            # Only ONE item should appear in the file list because of our duplicate skipping logic
            file_count = await page.locator('.fi').count()
            if file_count == 1:
                log_test("Duplicate logic skipped duplicating the file entry in UI", True)
            else:
                log_test(f"Duplicate logic failed, found {file_count} entries", False)
            
            # 2. Upload another valid file to have 2 items if possible? We only have 1 test image.
            # That's fine, we will just test selecting and deleting the 1 item.
            print("\n[Step 2] Bulk Deletion...")
            
            file_entries = page.locator('.fi')
            if await file_entries.count() > 0:
                first_item = file_entries.nth(0)
                # Shift+Click to select
                await first_item.click(modifiers=['Shift'])
                await page.wait_for_timeout(500)
                
                # Verify delete button is visible
                del_btn = page.locator('#delete-selected-btn')
                if await del_btn.is_visible():
                    log_test("Delete selected button visible", True)
                    
                    # Accept confirm dialog automatically
                    page.on('dialog', lambda dialog: dialog.accept())
                    
                    await del_btn.click()
                    await page.wait_for_timeout(1000)
                    
                    new_count = await page.locator('.fi').count()
                    if new_count == 0:
                        log_test("File successfully deleted from list", True)
                    else:
                        log_test(f"Delete failed, {new_count} items remain", False)
                else:
                    log_test("Delete selected button not visible", False)
            else:
                log_test("No files to delete", False)
                
        except Exception as e:
            print(f"Test failed with error: {e}")
        finally:
            await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
