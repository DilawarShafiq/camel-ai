# Camel AI one-line installer (Windows)
#   irm https://raw.githubusercontent.com/DilawarShafiq/camel-ai/main/install.ps1 | iex
#
# Installs Camel AI, its browser engine, and launches the setup wizard.

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "  Installing Camel AI ..." -ForegroundColor Cyan

# 1. Ensure Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "  Python not found. Installing via winget ..." -ForegroundColor Yellow
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 2. Ensure pipx and put its bin dir on PATH for THIS session, so the `camel`
#    command is found immediately (avoids "'camel' is not recognized").
python -m pip install --user -q pipx
python -m pipx ensurepath | Out-Null
$pipxBin = Join-Path $env:USERPROFILE ".local\bin"
if ($env:Path -notlike "*$pipxBin*") { $env:Path = "$pipxBin;$env:Path" }

# 3. Install Camel AI straight from GitHub.
python -m pipx install "camel-ai[desktop,vision] @ git+https://github.com/DilawarShafiq/camel-ai" --force

# 4. Install the browser engine (via python — no dependency on the camel PATH).
python -m playwright install chromium

# 5. First-run setup wizard. Resolve the exe explicitly so it runs even if the
#    updated PATH hasn't propagated to this session yet.
Write-Host ""
Write-Host "  Camel AI installed. Starting setup ..." -ForegroundColor Green
$camelExe = Join-Path $pipxBin "camel.exe"
if (Test-Path $camelExe) { & $camelExe setup } else { camel setup }

Write-Host ""
Write-Host "  Done! Open a NEW terminal and run:  camel" -ForegroundColor Green
