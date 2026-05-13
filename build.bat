@echo off
echo ============================================
echo   Building Time's Up! .exe
echo ============================================
echo.

:: Check if pip is available
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found. Make sure Python is installed and in your PATH.
    pause
    exit /b 1
)

:: Install PyInstaller if needed
echo [1/3] Installing PyInstaller...
pip install pyinstaller --quiet

:: Build the exe
echo [2/3] Compiling timesup.exe...
pyinstaller --onefile --windowed --name "TimesUp" timesup.py

:: Done
echo.
if exist "dist\TimesUp.exe" (
    echo [3/3] Done! Your exe is at:
    echo        dist\TimesUp.exe
) else (
    echo [ERROR] Build may have failed. Check output above.
)

echo.
pause
