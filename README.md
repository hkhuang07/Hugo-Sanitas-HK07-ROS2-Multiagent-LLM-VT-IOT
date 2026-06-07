# ─── [ HUGO SANITAS HK-07 ROBOT COMPANION ] ───

<p align="center">
  <img src="./asset/logo.jpg" alt="HK-07 Brand Logo" height="150" style="border-radius: 8px; filter: drop-shadow(0 0 10px #00E5FF);" />
</p>

```
┌─────────────────────────────────────────────────────────────────────────┐
│  IDENTIFIER: HK.Huang07                │  VERSION: 1.0.0-ALPHA          │
│  INITIATED:  2026-05-31                │  STATUS:  OPERATIONAL          │
│  PLATFORM:   Linux / WSL2 / ROS2       │  THEME:   CYBER-CINEMATIC      │
└─────────────────────────────────────────────────────────────────────────┘
```

> **HK-07 // HUGO SANITAS** is a next-generation healthcare robot companion designed to assist elderly patients and individuals with cardiovascular conditions. The system combines multi-agent artificial intelligence, real-time vital signs telemetry, computer vision fall-detection, and a <5ms emergency safety reflex system, operating efficiently under strict hardware constraints (<615MB RAM total).

---

## 🖥️ System Interface Showcase

The interface is built using a **Cyber-Cinematic HUD** design language (True Black `#000000` base, Holographic Cyan `#00E5FF` grids, Emerald Green `#00FF66` active telemetry, and Crimson `#FF3333` alarm warnings).

--- 

### 1. AI Cognitive & Agent Systems

#### A. Empathetic AI Companion Dialogue (Uplink)
![Companion Uplink](./asset/companion-uplink.jpg)
* **Description:** Empathetic dialogue interface powered by a Groq/Gemini Multi-Agent loop. Provides psychological comfort, primary diagnostics feedback, and sentiment classification.

#### B. Multi-Agent System Logs Event Stream
![Agent System Log](./asset/agent_system_log.jpg)
* **Description:** Terminal log telemetry showing real-time thought loops, decision-making, and diagnostic logs from the `Vitals Monitor Agent`, `Emergency Agent`, and `Empathetic Agent`.

---

---
### 2. Robotics & Spatial Safety Systems

#### A. Holographic Twin & Subsumption Radar
![Holographic Twin](./asset/holographic_twin.jpg)
![Holographic Twin](./asset/holographic_twin_01.jpg)
* **Description:** A virtual 3D wireframe radar showing the physical status, sensor fields, and orientation of the robot chassis in real-time.

#### B. Safety Coordinates & Motion Inhibition Control
![Safety Coordinates](./asset/safety_cooroinates.jpg)
* **Description:** Monitors LiDAR sensor ranges, coordinates, and triggers the hard reflex inhibition system to stop motors instantly if an obstacle or fall is detected.

---

### 3. Clinical Telemetry & Patient Monitoring

#### A. Dynamic Vitals Telemetry Monitor (60FPS)
![Dynamic Telemetry](./asset/dynamic-telemetry.jpg)
* **Description:** The central operations cockpit. Renders live bio-metrics (Heart Rate, SpO2, Body Temperature, Blood Pressure) with a GPU-accelerated HTML5 Canvas displaying real-time 60Hz ECG waveforms.

#### B. Vitals History Timeline Analytics
![History Metrics](./asset/history_metric.jpg)
* **Description:** Allows operators to customize historical search ranges (From Date / To Date) to load, plot, and analyze patient physiological trends and anomalies.

---

### 4. Security & Authentication Access

#### A. Cinematic Terminal Login
![Terminal Login](./asset/auth_login.jpg)
* **Description:** A futuristic terminal-style authentication interface. Built to look like a medical/military operations control panel, prompting operators for secure system credentials.

#### B. Multi-Factor Authentication & Backup Code Verify
![Backup Code Verification](./asset/auth_by_backupcode.jpg)
* **Description:** Fallback authentication using cryptographically secure Multi-Factor Authentication (MFA) backup codes when normal authenticator tokens are unavailable.

---

### 5. Edge Vision & Environment Simulation

#### A. Robot Camera Vision (Online)
![Robot Camera Online](./asset/robot-cam-simulate.jpg)
* **Description:** Live feed simulator from the robot's onboard camera tracking its environment and path inside the Webots simulator workspace.

#### B. Robot Camera Vision (Offline / Stream Lost)
![Robot Camera Lost](./asset/robot-cam-simulate-vision-lost.jpg)
* **Description:** Safety visual state triggered when visual feed telemetry is disconnected, alerting remote operators of sensor failure.

#### C. OpenCV & MediaPipe Computer Vision Processing
![Computer Vision Processing](./asset/robot-computer-visualize.jpg)
* **Description:** Edge vision telemetry showing real-time facial feature tracking, posture coordinates, and skeletal keypoints processing for automated fall detection.

---

### 6. User Profile & Security Settings

#### A. Profile Configuration & MFA Controls
![Profile Settings](./asset/profile-settings.jpg)
* **Description:** Management control panel containing patient medical profiles, user credentials, and active configuration of MFA keys.

---

## ⚙️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│          HK-07 HUGO SANITAS — SYSTEM ARCHITECTURE           │
├─────────────────┬───────────────────┬───────────────────────┤
│  [FRONTEND]     │   [BACKEND CORE]  │   [AGENT ENGINE]      │
│  Vue 3 + Vite   │  Spring Boot 3.2  │   Python FastAPI      │
│  Port: 5173     │   Java 21 VT      │   Port: 8889          │
│  Cyber-Dark UI  │   Port: 8888      │   3 Agent Loops       │
│                 │   JWT + RBAC      │   Groq/Gemini API     │
└────────┬────────┴────────┬──────────┴──────────┬────────────┘
         │  WebSocket/REST │   MQTT/WebSocket     │ MQTT
         ▼                 ▼                      ▼
┌────────────────┐  ┌─────────────┐  ┌───────────────────────┐
│    MySQL       │  │    Redis    │  │  Eclipse Mosquitto    │
│   (Persist)    │  │  (Buffer)   │  │  MQTT Broker :1883    │
└────────────────┘  └─────────────┘  └───────────────────────┘
                                              ▲
                              ┌───────────────┴───────────────┐
                              │     SENSOR LAYER (Simulated)  │
                              │            ROS 2 Nodes        │
                              └───────────────────────────────┘
```

---

## 🛠️ Practical Problems Solved

1. **Emergency Reflex Latency (<5ms):** Bypasses standard database persistence blocks to execute critical safety scripts (e.g. stopping motors upon collision threat or triggering medical alarms) utilizing optimized MQTT pipelines.
2. **Resource Constraints Optimization:** Runs a full suite of services (Spring Boot, Python Agents, databases, and message brokers) comfortably on host systems with limited resources, budgeting total memory usage to **<615MB RAM**.
3. **Hybrid Diagnostic System:** Implements a two-layer control system. A *Hard Reflex Layer* executes static medical threshold rules to trigger immediate alerts, while a *Soft Cognitive Layer* leverages AI Agents and LLMs for contextual medical evaluation and comforting communication.
4. **Secured Real-Time Telemetry:** Secures live health streams over WebSockets via a JWT Inbound Channel Interceptor on STOMP, ensuring that only authenticated users can access real-time medical data.

---

## 📦 Directory Structure

```
hk-07/
├── asset/                  ← System screenshots and UI graphics
├── docs/                   ← Document specifications and walkthroughs
│   ├── 00-project-init/    ← Project scope, requirements, techstack setup
│   ├── 01-system-design/   ← Architecture, database design, API specs
│   ├── 02-backend/         ← Core backend manuals & changelogs
│   ├── 03-frontend/        ← UI/UX manuals & frontend specifications
│   ├── 04-testing/         ← QA check-lists & testing guides
│   ├── 05-deployment/      ← Docker configuration and production guides
│   ├── 06-evolution/       ← System upgrade specs, post-mortems, and specs
│   └── MASTER_CHANGELOG.md ← Entire project version history changelog
└── source/                 ← Target codebases
    ├── backend/
    │   ├── hk07-core/      ← Java Spring Boot core service
    │   ├── hk07-agent/     ← Python AI Multi-Agent service
    │   └── docker/         ← Infrastructure config files
    ├── frontend/
    │   └── hk07-dashboard/ ← Vue 3 Single Page Application
    ├── robotics/
    |   ├─── build/  
    |   ├─── install/  
    |   ├─── logs/  
    │   └── sensor/             ← Sensor Node run in ROS2 
    │       ├───mobile_gateway  ← Gravity sensor
    │       ├───simulation      ← Nodes in ROS2 + Bridge
    │       └───vision_sensor   ← IP WebCam  
    └── docker-compose.yml  ← Integration orchestrator
```

---

## 🚀 Quick Start Guide

The system supports two operating modes: **Docker Orchestration** (fully integrated) or **Component-by-Component Developer Mode**.

### 1. Docker Deployment Mode

```bash
# 1. Enter target backend configuration folder
cd source/backend
cp .env.example .env
# Fill in either your GROQ_API_KEY or GEMINI_API_KEY inside the .env file

# 2. Spin up the integrated container stack
docker compose up -d --build

# 3. Access endpoints
# Frontend Dashboard:  http://localhost:4205 (nginx reverse proxy)
# Backend Swagger Docs: http://localhost:8888/swagger-ui.html
# AI Agent API Docs:   http://localhost:8889/docs
```

To run localized edge simulation scripts against the Docker cluster, set the appropriate host parameters and execute:
```bash
export MQTT_BROKER_HOST=localhost
export MQTT_BROKER_PORT=1883
export MQTT_USERNAME=hk07sim
export MQTT_PASSWORD=your_configured_mqtt_password

# Launch OpenCV & MediaPipe webcam capture
python source/sensors/vision_sensor/hk07_sensor_fusion.py

# Launch Webots robotics edge driver
python source/robotics/controllers/hk07_edge_controller.py
```

---

### 2. Local Developer Mode

#### Step 0: Boot Infrastructure Databases & Broker
```bash
cd source/backend
docker compose up -d redis hk07-mysql mosquitto
```
*(Alternatively, you can run native local instances of Mosquitto broker (1883), Redis (6379), and MySQL (3306) on your machine).*

#### Step 1: Run Spring Boot Backend
```bash
cd source/backend/hk07-core
mvn clean install -DskipTests
mvn spring-boot:run
# Listening on: http://localhost:8888
```

#### Step 2: Run Python AI Multi-Agent API
```bash
cd source/backend/hk07-agent
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8889
# Listening on: http://localhost:8889
```

#### Step 3: Run Vue 3 UI Dashboard
```bash
cd source/frontend/hk07-dashboard
npm install
npm run dev
# Vite server active on: http://localhost:5173
```

#### Step 4: Deploying the Unified ROS 2 Robotics Core
To run the high-performance unified robotics node execution loop without memory leaks, open a dedicated **WSL2 Ubuntu Terminal**:

```bash
# 1. Enter the target robotics workspace
cd source/robotics

# 2. Source the global ROS 2 Humble environment
source /opt/ros/humble/setup.bash

# 3. Compile the sensors package using a clean build configuration
rm -rf build log
colcon build --packages-select sensors

# 4. Source the localized workspace installation variables
source install/setup.bash

# 5. Launch all 8 robotics nodes consolidated under a single OS thread process
ros2 run sensors hk07_runtime_orchestrator

```

---

## 💾 Hardware RAM Allocation Target

| Service Name | Limit (RAM) | Sub-System Responsibilities |
| :--- | :--- | :--- |
| **Mosquitto** | 32 MB | Real-time broker for sensor telemetry |
| **Redis** | 64 MB | In-memory token cache & rate limiter |
| **MySQL** | 256 MB | Relational medical logs & user info |
| **hk07-core** | 512 MB | Spring Boot core backend JVM |
| **hk07-agent** | 256 MB | Python multi-agent event loop |
| **TOTAL** | **~615 MB** | **Highly optimized for low-spec WSL2/Docker** |

---

## 👤 Author

* **Huỳnh Quốc Huy** (HK.Huang07)
* **Email:** [huykyunh.k@gmail.com](mailto:huykyunh.k@gmail.com)
* **GitHub:** [hkhuang07](https://github.com/hkhuang07)
* **LinkedIn:** [hkhuang07](https://www.linkedin.com/in/hkhuang07/)

---

## 📄 License

Proprietary / Closed Source — All Rights Reserved.

Copyright (c) 2026 HK.Huang07 (Hugo Sanitas Project).

This software and its associated documentation files are the sole and exclusive property of the author. Copying, modification, distribution, redistribution, publishing, or sublicensing in any form, source or binary, with or without modification, is strictly prohibited without the prior written consent of the copyright owner.
