"""Pure-function tests for the report layer — no browser, fast, deterministic."""

from uiscout import report

AUDIT = {
    "tested": 4,
    "results": [
        {"label": "Add", "role": "button", "outcome": "dom_changed", "note": ""},
        {"label": "Open", "role": "button", "outcome": "opened_dialog_or_modal", "note": ""},
        {"label": "Go", "role": "a", "outcome": "navigated", "note": "x"},
        {"label": "Save", "role": "button", "outcome": "no_effect", "note": ""},
    ],
}


def test_summarize_counts():
    s = report.summarize(AUDIT, [])
    assert s["tested"] == 4
    assert s["working"] == 3
    assert s["dead_controls"] == 1
    assert 0 <= s["score"] <= 100


def test_console_errors_lower_score():
    clean = report.summarize(AUDIT, [])["score"]
    noisy = report.summarize(AUDIT, [{"kind": "console", "text": "boom"}] * 3)["score"]
    assert noisy < clean


def test_empty_audit_scores_zero():
    assert report.summarize({"results": []}, [])["score"] == 0


def test_markdown_flags_dead_control():
    md = report.to_markdown("http://x", AUDIT, [])
    assert "Save" in md and "dead" in md.lower()


def test_html_is_selfcontained_and_escaped():
    evil = {"results": [{"label": "<script>", "role": "button",
                         "outcome": "no_effect", "note": "a & b"}]}
    html = report.to_html("http://x", evil, [])
    assert "<!doctype html>" in html
    assert "<script>" not in html          # escaped
    assert "&lt;script&gt;" in html


def test_html_includes_a11y_section():
    a11y = {"issue_count": 1, "by_type": {"image-no-alt": 1},
            "issues": [{"type": "image-no-alt", "detail": "no alt", "selector": "img"}]}
    html = report.to_html("http://x", AUDIT, [], a11y=a11y)
    assert "Accessibility" in html and "image-no-alt" in html
