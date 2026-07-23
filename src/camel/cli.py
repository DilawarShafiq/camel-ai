"""camel command-line entry.

  camel setup           first-run wizard: pick a brain + paste a free API key
  camel run "GOAL"      do a goal in plain English (uses your configured brain)
  camel audit URL       run a full web audit and write an HTML report
  camel doctor          check the environment (brain, browsers, extras)
  camel mcp-config      print the JSON snippet to add camel to an MCP client
  camel server          run the MCP server (stdio) — what MCP clients launch
  camel                 (no args) opens setup on first run, else runs the app
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
    print("camel doctor\n" + "-" * 40)

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

    def brain() -> str:
        from . import config
        b = config.get_brain()
        if not b:
            raise RuntimeError("not set — run `camel setup`")
        keyed = b.get("api_key") not in (None, "", "not-needed")
        return f"{b['provider']} · {b['model']}" + ("" if keyed or b["provider"] == "local"
                                                     else " (no key yet)")

    def platform_line() -> str:
        import platform
        bits = platform.architecture()[0]
        note = ""
        if sys.platform == "win32" and bits.startswith("32"):
            note = "  ⚠ 32-bit: the browser engine needs 64-bit Windows"
        if sys.version_info < (3, 10):
            note += "  ⚠ Python 3.10+ required"
        return f"{platform.system()} {platform.machine()} · {bits}{note}"

    check("python", lambda: sys.version.split()[0])
    check("platform", platform_line)
    check("brain", brain)
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


def _browser_profile_dir() -> str:
    from . import config
    import os
    d = os.path.join(str(config.CONFIG_DIR), "browser-profile")
    os.makedirs(d, exist_ok=True)
    return d


def _cmd_login(args: argparse.Namespace) -> int:
    """Open the persistent browser so you can log into a site ONCE; the session
    is saved and reused by `camel audit --real-browser`."""
    from .browser import Session
    import asyncio as _a

    async def go() -> None:
        s = Session(headless=False, user_profile=_browser_profile_dir())
        await s.start()
        await s.navigate(args.url)
        print(f"\nA browser opened at {args.url}.")
        print("Log in (and complete any 2FA), then press Enter here to save it...")
        try:
            input()
        except EOFError:
            await s.page.wait_for_timeout(120000)
        await s.stop()
        print("Session saved. Now run:  camel audit <url> --real-browser")

    _a.run(go())
    return 0


def _cmd_audit(args: argparse.Namespace) -> int:
    from .runner import full_web_audit
    profile = _browser_profile_dir() if args.real_browser else None
    # A logged-in run should be visible so you can help if needed.
    show = args.show or args.real_browser
    result = asyncio.run(full_web_audit(
        args.url, headless=not show, max_elements=args.max,
        enrich=args.enrich, user_profile=profile))
    out = args.out or "camel-report.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(result["html"])
    s = result["summary"]
    print(f"Audited {args.url}")
    print(f"  score {s['score']}/100 · {s['tested']} tested · "
          f"{s['dead_controls']} dead · {s['console_errors']} console errors · "
          f"{len(result['findings'])} findings")
    print(f"  report -> {out}")
    brief_path = args.fix_brief or (out.rsplit(".", 1)[0] + ".fixbrief.json")
    with open(brief_path, "w", encoding="utf-8") as f:
        json.dump(result["fix_brief"], f, indent=2, default=str)
    print(f"  fix brief (for an AI coder) -> {brief_path}")
    if args.markdown:
        with open(args.markdown, "w", encoding="utf-8") as f:
            f.write(result["markdown"])
        print(f"  markdown -> {args.markdown}")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in result.items() if k != "html"}, f,
                      indent=2, default=str)
        print(f"  json   -> {args.json}")
    return 0


def _cmd_setup(args: argparse.Namespace) -> int:
    """OpenClaw-style first-run wizard: choose a brain, paste a free key."""
    from . import config
    print("\n  camel setup — connect your AI brain\n" + "  " + "-" * 38)

    # Non-interactive path (flags) — for scripts/CI.
    if args.provider:
        brain = config.set_brain(args.provider, api_key=args.api_key or "",
                                 model=args.model or "",
                                 base_url=getattr(args, "base_url", "") or "")
        print(f"  Saved: {brain['provider']} · {brain['model']}")
        print(f"  Config: {config.CONFIG_PATH}")
        return 0

    provs = list(config.PROVIDERS.items())
    print("  Choose your AI provider (the 'brain'):\n")
    for i, (key, p) in enumerate(provs, 1):
        star = "  ← recommended, FREE" if key == config.DEFAULT_PROVIDER else ""
        print(f"    {i}. {p['label']}{star}")
    try:
        pick = input(f"\n  Number [1-{len(provs)}] (default 1): ").strip() or "1"
        prov_key = provs[int(pick) - 1][0]
    except (ValueError, IndexError, EOFError):
        prov_key = config.DEFAULT_PROVIDER
    preset = config.PROVIDERS[prov_key]

    base_url = ""
    if prov_key == "custom":
        try:
            base_url = input("  OpenAI-compatible base URL "
                             "(e.g. https://host/v1): ").strip()
        except EOFError:
            base_url = ""

    api_key = ""
    if preset["key_url"] or prov_key == "custom":
        if preset["key_url"]:
            print(f"\n  Get a key here:  {preset['key_url']}")
        try:
            api_key = input("  Paste your API key: ").strip()
        except EOFError:
            api_key = ""

    default_model = preset["model"] or "(required)"
    try:
        model = input(f"  Model (default {default_model}): ").strip()
    except EOFError:
        model = ""

    brain = config.set_brain(prov_key, api_key=api_key, model=model,
                             base_url=base_url)
    print(f"\n  ✓ Brain set: {brain['provider']} · {brain['model']}")
    print(f"  ✓ Saved to {config.CONFIG_PATH}")
    print("\n  Try it:  camel run \"audit every button on https://example.com\"\n")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """Do a plain-English goal using the configured brain."""
    from . import config
    if not config.is_configured():
        print("No brain configured yet. Run:  camel setup")
        return 1
    from .agent import provider_from_config, run_audit
    provider = provider_from_config()
    print(f"Goal: {args.goal}\n(brain: {config.get_brain()['model']})\n")
    result = asyncio.run(run_audit(provider, args.goal,
                                   headless=not args.show, max_steps=args.max_steps))
    print("\n=== Result ===\n" + result)
    return 0


def _cmd_app(_: argparse.Namespace) -> int:
    from .app import main as run_app
    run_app()
    return 0


def _cmd_mcp_config(_: argparse.Namespace) -> int:
    cfg = {"mcpServers": {"camel": {"command": "camel", "args": ["server"]}}}
    print(json.dumps(cfg, indent=2))
    print("\nAdd this to your MCP client config "
          "(Claude Desktop / Cursor / Claude Code), then restart it.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    from . import __version__
    p = argparse.ArgumentParser(prog="camel",
                                description="AI-driven UI/UX automation & testing.")
    p.add_argument("-V", "--version", action="version",
                   version=f"camel {__version__}")
    sub = p.add_subparsers(dest="cmd")

    st = sub.add_parser("setup", help="first-run wizard: connect your AI brain")
    st.add_argument("--provider", help="gemini|openrouter|openai|anthropic|groq|"
                    "mistral|deepseek|together|local|custom (skip prompts)")
    st.add_argument("--api-key", help="API key (with --provider)")
    st.add_argument("--model", help="override the model")
    st.add_argument("--base-url", help="OpenAI-compatible endpoint (for custom)")
    st.set_defaults(fn=_cmd_setup)

    r = sub.add_parser("run", help="do a plain-English goal with your brain")
    r.add_argument("goal")
    r.add_argument("--show", action="store_true", help="show the browser window")
    r.add_argument("--max-steps", type=int, default=20)
    r.set_defaults(fn=_cmd_run)

    lg = sub.add_parser("login", help="log into a site once; reuse it later")
    lg.add_argument("url")
    lg.set_defaults(fn=_cmd_login)

    sub.add_parser("app", help="open the desktop window").set_defaults(fn=_cmd_app)
    sub.add_parser("server", help="run the MCP server (stdio)").set_defaults(fn=_cmd_server)
    sub.add_parser("doctor", help="check the environment").set_defaults(fn=_cmd_doctor)
    sub.add_parser("mcp-config", help="print MCP client config snippet").set_defaults(fn=_cmd_mcp_config)

    a = sub.add_parser("audit", help="run a full web audit and write a report")
    a.add_argument("url")
    a.add_argument("--out", help="HTML report path (default camel-report.html)")
    a.add_argument("--fix-brief", help="machine-readable fix brief JSON path")
    a.add_argument("--markdown", help="also write a Markdown report to this path")
    a.add_argument("--json", help="also write raw results to this JSON path")
    a.add_argument("--max", type=int, default=40, help="max controls to test")
    a.add_argument("--enrich", action="store_true",
                   help="use your AI brain to write app-specific fixes")
    a.add_argument("--real-browser", action="store_true",
                   help="use your saved logged-in profile (see `camel login`)")
    a.add_argument("--show", action="store_true", help="show the browser window")
    a.set_defaults(fn=_cmd_audit)
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not getattr(args, "cmd", None):
        # Bare `camel`: first run -> setup wizard; afterwards -> desktop app.
        # (MCP clients launch `camel server` explicitly.)
        from . import config
        if not config.is_configured():
            sys.exit(_cmd_setup(args))
        _cmd_app(args)
        return
    sys.exit(args.fn(args))


if __name__ == "__main__":
    main()
