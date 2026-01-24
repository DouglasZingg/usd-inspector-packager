@echo off
setlocal EnableExtensions
chcp 65001 >nul

echo.
echo [1/5] Creating venv...
if exist ".venv" goto VENV_OK
py -3.11 -m venv .venv
if errorlevel 1 goto VENV_FAIL
:VENV_OK

echo.
echo [2/5] Activating venv...
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto ACT_FAIL

echo.
echo [3/5] Upgrading pip + installing requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
echo [4/5] Verifying OpenUSD (pxr) import...
python -c "from pxr import Usd; print('pxr OK - Usd imported')" >nul 2>nul
if errorlevel 1 goto TRY_INSTALL_USDCORE
echo pxr OK.
goto PXR_DONE

:TRY_INSTALL_USDCORE
echo pxr not found. Trying: pip install usd-core
pip install usd-core
python -c "from pxr import Usd; print('pxr OK - Usd imported')" >nul 2>nul
if errorlevel 1 goto PXR_MISSING
echo pxr OK (installed via usd-core).
goto PXR_DONE

:PXR_MISSING
echo WARNING: pxr is still NOT available after installing usd-core.
echo.
echo Troubleshooting:
echo   - Confirm you are using Python 3.10 or 3.11
echo   - Try reinstalling: pip install --force-reinstall usd-core
echo   - If it still fails, use Conda: conda install -c conda-forge usd-core
echo.
goto PXR_DONE

:PXR_DONE


:PXR_DONE
echo.
echo [5/5] Generating demo USD files...
python tools\make_demos.py
if errorlevel 1 goto DEMO_FAIL
echo Demo files created under samples\
goto DONE

:DEMO_FAIL
echo WARNING: Demo generation failed (likely missing pxr). This is OK for now.
goto DONE

:VENV_FAIL
echo ERROR: Failed to create venv. Make sure Python is installed and the "py" launcher works.
goto DONE

:ACT_FAIL
echo ERROR: Failed to activate venv.
goto DONE

:DONE
echo.
echo Setup complete.
echo To run:
echo   call .venv\Scripts\activate
echo   python main.py
echo.
pause
endlocal
