@echo off
title Auto-Connect INET Installer
echo ===================================================
echo   Installing Auto-Connect INET - Free WiFi Daemon
echo ===================================================
echo.

set "INSTALL_DIR=%LOCALAPPDATA%\AutoConnectINET"
echo [*] Creating installation folder at: %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

echo [*] Copying executable...
copy /Y "%~dp0auto_connect_inet.exe" "%INSTALL_DIR%uto_connect_inet.exe" >nul

echo [*] Registering Windows Scheduled Task...
schtasks /create /tn AutoConnectINET /tr "\"%INSTALL_DIR%\auto_connect_inet.exe\"" /sc minute /mo 5 /f

echo [*] Starting daemon...
schtasks /run /tn AutoConnectINET

echo.
echo ===================================================
echo [+] SUCCESS: Auto-Connect INET is now installed!
echo     The daemon is running silently in the background
echo     and will start automatically with Windows.
echo ===================================================
echo.
pause
