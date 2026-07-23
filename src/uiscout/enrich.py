"""Optional: let the configured brain enrich the fix brief.

The heuristic findings (findings.py) are solid and specific, but generic. When a
brain is configured, this asks it to rewrite each `suggested_fix` into something
app-specific and actionable — the exact change a developer would make — using the
observed evidence. Fully optional and fail-safe: any error and the original
heuristic findings are returned unchanged, so this never breaks a run.
"""

from __future__ import annotations

import json
from typing import Any

_SYSTEM = (
    "You are a senior engineer triaging automated UI test findings. For each "
    "finding you are given its category, location, evidence, and a generic "
    "suggested fix. Rewrite ONLY the suggested_fix into a concrete, app-specific "
    "instruction a developer (or coding agent) can act on directly — name the "
    "likely code change, not vague advice. Keep it to 1-2 sentences. Do not "
    "invent findings or change severities."
)


def _prompt(url: str, findings: list[dict]) -> list[dict]:
    slim = [{"id": f["id"], "category": f["category"], "title": f["title"],
             "location": f["location"], "evidence": f["evidence"],
             "current_fix": f["suggested_fix"]} for f in findings]
    user = (f"App under test: {url}\n\nFindings:\n{json.dumps(slim, indent=2)}\n\n"
            "Return ONLY a JSON array of objects {\"id\": ..., \"suggested_fix\": ...} "
            "with an improved suggested_fix for each id.")
    return [{"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user}]


def _parse(content: str) -> list[dict]:
    content = content.strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1].lstrip("json").strip()
    start, end = content.find("["), content.rfind("]")
    if start == -1 or end == -1:
        return []
    return json.loads(content[start:end + 1])


def enrich_findings(provider: Any, url: str, findings: list[dict]) -> list[dict]:
    """Return findings with LLM-improved suggested_fix values. Never raises."""
    if not findings:
        return findings
    try:
        msg = provider.chat(_prompt(url, findings), tools=[])
        improved = {i["id"]: i["suggested_fix"] for i in _parse(msg.get("content", ""))
                    if i.get("id") and i.get("suggested_fix")}
        for f in findings:
            if f["id"] in improved:
                f["suggested_fix"] = improved[f["id"]]
                f["fix_source"] = "llm"
    except Exception:
        pass  # fail-safe: keep the heuristic fixes
    return findings
