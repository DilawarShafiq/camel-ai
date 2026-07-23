"""VisionDriver — the universal fallback.

When an app exposes NO accessibility tree (custom-rendered UIs, games, canvas
apps, remote desktops), the only way in is pixels. This driver screenshots the
screen, a vision-capable LLM reads it and decides *where* to act, and we execute
raw mouse/keyboard at those coordinates. Works on literally anything on screen —
at the cost of being slower, token-hungry, and less precise than the other
drivers. Use it only when desktop/web can't see the controls.

Requires the `vision` extra: `pip install 'camel[vision]'`.
Backed by `pyautogui` (input + screenshot) and Pillow.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any


def _pg() -> Any:
    try:
        import pyautogui  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Vision driver needs the 'vision' extra. Install with:\n"
            "  pip install 'camel[vision]'") from e
    # Safety: moving the mouse to a screen corner aborts a runaway automation.
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
    return pyautogui


class VisionSession:
    """Stateless screen driver operating in absolute screen coordinates."""

    def screenshot(self, path: str | None = None) -> dict:
        pg = _pg()
        path = path or os.path.join(tempfile.gettempdir(), "camel_screen.png")
        img = pg.screenshot()
        img.save(path)
        w, h = pg.size()
        return {"path": path, "screen_width": w, "screen_height": h,
                "hint": "Coordinates are absolute screen pixels, origin top-left."}

    def click(self, x: int, y: int, button: str = "left",
              double: bool = False) -> dict:
        pg = _pg()
        self._check_bounds(pg, x, y)
        if double:
            pg.doubleClick(x, y, button=button)
        else:
            pg.click(x, y, button=button)
        return {"clicked": [x, y], "button": button, "double": double}

    def move(self, x: int, y: int) -> dict:
        pg = _pg()
        self._check_bounds(pg, x, y)
        pg.moveTo(x, y, duration=0.15)
        return {"moved": [x, y]}

    def type_text(self, text: str) -> dict:
        pg = _pg()
        pg.write(text, interval=0.02)
        return {"typed": text}

    def hotkey(self, keys: list[str]) -> dict:
        pg = _pg()
        pg.hotkey(*keys)
        return {"pressed": keys}

    def scroll(self, amount: int) -> dict:
        pg = _pg()
        pg.scroll(amount)
        return {"scrolled": amount}

    @staticmethod
    def _check_bounds(pg: Any, x: int, y: int) -> None:
        w, h = pg.size()
        if not (0 <= x < w and 0 <= y < h):
            raise RuntimeError(f"({x},{y}) is off-screen (screen is {w}x{h}).")
