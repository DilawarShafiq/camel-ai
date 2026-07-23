# uiscout

An AI-driven **UI/UX auditor**. It opens a browser, walks your web app like a
human tester, and reports broken buttons, dead links, console errors, and
interactivity problems — driven by *any* LLM.

Two ways to use it, sharing one LLM-agnostic Playwright core:

1. **MCP server** — plug into Claude Code, Claude Desktop, Cursor, or Windsurf.
   Uses your existing **subscription**. No API key.
2. **Any-LLM agent** — point your own model (OpenAI, Ollama, LM Studio, vLLM,
   Groq, …) at it via a tiny `LLMProvider` interface.

## Install

```bash
uv pip install -e .        # or: pipx install .
python -m playwright install chromium
```

## Use as an MCP server (subscription users, no API key)

Add to your MCP client config (Claude Desktop / Cursor / Claude Code):

```json
{
  "mcpServers": {
    "uiscout": { "command": "uiscout" }
  }
}
```

Then ask your AI: *"Open http://localhost:3000 and audit every button."*
Set `UISCOUT_HEADLESS=1` to hide the browser window.

### Tools exposed
- `open_page(url)` — navigate
- `snapshot()` — title, url, every visible interactive element + selector
- `click(selector)` / `type_text(selector, text)`
- `audit_interactivity(max_elements)` — clicks everything, flags dead controls,
  navigations, dialogs, DOM changes, console errors
- `get_console_errors()` — JS errors, page errors, failed requests
- `screenshot()` — full-page PNG path

## Use with your own LLM (any model)

```python
import asyncio
from uiscout.agent import run_audit, OpenAICompatibleProvider

# Local Ollama — no API key
prov = OpenAICompatibleProvider(model="llama3.1",
                                base_url="http://localhost:11434/v1")
print(asyncio.run(run_audit(prov, "Audit every button on http://localhost:3000")))
```

Any LLM works — implement `LLMProvider.chat(messages, tools) -> message`.

## Three drivers — web, desktop, anything

Install the extras you need:

```bash
pip install 'uiscout[desktop,vision]'      # Windows desktop + universal fallback
```

| Driver | Reaches | How it "sees" | Reliability |
|--------|---------|---------------|-------------|
| **Web** (`browser.py`) | Websites / web apps | DOM + a11y tree (Playwright) | High |
| **Desktop** (`desktop.py`) | Native Windows apps | UI Automation control tree | Good |
| **Vision** (`vision.py`) | *Anything on screen* | Screenshot → LLM picks coords | Fallback |

Strategy: try Web/Desktop first (structured, fast, precise); drop to Vision only
when there's no accessibility info to read.

### Human-in-the-loop (2FA / CAPTCHA / login) — no API

`wait_for_login(message, until_url_contains=..., until_selector=...)` **pauses**
the automation, lets *you* finish the sensitive step in the visible browser, and
**resumes automatically** the moment it detects success. The automation never
touches your 2FA code. An optional `Notifier` (e.g. WhatsApp) can ping you that a
handoff is waiting.

## Architecture

```
        goal (natural language) ──► MCP host (subscription = brain, multi-agent)
                                          │ calls uiscout MCP tools
   ┌───────────────┬──────────────────────┼───────────────┬────────────────┐
   Web driver     Desktop driver        Vision driver   Human-handoff    Notifier
  (Playwright)   (Windows UIA)      (screenshot+click)   (2FA/CAPTCHA)  (WhatsApp…)
        └──────────────┴───────── shared core, one interface ─────────────────┘

Frontends:  server.py (MCP → subscription, no API key)
            agent.py  (any LLM → OpenAI-compatible / local Ollama)
```
