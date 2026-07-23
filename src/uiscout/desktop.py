"""DesktopDriver — native Windows apps via UI Automation (UIA).

UIA is the same accessibility layer screen readers use: it exposes an app's real
controls (buttons, edits, menus, list items) as a structured tree, with names,
control types, and automationIds. That means we can "see" and drive most native
and many Electron apps WITHOUT guessing pixels — the reliable middle tier
between the web driver and the vision fallback.

Requires the `desktop` extra: `pip install 'uiscout[desktop]'` (Windows only).
Backed by the pure-Python `uiautomation` package.
"""

from __future__ import annotations

from typing import Any


def _auto() -> Any:
    try:
        import uiautomation as auto  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Desktop driver needs the 'desktop' extra. Install with:\n"
            "  pip install 'uiscout[desktop]'   (Windows only)") from e
    return auto


class DesktopSession:
    """Stateless helper: each call locates the window fresh, so it survives the
    app changing state between MCP tool calls."""

    def __init__(self, search_depth: int = 1) -> None:
        self.search_depth = search_depth

    # --- windows ----------------------------------------------------------

    def list_windows(self) -> list[dict]:
        auto = _auto()
        out: list[dict] = []
        for w in auto.GetRootControl().GetChildren():
            try:
                if w.ControlTypeName == "WindowControl" and w.Name:
                    out.append({
                        "title": w.Name,
                        "class": w.ClassName,
                        "automation_id": w.AutomationId,
                    })
            except Exception:
                continue
        return out

    def _window(self, title: str) -> Any:
        auto = _auto()
        win = auto.WindowControl(searchDepth=self.search_depth, SubName=title)
        if not win.Exists(maxSearchSeconds=3):
            raise RuntimeError(f"No window matching title contains {title!r}. "
                               f"Call desktop_list_windows to see open windows.")
        win.SetActive()
        return win

    # --- observe ----------------------------------------------------------

    def snapshot(self, window_title: str, max_elements: int = 80,
                 max_depth: int = 12) -> dict:
        win = self._window(window_title)
        elements: list[dict] = []

        def walk(ctrl: Any, depth: int) -> None:
            if len(elements) >= max_elements or depth > max_depth:
                return
            for child in ctrl.GetChildren():
                try:
                    rect = child.BoundingRectangle
                    name = (child.Name or "").strip()
                    ctype = child.ControlTypeName
                    interactive = ctype in _INTERACTIVE_TYPES
                    if name or interactive:
                        elements.append({
                            "name": name[:80],
                            "control_type": ctype,
                            "automation_id": child.AutomationId,
                            "interactive": interactive,
                            "rect": [rect.left, rect.top, rect.right, rect.bottom],
                        })
                    if len(elements) >= max_elements:
                        return
                    walk(child, depth + 1)
                except Exception:
                    continue

        walk(win, 0)
        return {
            "window": win.Name,
            "count": len(elements),
            "elements": elements,
        }

    # --- act --------------------------------------------------------------

    def _find(self, win: Any, name: str, control_type: str,
              automation_id: str) -> Any:
        auto = _auto()
        kwargs: dict[str, Any] = {}
        if name:
            kwargs["Name"] = name
        if automation_id:
            kwargs["AutomationId"] = automation_id
        ctrl_cls = getattr(auto, (control_type or "") + "Control", None) \
            if control_type else auto.Control
        if ctrl_cls is None:
            ctrl_cls = auto.Control
        ctrl = ctrl_cls(searchFromControl=win, **kwargs)
        if not ctrl.Exists(maxSearchSeconds=3):
            raise RuntimeError(
                f"No control found (name={name!r}, type={control_type!r}, "
                f"automation_id={automation_id!r}). Check desktop_snapshot.")
        return ctrl

    def invoke(self, window_title: str, name: str = "", control_type: str = "",
               automation_id: str = "") -> dict:
        win = self._window(window_title)
        ctrl = self._find(win, name, control_type, automation_id)
        # Prefer the semantic Invoke pattern; fall back to a real click.
        try:
            ctrl.GetInvokePattern().Invoke()
            how = "invoke_pattern"
        except Exception:
            ctrl.Click(simulateMove=False)
            how = "click"
        return {"invoked": ctrl.Name, "control_type": ctrl.ControlTypeName,
                "via": how}

    def set_value(self, window_title: str, name: str, text: str) -> dict:
        win = self._window(window_title)
        ctrl = self._find(win, name, "", "")
        try:
            ctrl.GetValuePattern().SetValue(text)
            how = "value_pattern"
        except Exception:
            ctrl.SetFocus()
            ctrl.SendKeys("{Ctrl}a")
            ctrl.SendKeys(text)
            how = "sendkeys"
        return {"set": name, "text": text, "via": how}


# Control types we treat as actionable when snapshotting.
_INTERACTIVE_TYPES = {
    "ButtonControl", "HyperlinkControl", "EditControl", "ComboBoxControl",
    "CheckBoxControl", "RadioButtonControl", "MenuItemControl", "TabItemControl",
    "ListItemControl", "TreeItemControl", "SplitButtonControl", "SliderControl",
}
