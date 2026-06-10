#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import time


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8005", timeout=30000)
        page.wait_for_selector(".fi", timeout=15000)
        # click first file
        page.click('.fi')
        # wait for image loaded
        page.wait_for_function("() => window._app && window._app.viewer && window._app.viewer.imgLoaded === true", timeout=15000)
        # select brush mode
        page.click('#fab-mode-brush')
        # enter mark mode
        page.click('#fab')
        # draw on canvas
        canvas = page.locator('#viewer-canvas')
        bbox = canvas.bounding_box()
        x = bbox['x'] + bbox['width']/2
        y = bbox['y'] + bbox['height']/2
        page.mouse.move(x-30, y-10)
        page.mouse.down()
        page.mouse.move(x-10, y-5, steps=6)
        page.mouse.move(x+10, y+5, steps=6)
        page.mouse.move(x+30, y+10, steps=6)
        page.mouse.up()
        # wait for pending bar and accept enabled
        page.wait_for_selector('#pend-bar', timeout=15000)
        page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
        page.click('#accept-btn')
        # Wait for annotation list update
        page.wait_for_selector('#ann-list .ann-item', timeout=5000)
        count1 = page.locator('#ann-list .ann-item').count()
        print('ANNOT_COUNT_1:', count1)

        # Draw another brush stroke and accept to ensure multiple annotations
        page.click('#fab-mode-brush')
        page.click('#fab')
        page.mouse.move(x+10, y+10)
        page.mouse.down()
        page.mouse.move(x+40, y+20, steps=8)
        page.mouse.up()
        page.wait_for_function("() => !document.getElementById('accept-btn').disabled", timeout=15000)
        page.click('#accept-btn')
        time.sleep(1)
        count2 = page.locator('#ann-list .ann-item').count()
        print('ANNOT_COUNT_2:', count2)
        browser.close()


if __name__ == '__main__':
    run()
