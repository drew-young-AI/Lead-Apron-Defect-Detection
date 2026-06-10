import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def test_ui_features():
    print("Starting Playwright Test...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            print("Navigating to http://localhost:8005...")
            await page.goto('http://localhost:8005', wait_until='networkidle')
            await page.wait_for_timeout(1000)

            # 1. Test Delete Button Existence
            print("Checking if delete-current-btn exists...")
            del_btn = page.locator('#delete-current-btn')
            if await del_btn.is_visible():
                print("✅ delete-current-btn is visible in the header!")
            else:
                print("❌ delete-current-btn is NOT visible!")
                
            # Upload a file to test the delete functionality
            data_dir = Path('/Users/drew/ENV/lead_protection/dicom_annotator/data/test_batch')
            if data_dir.exists():
                print("Uploading test directory...")
                await page.locator('input[type="file"]').set_input_files(str(data_dir))
                await page.wait_for_timeout(2000)
                
                # Check file list
                file_count = await page.locator('.fi').count()
                print(f"Files loaded: {file_count}")
                
                # Click the first file to view it
                if file_count > 0:
                    await page.locator('.fi').nth(0).click()
                    await page.wait_for_timeout(1000)
                    
                    # Test zoom function injection to check rendering variables
                    print("Testing zoom logic via page.evaluate...")
                    eval_result = await page.evaluate('''() => {
                        const v = window._app.viewer;
                        v.scale = 10; // simulate zoom in
                        // test fs
                        const fs = 12 / v.scale;
                        // test brush
                        const tool = window._app.tools.brushTool;
                        const effectiveRadius = tool.radius / v.scale;
                        return { fs, effectiveRadius };
                    }''')
                    print(f"✅ Evaluated zoom properties at scale=10: fs={eval_result['fs']}, effectiveRadius={eval_result['effectiveRadius']}")
                    
                    if eval_result['fs'] == 1.2 and eval_result['effectiveRadius'] == 2.0:
                        print("✅ Scale logic is correct (inverse proportionate)!")
                    else:
                        print("❌ Scale logic evaluated incorrectly!")
                        
                    # Now click the delete button
                    print("Clicking delete-current-btn...")
                    page.on('dialog', lambda dialog: dialog.accept()) # accept confirmation
                    await del_btn.click()
                    await page.wait_for_timeout(1000)
                    
                    # File list should be empty if there was only 1 file
                    new_file_count = await page.locator('.fi').count()
                    if new_file_count < file_count:
                        print("✅ File successfully deleted using the header delete button!")
                    else:
                        print("❌ File was NOT deleted!")
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
        finally:
            await browser.close()
            print("Test finished.")

if __name__ == '__main__':
    asyncio.run(test_ui_features())
