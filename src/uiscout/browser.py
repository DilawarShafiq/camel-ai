"""LLM-agnostic Playwright audit toolkit.

This module contains ZERO AI logic. It knows how to drive and observe a browser
and how to gather objective UI/UX signals. Any frontend (MCP server, an agent
loop over any LLM, or a plain script) can call these functions.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import Browser, Page, async_playwright


@dataclass
class ConsoleError:
    kind: str          # "console" | "pageerror" | "requestfailed"
    text: str
    location: str = ""


@dataclass
class Session:
    """One live browser session. Held by a frontend for the duration of a task."""

    headless: bool = False
    _pw: Any = None
    _browser: Browser | None = None
    page: Page | None = None
    console_errors: list[ConsoleError] = field(default_factory=list)

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless)
        self.page = await self._browser.new_page()
        self._wire_listeners(self.page)

    def _wire_listeners(self, page: Page) -> None:
        def on_console(msg: Any) -> None:
            if msg.type in ("error", "warning"):
                loc = ""
                try:
                    l = msg.location
                    loc = f"{l.get('url', '')}:{l.get('lineNumber', '')}"
                except Exception:
                    pass
                self.console_errors.append(ConsoleError("console", msg.text, loc))

        page.on("console", on_console)
        page.on("pageerror", lambda exc: self.console_errors.append(
            ConsoleError("pageerror", str(exc))))
        page.on("requestfailed", lambda req: self.console_errors.append(
            ConsoleError("requestfailed", f"{req.method} {req.url}",
                         req.failure or "")))

    async def stop(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    # --- primitive actions -------------------------------------------------

    async def navigate(self, url: str) -> dict[str, Any]:
        assert self.page
        resp = await self.page.goto(url, wait_until="domcontentloaded")
        return {
            "url": self.page.url,
            "status": resp.status if resp else None,
            "title": await self.page.title(),
        }

    async def click(self, selector: str) -> dict[str, Any]:
        assert self.page
        before = self.page.url
        await self.page.click(selector, timeout=5000)
        await self.page.wait_for_timeout(400)
        return {"clicked": selector, "url_before": before, "url_after": self.page.url}

    async def type_text(self, selector: str, text: str) -> dict[str, Any]:
        assert self.page
        await self.page.fill(selector, text, timeout=5000)
        return {"filled": selector, "text": text}

    # --- observation -------------------------------------------------------

    async def snapshot(self) -> dict[str, Any]:
        """A compact, human-like view of the page: title, url, and the
        accessibility tree of interactive elements (what a user can act on)."""
        assert self.page
        interactive = await self.page.evaluate(_INTERACTIVE_JS)
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "interactive_elements": interactive,
        }

    async def screenshot(self, path: str) -> str:
        assert self.page
        await self.page.screenshot(path=path, full_page=True)
        return path

    def get_console_errors(self) -> list[dict[str, str]]:
        return [e.__dict__ for e in self.console_errors]

    # --- the "test like a human" audit ------------------------------------

    async def audit_interactivity(self, max_elements: int = 40) -> dict[str, Any]:
        """Click each interactive element and report whether it *did anything*:
        navigated, mutated the DOM, opened a dialog/modal, or was a dead control.
        This is the objective backbone of UX testing; the LLM reasons over it."""
        assert self.page
        elements = await self.page.evaluate(_INTERACTIVE_JS)
        results: list[dict[str, Any]] = []
        home = self.page.url

        for el in elements[:max_elements]:
            sel = el["selector"]
            # Reset to a clean baseline before EVERY control, so one click's
            # side effects (an open modal, appended DOM) can't corrupt the next
            # verdict. This is what makes per-control results trustworthy.
            try:
                await self.page.goto(home, wait_until="domcontentloaded")
                await self.page.wait_for_timeout(150)
            except Exception:
                pass

            before = await self.page.evaluate(_STATE_JS)
            errors_before = len(self.console_errors)
            outcome = "no_effect"
            note = ""
            try:
                await self.page.click(sel, timeout=2500)
                await self.page.wait_for_timeout(350)
                after = await self.page.evaluate(_STATE_JS)
                dialog = await self.page.evaluate(_MODAL_OPEN_JS)

                if self.page.url != home:
                    outcome = "navigated"
                    note = self.page.url
                elif dialog:
                    outcome = "opened_dialog_or_modal"
                elif (after["elements"] != before["elements"]
                      or abs(after["len"] - before["len"]) > 12):
                    outcome = "dom_changed"
                    note = f"+{after['elements'] - before['elements']} elements"
                else:
                    outcome = "no_effect"  # likely a dead button

                if len(self.console_errors) > errors_before:
                    note = (note + " | " if note else "") + "triggered console error"
            except Exception as exc:  # genuinely not clickable / detached
                outcome = "not_actionable"
                note = str(exc).splitlines()[0][:120]

            results.append({
                "label": el.get("label", ""),
                "role": el.get("role", ""),
                "selector": sel,
                "outcome": outcome,
                "note": note,
            })

        dead = [r for r in results if r["outcome"] == "no_effect"]
        return {
            "tested": len(results),
            "dead_controls": len(dead),
            "results": results,
        }


# Cheap page-state fingerprint: total element count + body HTML length.
# Element count is robust to whitespace noise and reliably reflects real DOM
# mutations (a new row, an inserted panel).
_STATE_JS = r"""
() => ({
  elements: document.getElementsByTagName('*').length,
  len: document.body ? document.body.innerHTML.length : 0,
})
"""

# JS that enumerates interactive elements with a usable label + unique selector.
_INTERACTIVE_JS = r"""
() => {
  const sels = 'button, a[href], [role=button], input[type=submit], input[type=button], [onclick], select, [tabindex]:not([tabindex="-1"])';
  const nodes = Array.from(document.querySelectorAll(sels));
  const cssPath = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    while (el && el.nodeType === 1 && parts.length < 5) {
      let part = el.nodeName.toLowerCase();
      if (el.className && typeof el.className === 'string') {
        const c = el.className.trim().split(/\s+/).filter(Boolean)[0];
        if (c) part += '.' + CSS.escape(c);
      }
      const sibs = el.parentNode ? Array.from(el.parentNode.children).filter(n => n.nodeName === el.nodeName) : [];
      if (sibs.length > 1) part += ':nth-of-type(' + (sibs.indexOf(el) + 1) + ')';
      parts.unshift(part);
      el = el.parentElement;
    }
    return parts.join(' > ');
  };
  return nodes.slice(0, 200).map(el => {
    const r = el.getBoundingClientRect();
    return {
      label: (el.getAttribute('aria-label') || el.innerText || el.value || el.title || '').trim().slice(0, 60),
      role: el.getAttribute('role') || el.nodeName.toLowerCase(),
      selector: cssPath(el),
      visible: r.width > 0 && r.height > 0,
    };
  }).filter(e => e.visible);
}
"""

# Detects a likely-open modal/dialog after a click.
_MODAL_OPEN_JS = r"""
() => {
  if (document.querySelector('dialog[open]')) return true;
  const modalish = document.querySelectorAll('[role=dialog], [aria-modal=true], .modal, .Modal');
  for (const m of modalish) {
    const s = getComputedStyle(m);
    const r = m.getBoundingClientRect();
    if (s.display !== 'none' && s.visibility !== 'hidden' && r.width > 0 && r.height > 0) return true;
  }
  return false;
}
"""


async def _demo() -> None:
    s = Session(headless=False)
    await s.start()
    print(await s.navigate("https://example.com"))
    print(await s.audit_interactivity())
    print("console errors:", s.get_console_errors())
    await s.stop()


if __name__ == "__main__":
    asyncio.run(_demo())
