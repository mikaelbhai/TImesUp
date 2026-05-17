@echo off
echo ============================================
echo   Building Time's Up! — all EXEs
echo ============================================
echo.

pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found. Install Python 3.9+ and add it to PATH.
    pause & exit /b 1
)

echo [1/5] Installing dependencies...
pip install pyinstaller pystray Pillow --quiet --disable-pip-version-check
if errorlevel 1 (
    echo [ERROR] pip install failed.
    pause & exit /b 1
)

echo [2/5] Compiling TimesUp.exe  (alert)...
py -m PyInstaller TimesUp.spec --noconfirm >nul 2>&1
if not exist "dist\TimesUp.exe" (
    echo [ERROR] TimesUp build failed — run without ^>nul to see output.
    pause & exit /b 1
)
echo        OK: dist\TimesUp.exe

echo [3/5] Compiling TimesUpStats.exe  (stats viewer)...
py -m PyInstaller TimesUpStats.spec --noconfirm >nul 2>&1
if not exist "dist\TimesUpStats.exe" (
    echo [WARN] TimesUpStats build failed — stats viewer unavailable.
) else (
    echo        OK: dist\TimesUpStats.exe
)

echo [4/5] Compiling TimesUpTray.exe  (system tray)...
py -m PyInstaller TimesUpTray.spec --noconfirm >nul 2>&1
if not exist "dist\TimesUpTray.exe" (
    echo [WARN] TimesUpTray build failed — tray unavailable.
) else (
    echo        OK: dist\TimesUpTray.exe
)

echo.
echo [5/5] Done!
echo   Alert:  dist\TimesUp.exe
echo   Stats:  dist\TimesUpStats.exe
echo   Tray:   dist\TimesUpTray.exe
echo.
pause
