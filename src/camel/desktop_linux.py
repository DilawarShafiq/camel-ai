"""DesktopDriver for Linux — native apps via AT-SPI (the accessibility bus).

The Linux analogue of the Windows UIA / macOS AX drivers: it reads real controls
from the AT-SPI tree (what Orca screen reader uses) and drives them. Backed by
`pyatspi`.

Requires: the system `python3-pyatspi` / `gir1.2-atspi-2.0` packages and an
accessibility-enabled session (`gsettings set org.gnome.desktop.interface
toolkit-accessibility true`). Install extra: `pip install 'camel[desktop-linux]'`.

NOTE: authored against the documented pyatspi API but NOT yet verified on Linux
from this project's CI — treat as experimental until validated on a Linux desktop.
"""

from __future__ import annotations

from typing import Any

# Normalize AT-SPI role names to the shared control_type vocabulary.
_ROLE_MAP = {
    "push button": "Button", "toggle button": "Button", "text": "Edit",
    "entry": "Edit", "password text": "Edit", "check box": "CheckBox",
    "radio button": "RadioButton", "combo box": "ComboBox", "menu item": "MenuItem",
    "link": "Hyperlink", "page tab": "TabItem", "table cell": "ListItem",
    "label": "Text",
}
_INTERACTIVE = {"Button", "Edit", "CheckBox", "RadioButton", "ComboBox",
                "MenuItem", "Hyperlink", "TabItem"}


def _atspi() -> Any:
    try:
        import pyatspi  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "Linux desktop driver needs the 'desktop-linux' extra and system "
            "AT-SPI packages:\n  pip install 'camel[desktop-linux]'\n"
            "  sudo apt install python3-pyatspi gir1.2-atspi-2.0") from e
    return pyatspi


class LinuxDesktopSession:
    """Same surface as the Windows DesktopSession, backed by AT-SPI."""

    def _app(self, title: str) -> Any:
        pyatspi = _atspi()
        desktop = pyatspi.Registry.getDesktop(0)
        for app in desktop:
            try:
                if app and title.lower() in (app.name or "").lower():
                    return app
            except Exception:
                continue
        raise RuntimeError(f"No app matching {title!r}. "
                           f"Use desktop_list_windows to see options.")

    def list_windows(self) -> list[dict]:
        pyatspi = _atspi()
        out: list[dict] = []
        try:
            for app in pyatspi.Registry.getDesktop(0):
                if app and app.name:
                    out.append({"title": app.name, "class": "", "automation_id": ""})
        except Exception:
            pass
        return out

    def _walk(self, node: Any, elements: list, max_elements: int) -> None:
        for i in range(node.childCount):
            if len(elements) >= max_elements:
                return
            try:
                child = node.getChildAtIndex(i)
                if child is None:
                    continue
                role = child.getRoleName()
                ctype = _ROLE_MAP.get(role, role.title().replace(" ", ""))
                name = child.name or ""
                interactive = ctype in _INTERACTIVE
                if name or interactive:
                    rect = None
                    try:
                        comp = child.queryComponent()
                        ext = comp.getExtents(0)  # ATSPI_COORD_TYPE_SCREEN
                        rect = [ext.x, ext.y, ext.x + ext.width, ext.y + ext.height]
                    except Exception:
                        pass
                    elements.append({
                        "name": name[:80], "control_type": ctype,
                        "automation_id": "", "interactive": interactive,
                        "rect": rect})
                self._walk(child, elements, max_elements)
            except Exception:
                continue

    def snapshot(self, window_title: str, max_elements: int = 80) -> dict:
        app = self._app(window_title)
        elements: list[dict] = []
        self._walk(app, elements, max_elements)
        return {"window": window_title, "count": len(elements), "elements": elements}

    def _find(self, app: Any, name: str) -> Any:
        stack = [app]
        while stack:
            node = stack.pop()
            try:
                if (node.name or "") == name:
                    return node
                stack.extend(node.getChildAtIndex(i)
                             for i in range(node.childCount))
            except Exception:
                continue
        raise RuntimeError(f"No control named {name!r}. Check desktop_snapshot.")

    def invoke(self, window_title: str, name: str = "", control_type: str = "",
               automation_id: str = "") -> dict:
        app = self._app(window_title)
        el = self._find(app, name)
        action = el.queryAction()
        # Prefer a click/press action if present, else the first action.
        idx = 0
        for i in range(action.nActions):
            if action.getName(i).lower() in ("click", "press", "activate"):
                idx = i
                break
        action.doAction(idx)
        return {"invoked": name, "via": f"atspi:{action.getName(idx)}"}

    def set_value(self, window_title: str, name: str, text: str) -> dict:
        app = self._app(window_title)
        el = self._find(app, name)
        el.queryEditableText().setTextContents(text)
        return {"set": name, "text": text, "via": "atspi:setTextContents"}
