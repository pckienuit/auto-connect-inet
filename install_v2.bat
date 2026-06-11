@echo off
schtasks /create /tn "AutoConnectINET" /tr "C:\Users\Chi Kien\auto-connect-inet\auto_connect_inet.exe" /sc onlogon /ru "%USERDOMAIN%\%USERNAME%" /rl highest /f
if %errorlevel% equ 0 (
    echo [OK] Scheduled Task 'AutoConnectINET' created successfully.
    echo [*] It will auto-start on next logon.
    echo [*] Starting now...
    start /B "" "C:\Users\Chi Kien\auto-connect-inet\auto_connect_inet.exe"
) else (
    echo [FAILED] Could not create scheduled task.
    echo Run as Administrator and try again.
)
pause
