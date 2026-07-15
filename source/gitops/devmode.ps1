# devmode.ps1
# HK-07 Multi-Terminal Developer Orchestrator
# Launches 5 terminals in development mode with specific colors and environments.

$ErrorActionPreference = "SilentlyContinue"

# Resolve absolute path of project root (2 levels up from source/gitops)
$ProjectRoot = (Get-Item "$PSScriptRoot\..\..").FullName
Write-Host $ProjectRoot -ForegroundColor Cyan
$RoboticsPath = "$ProjectRoot\source\robotics"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ">>> [GITOPS] Launching HK-07 Multi-Agent System (DEV)   " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# ── STEP 1: PRE-FLIGHT CLEANUP (Synchronous) ──────────────────────────────────
Write-Host ">>> [1/5] Executing pre-flight environment cleanup..." -ForegroundColor Yellow
if (Test-Path "$ProjectRoot\source\gitops\clean-env.bat") {
    Start-Process cmd.exe -ArgumentList "/c", "cd /d $ProjectRoot\source\gitops && clean-env.bat" -NoNewWindow -Wait
}

# ── STEP 2: NETWORK CONFIGURATION (Synchronous) ──────────────────────────────
Write-Host ">>> [2/5] Running Network Configuration..." -ForegroundColor Yellow
if (Test-Path "$ProjectRoot\source\gitops\setup_network.bat") {
    Start-Process cmd.exe -ArgumentList "/c", "cd /d $ProjectRoot\source\gitops && setup_network.bat" -NoNewWindow -Wait
}

# ── STEP 3: SPAWN BACKENDS IN BACKGROUND WINDOWS ──────────────────────────────

# ── WSL Rosbridge (Blue: 0000EE) ──
Write-Host ">>> [3/5] Starting WSL Rosbridge Websocket..." -ForegroundColor Cyan
Start-Process wsl.exe -ArgumentList "--cd", "`"$RoboticsPath`"", "bash", "-c", "`"echo -e '\\e[38;2;0;0;238m' && source /opt/ros/humble/setup.bash && rm -rf ~/.ros/log/* && ros2 launch rosbridge_server rosbridge_websocket_launch.xml default_call_service_timeout:=5.0 call_services_in_new_thread:=true send_action_goals_in_new_thread:=true; exec bash`""

# ── Spring Boot Core (Powershell Windows) ──
Write-Host ">>> [4/5] Starting Spring Boot Core Backend..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$ProjectRoot\source\backend\hk07-core';
    Write-Host '>>> [T2] Running Spring Boot Core (Maven)...' -ForegroundColor Green;
    mvn clean spring-boot:run
"

# ── WSL Sensors Orchestrator (Alice Blue: F0F8FF) ──
Write-Host ">>> [5/5] Starting WSL ROS2 Sensors Orchestrator..." -ForegroundColor Cyan
Start-Process wsl.exe -ArgumentList "--cd", "`"$RoboticsPath`"", "bash", "-c", "`"echo -e '\e[38;2;240;248;255m' && rm -rf log/ && source /opt/ros/humble/setup.bash && colcon build --packages-select sensors --symlink-install && source install/setup.bash && ros2 run sensors hk07_runtime_orchestrator; exec bash`""

# ── FastAPI Agent (WSL via PowerShell) ──
Write-Host ">>> [6/5] Starting FastAPI Agent Engine (WSL)..." -ForegroundColor White
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    wsl --cd `"$ProjectRoot\source\backend\hk07-agent`" bash -c 'python3 main.py; exec bash'
"

# ── STEP 4: RUN FRONTEND IN CURRENT TERMINAL ──────────────────────────────────
Write-Host "--------------------------------------------------------" -ForegroundColor Cyan
Write-Host ">>> [SUCCESS] All backend systems spawned." -ForegroundColor Green
Write-Host ">>> [FINAL] Starting Frontend Server (npm run dev) in this terminal..." -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

Set-Location "$ProjectRoot\source\frontend\hk07-dashboard"
npm run dev
