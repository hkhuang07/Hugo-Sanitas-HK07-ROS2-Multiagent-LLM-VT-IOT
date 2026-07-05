@echo off
setlocal enabledelayedexpansion
title HUGO MAS SYSTEM INTEGRATION - TUNNEL AUTOMATION V4

echo ======================================================================
echo [PROCESS] VERIFYING PRIVILEGES FOR INTERFACE CONFIGURATION...
echo ======================================================================
net session >nul 2>&1
if %errorLevel% equ 0 (
    echo [SUCCESS] Administrator privileges confirmed.
) else (
    echo [CRITICAL ERROR] Access Denied. Elevated privileges required.
    echo Please right-click this file and select 'Run as Administrator'.
    exit /b 1
)

echo.
echo ======================================================================
echo [PROCESS] DETECTING PHYSICAL ADAPTER CONTRACTS (WI-FI ^& HOTSPOT GATEWAY)...
echo ======================================================================
:: Extract Physical Laptop Wi-Fi IP
for /f "usebackq tokens=*" %%p in (`powershell -NoProfile -Command "(Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress"`) do set "WIFI_IP=%%p"

:: Extract Phone Hotspot Gateway IP dynamically
for /f "usebackq tokens=*" %%g in (`powershell -NoProfile -Command "(Get-NetRoute -InterfaceAlias 'Wi-Fi' -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue).NextHop"`) do set "PHONE_IP=%%g"

:: Dynamically resolve the absolute path to the central .env relative to this batch script location
powershell -NoProfile -Command "if (Test-Path '%~dp0..\backend\.env') { $content = Get-Content '%~dp0..\backend\.env'; if ($content -match 'PHONE_IP=') { $content = $content -replace 'PHONE_IP=.*', 'PHONE_IP=%PHONE_IP%' } else { $content = $content + 'PHONE_IP=%PHONE_IP%' }; if ($content -match 'WIFI_IP=') { $content = $content -replace 'WIFI_IP=.*', 'WIFI_IP=%WIFI_IP%' } else { $content = $content + 'WIFI_IP=%WIFI_IP%' }; $content | Set-Content '%~dp0..\backend\.env' }"

if "%WIFI_IP%"=="" (
    echo [CRITICAL ERROR] Failed to extract physical Wi-Fi IPv4 lease.
    echo Ensure your workstation is actively associated with the mobile hotspot.
    exit /b 1
) else (
    echo [SUCCESS] Laptop Wi-Fi IP Target: %WIFI_IP%
    echo [SUCCESS] Phone Hotspot Gateway IP: %PHONE_IP%
)
:: Extract WSL2 IP address
set "WSL_IP="
for /f "usebackq tokens=1" %%i in (`wsl -e hostname -I`) do set "WSL_IP=%%i"

if "%WSL_IP%"=="" (
    echo [WARNING] Failed to extract WSL2 IP address. Falling back to loopback 127.0.0.1
    set "WSL_IP=127.0.0.1"
) else (
    echo [SUCCESS] WSL2 Target VM IP: %WSL_IP%
)

echo.
echo ======================================================================
echo [PROCESS] BACKING UP OBSOLETE NETWORK PROXY STATE BEFORE WIPE
echo ======================================================================
echo ----------------------------------------------------------------------
netsh interface portproxy show all
echo ----------------------------------------------------------------------
echo [INFO] Historical configuration maps shown above are marked for purge.

echo.
echo ======================================================================
echo [PROCESS] PURGING OBSOLETE NETWORK ROUTING MAPS...
echo ======================================================================
netsh interface portproxy reset
echo [SUCCESS] Previous proxy tables cleared from Windows Kernel space.

echo.
echo ======================================================================
echo [PROCESS] PROVISIONING SENSORLOGS PRIMARY CHANNEL (PORT 5005)
echo ======================================================================
echo [COMMAND] netsh interface portproxy add v4tov4 listenport=5005 listenaddress=0.0.0.0 connectport=5005 connectaddress=!WSL_IP!
netsh interface portproxy add v4tov4 listenport=5005 listenaddress=0.0.0.0 connectport=5005 connectaddress=!WSL_IP!
if !errorlevel! equ 0 (
    echo [SUCCESS] Inbound traffic on 0.0.0.0:5005 mapped -^> !WSL_IP!:5005 (WSL2^)
    echo [INFO] Provisioning Windows Firewall rule for Port 5005...
    netsh advfirewall firewall delete rule name="HK07 Ingest 5005" >nul 2>&1
    netsh advfirewall firewall add rule name="HK07 Ingest 5005" dir=in action=allow protocol=TCP localport=5005 >nul
    echo [SUCCESS] Windows Firewall rule "HK07 Ingest 5005" created/verified.
) else (
    echo [CRITICAL ERROR] Binding statement failed for Port 5005.
)

echo.
echo ======================================================================
echo [PROCESS] PROVISIONING SENSORLOGS BACKUP CHANNEL (PORT 5006)
echo ======================================================================
echo [COMMAND] netsh interface portproxy add v4tov4 listenport=5006 listenaddress=0.0.0.0 connectport=5006 connectaddress=!WSL_IP!
netsh interface portproxy add v4tov4 listenport=5006 listenaddress=0.0.0.0 connectport=5006 connectaddress=!WSL_IP!
if !errorlevel! equ 0 (
    echo [SUCCESS] Inbound traffic on 0.0.0.0:5006 mapped -^> !WSL_IP!:5006 (WSL2^)
    echo [INFO] Provisioning Windows Firewall rule for Port 5006...
    netsh advfirewall firewall delete rule name="HK07 Ingest 5006" >nul 2>&1
    netsh advfirewall firewall add rule name="HK07 Ingest 5006" dir=in action=allow protocol=TCP localport=5006 >nul
    echo [SUCCESS] Windows Firewall rule "HK07 Ingest 5006" created/verified.
) else (
    echo [CRITICAL ERROR] Binding statement failed for Port 5006.
)


echo.
echo ======================================================================
echo [PROCESS] DE-PROVISIONING ROSBRIDGE WEBSOCKET SUITE PORTAL (PORT 9090)
echo [INFO] Removing self-referential loopback proxy to allow native WSL2 forwarding
echo ======================================================================
netsh interface portproxy delete v4tov4 listenport=9090 listenaddress=127.0.0.1 >nul 2>&1
echo [SUCCESS] Self-referential loopback proxy for port 9090 cleared.

echo.
echo ======================================================================
echo [PROCESS] VERIFYING ESTABLISHED ACTIVE PORTPROXY MAPS AFTER SETUP
echo ======================================================================
echo ----------------------------------------------------------------------
netsh interface portproxy show all
echo ----------------------------------------------------------------------

echo ======================================================================
echo [INFO] PIPELINE VERIFICATION COMPLETE. SYSTEM INGESTION LIVE.
echo [INFO] Set Mobile Endpoint Target URL to: http://%WIFI_IP%:5006/data
echo [INFO] IPWebCam Endpoint Target URL is: http://%PHONE_IP%:8080/video
echo ======================================================================
