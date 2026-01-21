# USD Inspector & Packager (Standalone Pipeline Utility)

Standalone Python tool for inspecting USD assets and packaging all dependencies into a portable drop.

**Target use cases**
- Move assets between machines / shares
- Department handoff (surfacing → lighting → FX)
- Farm submissions / render prep
- Quick validation of missing references, payloads, sublayers, and textures

## Features (v1.0.0)

### Inspector (Scan)
- Opens `.usd/.usda/.usdc/.usdz`
- Detects:
  - Missing **sublayers**
  - Missing **references**
  - Missing **payloads**
  - Missing **texture assets** (UsdShade asset-typed inputs)
- Produces a structured report with severities:
  - `INFO`, `WARNING`, `ERROR`

### Packager
Creates:
<OUTPUT>/<asset>_PACKAGE/
usd/
textures/
deps/
manifest.json


- Copies root USD + discovered dependencies
- Collision-safe renames for duplicate filenames
- Writes `manifest.json` (with optional SHA-256 hashes)
- Portable mode (optional):
  - Rewrites paths inside the packaged root USD to use **packaged-relative** paths

### Batch Mode
- Scan or package a folder of USDs
- Outputs `batch_summary.json`

---

## Install

### Requirements
- Python 3.10 / 3.11 recommended
- OpenUSD Python bindings (`pxr`)
- PySide6

### Create venv
**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
