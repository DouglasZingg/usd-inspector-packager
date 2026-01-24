@echo off
setlocal enabledelayedexpansion

REM ------------------------------------------------------------
REM Run USD Inspector & Packager (Windows)
REM Assumes you've already run setup.bat (creates .venv + installs deps)
REM ------------------------------------------------------------

set REPO_DIR=%~dp0
cd /d "%REPO_DIR%"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. Run setup.bat first.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python main.py

echo.
echo [INFO] App closed.
pause
endlocal
