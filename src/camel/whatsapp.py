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
    """Turn an incoming message into a reply."""
    t = text.strip()
    if t.lower().startswith("audit "):
        url = t[6:].strip()
        from .runner import full_web_audit
        try:
            r = await full_web_audit(url, headless=True, max_elements=20)
            s = r["summary"]
            return (f"Audit of {url}: {s['score']}/100 · {s['dead_controls']} dead "
                    f"controls · {s['a11y_issues']} a11y · {s['console_errors']} "
                    f"console errors.")
        except Exception as e:
            return f"Couldn't audit {url}: {e}"
    if not config.is_configured():
        return ("Send 'audit <url>' to test a site. (Configure a brain with "
                "`camel setup` for free-form chat.)")
    from .agent import provider_from_config
    prov = provider_from_config()
    msg = prov.chat([
        {"role": "system", "content": "You are Camel AI, a helpful assistant that "
         "can also test/automate software. Reply concisely for WhatsApp."},
        {"role": "user", "content": t},
    ], tools=[])
    return (msg.get("content") or "").strip()[:1500] or "(no reply)"


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
