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

if "%WIFI_IP%"=="" (
    echo [CRITICAL ERROR] Failed to extract physical Wi-Fi IPv4 lease.
    echo Ensure your workstation is actively associated with the mobile hotspot.
    exit /b 1
) else (
    echo [SUCCESS] Laptop Wi-Fi IP Target: %WIFI_IP%
    echo [SUCCESS] Phone Hotspot Gateway IP: %PHONE_IP%
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
echo [COMMAND] netsh interface portproxy add v4tov4 listenport=5005 listenaddress=%WIFI_IP% connectport=5005 connectaddress=127.0.0.1
netsh interface portproxy add v4tov4 listenport=5005 listenaddress=%WIFI_IP% connectport=5005 connectaddress=127.0.0.1
if !errorlevel! equ 0 (
    echo [SUCCESS] Inbound traffic on %WIFI_IP%:5005 mapped -^> 127.0.0.1:5005 (WSL2)
) else (
    echo [CRITICAL ERROR] Binding statement failed for Port 5005.
)

echo.
echo ======================================================================
echo [PROCESS] PROVISIONING SENSORLOGS BACKUP CHANNEL (PORT 5006)
echo ======================================================================
echo [COMMAND] netsh interface portproxy add v4tov4 listenport=5006 listenaddress=%WIFI_IP% connectport=5006 connectaddress=127.0.0.1
netsh interface portproxy add v4tov4 listenport=5006 listenaddress=%WIFI_IP% connectport=5006 connectaddress=127.0.0.1
if !errorlevel! equ 0 (
    echo [SUCCESS] Inbound traffic on %WIFI_IP%:5006 mapped -^> 127.0.0.1:5006 (WSL2)
) else (
    echo [CRITICAL ERROR] Binding statement failed for Port 5006.
)

echo.
echo ======================================================================
echo [PROCESS] PROVISIONING ROSBRIDGE WEBSOCKET SUITE PORTAL (PORT 9090)
echo ======================================================================
echo [COMMAND] netsh interface portproxy add v4tov4 listenport=9090 listenaddress=127.0.0.1 connectport=9090 connectaddress=127.0.0.1
netsh interface portproxy add v4tov4 listenport=9090 listenaddress=127.0.0.1 connectport=9090 connectaddress=127.0.0.1
if !errorlevel! equ 0 (
    echo [SUCCESS] Loopback communication matrix arming successful for port 9090.
) else (
    echo [CRITICAL ERROR] Binding statement failed for Port 9090.
)

echo.
echo ======================================================================
echo [PROCESS] VERIFYING ESTABLISHED ACTIVE PORTPROXY MAPS AFTER SETUP
echo ======================================================================
echo ----------------------------------------------------------------------
netsh interface portproxy show all
echo ----------------------------------------------------------------------

echo ======================================================================
echo [INFO] PIPELINE VERIFICATION COMPLETE. SYSTEM INGESTION LIVE.
echo [INFO] Set Mobile Endpoint Target URL to: http://%WIFI_IP%:5005/data
echo [INFO] IPWebCam Endpoint Target URL is: http://%PHONE_IP%:8080/video
echo ======================================================================