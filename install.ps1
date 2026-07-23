# Camel AI one-line installer (Windows)
#   irm https://raw.githubusercontent.com/DilawarShafiq/camel-ai/main/install.ps1 | iex
#
# Installs Camel AI, its browser engine, and launches the setup wizard.

$ErrorActionPreference = "Stop"
Write-Host ""
Write-Host "  Installing Camel AI ..." -ForegroundColor Cyan

$spec = "camel-ai[desktop,vision] @ git+https://github.com/DilawarShafiq/camel-ai"
$binDir = Join-Path $env:USERPROFILE ".local\bin"

# 1. Ensure Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  Write-Host "  Python not found. Installing via winget ..." -ForegroundColor Yellow
  winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
  $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" +
              [System.Environment]::GetEnvironmentVariable("Path","User")
}

# 2. Install Camel AI. Prefer uv (fast, reliable) — this is what works cleanly
#    when uv is present. Only fall back to pipx when uv is absent (so pipx never
#    tries to use uv as a backend, which is what broke before).
if (Get-Command uv -ErrorAction SilentlyContinue) {
  Write-Host "  Installing with uv ..." -ForegroundColor Cyan
  uv tool install $spec
  uv tool update-shell | Out-Null
  Write-Host "  Fetching the browser engine ..." -ForegroundColor Cyan
  uvx playwright install chromium
} else {
  Write-Host "  Installing with pipx ..." -ForegroundColor Cyan
  python -m pip install --user -q pipx
  python -m pipx ensurepath | Out-Null
  python -m pipx install $spec --force
  Write-Host "  Fetching the browser engine ..." -ForegroundColor Cyan
  python -m pip install --user -q playwright
  python -m playwright install chromium
}

# 3. Make the command dir available in THIS session; locate camel.exe.
if ($env:Path -notlike "*$binDir*") { $env:Path = "$binDir;$env:Path" }
$camelExe = Join-Path $binDir "camel.exe"

# 4. Run setup via the FULL PATH — never rely on PATH having refreshed.
Write-Host ""
Write-Host "  Camel AI installed. Starting setup ..." -ForegroundColor Green
if (Test-Path $camelExe) { & $camelExe setup }
elseif (Get-Command camel -ErrorAction SilentlyContinue) { camel setup }
else { Write-Host "  Installed — open a new terminal to run 'camel setup'." -ForegroundColor Yellow }

# 5. Clear next steps (bare `camel` needs a fresh terminal on Windows).
Write-Host ""
Write-Host "  Done! Open a NEW terminal, then:" -ForegroundColor Green
Write-Host "     camel audit https://example.com"
Write-Host "  If 'camel' isn't found yet, use the full path:" -ForegroundColor DarkGray
Write-Host "     & `"$camelExe`" audit https://example.com" -ForegroundColor DarkGray
