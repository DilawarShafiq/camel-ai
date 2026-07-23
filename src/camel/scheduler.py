"""Scheduled, autonomous jobs — the agentic layer.

Users register recurring jobs (e.g. "audit https://mysite.com every day at 09:00")
and a long-running `camel daemon` executes them on time, unattended. Jobs are
stored in ~/.camel/jobs.json. Time logic is pure/testable (pass `now`).
"""

from __future__ import annotations

import json
from datetime import datetime, time as dtime
from typing import Any

from . import config

JOBS_PATH = config.CONFIG_DIR / "jobs.json"


def _load() -> list[dict]:
    if JOBS_PATH.exists():
        try:
            return json.loads(JOBS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save(jobs: list[dict]) -> None:
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_PATH.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def add_job(task: str, kind: str = "audit", every: str = "day",
            at: str = "09:00") -> dict:
    """kind: 'audit' (task = URL) or 'goal' (task = plain-English goal).
    every: 'day' (runs at `at`) or 'hour'."""
    jobs = _load()
    job = {
        "id": f"J{len(jobs) + 1:03d}",
        "task": task, "kind": kind, "every": every, "at": at,
        "enabled": True, "last_run": None,
    }
    jobs.append(job)
    _save(jobs)
    return job


def list_jobs() -> list[dict]:
    return _load()


def remove_job(job_id: str) -> bool:
    jobs = _load()
    new = [j for j in jobs if j["id"] != job_id]
    _save(new)
    return len(new) != len(jobs)


def _parse_at(at: str) -> dtime:
    h, m = (at.split(":") + ["0"])[:2]
    return dtime(int(h), int(m))


def is_due(job: dict, now: datetime) -> bool:
    """Pure scheduling decision — testable with any `now`."""
    if not job.get("enabled", True):
        return False
    last = job.get("last_run")
    last_dt = datetime.fromisoformat(last) if last else None
    if job.get("every") == "hour":
        return last_dt is None or (now - last_dt).total_seconds() >= 3600
    # daily at HH:MM
    target = _parse_at(job.get("at", "09:00"))
    if now.time() < target:
        return False
    return last_dt is None or last_dt.date() < now.date()


def due_jobs(now: datetime | None = None) -> list[dict]:
    now = now or datetime.now()
    return [j for j in _load() if is_due(j, now)]


def mark_ran(job_id: str, now: datetime | None = None) -> None:
    now = now or datetime.now()
    jobs = _load()
    for j in jobs:
        if j["id"] == job_id:
            j["last_run"] = now.isoformat()
    _save(jobs)


async def run_job(job: dict) -> str:
    """Execute one job now."""
    if job["kind"] == "audit":
        from .runner import full_web_audit
        r = await full_web_audit(job["task"], headless=True)
        out = str(config.CONFIG_DIR / f"report-{job['id']}.html")
        with open(out, "w", encoding="utf-8") as f:
            f.write(r["html"])
        return f"audit score {r['summary']['score']}/100 -> {out}"
    if job["kind"] == "goal":
        if not config.is_configured():
            return "skipped: no brain configured (run `camel setup`)"
        from .agent import provider_from_config, run_audit
        return await run_audit(provider_from_config(), job["task"], headless=True)
    return f"unknown job kind {job['kind']!r}"


async def run_forever(interval_seconds: int = 60) -> None:
    """The daemon loop: check for due jobs every `interval_seconds` and run them."""
    import asyncio
    print(f"  Camel AI daemon running — checking {len(_load())} job(s) "
          f"every {interval_seconds}s. Ctrl+C to stop.\n")
    while True:
        for job in due_jobs():
            print(f"  ▶ running {job['id']}: {job['kind']} {job['task']}")
            try:
                print("    ", await run_job(job))
            except Exception as e:  # never let one job kill the daemon
                print("    error:", e)
            mark_ran(job["id"])
        await asyncio.sleep(interval_seconds)
