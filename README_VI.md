# HK-07 // HUGO SANITAS ROBOT COMPANION

<p align="center">
  <img src="./asset/main_logo.jpg" alt="Brand Logo" height="100" />
  &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;
  <img src="./asset/logo_name.jpg" alt="Logo Name" height="100" />
</p>

> **Mã hiệu:** HK.Huang07 | **Phiên bản:** 1.0.0-ALPHA | **Ngày khởi tạo:** 2026-05-31

Robot Bạn đồng hành Chăm sóc Sức khỏe thế hệ mới — Đồng hành trong cuộc sống hàng ngày bằng trí tuệ nhân tạo đa tác nhân, giám sát sinh tồn thời gian thực và phản xạ an toàn < 5ms.

---

## Giao diện trực quan (System Interface Showcase)

### 1. Màn hình giám sát Vitals Dashboard (60FPS)
![Vitals Dashboard](./asset/dashboard-ui.jpg)

### 2. Khung Chat thấu cảm AI & Suy luận Đa tác nhân (Companion Chat)
![Agent Chat](./asset/agent-chat.jpg)
![Agent Companion](./asset/agent-companion.jpg)

### 3. Nhật ký Động cơ Đa tác nhân (Agents Log)
![Agents Log](./asset/agent_logs.jpg)

### 4. Hệ thống điều phối an toàn (Safety Radar)
![Safety Radar](./asset/safemode-tab.jpg)

### 5. Lịch sử sinh tồn lâm sàng (History)
![Historical Metrics](./asset/history_tab.jpg)

### 6. Giả lập Camera Robot (Khi có hình ảnh / Khi mất kết nối)
![Robot Camera Simulation Online](./asset/robot-cam-simulate.jpg)
![Robot Camera Simulation Lost](./asset/robot-cam-simulate-vision-lost.jpg)

### 7. Trực quan hóa dữ liệu Robot trên máy tính
![Robot Computer Visualization](./asset/robot-computer-visualize.jpg)

### 8. Xử lý Camera bằng OpenCV & MediaPipe
![OpenCV MediaPipe Process](./asset/opencv_medipipe_webcam_process.jpg)

---

## Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────┐
│         HK-07 HUGO SANITAS — SYSTEM ARCHITECTURE           │
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
│   Mariadb      │  │    Redis    │  │  Eclipse Mosquitto    │
│   (Persist)    │  │  (Buffer)   │  │  MQTT Broker :1883    │
└────────────────┘  └─────────────┘  └───────────────────────┘
                                              ▲
                              ┌───────────────┴───────────────┐
                              │     SENSOR LAYER (Simulated)  │
                              │  Wokwi ESP32 (BLE Wristband)  │
                              │  ROS 2 LiDAR Mock Nodes       │
                              │  Webots Robot Simulator       │
                              └───────────────────────────────┘
```

---

## Ý nghĩa xây dựng & Bài toán giải quyết

### 1. Ý nghĩa dự án (Mission & Philosophy)
Dự án **HK-07 // HUGO SANITAS** được thiết kế nhằm mục đích xây dựng một hệ thống robot trợ lý cá nhân thông minh trong gia đình (Care-Robot Companion) dành cho người cao tuổi, người có bệnh nền tim mạch. Robot không chỉ là thiết bị giám sát chỉ số sinh tồn bị động mà còn đóng vai trò như một thực thể tương tác thấu cảm và phản ứng nhanh, kết nối chặt chẽ giữa bệnh nhân, gia đình và nhân viên y tế.

### 2. Bài toán thực tiễn giải quyết
* **Độ trễ phản xạ khẩn cấp:** Trong y khoa, mỗi giây đều quý giá. Hệ thống giải quyết bài toán xử lý phản xạ các sự kiện khẩn cấp y tế dưới 5ms (ví dụ: phát hiện đột quỵ, dừng chuyển động robot khi phát hiện chướng ngại vật hoặc va chạm cận kề) bằng mô hình xử lý ưu tiên dựa trên hàng đợi MQTT và STOMP WebSockets.
* **Tối ưu hóa tài nguyên phần cứng (Resource Constraint):** Robot hoạt động ổn định trên các vi điều khiển và máy tính nhúng hạn chế (như Dell Latitude E7270 cũ, chip 1.6GHz, 8GB RAM) với mức tiêu thụ tài nguyên cực kỳ tối ưu (<615MB RAM cho toàn bộ stack).
* **Kết hợp Chẩn đoán Logic & Thấu cảm AI:** Tách biệt hai lớp xử lý: Lớp phản xạ cứng (Hard Reflex - dựa trên ngưỡng chỉ số y tế cố định) để kích hoạt tín hiệu SOS ngay lập tức, và Lớp tương tác mềm (Empathetic Dialogue - dựa trên AI Multi-Agent và LLMs) để trò chuyện, giảm căng thẳng tâm lý cho bệnh nhân và đề xuất lộ trình chăm sóc lâm sàng thứ cấp.
* **Bảo mật kênh truyền thời gian thực (Secured Real-time Telemetry):** Giải quyết lỗ hổng bảo mật rò rỉ dữ liệu y tế trên luồng WebSockets thông qua hệ thống chặn quyền ở mức Inbound Channel của STOMP (JWT Authentication Interceptor), đảm bảo dữ liệu sinh tồn chỉ được truyền đến người dùng hợp lệ.

---

## Chi tiết Công nghệ & Nguyên lý hoạt động

### 1. Chi tiết Tech Stack toàn diện
* **Frontend Dashboard:**
  * **Vue 3 + TypeScript + Vite:** Khởi tạo giao diện SPA hiệu năng cao.
  * **Pinia:** Quản lý đồng bộ trạng thái luồng dữ liệu y tế thời gian thực.
  * **Custom Cinematic Cyber-Dark Theme:** Triết lý thiết kế FUI (Fictional User Interface) Big Hero 6 / Iron Man với hệ màu Cyber Dark-Blue, tối đa hóa trải nghiệm giám sát an ninh.
  * **ECG Waveform Canvas:** Vẽ biểu đồ sóng điện tâm đồ thời gian thực tần số 60Hz bằng HTML5 Canvas, tận dụng tối đa tăng tốc phần cứng (GPU-acceleration).
* **Backend Core (Trung tâm chỉ huy):**
  * **Spring Boot 3.2 + Java 21 (Virtual Threads):** Sử dụng cơ chế luồng ảo (Virtual Threads) để xử lý hàng ngàn kết nối WebSocket đồng thời mà không nghẽn tài nguyên CPU.
  * **Spring Security + JWT:** Hệ thống phân quyền chặt chẽ (RBAC) cho Owner, Medic, và Guest.
  * **STOMP Broker Interceptor:** Bảo mật luồng WebSocket ở mức kênh kết nối (Inbound Channel).
* **AI Multi-Agent Engine (Trí tuệ nhân tạo đa tác nhân):**
  * **Python FastAPI:** Cung cấp API tương tác thấu cảm và chuyển tiếp logs AI.
  * **Mô hình Đa tác nhân (Multi-Agent framework):**
    * *Vitals Monitor Agent:* Giám sát dòng dữ liệu sinh học từ xa.
    * *Emergency Diagnostics Agent:* Nhận diện biến cố sức khỏe lâm sàng khẩn cấp.
    * *Empathetic Interactive Agent:* Sử dụng Groq Llama 3 / Gemini Pro qua API để sinh phản hồi ngôn ngữ tự nhiên, tạo cảm giác gần gũi, thấu cảm y học.
* **Lớp thiết bị & Giả lập (IoT & Simulation):**
  * **Eclipse Mosquitto (MQTT):** Broker trung gian giúp ingest dữ liệu sinh tồn với độ trễ cực thấp (<5ms).
  * **Simulated ESP32 (Wokwi BLE Wristband):** Mô phỏng vòng đeo tay thông minh đo nhịp tim, nhiệt độ, SpO2 và nút khẩn cấp SOS.
  * **Webots Simulator & ROS 2 Mock Nodes:** Mô phỏng vật lý chuyển động của robot HK-07, cảm biến khoảng cách và LiDAR tránh chướng ngại vật thời gian thực.
* **Cơ sở dữ liệu (Database):**
  * **MariaDB:** Lưu trữ lâu dài thông tin lịch sử bệnh án, người dùng và logs hệ thống.
  * **Redis:** Lưu cache, kiểm soát chống spam tin nhắn (Throttling) và quản lý trạng thái token đăng nhập.

### 2. Nguyên lý hoạt động hệ thống (Operational Workflow)
```
[Vòng đeo tay BLE / Cảm biến Robot]
          │ (Dữ liệu 10Hz qua MQTT)
          ▼
[Eclipse Mosquitto (Port: 1883)]
    ├───► [Python Multi-Agent Engine (Port: 8889)] ───► Chẩn đoán Lâm sàng & LLM Reasoning
    └───► [Spring Boot Backend Core (Port: 8888)]
               │ (Xử lý ưu tiên, Ghi MariaDB & Redis)
               ▼ (WebSocket STOMP qua JWT Interceptor)
         [Vue 3 Frontend Dashboard (60FPS ECG)]
```

* **Bước 1: Tiếp nhận dữ liệu IoT (Ingestion):** Cảm biến vòng đeo tay y tế phát dữ liệu định dạng JSON tới MQTT topic `hk07/sensors/wristband/...`. Cùng lúc đó, Webots Robot phát dữ liệu khoảng cách laser đến `hk07/sensors/lidar/...`.
* **Bước 2: Phản xạ và Phân phối (Routing & Reflex):**
  * Spring Boot Core đăng ký nhận tin từ MQTT. Khi nhận gói tin sinh tồn, hệ thống kiểm tra ngưỡng an toàn. Nếu các chỉ số bình thường, nó lưu vào MariaDB và đẩy trực tiếp lên Vue 3 Dashboard thông qua STOMP WebSocket để hiển thị.
  * Nếu phát hiện chỉ số bất thường (nhịp tim > 150 BPM - Heart Attack), hệ thống lập tức bỏ qua lưu trữ đệm, kích hoạt cờ khẩn cấp (`emergency_button_pressed` hoặc `stroke_alert`), gửi lệnh khẩn cấp qua MQTT buộc robot Webots dừng di chuyển lập tức để đảm bảo an toàn, đồng thời thông báo SOS nổi trên Dashboard.
* **Bước 3: Suy luận AI thấu cảm (AI Dialogue):** AI Agent tiếp nhận luồng sự kiện khẩn cấp, phân tích bệnh án lịch sử của bệnh nhân, gọi mô hình ngôn ngữ lớn (LLM Groq/Gemini) để đưa ra lời khuyên y khoa sơ cấp và câu nói trấn an tâm lý phù hợp, gửi trực tiếp về khung chat Companion trên giao diện Vue 3.

---

## Cấu trúc thư mục

```
source/
├── backend/
│   ├── hk07-core/          ← Spring Boot (Java 21 Virtual Threads)
│   ├── hk07-agent/         ← Python Multi-Agent Engine (FastAPI)
│   └── docker/             ← Mosquitto + PostgreSQL configs
├── frontend/
│   └── hk07-dashboard/     ← Vue 3 + Vite Cyber-Cinematic UI
└── docker-compose.yml      ← Full stack (RAM budget: ~615MB)
```

## Quick Start & Testing Guide

Hệ thống hỗ trợ 2 chế độ chạy: **Full Docker Stack** (Môi trường dịch vụ tích hợp Docker) hoặc **Local Dev** (Khởi động thủ công từng module rời).

### 1. Chế độ Docker Deployment (Docker Stack)
Trong chế độ này, tất cả cơ sở dữ liệu nền, các cổng MQTT Broker, API chính của Spring Boot và Động cơ AI Multi-Agent đều được đóng gói và chạy dưới dạng Container.

```bash
# 1. Cấu hình biến môi trường
cd source/backend
cp .env.example .env
# Mở file .env và điền GROQ_API_KEY hoặc GEMINI_API_KEY

# 2. Khởi động toàn bộ stack dịch vụ
docker compose up -d --build

# 3. Kiểm tra các dịch vụ đang chạy
docker ps
# Dashboard Frontend: http://localhost:4205 (Được định tuyến qua Nginx)
# Backend Swagger Docs: http://localhost:8888/swagger-ui.html
# AI Agent API: http://localhost:8889
# Mosquitto MQTT Broker: http://localhost:1883 / Bản sao Replica: http://localhost:1884
```

Để khởi chạy các node robot điều khiển và cảm biến kết nối đến Docker stack, hãy thiết lập biến môi trường và chạy thủ công trên máy chủ (host) hoặc WSL:
```bash
# Cấu hình biến kết nối đến Broker MQTT Docker
export MQTT_BROKER_HOST=localhost
export MQTT_BROKER_PORT=1883
export MQTT_USERNAME=hk07sim
export MQTT_PASSWORD=hk07mqtt2026

# Khởi động Node Sensor Fusion (OpenCV Camera)
cd source/sensors/vision_sensor
python hk07_sensor_fusion.py

# Khởi động Node Robotics Edge Controller (Webots Robot)
cd source/robotics/controllers
python hk07_edge_controller.py

# Khởi động Node Vivo HTTP-MQTT Sensor Bridge
cd source/sensors/mobile_gateway
python vivo_http_mqtt_bridge.py
```

---

### 2. Chế độ Local Dev (Khởi động thủ công từng Node hệ thống)

Để phát triển mã nguồn cục bộ, bạn có thể khởi động các cơ sở hạ tầng nền và từng module một cách độc lập.

#### Bước 0: Khởi động các dịch vụ hạ tầng (Broker & Database)
```bash
# Chạy MQTT, MariaDB và Redis ở chế độ nền:
cd source/backend
docker compose up -d redis mariadb mosquitto
```
*Hoặc bạn có thể cài đặt chạy dịch vụ Mosquitto (port 1883), Redis (port 6379), MariaDB (port 3306) trực tiếp trên máy cục bộ.*

#### Bước 1: Khởi động Backend Core (Spring Boot)
```bash
cd source/backend/hk07-core
mvn clean install -DskipTests
mvn spring-boot:run
# Chạy tại cổng http://localhost:8888
```

#### Bước 2: Khởi động Node AI Engine (Python Multi-Agent FastAPI)
```bash
cd source/backend/hk07-agent
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8889
# Chạy tại cổng http://localhost:8889
```

#### Bước 3: Khởi động Node Frontend Dashboard (Vue 3)
```bash
cd source/frontend/hk07-dashboard
npm install
npm run dev
# Chạy tại cổng http://localhost:5173 (Vite Dev Server)
```

#### Bước 4: Khởi động Node Webots Edge Controller (Robotics Node)
Node này giả lập phần khung gầm robot di động, lắng nghe các lệnh phanh khẩn cấp từ cơ chế an toàn và điều chỉnh tốc độ bánh xe.
```bash
cd source/robotics/controllers
# Đảm bảo đường dẫn thư viện Webots đã được cấu hình hoặc chạy mock-fallback
python hk07_edge_controller.py
```

#### Bước 5: Khởi động Node OpenCV Sensor Fusion (Vision Node)
Quét và xử lý hình ảnh luồng camera nội bộ nhằm cập nhật tệp buffer ảnh `latest_frame.jpg` cho Gemini Vision và nhận diện tư thế ngã.
```bash
cd source/sensors/vision_sensor
python hk07_sensor_fusion.py
```

#### Bước 6: Khởi động Node Vivo HTTP-MQTT Sensor Bridge (Mobile Ingestion)
Lắng nghe tại cổng 8080 để tiếp nhận luồng dữ liệu gia tốc và thông số sinh tồn đẩy từ ứng dụng cảm biến di động.
```bash
cd source/sensors/mobile_gateway
python vivo_http_mqtt_bridge.py
```

#### Bước 7: Khởi chạy các công cụ kiểm thử giả lập
Sử dụng giao diện dòng lệnh giả lập tương tác để kiểm tra cơ chế cảnh báo ngã, chướng ngại vật hay tình huống khẩn cấp:
```bash
cd source/robotics/simulation
./run_full_simulation.sh
# Hoặc phát trực tiếp từng sự kiện y tế cụ thể:
python trigger_normal_vitals.py
python trigger_heart_attack.py
python trigger_fall.py
python trigger_obstacle.py
python trigger_emergency_button.py
```

---

## Troubleshooting (Sửa lỗi thường gặp)

### 1. Lỗi `RedisConnectionFailureException` khi login
* **Triệu chứng:** Khi đăng nhập thành công ở giao diện, Backend trả về lỗi ngoại lệ `Unable to connect to Redis`.
* **Khắc phục:** Đảm bảo container `hk07-redis` đang chạy bằng lệnh `docker ps`. Nếu chưa chạy, hãy thực hiện bước **0** (Khởi động cơ sở hạ tầng nền) ở trên.

### 2. Lỗi `no configuration file provided: not found` khi chạy Docker Compose
* **Triệu chứng:** Chạy `docker compose up -d` bị báo lỗi không tìm thấy file cấu hình.
* **Khắc phục:** File `docker-compose.yml` nằm ở thư mục `source/backend/`. Hãy chắc chắn đã chuyển hướng `cd source/backend` trước khi chạy lệnh, hoặc chỉ định rõ file cấu hình bằng tham số `-f`:
  ```bash
  docker compose -f source/backend/docker-compose.yml up -d redis mariadb mosquitto
  ```

## RAM Budget (8GB Host Dell Latitude E7270)

| Service | RAM Limit | Purpose |
|---------|-----------|---------|
| Mosquitto | 32MB | MQTT Broker |
| Redis | 64MB | Lag Compensation Buffer |
| PostgreSQL | 128MB | Persistent Health Records |
| hk07-core | 512MB | Spring Boot (JVM: -Xmx512m) |
| hk07-agent | 256MB | Python Multi-Agent |
| **Total** | **~615MB** | ✅ Safe on WSL2 4GB |

## Phase Status

| Phase | Status | Description |
|-------|--------|-------------|
| 01-foundation | ✅ DONE | Spring Boot core + Docker stack + Python agents |
| 02-auth | ✅ DONE | JWT + RBAC + In-Memory Token Handling |
| 03-data-closure | ✅ DONE | Flyway migrations, REST agent logging pipeline |
| 04-evolution | ✅ DONE | Red Teaming, Fix Leaks, Race conditions, MQTT Throttle |
| FE-01-dashboard | ✅ DONE | Vue 3 + Cyber-Cinematic UI, Subsumption Radar |
| FE-02-auth | ✅ DONE | Cinematic Terminal Login + Interceptor |
