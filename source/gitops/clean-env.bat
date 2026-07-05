@echo off
setlocal enabledelayedexpansion
title HK-07 ENVIRONMENT AUDIT AND PURGE

echo ======================================================================
echo [PROCESS] VERIFYING PRIVILEGES FOR ENVIRONMENT AUDIT...
echo ======================================================================
net session >nul 2>&1
if %errorLevel% equ 0 (
    echo [SUCCESS] Administrator privileges confirmed.
    set "IS_ADMIN=1"
) else (
    echo [WARNING] Running as non-administrator. Port proxy reset will be skipped.
    echo Please run as Administrator for complete cleanup.
    set "IS_ADMIN=0"
)
echo.

echo ======================================================================
echo [PROCESS] CHECKING BACKEND INFRASTRUCTURE STACK...
echo ======================================================================
where wsl >nul 2>&1
if !errorlevel! equ 0 (
    echo [INFO] Checking running Docker containers in WSL...
    wsl docker ps --filter name=hk07
) else (
    echo [INFO] WSL not found. Skipping WSL docker check.
)
echo.
echo [INFO] Checking active ports 3306, 6379, 1883, 11434...
netstat -aon | findstr /C:":3306 " /C:":6379 " /C:":1883 " /C:":11434 "
echo.

echo ======================================================================
echo [PROCESS] AUDITING ^& CLEANING WINDOWS LOCAL PORTS...
echo ======================================================================
echo [INFO] Keeping WSL Docker Compose containers running per policy.
echo [INFO] Purging native Windows processes on ports 3306, 6379, 1883, 11434...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /C:":3306 " /C:":6379 " /C:":1883 " /C:":11434 "') do (
    set "PID_TO_KILL=%%a"
    if not "!PID_TO_KILL!"=="0" (
        set "PROC_NAME="
        for /f "tokens=1" %%b in ('tasklist /FI "PID eq !PID_TO_KILL!" /NH 2^>NUL') do (
            set "PROC_NAME=%%b"
        )
        if /I "!PROC_NAME:~0,3!"=="wsl" (
            echo [SKIP] Port proxy handled by WSL2: !PROC_NAME!. Skipping taskkill.
        ) else if not "!PROC_NAME!"=="" (
            echo [KILL] Terminating native process !PROC_NAME! with PID !PID_TO_KILL!...
            taskkill /F /PID !PID_TO_KILL! 2>NUL
        )
    )
)
echo.

echo ======================================================================
echo [PROCESS] AUDITING ^& CLEANING HK07-CORE (SPRING BOOT - PORT 8888)...
echo ======================================================================
netstat -aon | findstr /C:":8888 "
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /C:":8888 "') do (
    set "PID_TO_KILL=%%a"
    if not "!PID_TO_KILL!"=="0" (
        set "PROC_NAME="
        for /f "tokens=1" %%b in ('tasklist /FI "PID eq !PID_TO_KILL!" /NH 2^>NUL') do (
            set "PROC_NAME=%%b"
        )
        if /I "!PROC_NAME:~0,3!"=="wsl" (
            echo [SKIP] Port 8888 proxy handled by WSL2: !PROC_NAME!. Skipping taskkill.
        ) else if not "!PROC_NAME!"=="" (
            echo [KILL] Terminating Spring Boot process !PROC_NAME! with PID !PID_TO_KILL!...
            taskkill /F /PID !PID_TO_KILL! 2>NUL
        )
    )
)
taskkill /F /IM java.exe 2>NUL
echo.

echo ======================================================================
echo [PROCESS] AUDITING ^& CLEANING HK07-AGENT (FASTAPI - PORT 8889)...
echo ======================================================================
netstat -aon | findstr /C:":8889 "
for /f "tokens=5" %%a in ('netstat -aon ^| findstr /C:":8889 "') do (
    set "PID_TO_KILL=%%a"
    if not "!PID_TO_KILL!"=="0" (
        set "PROC_NAME="
        for /f "tokens=1" %%b in ('tasklist /FI "PID eq !PID_TO_KILL!" /NH 2^>NUL') do (
            set "PROC_NAME=%%b"
        )
        if /I "!PROC_NAME:~0,3!"=="wsl" (
            echo [SKIP] Port 8889 proxy handled by WSL2: !PROC_NAME!. Skipping taskkill.
        ) else if not "!PROC_NAME!"=="" (
            echo [KILL] Terminating FastAPI Agent process !PROC_NAME! with PID !PID_TO_KILL!...
            taskkill /F /PID !PID_TO_KILL! 2>NUL
        )
    )
)
taskkill /F /IM python.exe 2>NUL
echo.

echo ======================================================================
echo [PROCESS] AUDITING ^& CLEANING ROBOTICS (WSL2 / ROS2 / PORT PROXY)...
echo ======================================================================
if %IS_ADMIN% equ 1 (
    echo [INFO] Resetting Port Proxies...
    netsh interface portproxy reset
)
where wsl >nul 2>&1
if !errorlevel! equ 0 (
    echo [INFO] Killing WSL ROS2 and Python nodes...
    wsl pkill -f rosbridge 2>NUL
    wsl pkill -f python3 2>NUL
    wsl rm -rf ~/.ros/log/* 2>NUL
)
if exist "%~dp0..\robotics\log" (
    echo [INFO] Removing local robotics build logs...
    rmdir /s /q "%~dp0..\robotics\log" 2>NUL
)
echo.

echo ======================================================================
echo [PROCESS] RUNNING NETWORK TUNNEL AUTOMATION (setup_network.bat)...
echo ======================================================================
if exist "%~dp0setup_network.bat" (
    call "%~dp0setup_network.bat"
) else (
    echo [ERROR] setup_network.bat not found.
)
echo.

echo ======================================================================
echo [SUCCESS] ENVIRONMENT WIPE AND SYSTEM RE-PROVISIONING COMPLETE.
echo ======================================================================

endlocal
