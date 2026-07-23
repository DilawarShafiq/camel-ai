"""High-level workflows that stitch the pieces into a finished deliverable.

`full_web_audit` is the "run a whole test pass and give me a report" flow — no
LLM required (deterministic). The multi-agent, goal-driven version lives in the
MCP host (see integrations/claude/) which orchestrates these same primitives.
"""

from __future__ import annotations

from .browser import Session
from . import report, findings


async def full_web_audit(url: str, *, headless: bool = True,
                         max_elements: int = 40, enrich: bool = False,
                         user_profile: str | None = None) -> dict:
    """Open a site, audit every interactive control, collect console errors,
    and return {summary, audit, console_errors, findings, fix_brief, markdown,
    html}. If `enrich` and a brain is configured, the LLM rewrites each
    suggested fix into something app-specific. Pass `user_profile` to reuse a
    persistent, already-logged-in browser profile."""
    s = Session(headless=headless, user_profile=user_profile)
    await s.start()
    try:
        await s.navigate(url)
        a11y = await s.check_accessibility()
        audit = await s.audit_interactivity(max_elements=max_elements)
        errors = s.get_console_errors()
    finally:
        await s.stop()

    summary = {**report.summarize(audit, errors), "a11y_issues": a11y["issue_count"]}
    found = findings.generate(url, audit, errors, a11y)
    if enrich:
        try:
            from . import config
            if config.is_configured():
                from .agent import provider_from_config
                from .enrich import enrich_findings
                found = enrich_findings(provider_from_config(), url, found)
        except Exception:
            pass  # enrichment is best-effort; heuristic fixes remain
    fix_brief = findings.to_fix_brief(url, found, summary)
    return {
        "url": url,
        "summary": summary,
        "audit": audit,
        "console_errors": errors,
        "accessibility": a11y,
        "findings": found,
        "fix_brief": fix_brief,               # hand this to a fixing AI/developer
        "markdown": report.to_markdown(url, audit, errors, a11y=a11y, findings=found),
        "html": report.to_html(url, audit, errors, a11y=a11y, findings=found),
    }
