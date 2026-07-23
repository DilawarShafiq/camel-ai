"""Human-in-the-loop handoff.

The automation cannot (and should not) type your 2FA code, solve a CAPTCHA, or
click a bank's "I approve" push. So it PAUSES, hands control back to you in the
already-open browser window, and resumes the moment it detects you're through.

No API and no secrets involved: the browser is visible, you act, we poll for a
success condition. An optional Notifier can ping you (e.g. WhatsApp) so you know
a handoff is waiting while you're away from the screen.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from .browser import Session


class Notifier(Protocol):
    """Ping the human that a handoff is waiting. Implement for any channel."""

    async def notify(self, message: str) -> None: ...


class ConsoleNotifier:
    """Default: just print. Zero dependencies, works everywhere."""

    async def notify(self, message: str) -> None:
        print(f"\n🔔 ACTION NEEDED: {message}\n", flush=True)


class WhatsAppWebNotifier:
    """EXPERIMENTAL, no API: drives web.whatsapp.com in a persistent browser
    profile you've logged into once via QR. Fragile and against WhatsApp's
    automation ToS — use for your own alerts only, or prefer a messaging API
    (Twilio / Meta Cloud) for anything production. Left as a clearly-marked stub
    so the interface is real without pretending it's robust."""

    def __init__(self, to_contact: str) -> None:
        self.to_contact = to_contact

    async def notify(self, message: str) -> None:
        # A real implementation opens a persistent-context page at
        # web.whatsapp.com (already QR-authed), searches self.to_contact, types
        # `message`, and presses Enter. Intentionally not auto-run here.
        raise NotImplementedError(
            "WhatsAppWebNotifier is a stub. Wire a persistent Playwright profile "
            "logged into WhatsApp Web, or use a Twilio/Meta notifier instead.")


async def wait_for_human(
    session: Session,
    message: str,
    *,
    until_url_contains: str | None = None,
    until_selector: str | None = None,
    timeout: float = 300.0,
    poll: float = 2.0,
    notifier: Notifier | None = None,
) -> dict:
    """Pause automation and wait for the human to finish something in the open
    browser (log in, enter a 2FA code, solve a CAPTCHA, approve a push).

    Resumes as soon as EITHER condition is met:
      - the URL contains `until_url_contains`, or
      - an element matching `until_selector` becomes visible.
    If neither is given, it waits the full `timeout` (a plain "give me a moment"
    pause). Returns how it resolved.
    """
    assert session.page, "session not started"
    await (notifier or ConsoleNotifier()).notify(message)

    if until_url_contains is None and until_selector is None:
        await asyncio.sleep(timeout)
        return {"resolved": "timeout_elapsed", "message": message}

    waited = 0.0
    while waited < timeout:
        url = session.page.url
        if until_url_contains and until_url_contains in url:
            return {"resolved": "url_matched", "url": url}
        if until_selector:
            try:
                el = await session.page.query_selector(until_selector)
                if el and await el.is_visible():
                    return {"resolved": "selector_appeared", "selector": until_selector}
            except Exception:
                pass
        await asyncio.sleep(poll)
        waited += poll

    return {"resolved": "timed_out",
            "message": "human did not complete the action in time",
            "seconds": timeout}
