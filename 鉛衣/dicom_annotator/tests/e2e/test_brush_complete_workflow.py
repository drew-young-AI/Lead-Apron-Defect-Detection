#!/usr/bin/env python3
"""
Comprehensive E2E test focusing on brush tool (known to work):
- Load multiple DICOM images
- Mark with brush tool (multiple times)
- Save annotations
- Navigate between images
- Verify persistence
- Edit annotations
- Re-save and verify
"""
from playwright.sync_api import sync_playwright
import time


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8005", timeout=30000)
        
        print("\n=== STEP 1: Load file list ===")
        page.wait_for_selector(".fi", timeout=15000)
        files = page.locator('.fi').all()
        print(f"✓ Found {len(files)} files in list")
        
        print("\n=== STEP 2: Open first file ===")
        first_file = page.locator('.fi').first
        first_file.click()
        page.wait_for_function("() => window._app && window._app.viewer && window._app.viewer.imgLoaded === true", timeout=15000)
        first_img_name = page.evaluate("() => window._app._currentPath || 'unknown'")
        print(f"✓ Opened: {first_img_name}")
        
        print("\n=== STEP 3: Mark with BRUSH tool (first stroke) ===")
        page.click('#fab-mode-brush')
        page.click('#fab')
        print("  Entered brush mark mode")
        
        # Draw brush stroke 1
        canvas = page.locator('#viewer-canvas')
        bbox = canvas.bounding_box()
        x = bbox['x'] + bbox['width']/2
        y = bbox['y'] + bbox['height']/2
        
        page.mouse.move(x - 60, y - 60)
        page.mouse.down()
        page.mouse.move(x - 40, y - 40, steps=4)
        page.mouse.move(x - 20, y - 20, steps=4)
        page.mouse.move(x, y, steps=4)
        page.mouse.up()
        print("  Drew brush stroke 1")
        
        # Wait for segmentation
        page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
        print("  Segmentation completed")
        
        # Accept
        page.click('#accept-btn')
        print("  Accepted annotation 1")
        time.sleep(0.5)
        
        ann_count_1 = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"✓ Annotations in image 1: {ann_count_1}")
        assert ann_count_1 == 1, f"Expected 1 annotation, got {ann_count_1}"
        
        print("\n=== STEP 4: Mark with BRUSH tool (second stroke) ===")
        page.click('#fab-mode-brush')
        page.click('#fab')
        
        # Draw brush stroke 2 (different area)
        page.mouse.move(x + 40, y - 60)
        page.mouse.down()
        page.mouse.move(x + 60, y - 40, steps=4)
        page.mouse.move(x + 80, y - 20, steps=4)
        page.mouse.move(x + 100, y, steps=4)
        page.mouse.up()
        print("  Drew brush stroke 2")
        
        page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
        page.click('#accept-btn')
        print("  Accepted annotation 2")
        time.sleep(0.5)
        
        ann_count_2 = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"✓ Total annotations in image 1: {ann_count_2}")
        assert ann_count_2 == 2, f"Expected 2 annotations, got {ann_count_2}"
        
        print("\n=== STEP 5: Save annotations ===")
        page.click('#save-btn')
        time.sleep(1)
        
        # Get annotation details for verification
        ann_ids_img1 = page.evaluate("""() => {
            const items = document.querySelectorAll('#ann-list .ann-item');
            return Array.from(items).map(li => ({id: li.dataset.id, text: li.textContent}));
        }""")
        print(f"✓ Saved {len(ann_ids_img1)} annotations on image 1")
        for ann in ann_ids_img1:
            print(f"    - {ann['id']}: {ann['text'][:50]}")
        
        print("\n=== STEP 6: Navigate to second file (direct click) ===")
        page.locator('.fi').nth(1).click()
        time.sleep(0.5)  # Wait for click to register
        page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
        time.sleep(0.5)  # Extra wait after imgLoaded
        second_img_name = page.evaluate("() => window._app._currentPath || 'unknown'")
        print(f"✓ Opened: {second_img_name}")
        
        # Verify annotations list for this file
        ann_count_img2_initial = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"  Initial annotations on image 2: {ann_count_img2_initial}")
        ann_baseline_img2 = ann_count_img2_initial
        
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
        print("  Drew brush on image 2")
        
        page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
        page.click('#accept-btn')
        time.sleep(0.5)
        
        ann_count_img2 = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"✓ Annotations on image 2: {ann_count_img2}")
        # Verify we added at least 1 new annotation (might have more if image was pre-saved)
        assert ann_count_img2 > ann_baseline_img2, f"Expected more annotations after marking, had {ann_baseline_img2}, got {ann_count_img2}"
        
        print("\n=== STEP 8: Save image 2 ===")
        page.click('#save-btn')
        time.sleep(1)
        print("✓ Saved image 2 annotations")
        
        print("\n=== STEP 9: Navigate back to image 1 (direct click) ===")
        page.locator('.fi').first.click()
        time.sleep(0.5)  # Wait for click to register
        page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
        time.sleep(0.5)  # Extra wait after imgLoaded for annotations to reload
        back_to_img1 = page.evaluate("() => window._app._currentPath || 'unknown'")
        print(f"✓ Navigated back to: {back_to_img1}")
        
        # Verify annotations are restored
        ann_count_back = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"  Annotations restored: {ann_count_back}")
        assert ann_count_back == 2, f"Expected 2 annotations after returning to image 1, got {ann_count_back}"
        
        # Verify same annotation IDs
        ann_ids_back = page.evaluate("""() => {
            const items = document.querySelectorAll('#ann-list .ann-item');
            return Array.from(items).map(li => li.dataset.id);
        }""")
        original_ids = set(ann['id'] for ann in ann_ids_img1)
        assert set(ann_ids_back) == original_ids, f"Annotation IDs mismatch after reload"
        print(f"✓ Annotation IDs match after reload")
        
        print("\n=== STEP 10: Delete one annotation ===")
        # Click first annotation to select it
        page.click('.ann-item')
        time.sleep(0.2)
        selected_id = page.evaluate("() => window._app.viewer.selectedId")
        print(f"  Selected: {selected_id}")
        
        # Click delete button (✕)
        page.click('.ann-del')
        time.sleep(0.5)
        
        ann_count_after_delete = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"✓ Annotations after delete: {ann_count_after_delete}")
        assert ann_count_after_delete == 1, f"Expected 1 annotation after delete, got {ann_count_after_delete}"
        
        print("\n=== STEP 11: Save after deletion ===")
        page.click('#save-btn')
        time.sleep(1)
        print("✓ Saved after deletion")
        
        print("\n=== STEP 12: Navigate and verify persistence ===")
        page.locator('.fi').nth(1).click()
        time.sleep(0.5)
        page.locator('.fi').first.click()
        page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
        
        final_ann_count = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
        print(f"✓ Final annotation count: {final_ann_count}")
        assert final_ann_count == 1, f"Expected 1 annotation after persistence check, got {final_ann_count}"
        
        print("\n" + "="*60)
        print("✅ ALL E2E TESTS PASSED")
        print("="*60)
        print("✓ Brush tool: mark annotations on multiple strokes")
        print("✓ Persistence: save/load across navigation")
        print("✓ Multi-image: switch between images, annotations isolated")
        print("✓ Edit: delete annotations and re-save")
        print("✓ List rendering: correct count and IDs")
        
        browser.close()


if __name__ == '__main__':
    run()
