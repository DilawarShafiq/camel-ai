"""Enrichment merge logic — verified with a fake provider (no live LLM)."""

from camel.enrich import enrich_findings


class FakeProvider:
    """Returns an LLM-style message improving one finding's fix."""
    def __init__(self, content):
        self._content = content

    def chat(self, messages, tools):
        return {"content": self._content}


FINDINGS = [
    {"id": "F001", "category": "broken-control", "title": "Dead button",
     "location": "#dead", "evidence": "no effect", "suggested_fix": "generic fix"},
    {"id": "F002", "category": "accessibility", "title": "no alt",
     "location": "img", "evidence": "no alt", "suggested_fix": "add alt"},
]


def test_enrich_merges_llm_fixes():
    prov = FakeProvider('[{"id":"F001","suggested_fix":"Bind onSaveClick to #dead"}]')
    out = enrich_findings(prov, "http://x", [dict(f) for f in FINDINGS])
    f1 = next(f for f in out if f["id"] == "F001")
    assert f1["suggested_fix"] == "Bind onSaveClick to #dead"
    assert f1["fix_source"] == "llm"


def test_enrich_is_failsafe_on_bad_output():
    prov = FakeProvider("not json at all")
    out = enrich_findings(prov, "http://x", [dict(f) for f in FINDINGS])
    assert out[0]["suggested_fix"] == "generic fix"   # unchanged, no crash


def test_enrich_handles_code_fenced_json():
    prov = FakeProvider('```json\n[{"id":"F002","suggested_fix":"alt=\\"logo\\""}]\n```')
    out = enrich_findings(prov, "http://x", [dict(f) for f in FINDINGS])
    f2 = next(f for f in out if f["id"] == "F002")
    assert f2["suggested_fix"] == 'alt="logo"'
