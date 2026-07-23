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

## Architecture

```
uiscout core (browser.py)  ← LLM-agnostic Playwright toolkit, no AI inside
   ├── server.py   MCP frontend   → subscription clients (no API key)
   └── agent.py    agent frontend → any LLM (OpenAI-compatible / local)
```

Roadmap: a `DesktopDriver` (Windows UI Automation) and a `VisionDriver`
(screenshot + coordinate clicks) behind the same interface, to reach native
desktop apps and anything without an accessibility tree.
