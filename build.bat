@echo off
REM Build a single-file Windows .exe with PyInstaller.
REM Run from a Python 3.10+ environment on Windows after: pip install -r requirements.txt pyinstaller

setlocal
set APP_NAME=PhotoDateWatermark
set ENTRY=photo_date_watermark.py

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

pyinstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name "%APP_NAME%" ^
  --collect-all pillow_heif ^
  "%ENTRY%"

echo.
echo Build finished. Output: dist\%APP_NAME%.exe
endlocal
