"""Turn an audit result into a human-readable report (Markdown + self-contained
HTML). Pure functions — no browser, no AI — so any frontend can call them."""

from __future__ import annotations

from typing import Any

_OUTCOME_LABEL = {
    "navigated": ("✅", "Navigated"),
    "opened_dialog_or_modal": ("✅", "Opened dialog/modal"),
    "dom_changed": ("✅", "Changed the page"),
    "no_effect": ("⚠️", "No visible effect (possible dead control)"),
    "not_actionable": ("⛔", "Could not click"),
    "skipped_login": ("🔒", "Login control — skipped (sign in yourself)"),
}


def summarize(audit: dict, console_errors: list[dict] | None = None) -> dict:
    """Reduce raw audit output to headline health numbers."""
    results = audit.get("results", [])
    console_errors = console_errors or []
    dead = [r for r in results if r["outcome"] == "no_effect"]
    stuck = [r for r in results if r["outcome"] == "not_actionable"]
    working = [r for r in results if r["outcome"] in
               ("navigated", "opened_dialog_or_modal", "dom_changed")]
    return {
        "tested": len(results),
        "working": len(working),
        "dead_controls": len(dead),
        "unclickable": len(stuck),
        "console_errors": len(console_errors),
        "score": _score(len(working), len(results), len(console_errors)),
    }


def _score(working: int, total: int, errors: int) -> int:
    if total == 0:
        return 0
    base = int(100 * working / total)
    return max(0, base - min(30, errors * 5))


def to_markdown(url: str, audit: dict, console_errors: list[dict] | None = None,
                title: str = "UI/UX Audit", a11y: dict | None = None,
                findings: list[dict] | None = None) -> str:
    s = summarize(audit, console_errors)
    console_errors = console_errors or []
    lines = [
        f"# {title}", "",
        f"**Target:** {url}  ",
        f"**Health score:** {s['score']}/100  ",
        f"**Controls tested:** {s['tested']} — "
        f"{s['working']} working, {s['dead_controls']} dead, "
        f"{s['unclickable']} unclickable  ",
        f"**Console errors:** {s['console_errors']}", "",
        "## Interactive elements", "",
        "| Control | Role | Outcome | Note |",
        "|---|---|---|---|",
    ]
    for r in audit.get("results", []):
        icon, label = _OUTCOME_LABEL.get(r["outcome"], ("", r["outcome"]))
        lines.append(f"| {_esc(r['label']) or '—'} | {r['role']} | "
                     f"{icon} {label} | {_esc(r['note'])} |")
    if console_errors:
        lines += ["", "## Console errors", ""]
        for e in console_errors:
            lines.append(f"- **{e.get('kind','')}**: {_esc(e.get('text',''))} "
                         f"`{_esc(e.get('location',''))}`")
    if a11y and a11y.get("issues"):
        lines += ["", f"## Accessibility ({a11y['issue_count']} issues)", ""]
        for i in a11y["issues"]:
            lines.append(f"- **{i['type']}** — {_esc(i['detail'])} "
                         f"`{_esc(i['selector'])}`")
    if findings is not None:
        from .findings import to_markdown_section
        lines.append(to_markdown_section(findings))
    return "\n".join(lines)


def to_html(url: str, audit: dict, console_errors: list[dict] | None = None,
            title: str = "UI/UX Audit", a11y: dict | None = None,
            findings: list[dict] | None = None) -> str:
    s = summarize(audit, console_errors)
    console_errors = console_errors or []
    color = "#16a34a" if s["score"] >= 80 else "#d97706" if s["score"] >= 50 else "#dc2626"
    rows = ""
    for r in audit.get("results", []):
        icon, label = _OUTCOME_LABEL.get(r["outcome"], ("", r["outcome"]))
        bad = r["outcome"] in ("no_effect", "not_actionable")
        rows += (f'<tr class="{"bad" if bad else ""}"><td>{_h(r["label"]) or "—"}</td>'
                 f'<td>{_h(r["role"])}</td><td>{icon} {label}</td>'
                 f'<td>{_h(r["note"])}</td></tr>')
    err_html = ""
    if console_errors:
        items = "".join(f"<li><b>{_h(e.get('kind',''))}</b>: {_h(e.get('text',''))} "
                        f"<code>{_h(e.get('location',''))}</code></li>"
                        for e in console_errors)
        err_html = f"<h2>Console errors</h2><ul class='err'>{items}</ul>"
    a11y_html = ""
    if a11y and a11y.get("issues"):
        items = "".join(f"<li><b>{_h(i['type'])}</b> — {_h(i['detail'])} "
                        f"<code>{_h(i['selector'])}</code></li>"
                        for i in a11y["issues"])
        a11y_html = (f"<h2>Accessibility ({a11y['issue_count']} issues)</h2>"
                     f"<ul class='err'>{items}</ul>")
    fix_html = ""
    if findings:
        sev_color = {"critical": "#dc2626", "high": "#ea580c",
                     "medium": "#d97706", "low": "#6b7280"}
        cards = ""
        for f in findings:
            c = sev_color.get(f["severity"], "#6b7280")
            cards += (
                f'<div class="finding"><div class="sev" style="background:{c}">'
                f'{_h(f["id"])} · {_h(f["severity"].upper())}</div>'
                f'<h3>{_h(f["title"])}</h3>'
                f'<p><b>Where:</b> <code>{_h(f["location"] or "page")}</code></p>'
                f'<p><b>Evidence:</b> {_h(f["evidence"])}</p>'
                f'<p><b>Impact:</b> {_h(f["impact"])}</p>'
                f'<p class="fix"><b>Suggested fix:</b> {_h(f["suggested_fix"])}</p>'
                f'</div>')
        fix_html = (f"<h2>Developer fix list ({len(findings)} findings)</h2>"
                    f"<p class='meta'>Ranked most-severe first — hand this to an "
                    f"AI coder or developer.</p>{cards}")
    return f"""<!doctype html><meta charset="utf-8">
<title>{_h(title)}</title>
<style>
 body{{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#111}}
 .score{{font-size:2.5rem;font-weight:700;color:{color}}}
 table{{border-collapse:collapse;width:100%;margin-top:1rem}}
 th,td{{border:1px solid #e5e7eb;padding:.5rem .6rem;text-align:left;font-size:14px}}
 th{{background:#f9fafb}} tr.bad{{background:#fef2f2}}
 .err code{{color:#6b7280}} .meta{{color:#6b7280}}
 .finding{{border:1px solid #e5e7eb;border-radius:8px;padding:.8rem 1rem;margin:.7rem 0}}
 .finding h3{{margin:.3rem 0 .5rem}} .finding p{{margin:.25rem 0;font-size:14px}}
 .finding .fix{{color:#166534}} .sev{{display:inline-block;color:#fff;font-size:12px;
   font-weight:700;padding:.1rem .5rem;border-radius:4px}}
 @media(prefers-color-scheme:dark){{body{{background:#0b0f19;color:#e5e7eb}}
   th{{background:#111827}} td,th{{border-color:#1f2937}} tr.bad{{background:#3f1d1d}}
   .finding{{border-color:#1f2937}} .finding .fix{{color:#4ade80}}}}
</style>
<h1>{_h(title)}</h1>
<p class="meta">Target: <b>{_h(url)}</b></p>
<p><span class="score">{s['score']}</span><span class="meta">/100 health</span></p>
<p class="meta">{s['tested']} controls tested · {s['working']} working ·
 {s['dead_controls']} dead · {s['unclickable']} unclickable ·
 {s['console_errors']} console errors</p>
<table><thead><tr><th>Control</th><th>Role</th><th>Outcome</th><th>Note</th></tr></thead>
<tbody>{rows}</tbody></table>
{fix_html}
{err_html}
{a11y_html}
"""


def _esc(s: str | None) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def _h(s: Any) -> str:
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))
