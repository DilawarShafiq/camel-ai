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
    # A persistent profile dir: log in ONCE and stay logged in across runs (your
    # real sessions/cookies persist here). Fixes "it asks me to log in every time".
    user_profile: str | None = None
    # Attach to an already-running Chrome (started with --remote-debugging-port)
    # to drive YOUR real browser with YOUR existing logins and tabs.
    cdp_url: str | None = None
    _pw: Any = None
    _browser: Browser | None = None
    _context: Any = None
    page: Page | None = None
    console_errors: list[ConsoleError] = field(default_factory=list)

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        if self.cdp_url:
            # Drive the user's real, already-open Chrome.
            self._browser = await self._pw.chromium.connect_over_cdp(self.cdp_url)
            ctx = (self._browser.contexts[0] if self._browser.contexts
                   else await self._browser.new_context())
            self.page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        elif self.user_profile:
            # Persistent profile — logins/cookies survive between runs.
            self._context = await self._pw.chromium.launch_persistent_context(
                self.user_profile, headless=self.headless)
            self.page = (self._context.pages[0] if self._context.pages
                         else await self._context.new_page())
        else:
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
        # Don't close a Chrome we merely attached to over CDP — it's the user's.
        if self._context is not None:
            await self._context.close()
        elif self._browser and not self.cdp_url:
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
        loc = await self._locate(selector)
        await loc.scroll_into_view_if_needed(timeout=4000)
        await loc.click(timeout=6000)
        await self.page.wait_for_timeout(400)
        return {"clicked": selector, "url_before": before, "url_after": self.page.url}

    async def type_text(self, selector: str, text: str) -> dict[str, Any]:
        assert self.page
        loc = await self._locate(selector)
        await loc.scroll_into_view_if_needed(timeout=4000)
        await loc.fill(text, timeout=6000)
        return {"filled": selector, "text": text}

    async def _locate(self, selector: str) -> Any:
        """Resolve a target flexibly: a CSS selector, or — if it's plain words —
        the best matching control. Lets callers say click("Sign in") without
        hunting for the exact selector. Real controls (buttons, links, labelled
        fields) win over stray text that happens to match."""
        assert self.page
        looks_css = any(c in selector for c in "#.[]>:") or selector.startswith(
            ("button", "input", "a", "div", "span", "//"))
        if looks_css:
            return self.page.locator(selector).first
        # Priority order: prefer an actionable, accessible control; fall back to
        # plain text only if nothing better matches.
        candidates = [
            self.page.get_by_role("button", name=selector, exact=False),
            self.page.get_by_role("link", name=selector, exact=False),
            self.page.get_by_label(selector, exact=False),
            self.page.get_by_placeholder(selector, exact=False),
            self.page.get_by_text(selector, exact=False),
        ]
        for cand in candidates:
            try:
                if await cand.count() > 0:
                    return cand.first
            except Exception:
                continue
        return self.page.locator(f"text={selector}").first

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
        # Give single-page apps a moment to render (login forms, dashboards, and
        # controls often appear a beat after the initial load).
        await self.page.wait_for_timeout(700)
        elements = await self.page.evaluate(_INTERACTIVE_JS)
        results: list[dict[str, Any]] = []
        home = self.page.url

        # If this is a login/auth wall, do NOT hammer the sign-in button — a real
        # human has to enter credentials + 2FA. We skip those controls (recording
        # them) and flag the wall so the caller can pause via wait_for_login.
        login = await self.page.evaluate(_LOGIN_JS)
        login_wall = bool(login.get("isLogin"))

        for el in elements[:max_elements]:
            sel = el["selector"]
            label_l = (el.get("label", "") or "").lower()
            if login_wall and any(k in label_l for k in _AUTH_KEYWORDS):
                results.append({
                    "label": el.get("label", ""), "role": el.get("role", ""),
                    "selector": sel, "outcome": "skipped_login",
                    "note": "login control — not clicked; sign in yourself, then "
                            "re-run (use wait_for_login to pause for you)"})
                continue
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
        out: dict[str, Any] = {
            "tested": len(results),
            "dead_controls": len(dead),
            "results": results,
            "login_wall": login_wall,
        }
        if login_wall:
            out["message"] = (
                "This looks like a login/authentication page. Sign-in controls "
                "were NOT clicked. To audit the app behind the login, call "
                "wait_for_login and complete the sign-in (and any 2FA) yourself "
                "in the open browser, then run the audit again on the "
                "logged-in page.")
        return out

    async def detect_login(self) -> dict[str, Any]:
        """Report whether the current page is a login/auth wall, and why. Use
        this to decide when to pause for the human (wait_for_login) instead of
        clicking sign-in controls."""
        assert self.page
        return await self.page.evaluate(_LOGIN_JS)

    async def check_accessibility(self) -> dict[str, Any]:
        """Flag common accessibility / UX defects a careful reviewer would catch,
        with no external library: images missing alt text, buttons/links with no
        accessible name, form fields with no label, missing page <title> or lang,
        and duplicate ids. Each issue names the offending element."""
        assert self.page
        issues = await self.page.evaluate(_A11Y_JS)
        by_type: dict[str, int] = {}
        for i in issues:
            by_type[i["type"]] = by_type.get(i["type"], 0) + 1
        return {"issue_count": len(issues), "by_type": by_type, "issues": issues}


# Cheap page-state fingerprint: total element count + body HTML length.
# Element count is robust to whitespace noise and reliably reflects real DOM
# mutations (a new row, an inserted panel).
_STATE_JS = r"""
() => ({
  elements: document.getElementsByTagName('*').length,
  len: document.body ? document.body.innerHTML.length : 0,
})
"""

# Control labels we must never auto-click on a login wall — a human signs in.
_AUTH_KEYWORDS = ("sign in", "signin", "sign-in", "log in", "login", "log-in",
                  "continue with", "sign in with", "authenticate", "sso")

# Detect a login / authentication wall so we pause for the human instead of
# clicking sign-in over and over.
_LOGIN_JS = r"""
() => {
  const hasPassword = !!document.querySelector('input[type=password]');
  const url = location.href.toLowerCase();
  const urlHint = /login|signin|sign-in|auth|sso|account|session/.test(url);
  const authControls = [];
  document.querySelectorAll('button, a[href], [role=button], input[type=submit]').forEach(el => {
    const t = (el.getAttribute('aria-label') || el.innerText || el.value || '').trim().toLowerCase();
    if (/(sign\s?-?in|log\s?-?in|continue with|sign in with|authenticate|\bsso\b)/.test(t))
      authControls.push(t.slice(0, 30));
  });
  const isLogin = hasPassword || (urlHint && authControls.length > 0);
  return { isLogin, hasPassword, urlHint, authControls: authControls.slice(0, 6) };
}
"""

# Dependency-free accessibility/UX checks. Mirrors the highest-signal rules from
# tools like axe-core, but needs nothing external.
_A11Y_JS = r"""
() => {
  const issues = [];
  const add = (type, detail, sel) => issues.push({type, detail, selector: sel});
  const desc = (el) => {
    if (el.id) return '#' + el.id;
    const t = (el.getAttribute('name') || el.className || '').toString().trim().split(/\s+/)[0];
    return el.tagName.toLowerCase() + (t ? '.' + t : '');
  };
  const name = (el) => (el.getAttribute('aria-label') || el.innerText ||
    el.getAttribute('title') || el.value || '').trim();

  if (!document.title || !document.title.trim())
    add('missing-page-title', 'The page has no <title>.', 'head');
  if (!document.documentElement.getAttribute('lang'))
    add('missing-lang', 'The <html> element has no lang attribute.', 'html');

  document.querySelectorAll('img').forEach(img => {
    if (!img.hasAttribute('alt')) add('image-no-alt',
      'Image has no alt attribute (invisible to screen readers).', desc(img));
  });
  document.querySelectorAll('button, [role=button], a[href]').forEach(el => {
    if (!name(el)) add('control-no-name',
      'Button/link has no accessible text.', desc(el));
  });
  document.querySelectorAll('input:not([type=hidden]), select, textarea').forEach(el => {
    const id = el.id;
    const labelled = (id && document.querySelector('label[for="' + CSS.escape(id) + '"]'))
      || el.closest('label') || el.getAttribute('aria-label') || el.getAttribute('placeholder');
    if (!labelled) add('input-no-label',
      'Form field has no associated label.', desc(el));
  });
  const seen = {};
  document.querySelectorAll('[id]').forEach(el => {
    seen[el.id] = (seen[el.id] || 0) + 1;
  });
  Object.keys(seen).filter(k => seen[k] > 1).forEach(k =>
    add('duplicate-id', 'id "' + k + '" used ' + seen[k] + ' times.', '#' + k));

  return issues.slice(0, 100);
}
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
