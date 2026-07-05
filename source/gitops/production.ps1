# production.ps1
# HK-07 Multi-Agent Production Orchestrator
# Builds frontend, packages core backend jar, and launches production instances.

$ErrorActionPreference = "Stop"

# Resolve absolute path of project root (2 levels up from source/gitops)
$ProjectRoot = (Get-Item "$PSScriptRoot\..\..").FullName
$RoboticsPath = "$ProjectRoot\source\robotics"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host ">>> [GITOPS] Launching HK-07 Multi-Agent System (PROD)  " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# ── STEP 1: Build Frontend Assets ─────────────────────────────────────────────
Write-Host ">>> [BUILD] Building Frontend production assets..." -ForegroundColor Yellow
Set-Location "$ProjectRoot\source\frontend\hk07-dashboard"
npm install
npm run build

# ── STEP 2: Compile & Package Java Spring Boot Core Jar ────────────────────────
Write-Host ">>> [BUILD] Packaging Spring Boot Core Core Backend Jar..." -ForegroundColor Yellow
Set-Location "$ProjectRoot\source\backend\hk07-core"
mvn clean package -DskipTests

# ── STEP 3: Clean up stale processes before launching ─────────────────────────
Write-Host ">>> [PRE-FLIGHT] Cleaning up running ports and processes..." -ForegroundColor Yellow
if (Test-Path "$ProjectRoot\source\gitops\clean-env.bat") {
    & "$ProjectRoot\source\gitops\clean-env.bat" | Out-Null
}

$ErrorActionPreference = "SilentlyContinue"

# ── TERMINAL 1: Run Spring Boot production Jar ───────────────────────────────
Write-Host ">>> [T1] Launching packaged Spring Boot Jar..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "
    Set-Location '$ProjectRoot\source\backend\hk07-core';
    Write-Host '>>> [T1] Starting production Jar instance...' -ForegroundColor Green;
    java -jar target/hk07-core-0.0.1-SNAPSHOT.jar
"

# ── TERMINAL 2: WSL Rosbridge ─────────────────────────────────────────────────
Write-Host ">>> [T2] Launching WSL ROS2 Rosbridge server..." -ForegroundColor Cyan
Start-Process wsl.exe -ArgumentList "--cd", "`"$RoboticsPath`"", "bash", "-c", "`"source /opt/ros/humble/setup.bash && rm -rf ~/.ros/log/* && ros2 launch rosbridge_server rosbridge_websocket_launch.xml default_call_service_timeout:=5.0 call_services_in_new_thread:=true send_action_goals_in_new_thread:=true; exec bash`""

# ── TERMINAL 3: WSL Sensors Orchestrator ──────────────────────────────────────
Write-Host ">>> [T3] Launching WSL ROS2 Sensors Orchestrator..." -ForegroundColor Cyan
Start-Process wsl.exe -ArgumentList "--cd", "`"$RoboticsPath`"", "bash", "-c", "`"source /opt/ros/humble/setup.bash && source install/setup.bash && ros2 run sensors hk07_runtime_orchestrator; exec bash`""

# ── TERMINAL 4: FastAPI Agent (Production mode) ───────────────────────────────
Write-Host ">>> [T4] Launching FastAPI Agent Engine..." -ForegroundColor Green
Start-Process cmd -ArgumentList "/k", "
    cd /d $ProjectRoot\source\backend\hk07-agent && python main.py
"

# ── RUN FRONTEND PREVIEW IN CURRENT TERMINAL ──────────────────────────────────
Write-Host "--------------------------------------------------------" -ForegroundColor White
Write-Host ">>> [SUCCESS] Production build completed and backends running." -ForegroundColor Green
Write-Host ">>> [FINAL] Serving production built frontend (npm run preview) in this terminal..." -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

Set-Location "$ProjectRoot\source\frontend\hk07-dashboard"
npm run preview
