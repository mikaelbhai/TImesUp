@echo off
setlocal EnableDelayedExpansion
title Time's Up! — Setup

:: ─── Colors via ANSI (requires Windows 10 1903+) ────────────────────────────
for /f "delims=" %%i in ('echo prompt $E^| cmd') do set "ESC=%%i"
set "CYAN=%ESC%[96m"
set "RED=%ESC%[91m"
set "GRN=%ESC%[92m"
set "YLW=%ESC%[93m"
set "WHT=%ESC%[97m"
set "DIM=%ESC%[90m"
set "RST=%ESC%[0m"

set "SCRIPT_DIR=%~dp0"
set "EXE_SRC=%SCRIPT_DIR%dist\TimesUp.exe"
set "INSTALL_DIR=%LOCALAPPDATA%\TimesUp"
set "INSTALL_EXE=%INSTALL_DIR%\TimesUp.exe"
set "TASK_NAME=TimesUp Alert"

cls
echo.
echo %CYAN%  ████████╗██╗███╗   ███╗███████╗███████╗    ██╗   ██╗██████╗ %RST%
echo %CYAN%     ██╔══╝██║████╗ ████║██╔════╝██╔════╝    ██║   ██║██╔══██╗%RST%
echo %CYAN%     ██║   ██║██╔████╔██║█████╗  ███████╗    ██║   ██║██████╔╝%RST%
echo %CYAN%     ██║   ██║██║╚██╔╝██║██╔══╝  ╚════██║    ██║   ██║██╔═══╝ %RST%
echo %CYAN%     ██║   ██║██║ ╚═╝ ██║███████╗███████║    ╚██████╔╝██║     %RST%
echo %CYAN%     ╚═╝   ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝     ╚═════╝ ╚═╝     %RST%
echo.
echo %WHT%  Setup Wizard — Windows Task Scheduler Edition%RST%
echo %DIM%  ─────────────────────────────────────────────%RST%
echo.

:: ─── MENU ───────────────────────────────────────────────────────────────────
echo  %WHT%[1]%RST% Full install (build EXE + add scheduled alert)
echo  %WHT%[2]%RST% Add / update a scheduled alert only
echo  %WHT%[3]%RST% List existing alerts
echo  %WHT%[4]%RST% Remove an alert
echo  %WHT%[5]%RST% Build EXE only
echo  %RED%[7]%RST% Set up Forever Snooze alert %DIM%(user cannot dismiss — 5-min re-alert)%RST%
echo  %WHT%[6]%RST% Exit
echo.
set /p "CHOICE=  Choose an option [1-7]: "

if "%CHOICE%"=="1" goto FULL_INSTALL
if "%CHOICE%"=="2" goto ADD_TASK_ONLY
if "%CHOICE%"=="3" goto LIST_TASKS
if "%CHOICE%"=="4" goto REMOVE_TASK
if "%CHOICE%"=="5" goto BUILD_ONLY
if "%CHOICE%"=="7" goto SNOOZE_SETUP
if "%CHOICE%"=="6" goto END
echo %RED%  Invalid choice.%RST%
pause & goto :eof

:: ═══════════════════════════════════════════════════════════════════════════
:FULL_INSTALL
echo.
echo %CYAN%  ── Step 1 of 3: Build the EXE ──────────────────────────%RST%
call :BUILD_EXE
if errorlevel 1 goto END

echo.
echo %CYAN%  ── Step 2 of 3: Install to %INSTALL_DIR% ──%RST%
call :DO_INSTALL
if errorlevel 1 goto END

echo.
echo %CYAN%  ── Step 3 of 3: Schedule the alert ─────────────────────%RST%
call :COLLECT_TIME
call :CREATE_TASK
goto DONE

:: ═══════════════════════════════════════════════════════════════════════════
:ADD_TASK_ONLY
if not exist "%INSTALL_EXE%" (
    echo %YLW%  TimesUp.exe not found at %INSTALL_EXE%%RST%
    echo %YLW%  Checking build output...%RST%
    if exist "%EXE_SRC%" (
        call :DO_INSTALL
    ) else (
        echo %RED%  No EXE found. Run option 1 or 5 first to build.%RST%
        pause & goto :eof
    )
)
call :COLLECT_TIME
call :CREATE_TASK
goto DONE

:: ═══════════════════════════════════════════════════════════════════════════
:BUILD_ONLY
call :BUILD_EXE
if errorlevel 1 goto END
call :DO_INSTALL
goto DONE

:: ═══════════════════════════════════════════════════════════════════════════
:LIST_TASKS
echo.
echo %CYAN%  ── Scheduled Time's Up! alerts ─────────────────────────%RST%
echo.
schtasks /query /fo LIST /v 2>nul | findstr /i "timesup\|Time's Up\|TaskName\|Next Run\|Scheduled Type\|Start Time" | findstr /i /v "Author\|Status\|Last Run\|Last Result\|Idle\|Power\|Stop\|Delete\|Missed"
echo.
echo %DIM%  (Run 'schtasks /query /tn "TimesUp Alert"' for full details)%RST%
echo.
pause
goto :eof

:: ═══════════════════════════════════════════════════════════════════════════
:REMOVE_TASK
echo.
echo %CYAN%  ── Remove a scheduled alert ────────────────────────────%RST%
echo.
schtasks /query /fo TABLE /nh 2>nul | findstr /i "timesup\|Time's Up"
echo.
set /p "TASK_DEL=  Enter exact task name to delete (or press Enter to cancel): "
if "%TASK_DEL%"=="" goto :eof
schtasks /delete /tn "%TASK_DEL%" /f >nul 2>&1
if errorlevel 1 (
    echo %RED%  Task "%TASK_DEL%" not found or could not be deleted.%RST%
) else (
    echo %GRN%  Task "%TASK_DEL%" removed.%RST%
)
echo.
pause
goto :eof

:: ═══════════════════════════════════════════════════════════════════════════
:: ═══════════════════════════════════════════════════════════════════════════
:SNOOZE_SETUP
echo.
echo %RED%  !! Forever Snooze Mode !!%RST%
echo %DIM%  ────────────────────────────────────────────────────────%RST%
echo  When the alert fires, the user sees %RED%SHUT DOWN%RST% and %YLW%SNOOZE (5 MIN)%RST%.
echo  Cancelling is %RED%NOT possible%RST% — snooze re-schedules the alert 5 min later.
echo  This loops until the user clicks SHUT DOWN.
echo.
if not exist "%INSTALL_EXE%" (
    echo %YLW%  TimesUp.exe not installed. Building and installing now...%RST%
    if not exist "%EXE_SRC%" (
        call :BUILD_EXE
        if errorlevel 1 goto END
    )
    call :DO_INSTALL
    if errorlevel 1 goto END
)
set "SNOOZE_ARG= --snooze"
call :COLLECT_TIME_NOPROMPT
call :CREATE_TASK
goto DONE

::  SUBROUTINES
:: ═══════════════════════════════════════════════════════════════════════════

:BUILD_EXE
echo.
echo  Checking for Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo %RED%  [ERROR] Python not found. Install Python 3.9+ and add it to PATH.%RST%
    echo  Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  Found: %%v

echo.
echo  Installing / verifying PyInstaller...
pip install pyinstaller --quiet --disable-pip-version-check
if errorlevel 1 (
    echo %RED%  [ERROR] pip failed. Make sure pip is available.%RST%
    pause
    exit /b 1
)

echo.
echo  Building TimesUp.exe (this takes ~30 seconds)...
cd /d "%SCRIPT_DIR%"
pyinstaller --onefile --windowed --name "TimesUp" timesup.py --noconfirm >nul 2>&1
if not exist "%EXE_SRC%" (
    echo %RED%  [ERROR] Build failed. Run build.bat manually for full output.%RST%
    pause
    exit /b 1
)
echo %GRN%  Build successful: %EXE_SRC%%RST%
exit /b 0

:DO_INSTALL
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
copy /y "%EXE_SRC%" "%INSTALL_EXE%" >nul
if errorlevel 1 (
    echo %RED%  [ERROR] Could not copy EXE to %INSTALL_DIR%%RST%
    exit /b 1
)
echo %GRN%  Installed to: %INSTALL_EXE%%RST%
exit /b 0

:COLLECT_TIME
set "SNOOZE_ARG="
echo.
echo %WHT%  Configure your alert%RST%
echo %DIM%  ─────────────────────%RST%
echo.
echo  Schedule type:
echo   %WHT%[D]%RST% Daily at a fixed time
echo   %WHT%[W]%RST% Weekly (choose day + time)
echo   %WHT%[O]%RST% Once (one-time alert)
echo.
set /p "SCHED_TYPE=  Choose [D/W/O]: "

:: Task name — allow multiple alerts with different names
set /p "TASK_LABEL=  Alert name (e.g. 'Bedtime', 'Work End') [default: TimesUp Alert]: "
if "%TASK_LABEL%"=="" set "TASK_LABEL=TimesUp Alert"

echo.
:ASK_TIME
set /p "ALERT_TIME=  Alert time (24h HH:MM, e.g. 22:00): "
:: Basic format check
echo %ALERT_TIME% | findstr /r "^[0-2][0-9]:[0-5][0-9]$" >nul
if errorlevel 1 (
    echo %RED%  Invalid format. Use HH:MM (e.g. 22:30)%RST%
    goto ASK_TIME
)

if /i "%SCHED_TYPE%"=="W" (
    echo.
    echo  Day of week: MON TUE WED THU FRI SAT SUN
    set /p "WEEK_DAY=  Day: "
)

echo.
echo  %RED%Forever Snooze Mode:%RST% user sees SNOOZE instead of Cancel —
echo  re-alerts every 5 min until they click SHUT DOWN.
set /p "SNOOZE_CHOICE=  Enable Forever Snooze? [Y/N, default N]: "
if /i "!SNOOZE_CHOICE!"=="Y" (
    set "SNOOZE_ARG= --snooze"
    echo %YLW%  Snooze mode ON — user cannot dismiss the alert.%RST%
)
exit /b 0

:: Same as COLLECT_TIME but skips the snooze prompt (snooze already set by caller)
:COLLECT_TIME_NOPROMPT
echo.
echo %WHT%  Configure your Forever Snooze alert%RST%
echo %DIM%  ─────────────────────────────────────%RST%
echo.
echo  Schedule type:
echo   %WHT%[D]%RST% Daily at a fixed time
echo   %WHT%[W]%RST% Weekly (choose day + time)
echo   %WHT%[O]%RST% Once (one-time alert)
echo.
set /p "SCHED_TYPE=  Choose [D/W/O]: "

set /p "TASK_LABEL=  Alert name [default: TimesUp Snooze]: "
if "%TASK_LABEL%"=="" set "TASK_LABEL=TimesUp Snooze"

echo.
:ASK_TIME_SNOOZE
set /p "ALERT_TIME=  First alert time (24h HH:MM): "
echo %ALERT_TIME% | findstr /r "^[0-2][0-9]:[0-5][0-9]$" >nul
if errorlevel 1 (
    echo %RED%  Invalid format. Use HH:MM (e.g. 22:30)%RST%
    goto ASK_TIME_SNOOZE
)

if /i "%SCHED_TYPE%"=="W" (
    echo.
    echo  Day of week: MON TUE WED THU FRI SAT SUN
    set /p "WEEK_DAY=  Day: "
)
exit /b 0

:CREATE_TASK
set "SC_PARAM=/sc daily"
if /i "%SCHED_TYPE%"=="W" set "SC_PARAM=/sc weekly /d %WEEK_DAY%"
if /i "%SCHED_TYPE%"=="O" set "SC_PARAM=/sc once"

schtasks /create /tn "%TASK_LABEL%" /tr "\"%INSTALL_EXE%\"%SNOOZE_ARG%" %SC_PARAM% /st %ALERT_TIME% /f >nul 2>&1
if errorlevel 1 (
    echo %RED%  [ERROR] Could not create scheduled task. Try running as Administrator.%RST%
    pause
    exit /b 1
)
echo.
echo %GRN%  ✓ Scheduled task created!%RST%
echo.
echo  %WHT%Task name:%RST%   %TASK_LABEL%
echo  %WHT%Runs:%RST%        %SCHED_TYPE% at %ALERT_TIME%
echo  %WHT%Launches:%RST%    %INSTALL_EXE%
if not "!SNOOZE_ARG!"=="" (
    echo  %RED%Mode:%RST%        Forever Snooze — re-alerts every 5 min until shutdown
)
echo.
echo %DIM%  Manage in: Task Scheduler → Task Scheduler Library%RST%
exit /b 0

:: ═══════════════════════════════════════════════════════════════════════════
:DONE
echo.
echo %GRN%  ══════════════════════════════════════════%RST%
echo %GRN%   All done! Time's Up! is ready.%RST%
echo %GRN%  ══════════════════════════════════════════%RST%
echo.
echo  Test it now by running:
echo  %CYAN%  "%INSTALL_EXE%"%RST%
echo.

:END
pause
endlocal
