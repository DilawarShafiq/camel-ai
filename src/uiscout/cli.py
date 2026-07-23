"""uiscout command-line entry.

  uiscout                 run the MCP server (stdio) — what MCP clients launch
  uiscout server          same, explicit
  uiscout doctor          check the environment (browsers, extras)
  uiscout audit URL       run a full web audit and write an HTML report
  uiscout mcp-config      print the JSON snippet to add uiscout to an MCP client
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


def _cmd_server(_: argparse.Namespace) -> int:
    from .server import main as run_server
    run_server()
    return 0


def _cmd_doctor(_: argparse.Namespace) -> int:
    ok = True
    print("uiscout doctor\n" + "-" * 40)

    def check(name: str, fn) -> None:
        nonlocal ok
        try:
            detail = fn()
            print(f"  [ok] {name}: {detail}")
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"  [--] {name}: {e}")

    def ver(dist: str) -> str:
        from importlib.metadata import version, PackageNotFoundError
        try:
            return f"v{version(dist)}"
        except PackageNotFoundError:
            return "not installed (optional)"

    check("python", lambda: sys.version.split()[0])
    check("playwright", lambda: ver("playwright"))

    def chromium() -> str:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            v = b.version
            b.close()
            return f"launches (v{v})"
    check("chromium", chromium)
    check("desktop extra (uiautomation)", lambda: ver("uiautomation"))
    check("vision extra (pyautogui)", lambda: ver("pyautogui"))

    print("-" * 40)
    print("All good." if ok else "Some checks failed — see above.")
    if not _try("chromium_installed"):
        print("Tip: if chromium failed, run:  python -m playwright install chromium")
    return 0 if ok else 1


def _try(mod: str) -> bool:
    if mod == "chromium_installed":
        return True
    try:
        __import__(mod)
        return True
    except Exception:
        return False


def _cmd_audit(args: argparse.Namespace) -> int:
    from .runner import full_web_audit
    result = asyncio.run(full_web_audit(
        args.url, headless=not args.show, max_elements=args.max))
    out = args.out or "uiscout-report.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(result["html"])
    s = result["summary"]
    print(f"Audited {args.url}")
    print(f"  score {s['score']}/100 · {s['tested']} tested · "
          f"{s['dead_controls']} dead · {s['console_errors']} console errors")
    print(f"  report -> {out}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in result.items() if k != "html"}, f,
                      indent=2, default=str)
        print(f"  json   -> {args.json}")
    return 0


def _cmd_mcp_config(_: argparse.Namespace) -> int:
    cfg = {"mcpServers": {"uiscout": {"command": "uiscout"}}}
    print(json.dumps(cfg, indent=2))
    print("\nAdd this to your MCP client config "
          "(Claude Desktop / Cursor / Claude Code), then restart it.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="uiscout",
                                description="AI-driven UI/UX automation & testing.")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("server", help="run the MCP server (stdio)").set_defaults(fn=_cmd_server)
    sub.add_parser("doctor", help="check the environment").set_defaults(fn=_cmd_doctor)
    sub.add_parser("mcp-config", help="print MCP client config snippet").set_defaults(fn=_cmd_mcp_config)

    a = sub.add_parser("audit", help="run a full web audit and write a report")
    a.add_argument("url")
    a.add_argument("--out", help="HTML report path (default uiscout-report.html)")
    a.add_argument("--json", help="also write raw results to this JSON path")
    a.add_argument("--max", type=int, default=40, help="max controls to test")
    a.add_argument("--show", action="store_true", help="show the browser window")
    a.set_defaults(fn=_cmd_audit)
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "cmd", None):
        # Bare `uiscout` = run the MCP server (what clients invoke).
        _cmd_server(args)
        return
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
