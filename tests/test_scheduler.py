"""Scheduler due-time logic — deterministic (inject `now`)."""

from datetime import datetime

from camel import scheduler


def test_daily_due_after_target_time_once_per_day():
    job = {"enabled": True, "every": "day", "at": "09:00", "last_run": None}
    # before 09:00 -> not due
    assert scheduler.is_due(job, datetime(2026, 7, 24, 8, 30)) is False
    # after 09:00, never run -> due
    assert scheduler.is_due(job, datetime(2026, 7, 24, 9, 30)) is True
    # already ran today -> not due
    job["last_run"] = datetime(2026, 7, 24, 9, 1).isoformat()
    assert scheduler.is_due(job, datetime(2026, 7, 24, 18, 0)) is False
    # next day after target -> due again
    assert scheduler.is_due(job, datetime(2026, 7, 25, 9, 5)) is True


def test_hourly_due_every_hour():
    job = {"enabled": True, "every": "hour", "last_run": None}
    now = datetime(2026, 7, 24, 10, 0)
    assert scheduler.is_due(job, now) is True
    job["last_run"] = datetime(2026, 7, 24, 9, 30).isoformat()
    assert scheduler.is_due(job, now) is False          # 30 min ago
    job["last_run"] = datetime(2026, 7, 24, 8, 45).isoformat()
    assert scheduler.is_due(job, now) is True           # 75 min ago


def test_disabled_never_due():
    job = {"enabled": False, "every": "hour", "last_run": None}
    assert scheduler.is_due(job, datetime(2026, 7, 24, 10, 0)) is False
