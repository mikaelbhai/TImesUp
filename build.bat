@echo off
echo ============================================
echo   Building Time's Up! EXEs
echo ============================================
echo.

:: Check pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found. Make sure Python is installed and in your PATH.
    pause
    exit /b 1
)

:: Install PyInstaller
echo [1/4] Installing PyInstaller...
pip install pyinstaller --quiet

:: Build main alert EXE
echo [2/4] Compiling TimesUp.exe...
pyinstaller TimesUp.spec --noconfirm >nul 2>&1
if not exist "dist\TimesUp.exe" (
    echo [ERROR] TimesUp build failed. Run without >nul to see output.
    pause
    exit /b 1
)
echo        OK: dist\TimesUp.exe

:: Build stats viewer EXE
echo [3/4] Compiling TimesUpStats.exe...
pyinstaller TimesUpStats.spec --noconfirm >nul 2>&1
if not exist "dist\TimesUpStats.exe" (
    echo [ERROR] TimesUpStats build failed. Run without >nul to see output.
    pause
    exit /b 1
)
echo        OK: dist\TimesUpStats.exe

echo.
echo [4/4] Done!
echo   Alert:  dist\TimesUp.exe
echo   Stats:  dist\TimesUpStats.exe
echo.
pause
