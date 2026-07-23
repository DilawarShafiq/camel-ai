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

mcp = FastMCP("uiscout")

# One session per running server. A frontend owns the browser lifecycle.
_session: Session | None = None


async def _require() -> Session:
    global _session
    if _session is None or _session.page is None:
        _session = Session(headless=_env_headless())
        await _session.start()
    return _session


def _env_headless() -> bool:
    return os.environ.get("UISCOUT_HEADLESS", "0").lower() in ("1", "true", "yes")


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
async def get_console_errors() -> list[dict]:
    """Return JS console errors/warnings, uncaught page errors, and failed
    network requests collected since the session started."""
    s = await _require()
    return s.get_console_errors()


@mcp.tool()
async def screenshot() -> str:
    """Capture a full-page screenshot and return the file path."""
    s = await _require()
    path = os.path.join(tempfile.gettempdir(), "uiscout_shot.png")
    return await s.screenshot(path)


def main() -> None:
    """Console entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
