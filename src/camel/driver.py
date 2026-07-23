"""Unified Driver layer.

One interface over all three backends so a caller can target web, native desktop,
or raw pixels the same way — and fall back down the ladder (web → desktop →
vision) when a more structured driver can't see the UI.

    driver = await get_driver("web")
    await driver.open("https://example.com")
    view = await driver.observe()          # normalized: list of Elements
    await driver.act("click", locator=view["elements"][0]["locator"])
    await driver.close()

Each Element is normalized to {label, role, locator, rect} regardless of backend,
so higher layers (report, agent, MCP tools) don't special-case the driver.
"""

from __future__ import annotations

from typing import Any, Protocol


class Driver(Protocol):
    kind: str
    async def open(self, target: str) -> dict: ...
    async def observe(self) -> dict: ...
    async def act(self, action: str, **params: Any) -> dict: ...
    async def close(self) -> None: ...


class WebDriver:
    kind = "web"

    def __init__(self, headless: bool = False) -> None:
        from .browser import Session
        self._session = Session(headless=headless)
        self._started = False

    async def _ensure(self) -> None:
        if not self._started:
            await self._session.start()
            self._started = True

    async def open(self, target: str) -> dict:
        await self._ensure()
        return await self._session.navigate(target)

    async def observe(self) -> dict:
        await self._ensure()
        snap = await self._session.snapshot()
        elements = [{
            "label": e["label"], "role": e["role"],
            "locator": e["selector"], "rect": None,
        } for e in snap["interactive_elements"]]
        return {"driver": self.kind, "url": snap["url"], "title": snap["title"],
                "elements": elements}

    async def act(self, action: str, **p: Any) -> dict:
        await self._ensure()
        if action == "click":
            return await self._session.click(p["locator"])
        if action == "type":
            return await self._session.type_text(p["locator"], p["text"])
        if action == "audit":
            return await self._session.audit_interactivity(p.get("max_elements", 40))
        if action == "errors":
            return {"console_errors": self._session.get_console_errors()}
        raise ValueError(f"web driver has no action {action!r}")

    async def close(self) -> None:
        if self._started:
            await self._session.stop()


def _desktop_session() -> Any:
    """Pick the native desktop backend for this OS (Windows UIA / macOS AX /
    Linux AT-SPI). All expose the same list_windows/snapshot/invoke/set_value."""
    import sys
    if sys.platform == "win32":
        from .desktop import DesktopSession
        return DesktopSession()
    if sys.platform == "darwin":
        from .desktop_mac import MacDesktopSession
        return MacDesktopSession()
    from .desktop_linux import LinuxDesktopSession
    return LinuxDesktopSession()


class DesktopDriver:
    kind = "desktop"

    def __init__(self) -> None:
        self._d = _desktop_session()
        self._window = ""

    async def open(self, target: str) -> dict:
        # `target` is a window-title substring to attach to.
        self._window = target
        return {"attached": target}

    async def observe(self) -> dict:
        snap = self._d.snapshot(self._window)
        elements = [{
            "label": e["name"], "role": e["control_type"],
            "locator": e["name"] or e["automation_id"], "rect": e["rect"],
        } for e in snap["elements"]]
        return {"driver": self.kind, "window": snap["window"],
                "elements": elements}

    async def act(self, action: str, **p: Any) -> dict:
        if action == "click":
            return self._d.invoke(self._window, name=p.get("locator", ""),
                                  control_type=p.get("role", ""),
                                  automation_id=p.get("automation_id", ""))
        if action == "type":
            return self._d.set_value(self._window, p["locator"], p["text"])
        raise ValueError(f"desktop driver has no action {action!r}")

    async def close(self) -> None:
        pass


class VisionDriver:
    kind = "vision"

    def __init__(self) -> None:
        from .vision import VisionSession
        self._v = VisionSession()

    async def open(self, target: str) -> dict:
        return {"note": "vision has no navigation; observe the current screen"}

    async def observe(self) -> dict:
        shot = self._v.screenshot()
        # Vision exposes no element list — the LLM reads the pixels.
        return {"driver": self.kind, "screenshot": shot["path"],
                "screen": [shot["screen_width"], shot["screen_height"]],
                "elements": []}

    async def act(self, action: str, **p: Any) -> dict:
        if action == "click":
            return self._v.click(int(p["x"]), int(p["y"]),
                                 button=p.get("button", "left"),
                                 double=bool(p.get("double", False)))
        if action == "type":
            return self._v.type_text(p["text"])
        if action == "hotkey":
            return self._v.hotkey(p["keys"])
        raise ValueError(f"vision driver has no action {action!r}")

    async def close(self) -> None:
        pass


async def get_driver(kind: str, **kw: Any) -> Driver:
    """Factory: 'web' | 'desktop' | 'vision'."""
    if kind == "web":
        return WebDriver(headless=kw.get("headless", False))
    if kind == "desktop":
        return DesktopDriver()
    if kind == "vision":
        return VisionDriver()
    raise ValueError(f"unknown driver {kind!r} (use web|desktop|vision)")
