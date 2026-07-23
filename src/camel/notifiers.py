"""Notifiers — ping the human when a handoff (2FA/CAPTCHA/login) is waiting.

Product principle: the ONLY APIs camel ever touches are LLM APIs (the brain).
Every other system — including WhatsApp — is driven through its real UI, never
through a service API. So notifications go out exactly the way a human would send
them: by automating WhatsApp Web in a browser.

  ConsoleNotifier      print to terminal (default, zero deps)
  WhatsAppWebNotifier  automate web.whatsapp.com in your own browser — no API

Both satisfy the `Notifier` protocol used by handoff.py.
"""

from __future__ import annotations

from typing import Any


class ConsoleNotifier:
    async def notify(self, message: str) -> None:
        print(f"\n🔔 ACTION NEEDED: {message}\n", flush=True)


class WhatsAppWebNotifier:
    """No API — on-thesis. Uses a PERSISTENT Playwright profile logged into
    WhatsApp Web (scan the QR once; the session persists in `user_data_dir`).
    This is UI automation, same as everything else camel does: it opens the
    chat, types the message, and hits Enter, exactly like a person would.

    Note: WhatsApp discourages automation, so keep this to your own alerts."""

    def __init__(self, to_contact: str, user_data_dir: str = ".wa_profile",
                 headless: bool = False) -> None:
        self.to_contact = to_contact
        self.user_data_dir = user_data_dir
        self.headless = headless

    async def notify(self, message: str) -> None:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            ctx = await pw.chromium.launch_persistent_context(
                self.user_data_dir, headless=self.headless)
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
            # If the search box isn't present, we're not logged in yet.
            search = 'div[contenteditable="true"][data-tab="3"]'
            try:
                await page.wait_for_selector(search, timeout=20000)
            except Exception as e:
                await ctx.close()
                raise RuntimeError(
                    "WhatsApp Web not logged in. Run once headful and scan the QR "
                    f"to populate {self.user_data_dir!r}.") from e
            await page.click(search)
            await page.fill(search, self.to_contact)
            await page.wait_for_timeout(1500)
            await page.keyboard.press("Enter")  # open first match
            box = 'div[contenteditable="true"][data-tab="10"]'
            await page.wait_for_selector(box, timeout=10000)
            await page.click(box)
            await page.type(box, message)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(800)
            await ctx.close()


def from_env() -> Any:
    """Build a notifier from environment variables, else ConsoleNotifier.

    CAMEL_NOTIFY = console | whatsapp_web
      whatsapp_web reads CAMEL_WA_CONTACT (+ optional CAMEL_WA_PROFILE)
    """
    import os
    kind = os.environ.get("CAMEL_NOTIFY", "console").lower()
    if kind == "whatsapp_web":
        return WhatsAppWebNotifier(
            os.environ["CAMEL_WA_CONTACT"],
            os.environ.get("CAMEL_WA_PROFILE", ".wa_profile"))
    return ConsoleNotifier()
