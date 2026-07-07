@echo off
REM ============================================================================
REM  Start Chrome with Remote Debugging (Windows)
REM  Required for linkedin_outreach automation scripts
REM ============================================================================
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo  Starting Chrome with Remote Debugging (Port 9222)
echo ============================================================
echo.

REM ─── Force kill all Chrome processes ─────────────────────────────────────
echo  [STEP 1/3] Killing all existing Chrome processes...
taskkill /F /IM chrome.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo   -> Chrome processes terminated.
) else (
    echo   -> No Chrome processes found.
)

REM Wait for processes to fully release
echo  Waiting 3 seconds for clean shutdown...
timeout /t 3 /nobreak >nul

REM ─── Find Chrome executable ──────────────────────────────────────────────
echo.
echo  [STEP 2/3] Locating Chrome...

set "CHROME_EXE="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if "%CHROME_EXE%"=="" (
    echo.
    echo  [ERROR] Chrome not found at standard locations.
    echo  Please start Chrome manually:
    echo     chrome.exe --remote-debugging-port=9222
    echo.
    pause
    exit /b 1
)

echo   Found: "%CHROME_EXE%"

REM ─── Launch Chrome with remote debugging ─────────────────────────────────
echo.
echo  [STEP 3/3] Launching Chrome...
echo   Debug port: 9222
echo.

start "" "%CHROME_EXE%" --remote-debugging-port=9222 --remote-allow-origins="*" --user-data-dir="C:\chrome-debug" --no-first-run

REM ─── Wait for CDP port to be ready ───────────────────────────────────────
echo  Waiting for port 9222 to become available...
set "WAIT_COUNT=0"
:WAIT_LOOP
timeout /t 1 /nobreak >nul
set /a WAIT_COUNT+=1
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:9222/json/version' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch { } ; exit 1" >nul 2>&1
if !ERRORLEVEL! EQU 0 goto CDP_READY
if !WAIT_COUNT! LSS 15 goto WAIT_LOOP

echo.
echo  [WARNING] Port 9222 not responding after 15 seconds.
echo  Chrome might still be starting up.
echo  Run "python chrome_utils.py diagnose" to check.
echo.
pause
exit /b 0

:CDP_READY
echo.
echo  ============================================================
echo   SUCCESS! Chrome remote debugging is ACTIVE on port 9222
echo  ============================================================
echo.
echo  You can now run: python guide.py
echo.
pause
