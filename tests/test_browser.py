"""Browser tests against a local HTML fixture — offline, deterministic.

Covers the real logic that live testing exposed bugs in: interactivity
classification (working vs dead controls) and the accessibility checker.
"""

import pathlib

import pytest

from camel.browser import Session

FIXTURE = (pathlib.Path(__file__).parent / "fixture.html").resolve().as_uri()


@pytest.fixture
async def session():
    s = Session(headless=True)
    await s.start()
    yield s
    await s.stop()


@pytest.mark.asyncio
async def test_audit_classifies_controls(session):
    await session.navigate(FIXTURE)
    audit = await session.audit_interactivity(max_elements=20)
    by_label = {r["label"]: r["outcome"] for r in audit["results"]}
    assert by_label.get("Add a row") == "dom_changed"
    assert by_label.get("Open settings") == "opened_dialog_or_modal"
    assert by_label.get("Dead button") == "no_effect"      # the broken one
    assert audit["dead_controls"] == 1


@pytest.mark.asyncio
async def test_accessibility_flags_missing_alt_and_label(session):
    await session.navigate(FIXTURE)
    a11y = await session.check_accessibility()
    types = a11y["by_type"]
    assert types.get("image-no-alt", 0) >= 1
    assert types.get("input-no-label", 0) >= 1


@pytest.mark.asyncio
async def test_text_click_prefers_button(session):
    await session.navigate(FIXTURE)
    # "Add a row" matches both a heading-ish text and the button; button wins.
    await session.click("Add a row")
    count = await session.page.locator("#log p").count()
    assert count == 1
