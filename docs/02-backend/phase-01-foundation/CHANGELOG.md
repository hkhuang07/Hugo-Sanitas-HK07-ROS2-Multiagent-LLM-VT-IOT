# [STATUS: DONE] CHANGELOG — Phase 01: Foundation
**Dự án:** Hugo Sanitas HK-07  
**Phase:** 02-backend/phase-01-foundation  
**Hoàn thành:** 2026-05-31  
**Thực hiện bởi:** HK.Huang07 Hyper-Autonomous Engine

---

## Tóm tắt công việc đã hoàn thành

### Backend Core (Spring Boot 3.2 / Java 21)
- [x] `pom.xml` — Java 21, Spring Boot 3.2, Virtual Threads, -Xms256m/-Xmx512m
- [x] `HK07Application.java` — Entry point với RAM warning banner
- [x] `VirtualThreadConfig.java` — Virtual Thread executor cho Tomcat + @Async
- [x] `WebSocketConfig.java` — STOMP WebSocket cho 60Hz sensor streaming
- [x] `GlobalExceptionHandler.java` — Centralized error handling (Foundation)
- [x] `ApiResponse<T>` — Unified response wrapper cho tất cả endpoints
- [x] `HK07NotFoundException`, `HK07BusinessException` — Domain exceptions
- [x] Enums: `AgentType`, `AlertLevel`, `SystemState`, `SensorType`, `SafetyTrigger`, `UserRole`
- [x] `MqttConfig.java` — Eclipse Paho MQTT với maxInflight=10, async publish
- [x] `MqttInboundProcessor.java` — Topic router cho tất cả sensor topics
- [x] `GroqApiClient.java` — Async WebClient cho Groq API (Empathetic + Medical)
- [x] `VitalSignDto.java` — Raw vital signs from MQTT
- [x] `application.yml` — Hardware-optimized config (Hikari pool=5, log rotation 1MB)
- [x] `Dockerfile` — Multi-stage Alpine JRE, non-root user, -Xmx512m

### Python Multi-Agent Engine (FastAPI)
- [x] `main.py` — FastAPI + lifespan startup/shutdown + Volatile RAM wipe
- [x] `safety_agent.py` — Tầng 0: Deterministic LiDAR/IMU (<5ms), no LLM
- [x] `medical_agent.py` — Tầng 1: Threshold screening + Groq 70B analysis
- [x] `empathetic_agent.py` — Tầng 2: Groq 8B chat + volatile history
- [x] `arbitrator.py` — Subsumption priority: SAFETY > MEDICAL > EMPATHETIC
- [x] `lance_memory.py` — LanceDB với batch writes, max 256MB cache
- [x] `requirements.txt` — CPU-only deps (opencv-headless, mediapipe)

### Infrastructure (Docker)
- [x] `docker-compose.yml` — 5 services, total RAM budget ~615MB
- [x] `mosquitto.conf` — max_queued_messages=100, persistence=false
- [x] `init.sql` — MariaDB schema: users, health_records, agent_logs, safety_alerts

### System Design Docs
- [x] `shared/dto-definitions.md` — Java + TypeScript DTOs
- [x] `shared/enums.md` — All system enums
- [x] `backend/api-design.md` — REST + WebSocket + MQTT topology

---

## 🅜0 Foundation Hardening (2026-06-02)
Milestone bảo mật & nhất quán nền tảng (không đổi logic chức năng):
- [x] **Thống nhất DB = MariaDB** trong toàn bộ docs/diagram (gỡ nhầm lẫn PostgreSQL).
- [x] **Gỡ secret hardcode** (`DB_PASSWORD=HK040103`, MQTT password, JWT dev secret) khỏi `application.yml`, `docker-compose.yml`, agent & sensor scripts → biến môi trường.
- [x] **`.env.example`** cho backend + frontend (mọi biến đều có template, `.env` đã được gitignore).
- [x] **MQTT auth bắt buộc** — `docker-entrypoint.sh` sinh `passwd` từ `$MQTT_PASSWORD` lúc khởi động (primary + replica), `allow_anonymous false`. Đã test: auth pub/sub OK, anonymous & sai mật khẩu bị từ chối.
- [x] **Externalize frontend endpoints** — xác nhận code dùng `VITE_API_URL` / `VITE_WS_URL`, bổ sung `.env.example`.

---

## Phase tiếp theo
**Phase 02:** `docs/02-backend/phase-02-auth/` — JWT + RBAC Security Layer
