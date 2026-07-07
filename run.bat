@echo off
REM ============================================================================
REM  run.bat — One-click start: Chrome + Guide
REM  Usage:   double-click or run from terminal
REM  What it does:
REM    1. If Chrome remote debugging (port 9222) is NOT active → restart Chrome
REM    2. Waits for Chrome to be ready
REM    3. Automatically launches guide.py
REM ============================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ============================================================
echo   UCTalent LinkedIn Outreach - Quick Start
echo ============================================================
echo.

REM ─── Check if Chrome + CDP is already running ───────────────────────────
echo  [STEP 1] Checking Chrome remote debugging...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:9222/json/version' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {} ; exit 1" >nul 2>&1

if !ERRORLEVEL! EQU 0 (
    echo   -> Chrome already running on port 9222. Skipping restart.
    goto RUN_GUIDE
)

echo   -> Chrome not detected. Starting Chrome with remote debugging...

REM ─── Kill existing Chrome ────────────────────────────────────────────────
taskkill /F /IM chrome.exe >nul 2>&1
echo   -> Old Chrome processes killed.
timeout /t 2 /nobreak >nul

REM ─── Locate Chrome ──────────────────────────────────────────────────────
set "CHROME_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if "%CHROME_EXE%"=="" (
    echo   [ERROR] Chrome not found! Please install Chrome or start manually.
    pause
    exit /b 1
)

start "" "%CHROME_EXE%" --remote-debugging-port=9222 --remote-allow-origins="*" --user-data-dir="C:\chrome-debug" --no-first-run

REM ─── Wait for CDP port ──────────────────────────────────────────────────
echo   Waiting for Chrome (port 9222)...
set "WAIT_COUNT=0"
:WAIT_CDP
timeout /t 1 /nobreak >nul
set /a WAIT_COUNT+=1
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:9222/json/version' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {} ; exit 1" >nul 2>&1
if !ERRORLEVEL! EQU 0 goto CDP_READY
if !WAIT_COUNT! LSS 15 goto WAIT_CDP

echo   [WARNING] Chrome did not respond after 15 seconds.
echo   You can still try running guide.py manually.
pause
exit /b 0

:CDP_READY
echo   -> Chrome is ready!

REM ─── Run Guide ──────────────────────────────────────────────────────────
:RUN_GUIDE
echo.
echo ============================================================
echo  Launching Guide...
echo ============================================================
echo.
echo  Tip: set PYTHONIOENCODING ensures Vietnamese/emoji displays correctly
echo.
set PYTHONIOENCODING=utf-8
python guide.py

echo.
echo  Guide exited. Restart me anytime to continue where you left off.
echo.
pause
