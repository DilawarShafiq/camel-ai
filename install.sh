#!/usr/bin/env bash
# Camel AI one-line installer (macOS / Linux)
#   curl -fsSL https://raw.githubusercontent.com/DilawarShafiq/camel-ai/main/install.sh | bash
#
# Installs Camel AI, its browser engine, and launches the setup wizard.
set -euo pipefail

echo ""
echo "  Installing Camel AI ..."

SPEC="aicamel[vision]"

# 1. Ensure Python 3
if ! command -v python3 >/dev/null 2>&1; then
  echo "  Python 3 is required. Install it (e.g. 'brew install python' or your"
  echo "  distro's package manager), then re-run this installer."
  exit 1
fi

# 2. Install Camel AI. Prefer uv (fast, reliable). Only use pipx when uv is
#    absent — so pipx never reaches for uv as a backend (which broke before).
if command -v uv >/dev/null 2>&1; then
  echo "  Installing with uv ..."
  uv tool install "$SPEC"
  uv tool update-shell >/dev/null 2>&1 || true
  echo "  Fetching the browser engine ..."
  uvx playwright install chromium
else
  echo "  Installing with pipx ..."
  command -v pipx >/dev/null 2>&1 || { python3 -m pip install --user -q pipx; python3 -m pipx ensurepath; }
  pipx install "$SPEC" --force
  echo "  Fetching the browser engine ..."
  python3 -m pip install --user -q playwright
  python3 -m playwright install chromium
fi

# 3. Make the command dir available in THIS session; locate camel.
export PATH="$HOME/.local/bin:$PATH"
CAMEL="$HOME/.local/bin/camel"

# 4. Run setup via the full path — never rely on PATH having refreshed.
echo ""
echo "  Camel AI installed. Starting setup ..."
if [ -x "$CAMEL" ]; then "$CAMEL" setup
elif command -v camel >/dev/null 2>&1; then camel setup
else echo "  Installed — open a new terminal and run 'camel setup'."; fi

echo ""
echo "  Done! Open a new terminal, then:  camel audit https://example.com"
