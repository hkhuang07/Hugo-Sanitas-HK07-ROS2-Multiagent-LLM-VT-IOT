# HK-07 // HUGO SANITAS — Backend Startup & Self-Healing Script
# Author: Antigravity AI Architect
# ─────────────────────────────────────────────────────────────────────────────

$ErrorActionPreference = "Stop"

# 1. Load environment variables from ../.env
if (Test-Path "../.env") {
    Write-Host ">>> [AGENT_EXECUTION]: Loading environment variables from ../.env..." -ForegroundColor Cyan
    Get-Content "../.env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and !$line.StartsWith("#") -and $line.Contains("=")) {
            $index = $line.IndexOf("=")
            $key = $line.Substring(0, $index).Trim()
            $value = $line.Substring($index + 1).Trim()
            if ($value.StartsWith('"') -and $value.EndsWith('"')) {
                $value = $value.Substring(1, $value.Length - 2)
            } elseif ($value.StartsWith("'") -and $value.EndsWith("'")) {
                $value = $value.Substring(1, $value.Length - 2)
            }
            [System.Environment]::SetEnvironmentVariable($key, $value, [System.EnvironmentVariableTarget]::Process)
        }
    }
}

# 2. Determine DB Port and Setup Config
$PORT = [System.Environment]::GetEnvironmentVariable("DB_PORT")
if (!$PORT) { $PORT = 3306 }
else { $PORT = [int]$PORT }

Write-Host ">>> [AGENT_EXECUTION]: Target DB Port: $PORT" -ForegroundColor Cyan

# 3. Check and start Database if not active
$portActive = $false
try {
    $connection = New-Object System.Net.Sockets.TcpClient("127.0.0.1", $PORT)
    $connection.Close()
    $portActive = $true
    Write-Host ">>> [AGENT_EXECUTION]: Database port $PORT is active and accepting connections." -ForegroundColor Green
} catch {
    # If using default port 3306, attempt to boot WampServer MySQL as a fallback
    $WAMP_MYSQL_DIR = "D:\wamp64\bin\mysql\mysql9.1.0"
    $MYSQLD_EXE = "$WAMP_MYSQL_DIR\bin\mysqld.exe"
    $MYSQL_EXE = "$WAMP_MYSQL_DIR\bin\mysql.exe"
    $MY_INI = "$WAMP_MYSQL_DIR\my.ini"

    if ((Test-Path $MYSQLD_EXE) -and (Test-Path $MY_INI)) {
        Write-Host ">>> [AGENT_EXECUTION]: Port $PORT is inactive. Booting local WampServer MySQL in background..." -ForegroundColor Yellow
        
        # Start mysqld as a user background process
        Start-Process -FilePath $MYSQLD_EXE -ArgumentList "--defaults-file=$MY_INI", "--console" -NoNewWindow
        
        # Wait for MySQL to boot
        Write-Host ">>> [AGENT_EXECUTION]: Waiting for MySQL port $PORT to open..." -ForegroundColor Yellow
        for ($i = 0; $i -lt 15; $i++) {
            Start-Sleep -Seconds 1
            try {
                $connection = New-Object System.Net.Sockets.TcpClient("127.0.0.1", $PORT)
                $connection.Close()
                $portActive = $true
                Write-Host ">>> [AGENT_EXECUTION]: MySQL successfully started on port $PORT!" -ForegroundColor Green
                break
            } catch {
                # Keep waiting
            }
        }
    } else {
        Write-Host ""
        Write-Host ">>> [AGENT_EXECUTION]: [ERROR] Database port 3306 is inactive." -ForegroundColor Red
        Write-Host ">>> Please start your Docker container by running this command in your WSL2/Docker shell:" -ForegroundColor Yellow
        Write-Host "    docker compose up -d hk07-mysql" -ForegroundColor Cyan
        Write-Host ""
        throw "MySQL database is not running on port 3306."
    }
}

if (!$portActive) {
    Write-Error "Failed to connect to MySQL database on port $PORT. Please ensure your database is running."
}

# 4. Initialize Database and User Credentials
$MYSQL_EXE = $null

# Option A: Check if mysql is in PATH
$cmd = Get-Command "mysql" -ErrorAction SilentlyContinue
if ($cmd) {
    $MYSQL_EXE = $cmd.Source
}

# Option B: Detect from running process on port $PORT
if (!$MYSQL_EXE) {
    $processId = (Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1).OwningProcess
    if ($processId) {
        $dbProcessPath = (Get-Process -Id $processId -ErrorAction SilentlyContinue).Path
        if ($dbProcessPath) {
            $dbDir = Split-Path -Parent $dbProcessPath
            $candidateMysql = Join-Path $dbDir "mysql.exe"
            if (Test-Path $candidateMysql) {
                $MYSQL_EXE = $candidateMysql
            }
        }
    }
}

# Option C: Fallback to local WampServer path
if (!$MYSQL_EXE) {
    $WAMP_MYSQL_DIR = "D:\wamp64\bin\mysql\mysql9.1.0"
    $candidateMysql = "$WAMP_MYSQL_DIR\bin\mysql.exe"
    if (Test-Path $candidateMysql) {
        $MYSQL_EXE = $candidateMysql
    }
}

if ($MYSQL_EXE) {
    Write-Host ">>> [AGENT_EXECUTION]: Found MySQL/MariaDB client: $MYSQL_EXE" -ForegroundColor Green
    Write-Host ">>> [AGENT_EXECUTION]: Executing db_init_local.sql on port $PORT..." -ForegroundColor Cyan
    try {
        & $MYSQL_EXE -u root -h 127.0.0.1 -P $PORT -e "source db_init_local.sql"
        Write-Host ">>> [AGENT_EXECUTION]: Database and user 'hk07user' initialized successfully." -ForegroundColor Green
    } catch {
        Write-Host ">>> [AGENT_EXECUTION]: SQL Script execution failed. Error: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host ">>> [AGENT_EXECUTION]: [WARNING] No local mysql client found. Skipping automatic db initialization." -ForegroundColor Yellow
}

# 5. Boot Spring Boot Backend
Write-Host ">>> [AGENT_EXECUTION]: Launching Spring Boot Core Engine..." -ForegroundColor Cyan
mvn spring-boot:run 
