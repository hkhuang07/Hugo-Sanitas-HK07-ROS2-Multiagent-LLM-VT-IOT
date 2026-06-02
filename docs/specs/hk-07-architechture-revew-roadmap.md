# HK-07 // HUGO SANITAS — BÁO CÁO REVIEW KIẾN TRÚC & ĐỀ XUẤT ROADMAP

> **Vai trò:** Chief System Architect (Cascade)
> **Repo:** hkhuang07/Hugo-Sanitas-HK07-ROS2-Multiagent-LLM-VT-IOT
> **Ngày:** 2026-06-02 · **Phạm vi:** Read-only audit (`docs/` + `source/`)

---

## BƯỚC 1 — DOCS DISCOVERY (Đã quét)

**Tài liệu kiến trúc cốt lõi đã đọc:**
- `project-requirement.md` (PRD — Hyper-Drive Edition)
- `docs/architecture/multi_agent_architecture.md` (MAS Standard: Router + 3 Agents + Arbitrator)
- `docs/analysis/system_analysis_and_limitations.md` (20 hạn chế kỹ thuật)
- `docs/06-evolution/ARCHITECTURE_CRITIQUE.md` (Red-teaming: memory leak, race, flooding)
- `docs/MASTER_CHANGELOG.md` (Phase 02→10, trạng thái khai báo: 100% COMPLETE)
- `docs/specs/`: auth_upgrade_v2, baymax_multimodal_upgrade, cognitive_upgrade, identity_medical_profile
- `README.md` / `README_VI.md`, `CLAUDE.md`

**Cấu trúc `source/` (đã đối chiếu với docs):**
```
source/backend/hk07-core      → Spring Boot 3.2 / Java 21 VT (54+ file Java, 7 Flyway migrations)
source/backend/hk07-agent     → Python FastAPI Multi-Agent (router/safety/medical/empathy + arbitrator + LanceDB)
source/frontend/hk07-dashboard→ Vue 3 + Vite + TS (8 views, 3 Pinia stores, STOMP service)
source/robotics               → ROS2 mock nodes, Webots edge controller, trigger scripts
source/sensors                → vision_sensor (OpenCV+MediaPipe), mobile_gateway (vivo HTTP→MQTT bridge)
source/backend/docker         → Mosquitto + docker-compose (MariaDB, Redis, 2x Mosquitto, core, agent, dashboard)
```
=> **Kết luận đối chiếu:** Code thực tế **khớp cao** với docs. Nhiều "hạn chế" trong analysis đã được vá trong code (vd: LanceDB compaction #15, throttle, `asyncio.gather`).

---

## BƯỚC 2 — CURRENT STATE ANALYSIS

### 2.1. Module/Tính năng đã hoàn thiện
- **Auth & IAM:** JWT + RBAC (Owner/Medic/Guest), Silent Refresh (HttpOnly cookie), Recovery Codes, Change/Forgot password.
- **Identity & Medical Profile:** Onboarding wizard, hồ sơ y tế CRUD, đồng bộ vào "trí nhớ" AI (LanceDB) — migration `V7`.
- **Health Pipeline:** MQTT → threshold check (60Hz, no-LLM) → MariaDB (batch) → STOMP `/topic/vitals`; persist WARNING+; throttle theo device.
- **Safety / Subsumption:** SafetyAgent (no-LLM, <5ms), `RobotCommandService` (AtomicReference state), `EmergencyController`, SafetyAlert có `responseTimeMs` (SLA tracking).
- **Multi-Agent Cognitive Engine:** Router (HF BART zero-shot → Groq → rule-based fallback) + Medical + Empathetic + Arbitrator; State `TypedDict`; agent-log fire-and-forget (REST, async batch).
- **RAG Memory:** LanceDB embedded, compaction nền (xóa vector >24h), giới hạn 256MB.
- **Frontend Dashboard:** Vitals (ECG canvas 60FPS), Companion chat, Agents log stream, Safety radar, Health history (Chart.js + LTTB), Login terminal, Profile settings, Notification toast.
- **Observability/Audit:** `AuditLogEntity` + `AuditService`, Medical thresholds động (`V4`).
- **Simulation & DevOps:** Wristband/LiDAR/IMU mock, Webots headless edge controller, vision sensor fusion, trigger scripts, `run_full_simulation.sh/.ps1`, full Docker stack.

### 2.2. Đánh giá độ vững chắc kiến trúc & điểm nghẽn tích hợp (Java ↔ Python ↔ Vue)

**Điểm mạnh:** Phân tách 3 tầng rõ ràng, clean architecture (controller/service/repo), tối ưu tài nguyên tốt (VT, batch insert, ring buffer, LanceDB embedded), có lớp red-teaming + auto-patch.

**Điểm nghẽn / Rủi ro tích hợp:**
1. **Safety coupling qua mạng (NGHIÊM TRỌNG):** Lệnh `INHIBIT` của Subsumption đi qua MQTT broker. Nếu broker lag/mất gói → SLA an toàn `<5ms` mất hiệu lực (đúng như limitation #16). An toàn cứng không nên phụ thuộc network.
2. **"Hai bộ não" an toàn (split-brain):** Phản xạ ngưỡng nằm cả ở `HealthService.java` (60Hz) **và** `SafetyAgent.py`. Quyền sở hữu quyết định trùng lặp → khó suy luận, dễ xung đột.
3. **Agent log Python→Java fire-and-forget (REST):** Không cùng đường giao dịch với vitals → mất log audit y tế khi backend nghẽn (rủi ro cho thanh tra y tế).
4. **Phụ thuộc Cloud LLM:** Router + Medical + Empathy đều cần Groq/Gemini/HF online. Có fallback chéo nhưng **offline = mất nhận thức** → không phù hợp robot tự trị di động.
5. **Bất nhất Docs ↔ Code (cần thống nhất):**
   - README diagram + `MASTER_CHANGELOG` ghi **PostgreSQL**, nhưng `application.yml` + `docker-compose` thực tế dùng **MariaDB 11.2**.
   - **PRD** khẳng định "**TUYỆT ĐỐI KHÔNG** thiết kế cho bệnh viện" (companion nơi công cộng/nhà), trong khi README/analysis lại đóng khung "bệnh nhân/bệnh án/giám sát y tế". → Phạm vi sản phẩm nhập nhằng.
6. **Bảo mật cấu hình:** Secret mặc định lộ trong file (`DB_PASSWORD=HK040103`, `MQTT_PASSWORD=hk07mqtt2026`, JWT dev secret); Mosquitto `allow_anonymous` (limitation #17). Frontend hardcode `localhost`/port `8888/8889` (limitation #5).

---

## BƯỚC 3 — STRATEGIC ROADMAP (Đề xuất Milestones)

> Operator chọn **1** mục để bắt đầu code ở phiên tiếp theo.

### 🅜0 (Tùy chọn — Quick Win) — Foundation & Consistency Hardening
- **Vấn đề giải quyết:** Xóa nợ kỹ thuật nền tảng: thống nhất DB (MariaDB) trong toàn bộ docs, gỡ secret hardcode → biến môi trường/secret store, bật MQTT auth, externalize endpoint frontend. Tạo nền sạch trước khi xây tính năng lớn.
- **Độ khó:** Dễ.
- **Công nghệ:** `.env`/Docker secrets, Mosquitto `password_file`, Vite env (`VITE_*`), cập nhật README/diagram.

### 🅜1 — Edge AI / Offline Cognition Core
- **Vấn đề giải quyết:** Robot tự trị di động không thể "mất não" khi rớt mạng. Hiện 100% cognition phụ thuộc Cloud API. Cần lớp suy luận nội bộ làm fallback khi offline (đặc biệt cho Medical Agent).
- **Độ khó:** **Khó.**
- **Công nghệ dự kiến:** LLM nhỏ chạy local (Ollama / `llama.cpp` với Phi-3-mini hoặc Qwen2-0.5B-instruct, quantized GGUF), embeddings local (`fastembed`/ONNX) thay HF API, giữ LanceDB; cơ chế chọn online↔offline tự động trong `agent_orchestrator`.

### 🅜2 — Wake Word / Keyword Spotting ("HK-07 ơi", "HK ơi")
- **Vấn đề giải quyết:** Hiện tương tác cần bấm nút Micro thủ công (spec Baymax V3) — bất tiện cho người già/khi khẩn cấp. Cần kích hoạt rảnh tay liên tục, low-power.
- **Độ khó:** **Trung bình.**
- **Công nghệ dự kiến:** openWakeWord / Porcupine (Picovoice) hoặc Vosk chạy trên edge; tạo custom wake-word "HK-07"; ghép vào luồng VUI Web Speech sẵn có + đẩy event qua MQTT/WebSocket để "đánh thức" companion.

### 🅜3 — Hardware Actuation & Closed-Loop Control
- **Vấn đề giải quyết:** Mô phỏng hiện **một chiều** (chỉ đẩy sensor lên MQTT, chưa nhận lệnh điều khiển thực — limitation #18). Cần đóng vòng lặp điều khiển + chuyển từ "cảnh báo phần mềm" sang "điều khiển phần cứng vật lý".
- **Độ khó:** **Trung bình–Khó.**
- **Công nghệ dự kiến:** Mở rộng MQTT command topics (`hk07/cmd/vel`, `hk07/cmd/actuator`), ROS2 `cmd_vel` bridge, Webots closed-loop, lớp interlock an toàn + xác nhận ACK.

### 🅜4 — Deterministic Safety Reflex (Subsumption Hardening)
- **Vấn đề giải quyết:** Gỡ rủi ro #1/#2/#16 — đưa phản xạ cứng `<5ms` về **một chủ sở hữu duy nhất** chạy cục bộ trên edge controller, không phụ thuộc broker mạng; chống split-brain Java/Python.
- **Độ khó:** **Khó.**
- **Công nghệ dự kiến:** Reflex loop cục bộ trong `hk07_edge_controller` (IPC/shared-memory hoặc serial trực tiếp), watchdog + heartbeat, dead-man switch; Java/Python chỉ giám sát, không tranh quyền inhibit.

### 🅜5 — Medical RAG Optimization (Clinical Knowledge Base)
- **Vấn đề giải quyết:** Câu trả lời Medical/Empathy hiện thiếu nền tri thức lâm sàng có trích dẫn; PRD yêu cầu GraphRAG. Cần KB y tế chuẩn + cá nhân hóa theo hồ sơ bệnh nhân + parse JSON LLM bền vững (limitation #14).
- **Độ khó:** **Trung bình.**
- **Công nghệ dự kiến:** Ingest corpus guideline y tế vào LanceDB, reranking + citation, fusion với MedicalProfile, schema-validated JSON (Pydantic/structured output) chống crash `json.loads`.

---

## KHUYẾN NGHỊ CHỌN (Architect's Pick)
- **Nếu ưu tiên giá trị "tự trị thực thụ":** chọn **🅜1 (Edge AI)** — gỡ phụ thuộc cốt tử lớn nhất.
- **Nếu ưu tiên trải nghiệm demo/ấn tượng nhanh:** chọn **🅜2 (Wake Word)** — độ khó vừa, hiệu ứng "Baymax sống dậy" rõ rệt.
- **Nếu ưu tiên an toàn-tính-mạng (đúng tinh thần y tế):** chọn **🅜4 (Safety Hardening)**.
- **Khuyến nghị làm 🅜0 trước** (rất nhanh) ở đầu phiên nào cũng được, để dọn nền.
