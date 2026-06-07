# CURSOR EXECUTION PROMPT — HK-07 BAYMAX FULL CAPABILITY PROGRAM

> **Cách dùng:** Dán toàn bộ prompt này vào Cursor Agent (Composer) khi bắt đầu mỗi phiên build. Sau **mỗi Phase hoàn thành**, bắt buộc cập nhật `docs/MASTER_CHANGELOG.md` (mục §6 — Execution Log).

---

## 0. VAI TRÒ & RÀNG BUỘC

Bạn là **Lead System Architect + Robotics/Health AI Engineer** cho dự án **HK-07 Hugo Sanitas** tại repo `hk-07`.

**Bắt buộc:**
- Đọc `docs/MASTER_CHANGELOG.md` trước mọi thay đổi lớn.
- Đọc `docs/architecture/multi_agent_architecture.md`, `docs/specs/hk07_baymax_multimodal_upgrade.md`.
- Không phá **Subsumption:** `SAFETY (0) > MEDICAL (1) > EMPATHETIC (2)`; Safety Agent **không dùng LLM** cho phản xạ <5ms.
- Giữ convention: Python agents trong `source/backend/hk07-agent/`, Spring trong `source/backend/hk07-core/`, Vue trong `source/frontend/hk07-dashboard/`.
- Mỗi phase: `vue-tsc`, `py_compile`, test script simulation nếu có.
- **Sau mỗi phase:** commit message rõ ràng + cập nhật `docs/MASTER_CHANGELOG.md` §6.

**Không được:**
- Gộp mọi năng lực vào một LLM prompt duy nhất (trái MAS).
- Bỏ qua MQTT/WebSocket pipeline hiện có.
- Claim "đo neurotransmitter" bằng cảm biến giả — chỉ proxy qua HRV/stress index có disclaimer y khoa.

---

## 1. BASELINE THỰC TẾ (ĐỪNG GIẢ ĐỊNH SAI)

| Thành phần | Trạng thái trong repo |
|------------|----------------------|
| Orchestrator | `agents/agent_orchestrator.py` — **routing tuần tự** (1 agent/lượt) |
| Router | `agents/router_agent.py` — classify → MEDICAL / EMPATHY / SYSTEM |
| Safety | `agents/safety_agent.py` — LiDAR/IMU/vitals MQTT, inhibit <5ms |
| Medical | `agents/medical_agent.py` — Groq/OpenRouter JSON vitals + chat |
| Empathetic | `agents/empathetic_agent.py` — Cohere/Gemini + Baymax prompt + `execute_visual_scan` |
| Arbitrator | `arbitrator/arbitrator.py` — inhibit timer đơn giản |
| Blackboard V2 | **Chưa có file** `blackboard_service.py` — chỉ spec trong docs |
| LiDAR UI | `SafetyView` + `SafetyTelemetryService` — **đã nối MQTT/WS thật** |
| Motion | `source/robotics/controllers/hk07_edge_controller.py` — inhibit motor |
| Memory | `memory/lance_memory.py` — vector DB, **chưa ingest guideline thật** |

**Mức “thông minh” hiện tại (~35–45% Baymax cinematic):** hội thoại + rule/LLM y tế + reactive safety; **chưa** có vòng OODA đóng (quan sát → chẩn đoán → kế hoạch → **thực thi vật lý** → đánh giá).

---

## 2. KIẾN TRÚC ĐÍCH — BAYMAX MULTI-AGENT (TARGET)

```
                    ┌─────────────────────────────────────┐
                    │  SUPERVISOR / COGNITIVE ROUTER V2    │
                    │  (Tool-calling, parallel gather)     │
                    └──────────────┬──────────────────────┘
                                   │
     ┌─────────────┬───────────────┼───────────────┬─────────────┐
     ▼             ▼               ▼               ▼             ▼
 [SAFETY]    [PERCEPTION]    [MEDICAL]      [EMPATHY]    [ACTION]
  Tier 0      Tier 0.5         Tier 1         Tier 2      Tier 2
  no LLM      vision+lidar     clinical       Baymax      execute
              fusion           reasoning      voice       plans
     │             │               │               │             │
     └─────────────┴─────── BLACKBOARD (Redis) ───┴─────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │  MOTION / BALANCE / MANIP   │
                    │  (ROS2/Webots/MQTT actuators) │
                    └─────────────────────────────┘
```

**Shared Blackboard keys (TypedDict / JSON schema):**
- `ClinicalEntry`, `EmotionalState`, `PerceptionScan`, `ThreatMap`, `ActionPlan`, `ExecutionStatus`

---

## 3. MA TRẬN NĂNG LỰC BAYMAX → MODULE

| # | Năng lực Baymax | Module đích | Sensor/Input | Output |
|---|-----------------|-------------|--------------|--------|
| A | Quét cơ thể toàn thân | `PerceptionAgent` + `execute_full_body_scan` | Camera depth/RGB, pose | `PerceptionScan` JSON |
| B | Phân tích vật lý (da, tư thế, vết) | Vision pipeline | Frame buffer + vitals | findings struct |
| C | “Neurotransmitter” / stress | `MedicalAgent` extension | HRV, sleep proxy, GSR nếu có | **StressIndex** (không claim hóa học trực tiếp) |
| D | Tâm trạng / cảm xúc | `EmpatheticAgent` + sentiment | voice/text | `EmotionalState` |
| E | Phát hiện vấn đề sức khỏe | `MedicalAgent` + rules | wristband 60Hz | alert_level |
| F | Đề xuất giải pháp | `MedicalAgent` + RAG | guidelines LanceDB | `ActionPlan` |
| G | Nạp tri thức Internet | `KnowledgeIngestionService` | URL/PDF curated | embeddings |
| H | Thực hiện giải pháp | `ActionAgent` | MQTT commands | executed steps |
| I | Thăng bằng | `BalanceController` node | IMU | corrective torque cmd |
| J | Di chuyển / né vật | `NavigationAgent` + Safety | LiDAR + map | cmd_vel |
| K | Di chuyển vật thể | `ManipulationAgent` | arm/gripper sim | future phase |

---

## 4. PHASED BUILD — THỰC THI TUẦN TỰ



### PHASE ƯU TIÊN - KHÓ NHƯNG Giá TRỊ NHẤT : ĐẶC TẢ MODULE MÔ PHỎNG 3D (DIGITAL TWIN SPECIFICATION)

Khi thực thi Phase liên quan đến môi trường giả lập 3D (Holographic Simulator), Agent phải tuân thủ Tuyệt Đối các quy chuẩn sau:

1. **Tech Stack:** Sử dụng `Three.js` trực tiếp trong Component Vue (sử dụng `<canvas ref="sceneRef">`). Đảm bảo memory management tốt (xóa scene/mesh khi component unmount) để giữ mức 60 FPS.
2. **Aesthetic (Holographic HUD):** - Không sử dụng material bóng bẩy có texture thực tế (như kim loại hay nhựa). Toàn bộ vật thể phải sử dụng chất liệu Hologram (Wireframe, phát sáng, trong suốt).
   - BẮT BUỘC sử dụng `EffectComposer` và `UnrealBloomPass` để làm viền lưới của robot và mặt phẳng Grid phát sáng ánh sáng neon trên nền `Midnight Black (#000000)`.
3. **Môi trường & Tọa độ:**
   - Vẽ một `GridHelper` vô cực màu `Electric Blue (#00D2FF)` mờ ở mặt phẳng sàn (Y=0).
   - Vẽ các đường line hiển thị rõ 3 trục tọa độ Vector (X, Y, Z).
4. **Mô hình Robot (Mockup):** - Dựng một cụm (Group) gồm các khối hình học cơ bản (Box, Cylinder) giả lập các bộ phận của HK-07. Bật chế độ `wireframe: true`.
   - Cung cấp một hàm/phương thức để cập nhật vị trí `position(x, y, z)` và góc xoay `rotation(x, y, z)` của Group này thông qua Pinia State hoặc Event Listener, sẵn sàng để nối với WebSockets từ Python Backend.
5. **UI Layer (HTML overlay):** Đặt canvas 3D này phía dưới. Phía trên canvas (z-index cao hơn) là các panel chứa thông số tọa độ dạng chữ ma trận số (Matrix font) cập nhật liên tục để đúng chuẩn Cinematic Cyber.

---

### PHASE 0 — Audit & Doc sync (2h) (Completed ✅)
**Tasks:**
1. Sửa `docs/MASTER_CHANGELOG.md` §1.2: phân biệt **Implemented (v1)** vs **Planned (v2)**.
2. Tạo `docs/architecture/baymax_capability_matrix.md` từ bảng §3.

**Acceptance:** Không còn reference file không tồn tại mà không ghi chú.

---

### PHASE 1 — Blackboard + Orchestrator V2 (12–16h) (Completed ✅)
**Files tạo/sửa:**
- `source/backend/hk07-agent/services/blackboard_service.py`
- `source/backend/hk07-agent/agents/agent_orchestrator_v2.py`
- `source/backend/hk07-agent/agents/router_agent_v2.py`
- `source/backend/hk07-agent/main.py` — feature flag `USE_ORCHESTRATOR_V2=true`
- `source/backend/hk07-core/.../AgentDebugController.java` — `GET /api/v1/agents/blackboard/inspect`

**Tools (function calling schema):**
1. `analyze_clinical_symptoms`
2. `speak_empathetic_response`
3. `search_medical_guidelines`
4. `trigger_sos_protocol`
5. `execute_visual_scan` (wrap existing)
6. `execute_environment_scan` (LiDAR snapshot từ blackboard)

**Logic:**
- Medical **ghi** `ClinicalEntry` trước khi Empathy đọc.
- `asyncio.gather` khi router chọn multi-tool (vd: đau ngực + sợ).
- Timeout router 2.5s; Redis blackboard TTL theo alert level.

**Tests:** `test_orchestrator_v2.py` E2E 4 kịch bản.

**CHANGELOG:** Ghi Phase 1 ✅ + file list.

---

### PHASE 2 — Perception Agent (Full Scan) (10–14h) (Completed ✅)
**Files:**
- `agents/perception_agent.py`
- `services/sensor_fusion_buffer.py` — ring buffer camera + vitals + lidar
- `scripts/hk07_sensor_fusion.py` (nếu chưa có)

**API:**
- `POST /api/v1/agents/perception/scan` → trigger full scan
- Tool `execute_full_body_scan` → Vision model + structured output:

```json
{
  "skin_tone_note": "string",
  "facial_distress": 0.0,
  "visible_injuries": [],
  "posture_risk": "LOW|MED|HIGH",
  "confidence": 0.0
}
```

**Baymax rule:** Perception **không** nói chuyện với user — chỉ ghi Blackboard.

**Frontend:** `CompanionView` — nút "Quét toàn thân" + hiển thị kết quả struct.

---

### PHASE 3 — Medical Depth + Stress Proxy (8–10h) (Completed ✅)
**Tasks:**
1. `MedicalAgent` thêm `compute_stress_index(vitals_history)` — HRV SDNN proxy, không gọi là "dopamine/serotonin".
2. Kết hợp `PerceptionScan` + vitals → `ClinicalEntry` đa modal.
3. Dynamic thresholds từ `MedicalThresholdController` (đã có Java).

**Output JSON mở rộng:**
```json
{
  "alert_level": "...",
  "clinical_summary": "...",
  "stress_index": { "score": 0, "label": "CALM|ANXIOUS|ELEVATED", "disclaimer": "..." },
  "recommended_actions": ["..."]
}
```

---

### PHASE 4 — RAG / Internet Knowledge (10–12h) (Completed ✅)
**Files:**
- `services/knowledge_ingestion.py` — ingest PDF/URL (allowlist domains: WHO, CDC, MoH VN)
- `scripts/ingest_medical_guidelines.py`
- Tool `search_medical_guidelines` — LanceDB hybrid search

**Không scrape tự do** — chỉ nguồn whitelist + chunk + cite source trong response.

---

### PHASE 5 — Action Agent (Đề xuất → Thực thi) (12–16h) (Completed ✅)
**Files:**
- `agents/action_agent.py`
- `ActionPlan` schema: steps `[{ type, mqtt_topic, payload, requires_confirm }]`

**Hành động cho phép MVP:**
- `SAFE_HOLD` / `RESUME` (đã có RobotCommandService)
- `SOS_DISPATCH`
- `REMINDER_MEDICATION` (log + notify)
- `NAVIGATE_TO` (mock waypoint MQTT)
- `SPEAK_MESSAGE` (TTS event)

**Safety gate:** ActionAgent **không** chạy nếu `Arbitrator.is_inhibited` hoặc Safety CRITICAL.

**Frontend:** Modal xác nhận trước step nguy hiểm.

---

### PHASE 6 — Balance & Navigation Agents (14–18h) (Completed ✅)
**Files:**
- `source/robotics/nodes/balance_controller.py` — PID từ IMU `hk07/sensors/imu/state`
- `source/robotics/nodes/navigation_agent.py` — local planner + LiDAR costmap
- Publish `hk07/control/motion/cmd_vel` (định nghĩa topic trong `MqttConfig`)

**Integration:**
- Safety override luôn thắng.
- Webots `hk07_edge_controller.py` subscribe cmd_vel.

**Tests:** `run_full_simulation.sh` + obstacle + fall scripts.

---

### PHASE 7 — Proactive Baymax (8h) (Completed ✅)
**Spec:** `docs/specs/hk07_baymax_multimodal_upgrade.md` Mũi nhọn 2.

**Tasks:**
1. [x] Medical loop MQTT → nếu CRITICAL → emit `AI_EMERGENCY_WAKEUP` qua agent-events WS.
2. [x] Frontend modal countdown SOS (đã có skeleton `App.vue` — wire đầy đủ).
3. [x] Empathy proactive message khi stress_index tăng 3 lần liên tiếp.

---

### PHASE 8 — Voice UI (6–8h) (Completed ✅)
**Frontend:**
- [x] Web Speech API push-to-talk `CompanionView`
- [x] SpeechSynthesis đọc câu trả lời Empathy (giọng trầm ấm)

**Backend:** optional STT proxy nếu browser không đủ.

---

### PHASE 9 — Manipulation (FUTURE / OPTIONAL)
- Chỉ sau Navigation ổn định.
- Gripper sim Webots + `ManipulationAgent`.

---

### PHASE 16 — ROS 2 Migration & DDS Integration (Completed ✅)
- Convert `sensors/` to a valid ROS2 Python package (add `setup.py`, `package.xml`).
- Refactor simulator scripts into ROS2 `rclpy` Nodes.
- Set up middle bridge node to link ROS2 DDS with MQTT.

---

### PHASE 17 — Clinical Depth & Multimodal Blackboard Integration (Completed ✅)
- Add Dynamic Threshold configuration from Spring Boot.
- Implement HRV Stress Index calculator.
- Integrate multimodal Blackboard diagnostics in Medical Agent.

---

### PHASE 18 — OpenCV rPPG & Thermal Vision Simulation & Integration (Completed ✅)
- Publish simulated thermal forehead temperature and rPPG heart rates to ROS 2 topics.
- Bridge topics to MQTT and Spring Boot WebSocket STOMP.
- Bind store data and display real-time forehead scans on Vue companion view.

---

### PHASE 19 — Local Edge LLM Fallback (Zero-Dependency) (Completed ✅)
- Implement `LocalOfflineFallback` engine inside `LLMClient`.
- Filter keywords for clinical concerns, greetings, and system status checks.
- Handle unaccented Vietnamese search queries and conceptual vs hardware queries.

---

### PHASE 20 — Clinical EHR / FHIR Standard Gateway (Completed ✅)
- Implement `FhirGatewayService` to format clinical entries to HL7 FHIR Observation & Condition schemas.
- Standardize REST and WebSocket data exchanges in the middleware.

---

### PHASE 21 — RTOS Fail-Safe Watchdog Simulation (Completed ✅)
- Develop a ROS 2 hardware watchdog simulating an ESP32 co-processor.
- Set relief actuator command if primary OS/middleware heartbeat fails.

---

### PHASE 22 — Real-Vision Integration & Quantized Edge SLM (Completed ✅)
- Integrate OpenCV + MediaPipe face detection to isolate cheek/forehead ROI for green-channel average BVP.
- Implement llama-cpp-python lazy-loaded GGUF models fallback engine in `llm_client.py`.
- Formulate system/user prompts with Phi-3 and Llama-3 instruct templates for text completion and structured JSON tool calls fallback.
- Run integration tests covering the local SLM path and rule-based fallback matrix.

---

## 5. TIÊU CHÍ HOÀN THÀNH TỪNG PHASE

| Phase | Metric |
|-------|--------|
| 1 | 4 tool parallel + blackboard inspect API |
| 2 | Full scan JSON + UI button |
| 3 | stress_index + multimodal ClinicalEntry |
| 4 | ≥50 chunks guideline searchable |
| 5 | ActionPlan execute ≥3 action types |
| 6 | Robot né obstacle trong Webots demo |
| 7 | Wakeup event <2s từ vitals CRITICAL |
| 8 | Voice round-trip demo |

---

## 6. QUY TRÌNH LÀM VIỆC TRONG CURSOR

1. **Đọc** `MASTER_CHANGELOG.md` §6 — xác định phase tiếp theo chưa ✅.
2. **Implement** đúng một phase — không nhảy phase.
3. **Chạy:**
   ```bash
   cd source/frontend/hk07-dashboard && npm run type-check
   python -m py_compile source/backend/hk07-agent/agents/*.py
   ```
4. **Test simulation:**
   ```bash
   python source/robotics/simulation/lidar_scan_publisher.py
   python source/robotics/simulation/trigger_obstacle.py
   python source/backend/hk07-agent/test_orchestrator_v2.py
   ```
5. **Cập nhật** `docs/MASTER_CHANGELOG.md`:

```markdown
### §6 Execution Log
| Date | Phase | Summary | Files |
|------|-------|---------|-------|
| YYYY-MM-DD | 1 | Blackboard + Orch V2 | ... |
```

6. Báo cáo user: gap đã đóng, % Baymax ước lượng, bước tiếp theo.

---

## 7. PROMPT KÍCH HOẠT NHANH (COPY 1 DÒNG)

```
Đọc docs/MASTER_CHANGELOG.md §6 và docs/prompts/CURSOR_BAYMAX_FULL_SYSTEM_BUILD.md — thực hiện Phase tiếp theo chưa hoàn thành, tuân Subsumption, cập nhật changelog khi xong. Phải dùng tư duy của một Software Architechture,Robotics Architechture, Frontend Designer, AI Engineer và Medical Device Engineer để triển khai một cách tối ưu, hiệu suất cao có khả năng mở rộng cao mà không khắc phục chắp vá hay tối ưu tạm bợ. 
```

---

**Document version:** 1.0  
**Created:** 2026-06-03  
**Owner:** HK-07 Architecture

