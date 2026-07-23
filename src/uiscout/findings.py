"""Turn raw observations into a prioritized, actionable FIX BRIEF.

This is the point of the whole testing side: not "here's what's broken" for a
human to sigh at, but a structured hand-off another AI coder or developer can
act on directly. Every finding carries a location, the evidence we observed,
the user-facing impact, and a concrete suggested fix — plus a machine-readable
JSON envelope (schema `uiscout.fixbrief/v1`) a fixing agent can consume.
"""

from __future__ import annotations

from typing import Any

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _finding(sev: str, category: str, title: str, location: str, evidence: str,
             impact: str, suggested_fix: str, confidence: str = "high") -> dict:
    return {
        "severity": sev, "category": category, "title": title,
        "location": location, "evidence": evidence, "impact": impact,
        "suggested_fix": suggested_fix, "confidence": confidence,
    }


def generate(url: str, audit: dict, console_errors: list[dict] | None = None,
             a11y: dict | None = None) -> list[dict]:
    """Produce ranked findings from an audit + console errors + a11y scan."""
    console_errors = console_errors or []
    out: list[dict] = []

    for r in audit.get("results", []):
        label = r.get("label") or r.get("selector") or "control"
        if r["outcome"] == "no_effect":
            out.append(_finding(
                "high", "broken-control",
                f'Control “{label}” does nothing when clicked',
                r.get("selector", ""),
                "Clicked it: no navigation, DOM change, dialog, or console "
                "activity followed.",
                "Users click it expecting something to happen and hit a dead end.",
                "Wire up the intended click handler (or disable/remove the control "
                "if it's not meant to be interactive). Verify the event listener "
                "is actually bound and isn't throwing before its effect runs."))
        elif r["outcome"] == "not_actionable":
            out.append(_finding(
                "medium", "unclickable-control",
                f'Control “{label}” could not be interacted with',
                r.get("selector", ""),
                f"Attempted click failed: {r.get('note','') or 'element not actionable'}.",
                "An overlay, z-index, timing, or disabled-state bug is blocking a "
                "control users are meant to use.",
                "Check for an invisible element intercepting pointer events, fix "
                "z-index/stacking, or ensure the element is rendered and enabled "
                "before it's needed."))

    for e in console_errors:
        kind = e.get("kind", "")
        text = e.get("text", "")
        loc = e.get("location", "")
        if kind == "pageerror":
            out.append(_finding(
                "critical", "js-error", "Uncaught JavaScript error on the page",
                loc, text,
                "An unhandled exception can break features silently for every user.",
                "Trace the exception to its source and guard/fix the throwing code "
                "(null checks, awaited promises, correct types)."))
        elif kind == "requestfailed":
            out.append(_finding(
                "high", "network-error", "A network request failed", loc or text,
                text, "A broken endpoint or missing asset degrades or breaks the UI.",
                "Fix the endpoint/URL, handle the failure gracefully, and check for "
                "CORS/auth/method mistakes."))
        elif kind == "console":
            out.append(_finding(
                "medium", "console-warning", "Console warning/error logged", loc,
                text, "Often the first sign of a real defect users will hit.",
                "Investigate the logged message and resolve the underlying cause "
                "rather than silencing the log.", confidence="medium"))

    for i in (a11y or {}).get("issues", []):
        out.append(_A11Y_FIX.get(i["type"], _a11y_generic)(i))

    # Collapse duplicates (e.g. the same failed request seen on every reload) so
    # the fixing agent gets each distinct problem once, with a count.
    deduped: dict[tuple, dict] = {}
    for f in out:
        key = (f["category"], f["location"], f["title"])
        if key in deduped:
            deduped[key]["occurrences"] = deduped[key].get("occurrences", 1) + 1
        else:
            f["occurrences"] = 1
            deduped[key] = f
    result = list(deduped.values())

    result.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 9))
    for n, f in enumerate(result, 1):
        f["id"] = f"F{n:03d}"
    return result


def _a11y_generic(i: dict) -> dict:
    return _finding("low", "accessibility", i["type"], i.get("selector", ""),
                    i.get("detail", ""), "Reduces accessibility/usability.",
                    "Follow WCAG guidance for this issue.", confidence="medium")


_A11Y_FIX = {
    "image-no-alt": lambda i: _finding(
        "low", "accessibility", "Image missing alt text", i["selector"],
        i["detail"], "Screen-reader users get no description of the image.",
        'Add a meaningful alt="" attribute (empty alt if purely decorative).'),
    "control-no-name": lambda i: _finding(
        "medium", "accessibility", "Button/link has no accessible name",
        i["selector"], i["detail"],
        "Assistive tech announces nothing; the control is unusable non-visually.",
        "Add visible text or an aria-label describing the action."),
    "input-no-label": lambda i: _finding(
        "medium", "accessibility", "Form field has no label", i["selector"],
        i["detail"], "Users (and screen readers) can't tell what to enter.",
        "Associate a <label for> (or aria-label) with the field."),
    "missing-page-title": lambda i: _finding(
        "low", "accessibility", "Page has no <title>", i["selector"], i["detail"],
        "Hurts tabs, history, SEO, and orientation.",
        "Add a descriptive <title> element."),
    "missing-lang": lambda i: _finding(
        "low", "accessibility", "<html> has no lang attribute", i["selector"],
        i["detail"], "Screen readers can't pick the right pronunciation.",
        'Add lang (e.g. <html lang="en">).'),
    "duplicate-id": lambda i: _finding(
        "medium", "correctness", "Duplicate id on the page", i["selector"],
        i["detail"], "Breaks label/for links, anchors, and JS getElementById.",
        "Make every id unique."),
}


def to_fix_brief(url: str, findings: list[dict], summary: dict) -> dict:
    """The machine-readable envelope to hand to a fixing AI/developer."""
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    return {
        "schema": "uiscout.fixbrief/v1",
        "tool": "uiscout",
        "target": url,
        "health_score": summary.get("score"),
        "totals": {"findings": len(findings), "by_severity": counts},
        "instructions_for_ai": (
            "You are fixing this application. Each finding has a location, the "
            "evidence uiscout observed, the user impact, and a suggested_fix. "
            "Apply fixes so the app behaves as a logical, non-broken product. "
            "Preserve intended features; don't delete functionality to silence a "
            "finding. Start with critical/high severity."),
        "findings": findings,
    }


def to_markdown_section(findings: list[dict]) -> str:
    if not findings:
        return "\n## Developer fix list\n\nNo actionable defects found. ✅\n"
    lines = ["", f"## Developer fix list ({len(findings)} findings)", ""]
    for f in findings:
        lines += [
            f"### {f['id']} · [{f['severity'].upper()}] {f['title']}",
            f"- **Where:** `{f['location'] or 'page'}`",
            f"- **Evidence:** {f['evidence']}",
            f"- **Impact:** {f['impact']}",
            f"- **Suggested fix:** {f['suggested_fix']}",
            "",
        ]
    return "\n".join(lines)
