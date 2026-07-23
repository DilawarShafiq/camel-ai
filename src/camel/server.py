"""MCP frontend.

Exposes the LLM-agnostic browser toolkit as MCP tools. Any MCP client
(Claude Code, Claude Desktop, Cursor, Windsurf) can drive it using the user's
existing subscription — no API key required anywhere in this product.
"""

from __future__ import annotations

import os
import tempfile

from mcp.server.fastmcp import FastMCP

from .browser import Session
from .handoff import wait_for_human

mcp = FastMCP("camel")

# One session per running server. A frontend owns the browser lifecycle.
_session: Session | None = None


async def _require() -> Session:
    global _session
    if _session is None or _session.page is None:
        _session = Session(headless=_env_headless())
        await _session.start()
    return _session


def _env_headless() -> bool:
    return os.environ.get("CAMEL_HEADLESS", "0").lower() in ("1", "true", "yes")


@mcp.tool()
async def open_page(url: str) -> dict:
    """Open a URL in the browser and return its title and HTTP status."""
    s = await _require()
    return await s.navigate(url)


@mcp.tool()
async def snapshot() -> dict:
    """Return a human-like view of the current page: title, url, and every
    visible interactive element (buttons, links, inputs) with a label and a
    selector you can pass to click()."""
    s = await _require()
    return await s.snapshot()


@mcp.tool()
async def click(selector: str) -> dict:
    """Click the element matching the CSS selector (use one from snapshot())."""
    s = await _require()
    return await s.click(selector)


@mcp.tool()
async def type_text(selector: str, text: str) -> dict:
    """Type text into the input/textarea matching the selector."""
    s = await _require()
    return await s.type_text(selector, text)


@mcp.tool()
async def audit_interactivity(max_elements: int = 40) -> dict:
    """Click every interactive element on the page and report what each did:
    navigated, opened a dialog/modal, changed the DOM, triggered a console
    error, or had NO effect (a likely-broken 'dead' control). This is the
    core UI/UX health check."""
    s = await _require()
    return await s.audit_interactivity(max_elements=max_elements)


@mcp.tool()
async def fix_brief(max_elements: int = 40) -> dict:
    """Run a full audit of the current page and return a machine-readable FIX
    BRIEF (schema camel.fixbrief/v1): ranked findings, each with location,
    evidence, user impact, and a suggested fix. Hand this to a coding agent to
    repair the app into a logical, non-broken product."""
    s = await _require()
    from . import report as _report, findings as _findings
    a11y = await s.check_accessibility()
    audit = await s.audit_interactivity(max_elements=max_elements)
    errors = s.get_console_errors()
    summary = {**_report.summarize(audit, errors),
               "a11y_issues": a11y["issue_count"]}
    found = _findings.generate(s.page.url, audit, errors, a11y)
    return _findings.to_fix_brief(s.page.url, found, summary)


@mcp.tool()
async def detect_login() -> dict:
    """Check whether the current page is a login/authentication wall. If it is,
    do NOT keep clicking the sign-in button — call wait_for_login and let the
    human complete the sign-in and any 2FA in the open browser, then continue."""
    s = await _require()
    return await s.detect_login()


@mcp.tool()
async def check_accessibility() -> dict:
    """Flag accessibility / UX defects on the current page a careful reviewer
    would catch: images without alt text, buttons/links with no accessible name,
    form fields with no label, missing page title or lang, duplicate ids."""
    s = await _require()
    return await s.check_accessibility()


@mcp.tool()
async def get_console_errors() -> list[dict]:
    """Return JS console errors/warnings, uncaught page errors, and failed
    network requests collected since the session started."""
    s = await _require()
    return s.get_console_errors()


@mcp.tool()
async def screenshot() -> str:
    """Capture a full-page screenshot and return the file path."""
    s = await _require()
    path = os.path.join(tempfile.gettempdir(), "camel_shot.png")
    return await s.screenshot(path)


@mcp.tool()
async def wait_for_login(message: str, until_url_contains: str = "",
                         until_selector: str = "", timeout: int = 300) -> dict:
    """PAUSE and let the human finish a step you must NOT automate — entering a
    2FA code, solving a CAPTCHA, approving a push, or completing a login — in the
    open browser window. Resumes automatically when the URL contains
    `until_url_contains` OR an element matching `until_selector` appears.
    Give at least one condition so it knows when the human is done."""
    s = await _require()
    return await wait_for_human(
        s, message,
        until_url_contains=until_url_contains or None,
        until_selector=until_selector or None,
        timeout=timeout)


# --- desktop (Windows UI Automation) and vision drivers ---------------------
# These live behind lazy imports so the base browser product installs and runs
# even without the optional `desktop`/`vision` extras.

@mcp.tool()
async def desktop_list_windows() -> list[dict]:
    """List open top-level desktop windows (title + process). Windows only;
    needs the `desktop` extra (pip install 'camel[desktop]')."""
    from .desktop import DesktopSession
    return DesktopSession().list_windows()


@mcp.tool()
async def desktop_snapshot(window_title: str, max_elements: int = 80) -> dict:
    """Read the accessibility (UI Automation) tree of a native app window —
    every button, field, menu, and label a screen reader would see. Returns
    controls with name, type, and automation_id for use with desktop_invoke."""
    from .desktop import DesktopSession
    return DesktopSession().snapshot(window_title, max_elements=max_elements)


@mcp.tool()
async def desktop_invoke(window_title: str, name: str = "",
                         control_type: str = "", automation_id: str = "") -> dict:
    """Click/invoke a control in a native window, located by name and/or type
    and/or automation_id (from desktop_snapshot)."""
    from .desktop import DesktopSession
    return DesktopSession().invoke(window_title, name=name,
                                   control_type=control_type,
                                   automation_id=automation_id)


@mcp.tool()
async def desktop_set_value(window_title: str, name: str, text: str) -> dict:
    """Type text into a named edit/field of a native window."""
    from .desktop import DesktopSession
    return DesktopSession().set_value(window_title, name, text)


@mcp.tool()
async def vision_screenshot() -> dict:
    """Capture the whole screen for pixel-level analysis when no accessibility
    tree exists. Returns the PNG path and screen size so you can reason about
    coordinates. Needs the `vision` extra (pip install 'camel[vision]')."""
    from .vision import VisionSession
    return VisionSession().screenshot()


@mcp.tool()
async def vision_click(x: int, y: int, button: str = "left",
                       double: bool = False) -> dict:
    """Click at absolute screen coordinates — the universal fallback for any UI
    with no accessibility info. Get coordinates from vision_screenshot."""
    from .vision import VisionSession
    return VisionSession().click(x, y, button=button, double=double)


@mcp.tool()
async def vision_type(text: str) -> dict:
    """Type text at the current focus via simulated keystrokes."""
    from .vision import VisionSession
    return VisionSession().type_text(text)


@mcp.tool()
async def vision_hotkey(keys: list[str]) -> dict:
    """Press a key combination, e.g. ["ctrl","s"] or ["enter"]."""
    from .vision import VisionSession
    return VisionSession().hotkey(keys)


def main() -> None:
    """Console entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
