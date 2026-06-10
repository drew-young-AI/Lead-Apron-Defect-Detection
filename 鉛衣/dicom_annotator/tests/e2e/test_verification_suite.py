#!/usr/bin/env python3
"""
Final E2E verification suite - runs all critical test scenarios
"""
from playwright.sync_api import sync_playwright
import sys
import time

results = {
    'passed': 0,
    'failed': 0,
    'tests': []
}

def test_brush_single_stroke():
    """Test: Single brush stroke → segmentation → accept"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto('http://127.0.0.1:8005', timeout=30000)
            page.wait_for_selector('.fi', timeout=15000)
            page.click('.fi')
            page.wait_for_function("() => window._app && window._app.viewer && window._app.viewer.imgLoaded === true", timeout=15000)
            
            # Brush stroke
            page.click('#fab-mode-brush')
            page.click('#fab')
            canvas = page.locator('#viewer-canvas')
            bbox = canvas.bounding_box()
            x = bbox['x'] + bbox['width']/2
            y = bbox['y'] + bbox['height']/2
            page.mouse.move(x-50, y-50)
            page.mouse.down()
            page.mouse.move(x+50, y+50, steps=10)
            page.mouse.up()
            
            page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
            page.click('#accept-btn')
            time.sleep(0.5)
            
            count = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
            browser.close()
            
            assert count == 1, f"Expected 1 annotation, got {count}"
            return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def test_multiple_strokes():
    """Test: Multiple brush strokes on same image"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto('http://127.0.0.1:8005', timeout=30000)
            page.wait_for_selector('.fi', timeout=15000)
            page.click('.fi')
            page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
            
            for i in range(3):
                page.click('#fab-mode-brush')
                page.click('#fab')
                canvas = page.locator('#viewer-canvas')
                bbox = canvas.bounding_box()
                x = bbox['x'] + bbox['width']/2
                y = bbox['y'] + bbox['height']/2
                x_offset = x - 60 + (i * 50)
                page.mouse.move(x_offset, y-60)
                page.mouse.down()
                page.mouse.move(x_offset+60, y+60, steps=8)
                page.mouse.up()
                page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
                page.click('#accept-btn')
                time.sleep(0.3)
            
            count = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
            browser.close()
            
            assert count == 3, f"Expected 3 annotations, got {count}"
            return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def test_save_and_reload():
    """Test: Save annotations and reload"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto('http://127.0.0.1:8005', timeout=30000)
            page.wait_for_selector('.fi', timeout=15000)
            page.click('.fi')
            page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
            
            # Mark and save
            page.click('#fab-mode-brush')
            page.click('#fab')
            canvas = page.locator('#viewer-canvas')
            bbox = canvas.bounding_box()
            x = bbox['x'] + bbox['width']/2
            y = bbox['y'] + bbox['height']/2
            page.mouse.move(x-50, y-50)
            page.mouse.down()
            page.mouse.move(x+50, y+50, steps=10)
            page.mouse.up()
            page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
            page.click('#accept-btn')
            time.sleep(0.3)
            page.click('#save-btn')
            time.sleep(1)
            
            count_before = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
            
            # Navigate and come back
            page.locator('.fi').nth(1).click()
            time.sleep(0.5)
            page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
            time.sleep(0.5)
            
            page.locator('.fi').first.click()
            time.sleep(0.5)
            page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
            time.sleep(0.5)
            
            count_after = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
            browser.close()
            
            assert count_before == count_after, f"Counts mismatch: {count_before} vs {count_after}"
            assert count_after == 1, f"Expected 1 annotation after reload, got {count_after}"
            return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def test_delete_annotation():
    """Test: Delete annotation and verify UI update"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto('http://127.0.0.1:8005', timeout=30000)
            page.wait_for_selector('.fi', timeout=15000)
            page.click('.fi')
            page.wait_for_function("() => window._app.viewer.imgLoaded === true", timeout=15000)
            
            # Mark 2x
            for i in range(2):
                page.click('#fab-mode-brush')
                page.click('#fab')
                canvas = page.locator('#viewer-canvas')
                bbox = canvas.bounding_box()
                x = bbox['x'] + bbox['width']/2
                y = bbox['y'] + bbox['height']/2
                x_start = x - 50 + (i * 80)
                page.mouse.move(x_start, y-50)
                page.mouse.down()
                page.mouse.move(x_start+50, y+50, steps=10)
                page.mouse.up()
                page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
                page.click('#accept-btn')
                time.sleep(0.3)
            
            count_before = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
            
            # Delete first
            page.click('.ann-item')
            time.sleep(0.2)
            page.click('.ann-del')
            time.sleep(0.5)
            
            count_after = page.evaluate("() => document.querySelectorAll('#ann-list .ann-item').length")
            browser.close()
            
            # We added 2 new annotations in this test
            # count_before should be at least 2, count_after should be 1 less
            assert count_before >= 2, f"Expected at least 2 annotations before delete, got {count_before}"
            assert count_after == count_before - 1, f"Expected count to decrease by 1, got {count_before} → {count_after}"
            return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

# Run all tests
tests = [
    ("Single brush stroke", test_brush_single_stroke),
    ("Multiple strokes", test_multiple_strokes),
    ("Save and reload", test_save_and_reload),
    ("Delete annotation", test_delete_annotation),
]

print("\n" + "="*60)
print("E2E VERIFICATION SUITE")
print("="*60)

for name, test_func in tests:
    print(f"\n▶ {name}...", end=" ")
    if test_func():
        print("✓ PASSED")
        results['passed'] += 1
        results['tests'].append((name, 'PASSED'))
    else:
        print("✗ FAILED")
        results['failed'] += 1
        results['tests'].append((name, 'FAILED'))

print("\n" + "="*60)
print(f"RESULTS: {results['passed']}/{len(tests)} passed")
print("="*60)
for name, status in results['tests']:
    symbol = "✓" if status == "PASSED" else "✗"
    print(f"{symbol} {name}: {status}")

sys.exit(0 if results['failed'] == 0 else 1)
