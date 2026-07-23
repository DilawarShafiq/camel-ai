"""High-level workflows that stitch the pieces into a finished deliverable.

`full_web_audit` is the "run a whole test pass and give me a report" flow — no
LLM required (deterministic). The multi-agent, goal-driven version lives in the
MCP host (see integrations/claude/) which orchestrates these same primitives.
"""

from __future__ import annotations

from .browser import Session
from . import report


async def full_web_audit(url: str, *, headless: bool = True,
                         max_elements: int = 40) -> dict:
    """Open a site, audit every interactive control, collect console errors,
    and return {summary, audit, console_errors, markdown, html}."""
    s = Session(headless=headless)
    await s.start()
    try:
        await s.navigate(url)
        a11y = await s.check_accessibility()
        audit = await s.audit_interactivity(max_elements=max_elements)
        errors = s.get_console_errors()
    finally:
        await s.stop()

    return {
        "url": url,
        "summary": {**report.summarize(audit, errors),
                    "a11y_issues": a11y["issue_count"]},
        "audit": audit,
        "console_errors": errors,
        "accessibility": a11y,
        "markdown": report.to_markdown(url, audit, errors, a11y=a11y),
        "html": report.to_html(url, audit, errors, a11y=a11y),
    }
