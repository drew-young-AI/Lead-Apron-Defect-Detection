#!/usr/bin/env python3
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        page.on('console', lambda msg: print('BROWSER:', msg.text))
        await page.goto('http://localhost:8005', wait_until='networkidle')
        await page.wait_for_timeout(1000)

        # ensure there's at least one file in list
        await page.wait_for_selector('.fi', timeout=10000)
        cnt = await page.locator('.fi').count()
        if cnt == 0:
            print('No files to test'); await browser.close(); return

        # open first file
        await page.locator('.fi').first.click()
        await page.wait_for_timeout(500)

        # Instead of relying on segmentation, add an annotation programmatically (box)
        await page.evaluate('''() => {
            const c = document.getElementById('viewer-canvas').getBoundingClientRect();
            const x = Math.round(c.width * 0.25);
            const y = Math.round(c.height * 0.25);
            const w = Math.round(c.width * 0.35);
            const h = Math.round(c.height * 0.3);
            // Convert to image coords
            const imgTL = App.viewer.screenToImage(x, y);
            const imgBR = App.viewer.screenToImage(x + w, y + h);
            App.annMgr.add({ type: 'box', x: Math.round(imgTL.x), y: Math.round(imgTL.y), w: Math.round(imgBR.x - imgTL.x), h: Math.round(imgBR.y - imgTL.y), class: 'defect' });
        }''')
        await page.wait_for_timeout(300)

        # save
        await page.click('#save-btn')
        await page.wait_for_timeout(1000)

        # reload same file (click again)
        await page.locator('.fi').first.click()
        await page.wait_for_timeout(800)

        # ensure annotation present
        ann_count = await page.eval_on_selector('#ann-count', 'el => el.textContent')
        print('ann_count_text=', ann_count)

        # enter edit mode
        await page.keyboard.press('e')
        await page.wait_for_timeout(300)

        # read annotation bbox from App
        ann = await page.evaluate('() => (App.annMgr.list && App.annMgr.list[0]) || null')
        print('ann_before=', ann)
        if not ann:
            print('No annotation found after reload'); await browser.close(); return

        # compute screen pos for annotation center to perform move
        coords = await page.evaluate('() => App.viewer.imageToScreen(App.annMgr.list[0].x + App.annMgr.list[0].w/2, App.annMgr.list[0].y + App.annMgr.list[0].h/2)')
        print('screen coords (center)', coords)
        sx = coords['x']; sy = coords['y']

        # drag annotation slightly (move)
        await page.mouse.move(sx, sy); await page.mouse.down(); await page.mouse.move(sx+40, sy+20); await page.mouse.up()
        await page.wait_for_timeout(400)

        # read annotation updated coords
        ann_after = await page.evaluate('() => (App.annMgr.list && App.annMgr.list[0]) || null')
        print('ann_after=', ann_after)

        moved = ann_after and (ann_after['x'] != ann['x'] or ann_after['y'] != ann['y'])
        print('moved=', moved)

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
