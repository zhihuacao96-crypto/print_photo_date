@echo off
REM Build a single-file Windows .exe with PyInstaller.
REM Requires Python 3.10+ on Windows.

setlocal EnableDelayedExpansion
cd /d "%~dp0"

set APP_NAME=PhotoDateWatermark
set ENTRY=photo_date_watermark.py

REM --- Locate Python (try `python`, then the `py` launcher) ---
set PY=
where python >nul 2>nul
if %ERRORLEVEL%==0 (
    set PY=python
) else (
    where py >nul 2>nul
    if %ERRORLEVEL%==0 (
        set PY=py -3
    )
)

if "%PY%"=="" (
    echo [ERROR] Python not found. Install Python 3.10+ from https://www.python.org/downloads/
    echo         and make sure "Add Python to PATH" is checked during install.
    goto :end
)

echo Using Python: %PY%
%PY% --version
echo.

echo === Upgrading pip ===
%PY% -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo.
echo === Installing dependencies ===
%PY% -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo.
echo === Building exe with PyInstaller ===
%PY% -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "%APP_NAME%" ^
  --collect-all pillow_heif ^
  "%ENTRY%"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo Build finished. Output: dist\%APP_NAME%.exe
echo ============================================================
goto :end

:fail
echo.
echo ============================================================
echo [BUILD FAILED] See messages above for the cause.
echo ============================================================

:end
echo.
pause
endlocal
