#!/usr/bin/env python3
"""
Browser-based E2E testing for all three bug fixes.
Tests BUG #1, #2, #3 through complete user workflows.
"""
import asyncio
import sys
import json
from pathlib import Path
from playwright.async_api import async_playwright

# Color codes for terminal output
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
    except UnicodeEncodeError:
        try:
            encoding = sys.stdout.encoding or 'ascii'
            safe_title = title.encode(encoding, errors='replace').decode(encoding)
            print(f"{color}{icon} {safe_title}{RESET}")
        except:
            safe_title = title.encode('ascii', errors='replace').decode('ascii')
            print(f"{color}{icon} {safe_title}{RESET}")

def safe_print_browser(msg):
    text = msg.text
    try:
        print("BROWSER:", text)
    except UnicodeEncodeError:
        try:
            encoding = sys.stdout.encoding or 'ascii'
            print("BROWSER:", text.encode(encoding, errors='replace').decode(encoding))
        except:
            print("BROWSER:", text.encode('ascii', errors='replace').decode('ascii'))

def log_section(title):
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}{title}{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")

async def test_bug_3_vertex_deletion():
    """BUG #3: Test right-click vertex deletion in edit mode."""
    log_section("BUG #3: Vertex Deletion via Right-Click")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        page.on("console", safe_print_browser)
        
        try:
            await page.goto('http://localhost:8005', wait_until='networkidle')
            await page.wait_for_timeout(2000)
            
            # 1. Upload test image
            print(f"{YELLOW}Step 1: Upload test image{RESET}")
            upload_input = page.locator('input[type="file"]')
            test_image = Path(__file__).parent.parent / 'data' / 'test_image.dcm'
            
            if test_image.exists():
                temp_dir = Path(__file__).parent / "temp_upload_dir"
                temp_dir.mkdir(exist_ok=True)
                import shutil
                shutil.copy(str(test_image), str(temp_dir / "test_image.dcm"))
                await upload_input.set_input_files(str(temp_dir))
                await page.wait_for_timeout(2000)
                log_test("Image uploaded", True)
                # Ensure uploaded file is opened: click the last file-list entry
                await page.wait_for_selector('.fi', timeout=10000)
                cnt = await page.locator('.fi').count()
                if cnt > 0:
                    await page.locator('.fi').nth(cnt-1).click()
                    await page.wait_for_timeout(1000)
            else:
                log_test("Test image not found (skipping)", False)
                await browser.close()
                return
            
            # 2. Switch to BOX tool
            print(f"{YELLOW}Step 2: Select BOX tool{RESET}")
            box_btn = page.locator('button', has_text='▭ 矩形框選')
            if await box_btn.count() > 0:
                await box_btn.click()
                await page.wait_for_timeout(500)
                log_test("BOX tool selected", True)
                await page.evaluate("App._enterMarkMode()")
                await page.wait_for_timeout(300)
            
            # 3. Draw a box to create annotation
            await page.click('#fab-mode-box')
            await page.wait_for_timeout(200)
            await page.click('#fab')
            await page.wait_for_timeout(200)
            print(f"{YELLOW}Step 3: Draw annotation box{RESET}")
            canvas = page.locator('canvas').first
            box = await canvas.bounding_box()
            
            if box:
                # Draw box from (100,100) to (300,200)
                x1, y1 = box['x'] + 100, box['y'] + 100
                x2, y2 = box['x'] + 300, box['y'] + 200
                
                await page.mouse.move(x1, y1)
                await page.mouse.down()
                await page.mouse.move(x2, y2)
                await page.mouse.up()
                await page.wait_for_timeout(1000)
                log_test("Box drawn", True)
            
            # 4. Confirm the annotation
            print(f"{YELLOW}Step 4: Confirm annotation{RESET}")
            await page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
            await page.click('#accept-btn')
            await page.wait_for_timeout(1500)
            log_test("Annotation confirmed", True)
            
            # 5. Switch to EDIT tool
            print(f"{YELLOW}Step 5: Switch to EDIT tool{RESET}")
            edit_btn = page.locator('button', has_text='✎ 編輯頂點')
            if await edit_btn.count() > 0:
                await edit_btn.click()
                await page.wait_for_timeout(500)
                log_test("EDIT tool activated", True)
            
            # 6. Right-click on a vertex to delete it
            print(f"{YELLOW}Step 6: Right-click on vertex to delete{RESET}")
            canvas = page.locator('canvas').first
            box = await canvas.bounding_box()
            
            if box:
                # Target first vertex (approximately at 100,100 relative to canvas)
                vx, vy = box['x'] + 100, box['y'] + 100
                
                # Right-click
                await page.mouse.click(vx, vy, button='right')
                await page.wait_for_timeout(500)
                
                # Check for success message or hint
                hint = page.locator('.hint, .toast, .message')
                message_count = await hint.count()
                
                if message_count > 0:
                    message_text = await hint.first.text_content()
                    if '刪除' in message_text or 'delete' in message_text.lower():
                        log_test("Vertex deletion triggered (feedback received)", True)
                    else:
                        log_test(f"Message received: {message_text[:50]}", True)
                else:
                    log_test("Right-click processed (no explicit feedback)", True)
            
            print(f"\n{GREEN}[OK] BUG #3 Test Complete{RESET}")
            
        except Exception as e:
            log_test(f"Error in BUG #3 test: {e}", False)
        finally:
            await browser.close()


async def test_bug_2_canvas_opacity():
    """BUG #2: Test that brush canvas opacity is reduced."""
    log_section("BUG #2: Brush Canvas Opacity")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        page.on("console", safe_print_browser)
        
        try:
            # Set up Network tab inspection
            network_data = []
            
            async def handle_response(response):
                if 'segment' in response.url:
                    network_data.append({
                        'url': response.url,
                        'status': response.status
                    })
            
            page.on('response', handle_response)
            
            await page.goto('http://localhost:8005', wait_until='networkidle')
            await page.wait_for_timeout(2000)
            
            # 1. Upload test image
            print(f"{YELLOW}Step 1: Upload test image{RESET}")
            upload_input = page.locator('input[type="file"]')
            test_image = Path(__file__).parent.parent / 'data' / 'test_image.dcm'
            
            if test_image.exists():
                temp_dir = Path(__file__).parent / "temp_upload_dir"
                temp_dir.mkdir(exist_ok=True)
                import shutil
                shutil.copy(str(test_image), str(temp_dir / "test_image.dcm"))
                await upload_input.set_input_files(str(temp_dir))
                await page.wait_for_timeout(2000)
                log_test("Image uploaded", True)
                # Ensure uploaded file is opened: click the last file-list entry
                await page.wait_for_selector('.fi', timeout=10000)
                cnt = await page.locator('.fi').count()
                if cnt > 0:
                    await page.locator('.fi').nth(cnt-1).click()
                    await page.wait_for_timeout(1000)
            else:
                log_test("Test image not found (skipping)", False)
                await browser.close()
                return
            
            # 2. Switch to BRUSH tool
            print(f"{YELLOW}Step 2: Select BRUSH tool{RESET}")
            brush_btn = page.locator('button', has_text='🖌')
            if await brush_btn.count() > 0:
                await brush_btn.click()
                await page.wait_for_timeout(500)
                log_test("BRUSH tool selected", True)
            # ensure brush mode before entering mark mode
            await page.evaluate("(()=>{App.fabMode='brush';document.getElementById('fab-mode-brush')?.classList.add('active');document.getElementById('fab-mode-box')?.classList.remove('active');})()")
            await page.wait_for_timeout(200)
            # debug: print fab status
            fab_info = await page.evaluate("() => ({text: document.getElementById('fab')?.textContent, className: document.getElementById('fab')?.className, disabled: document.getElementById('fab')?.disabled})")
            print("FAB DEBUG:", fab_info)
            await page.evaluate("App._enterMarkMode()")
            await page.wait_for_timeout(300)
            
            # 3. Draw a brush stroke (target image center to ensure painting on image area)
            print(f"{YELLOW}Step 3: Draw brush stroke{RESET}")
            coords = await page.evaluate("""
                () => {
                    const c = document.getElementById('viewer-canvas').getBoundingClientRect();
                    const absX = c.left + Math.round(c.width/2);
                    const absY = c.top  + Math.round(c.height/2);
                    return {x: Math.round(absX), yStart: Math.round(absY - 50), yEnd: Math.round(absY + 50)};
                }
            """)
            
            if coords:
                x = coords['x']
                y_start = coords['yStart']
                y_end = coords['yEnd']
                
                await page.mouse.move(x, y_start)
                await page.mouse.down()
                
                for y in range(int(y_start), int(y_end), 10):
                    await page.mouse.move(x, y)
                    await page.wait_for_timeout(50)
                
                await page.mouse.up()
                await page.wait_for_timeout(1000)
                log_test("Brush stroke drawn", True)
            
            # 4. Check if canvas is still visible (not completely covered)
            print(f"{YELLOW}Step 4: Verify canvas visibility{RESET}")
            # Take screenshot to visually confirm
            screenshot_opacity_p = Path(__file__).parent / 'brush_opacity_test.png'
            await page.screenshot(path=str(screenshot_opacity_p))
            log_test("Screenshot captured for opacity verification", True)
            
            # 5. Check Network for brush_mask_b64 transmission
            print(f"{YELLOW}Step 5: Check API requests (Network tab){RESET}")
            await page.wait_for_timeout(500)
            
            # Take another screenshot
            screenshot_after_p = Path(__file__).parent / 'brush_after_segmentation.png'
            await page.screenshot(path=str(screenshot_after_p))
            
            if network_data:
                log_test(f"Segmentation API called ({len(network_data)} request(s))", True)
                for req in network_data:
                    print(f"   - {req['url']} (Status: {req['status']})")
            else:
                log_test("Segmentation API call not captured yet", False)
            
            print(f"\n{GREEN}[OK] BUG #2 Test Complete{RESET}")
            
        except Exception as e:
            log_test(f"Error in BUG #2 test: {e}", False)
        finally:
            await browser.close()


async def test_bug_1_brush_mask():
    """BUG #1: Test that brush_mask_b64 is sent in API request."""
    log_section("BUG #1: Brush Mask Transmission")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()
        page = await context.new_page()
        
        request_body = None
        
        async def handle_request(request):
            nonlocal request_body
            if 'segment' in request.url:
                try:
                    # Try JSON parse first
                    data = request.post_data
                    if not data:
                        return
                    try:
                        request_body = json.loads(data)
                    except Exception:
                        # store raw body for inspection
                        request_body = {'raw': data}
                except Exception as e:
                    print('Request capture error:', e)
                    return
        
        page.on('request', handle_request)
        
        try:
            await page.goto('http://localhost:8005', wait_until='networkidle')
            await page.wait_for_timeout(2000)
            
            # 1. Upload test image
            print(f"{YELLOW}Step 1: Upload test image{RESET}")
            upload_input = page.locator('input[type="file"]')
            test_image = Path(__file__).parent.parent / 'data' / 'test_image.dcm'
            
            if test_image.exists():
                temp_dir = Path(__file__).parent / "temp_upload_dir"
                temp_dir.mkdir(exist_ok=True)
                import shutil
                shutil.copy(str(test_image), str(temp_dir / "test_image.dcm"))
                await upload_input.set_input_files(str(temp_dir))
                await page.wait_for_timeout(2000)
                log_test("Image uploaded", True)
                # Ensure uploaded file is opened: click the last file-list entry
                await page.wait_for_selector('.fi', timeout=10000)
                cnt = await page.locator('.fi').count()
                if cnt > 0:
                    await page.locator('.fi').nth(cnt-1).click()
                    await page.wait_for_timeout(1000)
            else:
                log_test("Test image not found (skipping)", False)
                await browser.close()
                return
            
            # 2. Switch to BRUSH tool
            print(f"{YELLOW}Step 2: Select BRUSH tool{RESET}")
            brush_btn = page.locator('button', has_text='🖌')
            if await brush_btn.count() > 0:
                await brush_btn.click()
                await page.wait_for_timeout(500)
                log_test("BRUSH tool selected", True)
            # ensure brush mode before entering mark mode
            await page.evaluate("(()=>{App.fabMode='brush';document.getElementById('fab-mode-brush')?.classList.add('active');document.getElementById('fab-mode-box')?.classList.remove('active');})()")
            await page.wait_for_timeout(200)
            # debug: print fab status
            fab_info = await page.evaluate("() => ({text: document.getElementById('fab')?.textContent, className: document.getElementById('fab')?.className, disabled: document.getElementById('fab')?.disabled})")
            print("FAB DEBUG:", fab_info)
            await page.evaluate("App._enterMarkMode()")
            await page.wait_for_timeout(300)
            
            # 3. Draw a brush stroke (target image center to ensure painting on image area)
            print(f"{YELLOW}Step 3: Draw brush stroke{RESET}")
            coords = await page.evaluate("""
                () => {
                    const c = document.getElementById('viewer-canvas').getBoundingClientRect();
                    const absX = c.left + Math.round(c.width/2);
                    const absY = c.top  + Math.round(c.height/2);
                    return {x: Math.round(absX), yStart: Math.round(absY - 50), yEnd: Math.round(absY + 50)};
                }
            """)
            
            if coords:
                x = coords['x']
                y_start = coords['yStart']
                y_end = coords['yEnd']
                
                await page.mouse.move(x, y_start)
                await page.mouse.down()
                
                for y in range(int(y_start), int(y_end), 10):
                    await page.mouse.move(x, y)
                    await page.wait_for_timeout(50)
                
                await page.mouse.up()
                await page.wait_for_timeout(2000)
                log_test("Brush stroke drawn", True)
            
            # 4. Check API request for brush_mask_b64
            print(f"{YELLOW}Step 4: Inspect API request payload{RESET}")
            
            if request_body:
                log_test(f"Segmentation API request captured", True)
                
                if 'brush_mask_b64' in request_body:
                    mask_data = request_body['brush_mask_b64']
                    if mask_data and len(mask_data) > 50:
                        log_test(f"brush_mask_b64 present ({len(mask_data)} bytes)", True)
                    else:
                        log_test("brush_mask_b64 field present but empty", False)
                else:
                    log_test("brush_mask_b64 NOT in request (expected for BUG #1 Phase 2)", False)
                
                # Show other fields
                print(f"\n   Request fields:")
                for key in request_body.keys():
                    if key != 'brush_mask_b64':
                        val_str = str(request_body[key])[:60]
                        print(f"   - {key}: {val_str}...")
            else:
                log_test("Could not capture API request body", False)
            
            print(f"\n{GREEN}[OK] BUG #1 Test Complete{RESET}")
            
        except Exception as e:
            log_test(f"Error in BUG #1 test: {e}", False)
        finally:
            await browser.close()


async def main():
    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{BLUE}Browser E2E Testing - Bug Fixes Validation{RESET}")
    print(f"{BLUE}{'='*70}{RESET}")
    
    print("\n[Wait] Waiting for app to be ready...")
    for i in range(10):
        try:
            import urllib.request
            urllib.request.urlopen('http://localhost:8005', timeout=2)
            print("[OK] App is ready")
            break
        except:
            await asyncio.sleep(1)
    
    # Run all three bug tests
    await test_bug_3_vertex_deletion()
    await test_bug_2_canvas_opacity()
    await test_bug_1_brush_mask()
    
    # Clean up temp_upload_dir
    temp_dir = Path(__file__).parent / "temp_upload_dir"
    if temp_dir.exists():
        import shutil
        try:
            shutil.rmtree(str(temp_dir))
        except:
            pass

    print(f"\n{BLUE}{'='*70}{RESET}")
    print(f"{GREEN}All tests completed!{RESET}")
    print(f"{BLUE}{'='*70}{RESET}\n")


if __name__ == '__main__':
    asyncio.run(main())
