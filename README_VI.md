# ─── [ HK-07 // HUGO SANITAS ROBOT COMPANION ] ──────────────────────────────

<p align="center">
  <img src="./asset/main_logo.jpg" alt="HK-07 Brand Logo" height="75" style="border-radius: 8px; filter: drop-shadow(0 0 10px #00E5FF);" />
  <img src="./asset/logo_name.jpg" alt="HK-07 Brand Logo" height="75" style="border-radius: 8px; filter: drop-shadow(0 0 10px #00E5FF);" />
</p>

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  MÃ HIỆU:  HK.Huang07           │  PHIÊN BẢN: 1.0.0-BETA                     │
│  KHỞI TẠO: 2026-05-31           │  TRẠNG THÁI: ĐANG VẬN HÀNH                 │
│  NỀN TẢNG: Linux / WSL2 / ROS2  │  GIAO DIỆN: CYBER-CINEMATIC (HUD THUẦN)    │
└──────────────────────────────────────────────────────────────────────────────┘
```

> **HK-07 // HUGO SANITAS** là thế hệ robot bạn đồng hành chăm sóc sức khỏe thông minh thế hệ mới — hỗ trợ người cao tuổi và bệnh nhân mắc các hội chứng tim mạch trong sinh hoạt hàng ngày. Hệ thống tích hợp một lõi robot hiệu năng cao chạy **ROS 2 Humble**, trí tuệ nhân tạo đa tác nhân (multi-agent AI), truyền tải dữ liệu sinh tồn thời gian thực, thị giác máy tính nhận diện té ngã và cơ chế phản xạ an toàn khẩn cấp <5ms, vận hành mượt mà dưới ràng buộc tài nguyên cực kỳ khắt khe (<615MB RAM tổng).

---

## 🖥️ Trực Quan Hóa Giao Diện Hệ Thống (Showcase)

Giao diện ứng dụng được thiết kế theo triết lý thiết kế **FUI Cyber-Cinematic** (Nền đen tuyệt đối `#000000`, lưới tọa độ xanh Holographic Cyan `#00E5FF`, thông số sinh tồn hoạt động xanh Emerald Green `#00FF66` và cảnh báo nguy hiểm đỏ Crimson `#FF3333`).

---

### 1. Hệ Thống Trí Tuệ Nhân Tạo (AI Cognitive & Agents)

#### A. Kênh Trò Chuyện Thấu Cảm AI & Giao Diện Giọng Nói (Voice UI)
![Companion Uplink](./asset/companion-uplink.jpg)
* **Mô tả:** Khung hội thoại tương tác được cung cấp bởi động cơ AI Đa tác nhân (Multi-Agent Engine) qua API Groq/Gemini/Local-SLM. Tích hợp nút nhấn nói tiếng Việt (STT) và phát giọng nói phản hồi thấu cảm (TTS) cùng hiệu ứng hiển thị dao động kí nhận thức **AGENT_COGNITIVE_SCOPE** động.

#### B. Nhật Ký Hoạt Động Đa Tác Nhân & Blackboard
![Agent System Log](./asset/agent_system_log.jpg)
* **Mô tả:** Luồng dữ liệu log hiển thị chuỗi suy luận thời gian thực và hành động của các đặc vụ: `Vitals Monitor Agent`, `Emergency Agent`, `Empathetic Agent`, `Perception Agent`, và `Action Agent` thông qua bộ nhớ chia sẻ Blackboard lưu trên Redis.

---

### 2. Hệ Thống Điều Phối Robot & An Toàn Vật Lý

#### A. Mô Hình Robot 3D Holographic Twin & Bản Đồ Chi phí Costmap
![Holographic Twin](./asset/holographic_twin.jpg)
![Holographic Twin](./asset/holographic_twin_01.jpg)
![Holographic Twin](./asset/holographic_twin_02.jpg)
* **Mô tả:** Trực quan hóa bản đồ radar 3D ảo hiển thị trạng thái chuyển động vật lý, các khớp xương nối động lực học, điểm cản PointCloud từ LiDAR 3D, và các vector lực đẩy né tránh APF. Chiếu dữ liệu LiDAR xuống sàn thành bản đồ Costmap 2D động. Tích hợp cảnh báo đồng bộ khi phát hiện té ngã.

#### B. Tọa Độ An Toàn & Cơ Chế Phanh Khẩn Cấp (Inhibition)
![Safety Coordinates](./asset/safety_cooroinates.jpg)
* **Mô tả:** Giám sát khoảng cách chướng ngại vật từ cảm biến LiDAR, tọa độ robot và tự động kích hoạt phản xạ ngắt động cơ ngay lập tức nếu phát hiện nguy cơ va chạm hoặc té ngã.

---

### 3. Giám Sát Chỉ Số Sinh Tồn Lâm Sàng

#### A. Bảng Giám Sát Dữ Liệu Sinh Tồn Thời Gian Thực (60FPS)
![Dynamic Telemetry](./asset/dynamic-telemetry.jpg)
* **Mô tả:** Trung tâm điều khiển chính. Hiển thị trực quan các chỉ số sinh học (Nhịp tim, SpO2, Thân nhiệt, Huyết áp) cùng sóng điện tâm đồ (ECG) tần số 60Hz vẽ bằng HTML5 Canvas tăng tốc phần cứng.

#### B. Lịch Sử Biểu Đồ Sinh Tồn Lâm Sàng
![History Metrics](./asset/history_metric.jpg)
* **Mô tả:** Cho phép điều phối viên thiết lập khoảng thời gian linh hoạt (Từ ngày / Đến ngày) để tải, vẽ biểu đồ và phân tích diễn biến sức khỏe dài hạn của bệnh nhân.

---

### 4. Hệ Thống Xác Thực & Bảo Mật

#### A. Giao Diện Đăng Nhập Kiểu Terminal
![Terminal Login](./asset/auth_login.jpg)
* **Mô tả:** Giao diện xác thực mang phong cách terminal tương lai. Thiết kế mô phỏng bảng điều khiển y tế/quân sự, yêu cầu thông tin đăng nhập được mã hóa an toàn.

#### B. Xác Thực Đa Yếu Tố (MFA) & Khôi Phục Bằng Backup Code
![Backup Code Verification](./asset/auth_by_backupcode.jpg)
* **Mô tả:** Kênh xác thực dự phòng sử dụng các mã bảo mật (Backup Codes) được tạo ngẫu nhiên bằng mật mã học khi token của authenticator không khả dụng.

---

### 5. Giả Lập Camera & Xử Lý Thị Giác Biên (Edge Vision)

#### A. Luồng Hình Ảnh Trực Tiếp Từ Camera Robot (Online)
![Robot Camera Online](./asset/robot-cam-simulate.jpg)
* **Mô tả:** Luồng camera truyền hình ảnh trực tiếp từ góc nhìn của robot khi di chuyển trong không gian giả lập Webots.

#### B. Luồng Hình Ảnh Khi Mất Kết Nối (Offline / Connection Lost)
![Robot Camera Offline](./asset/robot-cam-simulate-vision-lost.jpg)
* **Mô tả:** Màn hình giả lập trạng thái mất tín hiệu camera của robot hiển thị nhiễu nhiễu CRT (scanlines) và telemetry cảnh báo khi luồng truyền phát video bị ngắt kết nối.

#### C. Phân Tích rPPG & Theo Dõi Nhiệt Độ Trán Qua OpenCV
![Computer Vision Processing](./asset/robot-computer-visualize.jpg)
* **Mô tả:** Bộ xử lý thị giác máy tính biên phân tích khuôn mặt bệnh nhân qua MediaPipe, khoanh vùng trán/má (ROI) để tính toán nhịp tim rPPG (BVP) và đo nhiệt độ trán để đưa ra cảnh báo sốt thời gian thực.

---

### 6. Hồ Sơ Bệnh Nhân & Cài Đặt Bảo Mật

#### A. Cấu Hình Hồ Sơ Sức Khỏe & Quản Lý Khóa Bảo Mật MFA
![Profile Settings](./asset/profile-settings.jpg)
* **Mô tả:** Bảng quản trị chứa thông tin tóm tắt hồ sơ y tế bệnh nhân, thông tin tài khoản cá nhân, và cấu hình kích hoạt khóa xác thực đa yếu tố.

---

### 7. Bảng Điều Khiển Sensor HUD & Cầu Nối Telemetry Di Động

#### A. Bảng Điều Khiển Cảm Biến Di Động (13 Kênh Dữ Liệu)
![Sensor Telemetry Dashboard](./asset/sensor-telemetry-dashboard.jpg)
* **Mô tả:** Giao diện điều khiển giám sát cảm biến chuyên dụng. Hiển thị thông số IMU 9 trục thời gian thực (xoay mô hình hộp 3D, vòng la bàn cơ học, biểu đồ chuyển động gia tốc/con quay/từ trường), các biến môi trường (cường độ ánh sáng lux, áp suất khí quyển), và chỉ số vận động của bệnh nhân (đếm bước chân pedometer, trạng thái vận động, gia tốc cổ tay).

#### B. Danh Sách Kênh Cảm Biến & Xuất Dữ Liệu CSV
![Sensor Telemetry Sensor List](./asset/sensor-telemetry-sensor-list.jpg)
* **Mô tả:** Bảng theo dõi 13 kênh dữ liệu telemetry thời gian thực. Hiển thị trạng thái các cảm biến, tự động tính toán giá trị cực đại/cực tiểu (min/max) trong phiên kết nối, hiển thị nhãn cảnh báo động (OK / WARNING / DANGER) và tích hợp nút xuất báo cáo dữ liệu định dạng CSV hiệu năng cao.

---

## ⚙️ Kiến Trúc Hệ Thống

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        HK-07 HUGO SANITAS — KIẾN TRÚC HỆ THỐNG                         │
├───────────────────────┬─────────────────────────┬──────────────────────────────────────┤
│    [FRONTEND]         │     [BACKEND CORE]      │            [AGENT ENGINE]            │
│    Vue 3 + Vite       │    Spring Boot 3.2      │            Python FastAPI            │
│    Cổng: 5173         │     Java 21 VT          │            Cổng: 8889                │
│    Three.js 3D Twin   │     Cổng: 8888          │            Vòng Lặp Đa Tác Nhân      │
│    Giao diện Voice UI │     JWT Auth & RBAC     │            Redis Blackboard          │
└──────────┬────────────┴──────────┬──────────────┴──────────────────┬───────────────────┘
           │ WebSocket/REST        │ MQTT/WebSocket                  │ MQTT/REST
           ▼                       ▼                                 ▼
┌───────────────────────┐  ┌─────────────┐  ┌────────────────────────────────────────────┐
│      MariaDB          │  │    Redis    │  │             Eclipse Mosquitto              │
│  (Lưu Trữ Cổng: 3307) │  │(Bộ Nhớ Tạm) │  │             MQTT Broker :1883              │
└───────────────────────┘  └─────────────┘  └─────────────────────┬──────────────────────┘
                                                                  ▲
                                                  Cầu nối MQTT    │ (ros2_mqtt_bridge_node)
                                                                  ▼
                                            ┌────────────────────────────────────────────┐
                                            │             LÕI ROBOT ROS 2 HUMBLE         │
                                            │  - balance_controller (Bộ điều khiển PID)  │
                                            │  - navigation_agent (Lập quỹ đạo né APF)   │
                                            │  - physics_node (Bộ giải IK & APF)         │
                                            │  - rppg_thermal_node (Xử lý ảnh MediaPipe) │
                                            │  - rtos_watchdog_simulator (Watchdog)      │
                                            └────────────────────────────────────────────┘
```

---

## 🛠️ Các Bài Toán Thực Tiễn Được Giải Quyết

1. **Độ Trễ Phản Xạ Khẩn Cấp Cực Thấp (<5ms):** Bỏ qua các khối ghi cơ sở dữ liệu đồng bộ thông thường để phát tín hiệu dừng khẩn cấp (như dừng bánh xe robot khi có chướng ngại vật hay gọi SOS) thông qua luồng MQTT được tối ưu hóa.
2. **Tối Ưu Hóa Ràng Buộc Tài Nguyên:** Vận hành trơn tru toàn bộ các dịch vụ phức tạp (Spring Boot, Python Agents, hệ cơ sở dữ liệu và trung gian thông điệp) trên một máy chủ thử nghiệm cấu hình thấp, giới hạn tổng lượng RAM tiêu thụ dưới **<615MB RAM**.
3. **Mô Hình Chẩn Đoán Lưỡng Tầng & Blackboard:** Kết hợp Lớp phản xạ cứng (Hard Reflex) ngưỡng cố định và Lớp suy luận mềm (Soft Cognitive) sử dụng các Agent, LLM, và bộ nhớ chia sẻ Blackboard qua Redis để trao đổi thông tin ngữ cảnh bệnh nhân.
4. **Bảo Mật Dữ Liệu Sinh Tồn Thời Gian Thực:** Bảo vệ luồng WebSocket truyền thông số y sinh bằng bộ chặn kênh Inbound của STOMP (JWT Channel Interceptor), ngăn chặn truy cập trái phép vào luồng dữ liệu y tế nhạy cảm.
5. **Cầu Nối ROS 2 sang MQTT:** Chuyển đổi định dạng dữ liệu robot khớp chuẩn ROS 2 (`sensor_msgs/Imu`, `sensor_msgs/PointCloud2`, `sensor_msgs/JointState`, `geometry_msgs/Twist`) và bridge mượt mà sang MQTT Broker để đẩy lên Dashboard thời gian thực.
6. **Cơ Chế Ngoại Tuyến Edge Fallback:** Tích hợp bộ xử lý tiếng Việt không dấu rule-based và engine chạy local GGUF SLM (`llama-cpp-python` hỗ trợ Phi-3/Llama-3) đảm bảo robot vẫn có thể trò chuyện và phân loại lệnh của người dùng khi mất Internet.
7. **Đồng Bộ Y Tế EHR chuẩn FHIR:** Cung cấp dịch vụ FHIR Gateway tự động biên dịch chẩn đoán Blackboard thành gói tài nguyên chuẩn quốc tế HL7 FHIR Observation và Condition.
8. **Watchdog Phần Cứng RTOS:** Node watchdog giám sát nhịp tim hệ thống và tự động kích hoạt trạng thái dừng khẩn cấp E-STOP cũng như xả khí suit mềm nếu mất kết nối quá 3 giây.
9. **Nhận Diện Té Ngã Song Yếu Tố (Dual-Factor):** Kết hợp các ngưỡng gia tốc va chạm/không trọng lực của cảm biến IMU với các biến động sụt giảm áp suất khí quyển đột ngột nhằm giảm thiểu tối đa các cảnh báo sai (false positive) do các cử động vung tay thông thường gây ra.
10. **Tích Hợp Cảm Biến Di Động Động (Dynamic Mobile):** Dịch và đồng bộ hóa telemetry thô từ thiết bị di động (GPS, IMU, Pedometer, Cường độ ánh sáng, Áp suất khí quyển) thông qua một cổng cầu nối hotspot tự cấu hình, phân luồng các gói tin tần số cao lên bảng điều khiển thông qua các luồng ảo (Virtual Threads) không gây tắc nghẽn.

---

## 📦 Cấu Trúc Thư Mục

```
hk-07/
├── asset/                  ← Chứa ảnh chụp màn hình giao diện hệ thống
├── docs/                   ← Tài liệu đặc tả kỹ thuật và hướng dẫn
│   ├── 00_init/            ← Khởi tạo dự án, phân tích yêu cầu, techstack
│   ├── 01_system_design/   ← Kiến trúc hệ thống, cơ sở dữ liệu, đặc tả API
│   ├── 02_subsystems/      ← Tài liệu Backend, Deployment, Frontend và Testing
│   ├── 03_evolution_specs/ ← Tài liệu nâng cấp và cải tiến hệ thống (Phases 1-22)
│   ├── 04_walkthroughs/    ← Hướng dẫn chạy thử nghiệm các tính năng đã code
│   └── MASTER_CHANGELOG.md ← Nhật ký kiểm toán thay đổi toàn bộ hệ thống
└── source/                 ← Mã nguồn các thành phần dự án
    ├── backend/
    │   ├── hk07-core/      ← Mã nguồn Java Spring Boot Core (Hỗ trợ MariaDB 3307)
    │   ├── hk07-agent/     ← Mã nguồn Python AI Multi-Agent (Tiers 0-2, Router V2, Blackboard)
    │   └── docker/         ← Các tệp cấu hình hạ tầng Docker
    ├── frontend/
    │   └── hk07-dashboard/ ← Mã nguồn Vue 3 (Three.js 3D Twin, Voice UI)
    └── robotics/           ← Không gian làm việc ROS 2
        ├── build/          ← Thư mục build ROS 2
        ├── install/        ← Thư mục cài đặt ROS 2
        ├── log/            ← Nhật ký chạy ROS 2
        └── sensors/        ← ROS 2 Sensors Package (rclpy Nodes: physics, telemetry, lidar, bridge, watchdog)
```

---

## 🚀 Hướng Dẫn Khởi Động Nhanh

Hệ thống hỗ trợ 2 chế độ vận hành: **Chạy Tích Hợp Bằng Docker** hoặc **Khởi Động Thủ Công Từng Thành Phần (Local Developer Mode)**.

### 1. Vận Hành Qua Docker Compose

```bash
# 1. Di chuyển vào thư mục chứa cấu hình backend
cd source/backend
cp .env.example .env
# Mở file .env và điền các khóa GROQ_API_KEY, GEMINI_API_KEY, hoặc OPENROUTER_API_KEY phù hợp

# 2. Khởi động toàn bộ stack dịch vụ bằng container
docker compose up -d --build

# 3. Các cổng kết nối
# Dashboard Frontend:  http://localhost:4205 (Định tuyến qua Nginx)
# Backend Swagger Docs: http://localhost:8888/swagger-ui.html
# AI Agent API Docs:   http://localhost:8889/docs
```

Để chạy các tệp kịch bản giả lập thị giác máy tính và điều khiển robot hướng tới cụm Docker, thiết lập các biến môi trường và chạy:
```bash
export MQTT_BROKER_HOST=localhost
export MQTT_BROKER_PORT=1883
export MQTT_USERNAME=hk07sim
export MQTT_PASSWORD=mật_khẩu_mqtt_trong_file_env

# Chạy node xử lý thị giác máy tính OpenCV & MediaPipe
python source/robotics/sensors/vision_sensor/hk07_sensor_fusion.py
```

---

### 2. Khởi Động Thủ Công Trong Phát Triển Cục Bộ (Local Dev)

#### Bước 0: Khởi động các cơ sở dữ liệu và Broker nền
Khởi động cụm dịch vụ MariaDB 3307, Redis 6379, và Mosquitto 1883 bằng file script PowerShell:
```powershell
./source/backend/run_backend.ps1
```

#### Bước 1: Khởi động Backend Core (Spring Boot)
```bash
cd source/backend/hk07-core
mvn clean install -DskipTests
mvn spring-boot:run
# Backend lắng nghe tại: http://localhost:8888
```

#### Bước 2: Khởi động Python AI Multi-Agent API
```bash
cd source/backend/hk07-agent
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8889
# Đặc vụ AI lắng nghe tại: http://localhost:8889
```

#### Bước 3: Khởi động Giao diện Frontend (Vue 3)
```bash
cd source/frontend/hk07-dashboard
npm install
npm run dev
# Giao diện hoạt động tại: http://localhost:5173
```

#### Bước 4: Khởi chạy Lõi Robot ROS 2
Để chạy vòng lặp xử lý robot hiệu năng cao, mở một **WSL2 Ubuntu Terminal** chuyên biệt:

```bash
# 1. Di chuyển vào không gian làm việc robotics
cd source/robotics

# 2. Source môi trường ROS 2 Humble hệ thống
source /opt/ros/humble/setup.bash

# 3. Dọn dẹp và biên dịch sensors package
rm -rf build log install
colcon build --packages-select sensors

# 4. Source setup biến môi trường local
source install/setup.bash

# 5. Khởi chạy 5 Node ROS 2 chính thức & MQTT Dual Bridge
ros2 run sensors ros2_mqtt_bridge_node
ros2 run sensors hk07_physics_node
ros2 run sensors balance_controller
ros2 run sensors navigation_agent
ros2 run sensors rtos_watchdog_simulator
```

#### Bước 5: Khởi chạy Cầu Nối Cảm Biến Điện Thoại (HTTP-to-MQTT Bridge)
Định tuyến ứng dụng ghi nhật ký cảm biến (Sensor Logs) trên điện thoại để truyền phát trực tiếp dữ liệu vào máy tính thông qua cầu nối này:
```bash
cd source/robotics/sensors/mobile_gateway
pip install Flask paho-mqtt
python vivo_http_mqtt_bridge.py --port 5005
```
*(Cầu nối sẽ tự động nhận diện địa chỉ IP Wi-Fi của máy tính và in ra URL cấu hình tương ứng trên điện thoại, ví dụ: `http://<WIFI_IP>:<PORT>/data`).*

---

## 💾 Phân Bổ Tài Nguyên Bộ Nhớ RAM Thực Tế

| Tên Dịch Vụ | Giới Hạn RAM | Trách Nhiệm Chi Tiết Trong Hệ Thống |
| :--- | :--- | :--- |
| **Mosquitto** | 32 MB | Broker MQTT trao đổi dữ liệu cảm biến thời gian thực |
| **Redis** | 64 MB | Bộ nhớ chung Blackboard, lưu token & kiểm soát tần suất |
| **MariaDB** | 256 MB | Lưu trữ dữ liệu lịch sử sinh vật học & thông tin người dùng |
| **hk07-core** | 512 MB | Máy ảo JVM chạy dịch vụ Spring Boot Core |
| **hk07-agent** | 256 MB | Tiến trình Python chạy vòng lặp AI Multi-Agent & GGUF Local SLM |
| **TỔNG CỘNG** | **~615 MB** | **Tối ưu hóa tuyệt đối cho môi trường nhúng WSL2/Docker** |

---

## 👤 Tác Giả (Author)

* **Huỳnh Quốc Huy** (HK.Huang07)
* **Email:** [huykyunh.k@gmail.com](mailto:huykyunh.k@gmail.com)
* **GitHub:** [hkhuang07](https://github.com/hkhuang07)
* **LinkedIn:** [hkhuang07](https://www.linkedin.com/in/hkhuang07/)

---

## 📄 Bản Quyền (License)

Bản quyền sở hữu riêng (Proprietary / Closed Source) — Tất cả các quyền được bảo lưu.

Bản quyền © 2026 thuộc về HK.Huang07 (Dự án Hugo Sanitas).

Phần mềm này cùng tất cả tài liệu đi kèm là tài sản độc quyền của tác giả. Nghiêm cấm mọi hành vi sao chép, chỉnh sửa, phân phối, tái phân phối, xuất bản hoặc cấp phép lại dưới mọi hình thức, cho dù ở dạng mã nguồn hay mã máy, có hoặc không có sửa đổi, nếu không có sự đồng ý trước bằng văn bản từ chủ sở hữu bản quyền.
