#!/usr/bin/env python3
"""
Comprehensive E2E test:
- Load multiple DICOM images
- Mark with box tool
- Mark with brush tool
- Save annotations
- Navigate between images
- Verify persistence
- Edit annotations
- Re-save and verify
"""
from playwright.sync_api import sync_playwright
import time
import json


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8005", timeout=30000)
        
        print("\n=== STEP 1: Load file list ===")
        page.wait_for_selector(".fi", timeout=15000)
        files = page.locator('.fi').all()
        print(f"Found {len(files)} files in list")
        
        print("\n=== STEP 2: Open first file ===")
        page.click('.fi')
        page.wait_for_function("() => window._app && window._app.viewer && window._app.viewer.imgLoaded === true", timeout=15000)
        first_img_name = page.evaluate("() => window._app._currentPath || 'unknown'")
        print(f"Opened: {first_img_name}")
        
        print("\n=== STEP 3: Mark with BOX tool ===")
        # Use box tool (default)
        page.click('#fab-mode-box')
        page.click('#fab')
        print("Entered mark mode (box)")
        
        # Draw a box (use region known to work from testing)
        canvas = page.locator('#viewer-canvas')
        bbox = canvas.bounding_box()
        x = bbox['x'] + bbox['width']/2
        y = bbox['y'] + bbox['height']/2
        
        # Draw box in region with good features (lower center area)
        page.mouse.move(x - 80, y + 80)
        page.mouse.down()
        page.mouse.move(x + 20, y + 180, steps=6)
        page.mouse.up()
        print("Drew box (in feature-rich region)")
        
        # Wait for segmentation
        page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
        print("Segmentation ready")
        
        # Accept
        page.click('#accept-btn')
        print("Accepted box annotation")
        time.sleep(0.5)
        
        box_count = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"Ann list count after box: {box_count}")
        assert box_count == 1, f"Expected 1 annotation, got {box_count}"
        
        print("\n=== STEP 4: Mark with BRUSH tool ===")
        page.click('#fab-mode-brush')
        page.click('#fab')
        print("Entered mark mode (brush)")
        
        # Draw brush stroke
        page.mouse.move(x + 40, y - 60)
        page.mouse.down()
        page.mouse.move(x + 50, y - 40, steps=5)
        page.mouse.move(x + 60, y - 20, steps=5)
        page.mouse.move(x + 70, y, steps=5)
        page.mouse.up()
        print("Drew brush stroke (large area)")
        
        # Wait for segmentation
        page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
        print("Segmentation ready")
        
        # Accept
        page.click('#accept-btn')
        print("Accepted brush annotation")
        time.sleep(0.5)
        
        brush_count = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"Ann list count after brush: {brush_count}")
        assert brush_count == 2, f"Expected 2 annotations, got {brush_count}"
        
        print("\n=== STEP 5: Save annotations ===")
        page.click('#save-btn')
        time.sleep(1)
        saved_msg = page.evaluate("() => document.getElementById('msg-area')?.textContent || 'no message'")
        print(f"Save message: {saved_msg}")
        
        # Get annotation IDs for later verification
        ann_ids_img1 = page.evaluate("""() => {
            const items = document.querySelectorAll('#ann-list .ann-item');
            return Array.from(items).map(li => li.dataset.id);
        }""")
        print(f"Image 1 annotation IDs: {ann_ids_img1}")
        
        print("\n=== STEP 6: Navigate to second file ===")
        page.click('#next-btn')
        page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
        second_img_name = page.evaluate("() => window._app._currentPath || 'unknown'")
        print(f"Opened: {second_img_name}")
        
        # Verify annotations list is empty for new image
        ann_count_img2_initial = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"Ann list count (image 2, initial): {ann_count_img2_initial}")
        
        print("\n=== STEP 7: Mark image 2 with BRUSH ===")
        page.click('#fab-mode-brush')
        page.click('#fab')
        canvas = page.locator('#viewer-canvas')
        bbox = canvas.bounding_box()
        x2 = bbox['x'] + bbox['width']/2
        y2 = bbox['y'] + bbox['height']/2
        
        page.mouse.move(x2 - 80, y2 - 80)
        page.mouse.down()
        page.mouse.move(x2 - 40, y2 - 40, steps=8)
        page.mouse.move(x2, y2, steps=8)
        page.mouse.up()
        print("Drew brush on image 2 (large area)")
        
        page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
        page.click('#accept-btn')
        time.sleep(0.5)
        
        ann_count_img2 = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"Ann list count (image 2): {ann_count_img2}")
        assert ann_count_img2 == 1, f"Expected 1 annotation on image 2, got {ann_count_img2}"
        
        print("\n=== STEP 8: Save image 2 ===")
        page.click('#save-btn')
        time.sleep(1)
        print("Saved image 2")
        
        print("\n=== STEP 9: Navigate back to image 1 ===")
        page.click('#prev-btn')
        page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
        back_to_img1 = page.evaluate("() => window._app._currentPath || 'unknown'")
        print(f"Navigated back to: {back_to_img1}")
        
        # Verify annotations are restored
        ann_count_back = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"Ann list count (image 1, after returning): {ann_count_back}")
        assert ann_count_back == 2, f"Expected 2 annotations after returning to image 1, got {ann_count_back}"
        
        # Verify same annotation IDs
        ann_ids_back = page.evaluate("""() => {
            const items = document.querySelectorAll('#ann-list .ann-item');
            return Array.from(items).map(li => li.dataset.id);
        }""")
        print(f"Image 1 annotation IDs (after return): {ann_ids_back}")
        assert set(ann_ids_img1) == set(ann_ids_back), f"Annotation IDs mismatch: {ann_ids_img1} vs {ann_ids_back}"
        
        print("\n=== STEP 10: Delete one annotation ===")
        # Click first annotation to select it
        page.click('.ann-item')
        time.sleep(0.2)
        selected_id = page.evaluate("() => window._app.viewer.selectedId")
        print(f"Selected annotation: {selected_id}")
        
        # Click delete button (✕)
        page.click('.ann-del')
        time.sleep(0.5)
        
        ann_count_after_delete = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"Ann list count after delete: {ann_count_after_delete}")
        assert ann_count_after_delete == 1, f"Expected 1 annotation after delete, got {ann_count_after_delete}"
        
        print("\n=== STEP 11: Save again and verify persistence ===")
        page.click('#save-btn')
        time.sleep(1)
        print("Saved after deletion")
        
        # Navigate away and back to verify persistence
        page.click('#next-btn')
        time.sleep(0.5)
        page.click('#prev-btn')
        page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
        
        final_ann_count = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"Final ann list count (after reload): {final_ann_count}")
        assert final_ann_count == 1, f"Expected 1 annotation after persistence check, got {final_ann_count}"
        
        print("\n=== ✅ ALL TESTS PASSED ===")
        print("• Box tool: ✓")
        print("• Brush tool: ✓")
        print("• Save/Load persistence: ✓")
        print("• Multi-image navigation: ✓")
        print("• Edit annotations: ✓")
        
        browser.close()


if __name__ == '__main__':
    run()
