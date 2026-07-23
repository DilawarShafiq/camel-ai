# Contributing to Camel AI

Thanks for helping build Camel AI! 🐫

## Dev setup

```bash
git clone https://github.com/DilawarShafiq/camel-ai
cd camel-ai
pip install -e ".[desktop,vision,dev]"     # desktop is Windows-only
python -m playwright install chromium
pytest -q                                   # should be all green
camel doctor                                # check your environment
```

## Ground rules

- **Match the surrounding code** — style, naming, comment density.
- **Add a test** for behavior changes. The suite is offline (a local HTML
  fixture) so it runs anywhere.
- **Keep drivers behind the shared interface** (`driver.py`). A new backend
  should expose `list_windows/snapshot/invoke/set_value` (desktop) or the
  `Driver` verbs (web/vision).
- **The only external API Camel AI uses is an LLM API.** Never add a dependency
  on a target app's API — automate its UI instead.

## Especially wanted

- **Verify the macOS (AX) and Linux (AT-SPI) desktop drivers** on real hardware —
  they're written but not yet CI-verified.
- More accessibility/UX heuristics in `browser.py`.
- Richer fix suggestions in `findings.py` / `enrich.py`.

## Pull requests

1. Branch from `main`.
2. `pytest -q` passes.
3. Describe what changed and why. Small, focused PRs merge fastest.

By contributing you agree your work is licensed under the MIT License.
