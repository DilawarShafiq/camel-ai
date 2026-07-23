# camel one-line installer (Windows)
#   irm https://raw.githubusercontent.com/DilawarShafiq/camel/main/install.ps1 | iex
#
# Installs camel, its browser engine, and launches the setup wizard.
# No prior Python/terminal knowledge needed beyond running this one line.

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "  Installing camel ..." -ForegroundColor Cyan

# 1. Ensure Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "  Python not found. Installing via winget ..." -ForegroundColor Yellow
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 2. Ensure pipx (isolated app install)
python -m pip install --user -q pipx
python -m pipx ensurepath | Out-Null

# 3. Install camel with desktop + vision extras (straight from GitHub, so it
#    works the moment the repo is public — no PyPI needed for launch).
python -m pipx install "camel[desktop,vision] @ git+https://github.com/DilawarShafiq/camel" --force

# 4. Install the browser engine
camel doctor *> $null
python -m playwright install chromium

# 5. First-run setup wizard (pick a brain, paste a free key)
Write-Host ""
Write-Host "  camel installed. Starting setup ..." -ForegroundColor Green
camel setup

Write-Host ""
Write-Host "  Done. Launch anytime with:  camel" -ForegroundColor Green
