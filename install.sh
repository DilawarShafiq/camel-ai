#!/usr/bin/env bash
# uiscout one-line installer (macOS / Linux)
#   curl -fsSL https://raw.githubusercontent.com/yourname/uiscout/main/install.sh | bash
#
# Installs uiscout, its browser engine, and launches the setup wizard.
set -euo pipefail

echo ""
echo "  Installing uiscout ..."

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

# 3. Install uiscout (vision extra; desktop UIA is Windows-only)
pipx install "uiscout[vision]" --force

# 4. Browser engine
python3 -m playwright install chromium

# 5. First-run setup wizard
echo ""
echo "  uiscout installed. Starting setup ..."
uiscout setup

echo ""
echo "  Done. Launch anytime with:  uiscout"
