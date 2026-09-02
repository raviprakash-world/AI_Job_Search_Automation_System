from contextlib import asynccontextmanager

from playwright.async_api import async_playwright


@asynccontextmanager
async def browser_page():
    """A single headless page for one staging run — opened and torn down per
    call rather than kept as a shared/pooled session, since staging is
    infrequent and isolation matters more than startup cost here."""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            yield page
        finally:
            await browser.close()
