# Changelog

All notable changes to Camel AI are documented here.
This project adheres to [Semantic Versioning](https://semver.org/).

## [0.0.3] — 2026-07-24

### Added
- **Real, persistent browser** — `camel login <url>` to sign in once; `camel
  audit <url> --real-browser` reuses the logged-in session. Plus CDP attach to
  your running Chrome.
- **`camel dashboard`** — an enterprise web UI (audit, findings, "use my browser",
  see all windows), served locally on starlette + uvicorn.
- **`camel see`** — list every open window + full-screen screenshot.
- **Scheduled autonomous jobs** — `camel jobs add/list/remove` + `camel daemon`
  run recurring audits/goals unattended.
- **WhatsApp chat (experimental)** — `camel whatsapp connect` (QR) + `camel
  whatsapp bot` to chat with Camel AI from your phone.

### Fixed
- **Login walls** (0.0.2) — detect login/auth pages, skip the sign-in button
  instead of hammering it, and hand off to the human (`wait_for_login`).

## [0.0.1] — 2026-07-24

First public release. 🐫

### Added
- **Web driver** (Playwright): audit every control, classify outcomes
  (navigated / dialog / DOM change / dead / unclickable), capture console errors.
- **Desktop driver**: native Windows apps via UI Automation; experimental macOS
  (Accessibility) and Linux (AT-SPI) drivers behind the same interface.
- **Vision driver**: universal screenshot + coordinate fallback (any OS).
- **Fix brief** (`schema: camel.fixbrief/v1`): ranked, deduplicated findings with
  location, evidence, impact, and a suggested fix — a hand-off for an AI coder.
  Optional LLM enrichment for app-specific fixes.
- **Accessibility audit**: alt text, accessible names, labels, page title/lang,
  duplicate ids — no external library.
- **Human handoff**: `wait_for_login` pauses for 2FA/CAPTCHA/login and resumes on
  a success condition; the tool never handles your codes.
- **Setup wizard**: connect any LLM brain — Gemini (free default), OpenAI, Claude,
  OpenRouter, Groq, Mistral, DeepSeek, Together, local Ollama, or any custom
  OpenAI-compatible endpoint.
- **Two frontends**: an MCP server (Claude Code / Desktop / Cursor) and an
  any-LLM agent loop.
- **One-line install** from GitHub + a landing page; universal `py3-none-any`
  wheel; CI + PyPI-publish workflows.
- Test suite (12 tests) over the report logic and interactivity/accessibility
  classification.
