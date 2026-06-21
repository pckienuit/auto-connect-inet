@echo off
title Auto-Connect INET Installer
echo ===================================================
echo   Installing Auto-Connect INET - Free WiFi Daemon
echo ===================================================
echo.

set "EXE_PATH=%~dp0auto_connect_inet.exe"

if not exist "%EXE_PATH%" (
    echo [ERROR] auto_connect_inet.exe not found in this directory!
    echo Please make sure the compiled executable is in the same folder.
    pause
    exit /b
)

echo [*] Registering startup in Registry (HKCU\Run)...
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "AutoConnectINET" /t REG_SZ /d "\"%EXE_PATH%\"" /f

if %errorlevel% equ 0 (
    echo [OK] Registry entry created successfully (No Admin rights needed).
    echo [*] Stopping any running daemon instances...
    taskkill /f /im auto_connect_inet.exe >nul 2>&1
    
    echo [*] Starting daemon in the background...
    start "" /B "%EXE_PATH%"
    echo.
    echo ===================================================
    echo [+] SUCCESS: Auto-Connect INET is now installed!
    echo     The daemon is running silently in the background
    echo     and will start automatically with Windows.
    echo ===================================================
) else (
    echo [FAILED] Could not write to Windows Registry.
)
echo.
pause
