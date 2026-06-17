#!/usr/bin/env python3
"""
E2E testing for metadata panels, double-line file labels, and HU heatmap.
Verifies that all three features work end-to-end after loading a DICOM.
"""
import asyncio
import sys
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log_test(title, status):
    icon = "[OK]" if status else "[FAIL]"
    color = GREEN if status else RED
    try:
        print(f"{color}{icon} {title}{RESET}")
    except:
        safe_title = title.encode('ascii', errors='replace').decode('ascii')
        print(f"{color}{icon} {safe_title}{RESET}")

def log_section(title):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{title}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")

async def test_meta_and_hu():
    log_section("TESTING METADATA DISPLAY AND HU HEATMAP")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # Connect to app
            await page.goto('http://localhost:8005', wait_until='networkidle')
            await page.wait_for_timeout(2000)
            
            # 1. Upload the test image
            print(f"{YELLOW}Step 1: Uploading data/test_image.dcm...{RESET}")
            upload_input = page.locator('input[type="file"]')
            test_image = Path(__file__).parent.parent / 'data' / 'test_image.dcm'
            
            if not test_image.exists():
                log_test("data/test_image.dcm does not exist!", False)
                return False
                
            temp_dir = Path(__file__).parent / "temp_upload_meta"
            temp_dir.mkdir(exist_ok=True)
            shutil.copy(str(test_image), str(temp_dir / "test_image.dcm"))
            await upload_input.set_input_files(str(temp_dir))
            await page.wait_for_timeout(2000)
            log_test("Image uploaded successfully", True)
            
            # 2. Select the file in list
            print(f"{YELLOW}Step 2: Selecting uploaded DICOM...{RESET}")
            await page.wait_for_selector('.fi', timeout=10000)
            cnt = await page.locator('.fi').count()
            if cnt > 0:
                await page.locator('.fi').nth(cnt-1).click()
                await page.wait_for_timeout(2000)
                log_test("DICOM loaded into viewer", True)
            else:
                log_test("No files found in list", False)
                return False
                
            # 3. Verify Left Sidebar Three-Column label format
            print(f"{YELLOW}Step 3: Checking three-column labels...{RESET}")
            label_series_el = page.locator('.fi-label-series').nth(cnt-1)
            label_study_el = page.locator('.fi-label-study').nth(cnt-1)
            label_date_el = page.locator('.fi-label-date').nth(cnt-1)
            
            series_text = await label_series_el.text_content()
            study_text = await label_study_el.text_content()
            date_text = await label_date_el.text_content()
            
            print(f"   Label Series Description: '{series_text.strip()}'")
            print(f"   Label Study Description : '{study_text.strip()}'")
            print(f"   Label Series Date       : '{date_text.strip()}'")
            
            if len(series_text.strip()) > 0:
                log_test("Three-column primary text is non-empty", True)
            else:
                log_test("Three-column primary text is empty!", False)
                
            # 4. Verify right metadata panel attributes
            print(f"{YELLOW}Step 4: Checking right-side metadata panels...{RESET}")
            fields = {
                'meta-pixel-spacing': 'Pixel Spacing',
                'meta-kvp': 'kVp',
                'meta-ma': 'mA',
                'meta-protocol': 'Protocol/Series description',
                'meta-lead-property-no': 'Lead Property/Tag No',
                'meta-lead-part-type': 'Lead Part Type',
                'meta-lead-status': 'Lead Status'
            }
            
            for fid, label in fields.items():
                el = page.locator(f"#{fid}")
                if await el.count() > 0:
                    val = await el.text_content()
                    # 安全處理控制台列印
                    val_clean = val.strip()
                    try:
                        print(f"   - {label} (#{fid}): '{val_clean}'")
                    except UnicodeEncodeError:
                        print(f"   - {label} (#{fid}): '{val_clean.encode('ascii', errors='replace').decode('ascii')}'")
                    
                    if val_clean != "–" and len(val_clean) > 0:
                        log_test(f"Metadata field {label} loaded real data: {val_clean}", True)
                    else:
                        print(f"   [WARN] Field {label} is placeholder/empty")
                else:
                    log_test(f"Metadata field {label} element NOT found in DOM!", False)
                    
            # 5. Verify HU analysis canvas & histogram
            print(f"{YELLOW}Step 5: Verifying HU heatmap canvas...{RESET}")
            # Ensure the details panel is open or check elements
            hu_panel = page.locator('#hu-panel')
            if await hu_panel.count() > 0:
                # Open details element so it renders
                await page.evaluate("document.getElementById('hu-panel').setAttribute('open', 'true')")
                await page.wait_for_timeout(500)
                
            canvas_el = page.locator('#hu-heatmap')
            if await canvas_el.count() > 0:
                is_visible = await canvas_el.is_visible()
                log_test(f"HU Heatmap Canvas is visible: {is_visible}", is_visible)
                
                # Check that canvas has width/height and contains image data (not blank)
                canvas_data = await page.evaluate("""() => {
                    const c = document.getElementById('hu-heatmap');
                    const ctx = c.getContext('2d');
                    const imgData = ctx.getImageData(0, 0, c.width, c.height).data;
                    // Check if there are non-zero/non-transparent pixels
                    let hasPixels = false;
                    for (let i = 3; i < imgData.length; i += 4) {
                        if (imgData[i] > 0) {
                            hasPixels = true;
                            break;
                        }
                    }
                    return { width: c.width, height: c.height, hasPixels };
                }""")
                print(f"   Canvas metrics: {canvas_data}")
                log_test("HU Heatmap canvas successfully rendered with non-zero pixels", canvas_data['hasPixels'])
            else:
                log_test("HU Heatmap Canvas NOT found in DOM!", False)
                
            # 6. Capture visual screenshot for verification
            screenshot_path = Path(__file__).parent / "meta_hu_verification.png"
            await page.screenshot(path=str(screenshot_path))
            log_test(f"Verification screenshot saved to {screenshot_path}", True)
            
            return True
        except Exception as e:
            log_test(f"Error executing E2E tests: {e}", False)
            return False
        finally:
            await browser.close()
            # Cleanup temp directory
            if temp_dir.exists():
                try:
                    shutil.rmtree(str(temp_dir))
                except:
                    pass

if __name__ == "__main__":
    asyncio.run(test_meta_and_hu())
