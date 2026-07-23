"""Login-wall detection: the audit must NOT hammer the sign-in button."""

import pathlib

import pytest

from camel.browser import Session

LOGIN = (pathlib.Path(__file__).parent / "login_fixture.html").resolve().as_uri()


@pytest.fixture
async def session():
    s = Session(headless=True)
    await s.start()
    yield s
    await s.stop()


@pytest.mark.asyncio
async def test_detect_login_flags_password_page(session):
    await session.navigate(LOGIN)
    d = await session.detect_login()
    assert d["isLogin"] is True
    assert d["hasPassword"] is True


@pytest.mark.asyncio
async def test_audit_skips_signin_and_flags_wall(session):
    await session.navigate(LOGIN)
    audit = await session.audit_interactivity(max_elements=20)
    assert audit["login_wall"] is True
    outcomes = {r["label"]: r["outcome"] for r in audit["results"]}
    # The "Sign in" button must be skipped, not clicked repeatedly.
    assert outcomes.get("Sign in") == "skipped_login"
