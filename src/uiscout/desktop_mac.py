"""DesktopDriver for macOS — native apps via the Accessibility (AX) API.

The macOS analogue of the Windows UIA driver: it reads an app's real controls
(buttons, fields, menus) through the system Accessibility tree and drives them —
no pixel guessing. Backed by `atomacos` (a maintained wrapper over Apple's AX
APIs).

Requires: `pip install 'uiscout[desktop-mac]'` and granting the running terminal
Accessibility permission (System Settings ▸ Privacy & Security ▸ Accessibility).

NOTE: authored against the documented atomacos/AX API but NOT yet verified on a
Mac from this project's CI — treat as experimental until validated on macOS.
"""

from __future__ import annotations

from typing import Any

# Map AX roles to the same control_type vocabulary the Windows driver emits, so
# higher layers stay OS-agnostic.
_ROLE_MAP = {
    "AXButton": "Button", "AXTextField": "Edit", "AXTextArea": "Edit",
    "AXCheckBox": "CheckBox", "AXRadioButton": "RadioButton",
    "AXPopUpButton": "ComboBox", "AXMenuItem": "MenuItem", "AXLink": "Hyperlink",
    "AXTab": "TabItem", "AXRow": "ListItem", "AXStaticText": "Text",
}
_INTERACTIVE = {"Button", "Edit", "CheckBox", "RadioButton", "ComboBox",
                "MenuItem", "Hyperlink", "TabItem"}


def _atomac() -> Any:
    try:
        import atomacos  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "macOS desktop driver needs the 'desktop-mac' extra:\n"
            "  pip install 'uiscout[desktop-mac]'\n"
            "and Accessibility permission for your terminal.") from e
    return atomacos


class MacDesktopSession:
    """Same surface as the Windows DesktopSession, backed by AX."""

    def _app(self, title: str) -> Any:
        atomacos = _atomac()
        try:
            return atomacos.getAppRefByLocalizedName(title)
        except Exception as e:
            raise RuntimeError(f"No running app named ~{title!r}. "
                               f"Use desktop_list_windows to see options.") from e

    def list_windows(self) -> list[dict]:
        atomacos = _atomac()
        out: list[dict] = []
        try:
            for app in atomacos.NativeUIElement.getRunningApps():
                name = getattr(app, "localizedName", lambda: None)()
                if name:
                    out.append({"title": name, "class": "", "automation_id": ""})
        except Exception:
            pass
        return out

    def snapshot(self, window_title: str, max_elements: int = 80) -> dict:
        app = self._app(window_title)
        elements: list[dict] = []
        try:
            for el in app.findAllR():  # recursive descendants
                if len(elements) >= max_elements:
                    break
                role = getattr(el, "AXRole", "")
                ctype = _ROLE_MAP.get(role, role.replace("AX", "") or "Unknown")
                name = (getattr(el, "AXTitle", "") or getattr(el, "AXValue", "")
                        or getattr(el, "AXDescription", "") or "")
                interactive = ctype in _INTERACTIVE
                if name or interactive:
                    pos = getattr(el, "AXPosition", None)
                    size = getattr(el, "AXSize", None)
                    rect = None
                    if pos and size:
                        rect = [pos[0], pos[1], pos[0] + size[0], pos[1] + size[1]]
                    elements.append({
                        "name": str(name)[:80], "control_type": ctype,
                        "automation_id": getattr(el, "AXIdentifier", "") or "",
                        "interactive": interactive, "rect": rect})
        except Exception as e:
            raise RuntimeError(f"Could not read {window_title!r}: {e}") from e
        return {"window": window_title, "count": len(elements), "elements": elements}

    def _find(self, app: Any, name: str, control_type: str,
              automation_id: str) -> Any:
        crit: dict[str, Any] = {}
        if name:
            crit["AXTitle"] = name
        if automation_id:
            crit["AXIdentifier"] = automation_id
        el = app.findFirstR(**crit) if crit else None
        if el is None:
            raise RuntimeError(f"No control (name={name!r}, id={automation_id!r}). "
                               f"Check desktop_snapshot.")
        return el

    def invoke(self, window_title: str, name: str = "", control_type: str = "",
               automation_id: str = "") -> dict:
        app = self._app(window_title)
        el = self._find(app, name, control_type, automation_id)
        el.Press()  # AXPress
        return {"invoked": name or automation_id, "via": "AXPress"}

    def set_value(self, window_title: str, name: str, text: str) -> dict:
        app = self._app(window_title)
        el = self._find(app, name, "", "")
        el.AXValue = text
        return {"set": name, "text": text, "via": "AXValue"}
