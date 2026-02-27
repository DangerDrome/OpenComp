@echo off
REM OpenComp Launcher for Windows
REM Double-click this script to launch OpenComp

echo ==============================================
echo   OpenComp - Professional VFX Compositor
echo ==============================================
echo.

cd /d "%~dp0"

REM Check for Blender
if not exist "blender\blender.exe" (
    echo ERROR: Blender not found!
    echo.
    echo Please download Blender 5.0+ and extract it to:
    echo   %~dp0blender\
    echo.
    echo Download from: https://www.blender.org/download/
    echo.
    pause
    exit /b 1
)

echo [1/3] Checking dependencies...

REM Check for Node.js
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Node.js not found!
    echo.
    echo Please install Node.js from: https://nodejs.org/
    echo.
    pause
    exit /b 1
)

REM Install npm dependencies if needed
if not exist "opencomp_electron\node_modules" (
    echo [2/3] Installing dependencies (first run)...
    cd opencomp_electron
    call npm install
    cd ..
) else (
    echo [2/3] Dependencies OK
)

echo [3/3] Launching OpenComp...
echo.

REM Launch the Electron app
cd opencomp_electron
call npm run electron:dev

pause
