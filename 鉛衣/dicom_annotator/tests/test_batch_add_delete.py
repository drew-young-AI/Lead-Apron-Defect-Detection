#!/usr/bin/env python3
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('http://localhost:8005', wait_until='networkidle')
        await page.wait_for_timeout(1000)

        # Open settings drawer and then folder loader
        await page.evaluate('App.openDrawer("settings")')
        await page.wait_for_selector('#drawer-body')
        await page.click('#d-folder')
        await page.wait_for_selector('#d-root')

        root = '/Users/drew/ENV/lead_protection/dicom_annotator/backend/uploads'
        await page.fill('#d-root', root)
        await page.click('#d-load-root')

        # Wait for UI to update
        await page.wait_for_timeout(2000)
        files_count = await page.locator('.fi').count()
        print('files_count=', files_count)
        if files_count > 0:
            print('Batch add via folder loader: OK')
        else:
            print('Batch add via folder loader: FAILED')
            await browser.close()
            return

        # Multi-select first 2 files and test delete-selected button visibility
        if files_count >= 2:
            first = page.locator('.fi').first
            second = page.locator('.fi').nth(1)
            # Use Ctrl to multi-select both entries
            # On macOS use Meta (Command) for multi-select; on others Control may work
            await first.click(modifiers=['Meta'])
            await second.click(modifiers=['Meta'])
            await page.wait_for_timeout(200)
            visible = await page.eval_on_selector('#delete-selected-btn', 'el => getComputedStyle(el).display !== "none"')
            sel_list = await page.evaluate('Array.from(App._selectedFiles || [])')
            print('selected_files=', sel_list)
            print('delete_selected_btn_visible=', visible)

            # Intercept any confirm dialog and dismiss (to avoid deleting files)
            page.on('dialog', lambda dialog: asyncio.create_task(dialog.dismiss()))

            # Press Shift+Delete to trigger batch delete; confirm will be dismissed
            await page.keyboard.down('Shift')
            await page.keyboard.press('Delete')
            await page.keyboard.up('Shift')
            await page.wait_for_timeout(500)
            print('Shift+Delete pressed (confirm dismissed)')

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
