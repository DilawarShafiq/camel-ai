"""WhatsApp chat interface — talk to Camel AI from your phone. EXPERIMENTAL.

Flow (OpenClaw-style):
  camel whatsapp connect   -> opens WhatsApp Web, you scan the QR once (session
                              persists in ~/.camel/wa-profile).
  camel whatsapp bot       -> watches for incoming messages and replies: it
                              answers with the LLM, and if you send "audit <url>"
                              it runs a real audit and replies with the score.

Message yourself (or a dedicated number) to chat with your system.

⚠️ This drives web.whatsapp.com through a browser (no API — on-thesis), which is
fragile (WhatsApp's DOM changes) and against WhatsApp's automation terms. Use for
your own alerts/assistant only. NOT verified in CI — selectors may need updating.
"""

from __future__ import annotations

import os

from . import config

WA_PROFILE = str(config.CONFIG_DIR / "wa-profile")
_URL = "https://web.whatsapp.com"
# Selectors are best-effort and may drift with WhatsApp Web updates.
_SEARCH = 'div[contenteditable="true"][data-tab="3"]'
_MSG_BOX = 'div[contenteditable="true"][data-tab="10"]'
_UNREAD = 'span[aria-label*="unread"]'
_IN_MSG = 'div.message-in span.selectable-text span'


async def connect(headless: bool = False) -> bool:
    """Open WhatsApp Web for a one-time QR scan. Returns True once logged in."""
    from playwright.async_api import async_playwright
    os.makedirs(WA_PROFILE, exist_ok=True)
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(WA_PROFILE, headless=headless)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(_URL, wait_until="domcontentloaded")
        print("  If you see a QR code, scan it in WhatsApp ▸ Linked devices.")
        try:
            await page.wait_for_selector(_SEARCH, timeout=120000)
            print("  ✓ WhatsApp connected — session saved.")
            ok = True
        except Exception:
            print("  ✗ Timed out waiting for login.")
            ok = False
        await ctx.close()
        return ok


async def _handle(text: str) -> str:
    """Turn an incoming WhatsApp message into an action + reply — agentically.
    Whatever you send ('audit mysite.com', 'log in and download invoices') is run
    through the agent, which decides what to do."""
    if not config.is_configured():
        return "Configure a brain first: run `camel setup`, then message me a task."
    from .agent import provider_from_config, run_audit
    try:
        result = await run_audit(provider_from_config(), text.strip(),
                                 headless=True, max_steps=8)
        return (result or "(done)").strip()[:1500]
    except Exception as e:  # keep the bot alive
        return f"Sorry, that failed: {e}"


async def run_bot(poll_seconds: int = 5, headless: bool = True) -> None:
    """Watch for unread chats, read the latest incoming message, reply in-chat."""
    import asyncio
    from playwright.async_api import async_playwright
    os.makedirs(WA_PROFILE, exist_ok=True)
    async with async_playwright() as pw:
        ctx = await pw.chromium.launch_persistent_context(WA_PROFILE, headless=headless)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(_URL, wait_until="domcontentloaded")
        try:
            await page.wait_for_selector(_SEARCH, timeout=60000)
        except Exception:
            print("  Not logged in. Run `camel whatsapp connect` first.")
            await ctx.close()
            return
        print(f"  Camel AI WhatsApp bot running (poll {poll_seconds}s). Ctrl+C to stop.")
        seen = ""
        while True:
            try:
                unread = await page.query_selector(_UNREAD)
                if unread:
                    chat = await unread.evaluate_handle(
                        "e => e.closest('[role=listitem]') || e.closest('div')")
                    await (await chat.as_element()).click()
                    await page.wait_for_timeout(800)
                    msgs = await page.query_selector_all(_IN_MSG)
                    if msgs:
                        last = (await msgs[-1].inner_text()).strip()
                        if last and last != seen:
                            seen = last
                            reply = await _handle(last)
                            box = await page.query_selector(_MSG_BOX)
                            if box and reply:
                                await box.click()
                                await box.type(reply)
                                await page.keyboard.press("Enter")
                                print(f"  replied to: {last[:40]!r}")
            except Exception as e:
                print("  bot loop error:", e)
            await asyncio.sleep(poll_seconds)
