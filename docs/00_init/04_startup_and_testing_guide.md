# HƯỚNG DẪN KHỞI ĐỘNG & TEST TÍNH NĂNG DỰ ÁN HUGO SANITAS HK-07
**Hệ thống:** Robot đồng hành Baymax (HK-07)  
**Tài liệu hướng dẫn vận hành và kiểm thử E2E (End-to-End)**

---

## 📋 1. DANH SÁCH CÁC THÀNH PHẦN (SYSTEM MODULES)

Dự án HK-07 bao gồm 5 thành phần chính hoạt động phối hợp:
1. **Infrastructure**: Mosquitto Broker (MQTT) và Redis (Blackboard shared memory).
2. **Spring Boot Core Backend (`hk07-core`)**: Trung chuyển dữ liệu sinh hiệu, quản lý cấu hình cảnh báo, và STOMP WebSockets server.
3. **Multi-Agent Engine Backend (`hk07-agent`)**: Bộ não AI (FastAPI) quản lý Blackboard, RAG LanceDB, và các agents (Safety, Medical, Empathy, Perception) theo cơ chế Mixture of Agents (MoA).
4. **ROS 2 Simulation package (`sensors`)**: Gói phần cứng giả lập chạy trên môi trường Linux/WSL (Humble).
5. **Vue 3 Dashboard Frontend (`hk07-dashboard`)**: Giao diện điều khiển trung tâm (Cyber-Cinematic HUD).

---

## 🚀 2. QUY TRÌNH KHỞI ĐỘNG TỪNG PHÂN HỆ (STARTUP SEQUENCE)

Thực hiện khởi động tuần tự theo các bước dưới đây để đảm bảo luồng truyền tin không bị ngắt quãng:

### BƯỚC 1: Khởi động Mosquitto MQTT & Redis Broker
- **Mosquitto MQTT**: Đảm bảo broker chạy trên cổng `1883`.
  ```powershell
  # Khởi động dịch vụ Mosquitto trên Windows
  Start-Service mosquitto
  ```
- **Redis**: Chạy trên cổng `6379`.
  ```powershell
  # Khởi động dịch vụ Redis
  Start-Service redis
  ```

### BƯỚC 2: Khởi động Spring Boot Core (`hk07-core`)
- Thư mục: `source/backend/hk07-core`
- Lệnh chạy:
  ```powershell
  mvn clean spring-boot:run
  ```
- *Xác nhận*: Log hiển thị `Started MqttConfig` và WebSocket STOMP listener sẵn sàng tại địa chỉ `http://localhost:8888/ws`.

### BƯỚC 3: Khởi động Multi-Agent Engine (`hk07-agent`)
- Thư mục: `source/backend/hk07-agent`
- Lệnh chạy:
  ```powershell
  python main.py
  ```
- *Xác nhận*: FastAPI engine khởi chạy tại cổng `8889`. Bạn có thể truy cập Swagger UI tại `http://localhost:8889/docs` để kiểm tra các endpoint.

### BƯỚC 4: Khởi động ROS 2 Nodes (Chạy trong WSL Ubuntu)
Mở một terminal WSL Ubuntu đã cài đặt **ROS 2 Humble**:

1. **Sourcing & Biên dịch workspace**:
   ```bash
   cd /mnt/d/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/robotics
   source /opt/ros/humble/setup.bash
   colcon build --packages-select sensors
   source install/setup.bash
   ```

2. **Chạy các nodes cảm biến và điều khiển**:
   Mở các tab terminal WSL mới (nhớ chạy `source install/setup.bash` ở mỗi tab):
   
   - **Tab 1: ROS 2 $\leftrightarrow$ MQTT Bridge** (Cầu nối trung chuyển):
     ```bash
     ros2 run sensors ros2_mqtt_bridge_node
     ```
   - **Tab 2: Baymax Telemetry Simulator** (Giả lập sinh hiệu cơ học):
     ```bash
     ros2 run sensors baymax_telemetry_sim
     ```
   - **Tab 3: Physics Solver & IK Node** (Giải solver khớp xương 3D và né vật cản):
     ```bash
     ros2 run sensors hk07_physics_node
     ```
   - **Tab 4: OpenCV rPPG & Thermal Vision** (Đo nhịp tim và quét nhiệt nhiệt độ qua camera):
     ```bash
     # Để chạy chế độ giả lập (simulation logs):
     ros2 run sensors rppg_thermal_node
     
     # Hoặc chạy luồng bắt webcam thực tế (Phase 22):
     ros2 run sensors rppg_thermal_node --ros-args -p video_source:="0"
     ```
   - **Tab 5: ESP32 Co-processor RTOS Watchdog** (Fail-Safe an toàn phần cứng):
     ```bash
     ros2 run sensors rtos_watchdog_simulator
     ```

### BƯỚC 5: Khởi động Vue 3 Dashboard (`hk07-dashboard`)
- Thư mục: `source/frontend/hk07-dashboard`
- Lệnh chạy:
  ```powershell
  npm run dev
  ```
- *Xác nhận*: Mở trình duyệt truy cập `http://localhost:5173`. HUD hiển thị kết nối `STREAMING` (màu xanh lá) tức là đã nhận được luồng dữ liệu WebSocket từ robot thực tế qua bridge.

---

## 🧪 3. KỊCH BẢN KIỂM THỬ TÍNH NĂNG (TEST CASES & VERIFICATION)

### KỊCH BẢN 1: Đồng bộ dữ liệu Nhịp tim & Nhiệt độ khuôn mặt (OpenCV rPPG)
1. Khởi chạy `rppg_thermal_node` ở tab 4 và `ros2_mqtt_bridge_node` ở tab 1.
2. Trên dashboard, truy cập màn hình `[05] COMPANION_INTELLIGENCE` (hoặc view tương ứng).
3. **Xác nhận**: Card `[ VISION_SENSORS_FEED ]` hiển thị giá trị *HR (rPPG)* và *Forehead Temp* thay đổi động theo thời gian thực (từ camera thật hoặc chế độ fallback giả lập). Cảnh báo sốt màu Đỏ Crimson `#FF3333` xuất hiện nếu nhiệt độ $\ge 38^\circ\text{C}$.

### KỊCH BẢN 2: Kiểm thử Cổng FHIR Lâm sàng (Phase 20 Clinical EHR)
1. Tạo hội thoại lâm sàng bằng cách gửi tin nhắn trên chatbox (ví dụ: *"Tôi bị đau ngực quá"*).
2. Sau khi AI Agent phản hồi, mở trình duyệt hoặc Postman truy cập endpoint FHIR:
   `GET http://localhost:8889/api/v1/fhir/clinical-bundle/latest`
3. **Xác nhận**: Trả về một JSON Bundle chuẩn HL7 FHIR chứa:
   - Các tài nguyên `Observation` (LOINC-coded) cho nhịp tim, nhiệt độ, huyết áp.
   - Tài nguyên `Condition` (SNOMED-CT coded `3424008` cho Tachycardia) mô tả chẩn đoán lâm sàng tương ứng.

### KỊCH BẢN 3: Kiểm thử Fail-Safe Watchdog khi Middleware bị treo (Phase 21 RTOS)
1. Khi toàn bộ hệ thống đang chạy bình thường (Dashboard hiển thị áp suất khí nén `pressure_L` / `pressure_R` $\approx 1.8\text{ bar}$).
2. Tắt nóng ứng dụng **Spring Boot Core** (hoặc `ros2_mqtt_bridge_node`) để mô phỏng sự cố hệ điều hành middleware bị đơ/đóng băng đột ngột.
3. Watchdog simulator ở Tab 5 sẽ phát hiện mất tín hiệu heartbeat `/system/heartbeat` quá 3.0 giây.
4. **Xác nhận (Phản xạ Cơ học)**:
   - Trên console của tab watchdog xuất hiện log cảnh báo: `[RTOS WATCHDOG ALERT] HEARTBEAT LOST! OS/Middleware frozen. TRIGGERING EMERGENCY SAFE SUIT DEFLATION.`
   - Node watchdog lập tức ghi đè trạng thái SOS lên `/vitals/wristband`.
   - Node `baymax_telemetry_sim` nhận được tín hiệu khẩn cấp, lập tức chuyển sang trạng thái `DISTRESSED`.
   - Áp suất xả hơi kích hoạt (`relief_active = True`). Áp suất `pressure_L/R` tụt nhanh về `0.0` trên console để bảo vệ an toàn cho bệnh nhân.
