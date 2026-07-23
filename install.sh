#!/usr/bin/env bash
# camel one-line installer (macOS / Linux)
#   curl -fsSL https://raw.githubusercontent.com/DilawarShafiq/camel-ai/main/install.sh | bash
#
# Installs camel, its browser engine, and launches the setup wizard.
set -euo pipefail

echo ""
echo "  Installing camel ..."

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
  export PATH="$HOME/.local/bin:$PATH"
fi

# 3. Install camel (vision extra; desktop UIA is Windows-only). Installed
#    straight from GitHub so it works the moment the repo is public — no PyPI.
pipx install "camel-ai[vision] @ git+https://github.com/DilawarShafiq/camel-ai" --force

# 4. Browser engine
python3 -m playwright install chromium

# 5. First-run setup wizard
echo ""
echo "  camel installed. Starting setup ..."
camel setup

echo ""
echo "  Done. Launch anytime with:  camel"
