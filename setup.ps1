#requires -Version 5.1
<#
setup.ps1
Creates/updates a virtual environment, installs deps, validates pxr import, and generates demo samples.

Usage:
  PowerShell (recommended):
    .\setup.ps1

If your system blocks scripts:
  Set-ExecutionPolicy -Scope Process Bypass
#>

$ErrorActionPreference = "Stop"

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoDir

Write-Host "[INFO] Repo: $RepoDir"

# Pick a python executable (prefer py launcher if available)
$python = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
  # Prefer 3.11 then 3.10 if available
  try { $python = "py -3.11" ; & py -3.11 -c "import sys; assert sys.version_info[:2]==(3,11)" | Out-Null } catch { $python = $null }
  if (-not $python) { try { $python = "py -3.10" ; & py -3.10 -c "import sys; assert sys.version_info[:2]==(3,10)" | Out-Null } catch { $python = $null } }
  if (-not $python) { $python = "py -3" }
} else {
  $python = "python"
}

Write-Host "[INFO] Using: $python"

# Create venv if missing
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
  Write-Host "[INFO] Creating venv: .venv"
  & $python -m venv .venv
} else {
  Write-Host "[INFO] venv exists: .venv"
}

# Activate venv
& ".\.venv\Scripts\Activate.ps1"

Write-Host "[INFO] Upgrading pip..."
python -m pip install --upgrade pip

Write-Host "[INFO] Installing requirements..."
pip install -r requirements.txt

Write-Host "[INFO] Checking pxr import..."
python -c "from pxr import Usd; print('pxr OK:', Usd.GetVersion())" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Warning "pxr import failed. The app can still launch, but USD scanning/packaging won't work until OpenUSD bindings are installed."
  Write-Host "See README section: 'pxr / OpenUSD install notes (important)'."
} else {
  Write-Host "[INFO] pxr import succeeded."
}

# Generate demo samples (best-effort)
if (Test-Path ".\tools\make_demos.py") {
  Write-Host "[INFO] Generating demo samples..."
  python .\tools\make_demos.py
  Write-Host "[INFO] Demo samples generated under .\samples\"
} else {
  Write-Warning "tools\make_demos.py not found; skipping demo generation."
}

Write-Host ""
Write-Host "[DONE] Setup complete."
Write-Host "Run the app:"
Write-Host "  .\run_app.bat"
