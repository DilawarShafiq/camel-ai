# uiscout one-line installer (Windows)
#   irm https://raw.githubusercontent.com/yourname/uiscout/main/install.ps1 | iex
#
# Installs uiscout, its browser engine, and launches the setup wizard.
# No prior Python/terminal knowledge needed beyond running this one line.

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "  Installing uiscout ..." -ForegroundColor Cyan

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

# 3. Install uiscout with desktop + vision extras
python -m pipx install "uiscout[desktop,vision]" --force

# 4. Install the browser engine
uiscout doctor *> $null
python -m playwright install chromium

# 5. First-run setup wizard (pick a brain, paste a free key)
Write-Host ""
Write-Host "  uiscout installed. Starting setup ..." -ForegroundColor Green
uiscout setup

Write-Host ""
Write-Host "  Done. Launch anytime with:  uiscout" -ForegroundColor Green
