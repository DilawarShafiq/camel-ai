#!/usr/bin/env bash
# Camel AI one-line installer (macOS / Linux)
#   curl -fsSL https://raw.githubusercontent.com/DilawarShafiq/camel-ai/main/install.sh | bash
#
# Installs Camel AI, its browser engine, and launches the setup wizard.
set -euo pipefail

echo ""
echo "  Installing Camel AI ..."

# 1. Ensure Python 3
if ! command -v python3 >/dev/null 2>&1; then
  echo "  Python 3 is required. Install it (e.g. 'brew install python' or your"
  echo "  distro's package manager), then re-run this installer."
  exit 1
fi

# 2. Ensure pipx
if ! command -v pipx >/dev/null 2>&1; then
  python3 -m pip install --user -q pipx
  python3 -m pipx ensurepath
fi
# Always put pipx's bin dir on PATH for THIS session, so `camel` is found
# immediately (whether or not pipx was already installed).
export PATH="$HOME/.local/bin:$PATH"

# 3. Install Camel AI (vision extra; desktop UIA is Windows-only), from GitHub.
pipx install "camel-ai[vision] @ git+https://github.com/DilawarShafiq/camel-ai" --force

# 4. Browser engine (via python3 — no dependency on the camel PATH).
python3 -m playwright install chromium

# 5. First-run setup wizard. Resolve the path explicitly as a fallback.
echo ""
echo "  Camel AI installed. Starting setup ..."
if command -v camel >/dev/null 2>&1; then camel setup; else "$HOME/.local/bin/camel" setup; fi

echo ""
echo "  Done! Open a new terminal and run:  camel"
