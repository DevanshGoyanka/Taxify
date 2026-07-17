import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        print("Navigating...")
        await page.goto("https://eportal.incometax.gov.in/iec/foservices/#/login", wait_until="domcontentloaded", timeout=90000)
        print("Loaded:", page.url)
        await asyncio.sleep(10)
        await context.close()
        await browser.close()

asyncio.run(main())
