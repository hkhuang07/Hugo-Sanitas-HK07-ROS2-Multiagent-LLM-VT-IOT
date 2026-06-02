# [STATUS: DONE] MASTER CHANGELOG — Phase 02 → 07 + Robotics
**Dự án:** Hugo Sanitas HK-07
**Thực hiện:** 2026-05-31 — HYPER-AUTONOMOUS ENGINE CYCLE 2

---

## Backend (Phase 02 → 07)

### Phase 02 — Auth & JWT
- [x] `UserEntity.java` — JPA entity với UUID, role, timestamps
- [x] `WristbandConfigEntity.java` — BLE device config với MQTT topic + thresholds
- [x] `UserRepository.java`, `WristbandConfigRepository.java`
- [x] `AuthDto.java` — LoginRequest, RegisterRequest, RefreshRequest, TokenResponse
- [x] `AuthService.java` — Login + Register + Refresh Token rotation (Redis TTL)
- [x] `AuthController.java` — `/api/v1/auth/login|register|refresh|logout|ping`

### Phase 03 — User Management
- [x] `UserDto.java`, `WristbandConfigDto.java`
- [x] `UserService.java` — getById, updateDisplayName, upsertWristbandConfig (MQTT topic validation)
- [x] `UserController.java` — `/api/v1/users/me`, `/me/wristband`

### Phase 04 — Health Pipeline
- [x] `HealthRecordEntity.java` — Denormalized vitals + AI analysis + AlertLevel
- [x] `HealthRecordRepository.java` — Latest vital query, active alerts filter
- [x] `HealthService.java` — MQTT→threshold→DB→WebSocket pipeline at 60Hz on Virtual Threads
  - Fast arithmetic threshold check (no LLM at 60Hz)
  - Persist only WARNING+ records (protects DB under load)
  - Broadcasts `VitalSignWithAlertDto` via STOMP to `/topic/vitals`
- [x] `HealthController.java` — `/api/v1/health/vitals/latest`, `/alerts/active`

### Phase 05-06 — Safety + Agent Entities
- [x] `SafetyAlertEntity.java` — responseTimeMs field for < 5ms SLA tracking
- [x] `AgentLogEntity.java` — Full audit trail per agent decision

### Phase 07 — Robot Command
- [x] `RobotCommandController.java` — `/api/v1/robot/state|hold|resume|shutdown` (RBAC)
- [x] `RobotCommandService.java` — AtomicReference SystemState (thread-safe Virtual Thread)

---

## Robotics (source/robotics/)

- [x] `ros2_nodes/safety_lidar_node.py` — 360° LiDAR mock at 10Hz, injects obstacles for SafetyAgent testing
- [x] `ros2_nodes/motion_controller.py` — Subsumption inhibit subscriber, < 5ms response timing, prints Webots-compatible CMD_VEL
- [x] `mock_sensors/wristband_simulator.py` — Cycles NORMAL→WARNING→CRITICAL→STROKE scenarios for full pipeline test

---

## Frontend (FE-02 → FE-07)

### Stores (Pinia)
- [x] `stores/vitals.ts` — Pre-allocated ring buffer (120 frames), no GC at 60Hz
- [x] `stores/agents.ts` — Event log (max 100 entries), agentStatus, subsumptionActive
- [x] `stores/auth.ts` — JWT tokens + localStorage persistence + role computed flags

### Services
- [x] `services/websocket.ts` — STOMP singleton with exponential backoff, routes to Pinia
- [x] `services/api.ts` — Axios with JWT interceptor + 401 → event dispatch

### Views
- [x] `DashboardView.vue` — Full rewrite using Pinia stores, WebSocket service, ECG ring buffer
- [x] `AgentsView.vue` — 3-agent live thought stream, Subsumption panel, event ticker
- [x] `SafetyView.vue` — Rotating 60FPS radar canvas, SLA latency meter, alert history

### Config
- [x] `tsconfig.json`, `tsconfig.node.json`
- [x] `.env.example`

---

## Cycle 3 — Data Closure & History (Phase 08-09)

### Phase 08 — Flyway Migrations
- [x] Deleted raw `init.sql`.
- [x] `V1__init_schema.sql`: Full schema with constraints and minimal indexes (128MB RAM tuned).
- [x] `V2__seed_data.sql`: Default OWNER account with BCrypt hash and demo safety alert.
- [x] `V3__views_and_missing_columns.sql`: Added `device_id`, `spo2_min`, and `v_health_hourly_summary` view.
- [x] Configured `application.yml` and `pom.xml` for Flyway.

### Phase 09 — Agent Log Pipeline
- [x] `AgentLogRepository`, `AgentLogService`, `AgentLogController` for REST-based agent log ingestion.
- [x] `agent_log_client.py`: Python async batching HTTP client with JWT auth (fire-and-forget).
- [x] Integrated `log_agent_decision` into `MedicalAgent`, `EmpathyAgent`, and `SafetyAgent`.

### Frontend — History & Alerts
- [x] `HealthHistoryView.vue`: Chart.js timeline with LTTB decimation (SpO2/BP/HR) and Hourly distribution.
- [x] `NotificationToast.vue`: Cyber-cinematic global toast notifications driven by WebSocket events.
- [x] Updated `App.vue` and `router/index.ts` to mount new components.

### Testing Scripts
- [x] `trigger_heart_attack.py`: Simulates critical vital signs via MQTT.
- [x] `trigger_obstacle.py`: Simulates LiDAR obstacle for <5ms Subsumption test.
- [x] `run_full_simulation.sh`: Orchestrates all nodes and the FastAPI agent engine.

---

## Cycle 4 — Simulation & Full Integration (Phase 10)

### Phase 10 — Robotics & Simulation
- [x] `webots_edge_controller.py`: Webots Python API controller running in headless mode (`--mode=fast`) to save RAM. Pushes Lidar/IMU to MQTT and subscribes to velocity/inhibit commands.
- [x] `hk07_demo.wbt`: World setup with HK-07 robot model (Differential drive, Lidar, IMU).

### Frontend — Login & Security
- [x] `LoginView.vue`: Cyber-cinematic hacker terminal boot sequence.
- [x] `stores/auth.ts`: Replaced `localStorage` with in-memory JWT storage for maximum security.
- [x] `services/api.ts`: Implemented 401 interceptor for silent token refresh without disrupting the user.

### DevOps & Deployment
- [x] `Dockerfile` (Frontend): Multi-stage Vite build into an Alpine Nginx container.
- [x] `nginx.conf`: Proxies `/api` and `/ws` to the Spring Boot core, handles Vue history mode routing.
- [x] `docker-compose.yml`: Fully unified deployment script. Launches Mosquitto, Redis, MariaDB, Spring Boot Core, Python Agent Engine, Vue Dashboard (Nginx), and Headless Webots Simulation with a single command.

## System Evolution & Red Teaming (Auto-Patching)
**Thực thi:** 2026-05-31 — EVOLUTION PROTOCOL

- **Memory Leaks Fixed:** Bổ sung cờ `isUnmountedFlag` trong `DashboardView.vue` và `SafetyView.vue` để hủy bỏ vòng lặp `requestAnimationFrame` ảo, chống rò rỉ rác (Ghost Loop) khi chuyển trang.
- **Race Condition & API Bottleneck Mitigated:** `agent_log_client.py` hiện tại sử dụng `asyncio.gather()` để bắn đồng thời các REST logs theo batch thay vì bắn tuần tự (sequence loop), không làm nghẽn luồng xử lý chính.
- **Message Flooding Protection:** Áp dụng thuật toán Debounce/Throttling:
  - `SafetyAgent.py`: Hạn chế tần số xử lý LiDAR và IMU xuống tối đa 20Hz (50ms) để bảo vệ luồng Subsumption khỏi Spam.
  - `HealthService.java`: Bổ sung `ConcurrentHashMap` throttle ở mức 60Hz (~16ms) trên mỗi device ID, ngăn chặn MQTT flood làm tràn RAM (OOM) của Virtual Threads.

---
**[PROJECT STATUS]: 100% COMPLETE & ROBUST.**
