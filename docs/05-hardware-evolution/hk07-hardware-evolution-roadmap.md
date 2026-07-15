# Lộ Trình Phát Triển Phần Cứng HK-07: Từ Phần Mềm Sang Robot Thật

Kế hoạch này phác thảo việc chuyển đổi có hệ thống Hugo Sanitas HK-07 từ hệ thống mô phỏng phần mềm thành robot chăm sóc sức khỏe vật lý, tận dụng kiến trúc ROS2 hiện có đồng thời tích hợp các thành phần phần cứng thực.

## Phân Tích Kiến Trúc Hiện Tại

### Cơ Sở Hạ Tầng ROS2 Hiện Có
- **Không gian làm việc ROS2 Humble**: 9 node hoạt động trong MultiThreadedExecutor
- **Các Node Chính**: `hugo_action_controller_node`, `balance_controller`, `navigation_agent`, `rppg_thermal_node`, `hugo_telemetry_sim`, `hk07_physics_node`, `rtos_watchdog_simulator`, `HugoPerceptionBridgeNode`, `Hk07SensorFusionNode`
- **Trọng tài điều phối**: 4 cấp độ lệnh (Khẩn cấp > Cân bằng > Điều hướng > Chờ)
- **Điều khiển chuyển động**: Động học ngược với bộ giải 2-link tay, tạo gait hình sin
- **Cổng cảm biến**: Cầu HTTP-to-MQTT (`vivo_http_mqtt_bridge.py`) như node ROS2

### Hệ Thống Cảm Biến Hiện Tại
- **Cảm biến di động**: SensorLogs App → HTTP POST → MQTT → ROS2
- **Thị giác**: IPWebcam → MJPEG → MediaPipe → rPPG/phát hiện tư thế
- **IMU/Vitals**: Gia tốc kế/con quay hồi chuyển/nhịp tim/spo2 từ điện thoại
- **Môi trường**: Ánh sáng, áp suất khí quyển, GPS từ điện thoại

## Giai Đoạn 1: Nền Tảng Phần Cứng (Tháng 1-3)

### 1.1 Thiết Kế Cơ Khí & In 3D
- **Tỷ lệ**: 0.5:1 so với Baymax (chiều cao mục tiêu ~1.2m)
- **Các thành phần**:
  - Cấu trúc suit khí nén (soft robotics)
  - Khớp tay có khớp nối (2-DOF mỗi tay)
  - Cơ sở di động với dẫn động vi sai
  - Đầu với giá đỡ camera và loa
- **Phần mềm CAD**: Fusion 360 / SolidWorks
- **In 3D**: PETG/PLA cho phần cấu trúc, TPU cho khớp linh hoạt
- **Kết quả**: File CAD hoàn chỉnh + nguyên mẫu in

### 1.2 Thiết Kế PCB & Điện Tử
- **Bộ điều khiển chính**: ESP32-S3 hoặc STM32H7 cho sensor fusion
- **Quản lý năng lượng**: Pin Li-ion 24V với BMS
- **Driver động cơ**: TB6612FNG cho động cơ DC, điều khiển servo cho tay
- **Tích hợp cảm biến**:
  - MPU-6050 (IMU 6-DOF)
  - MAX30102 (SpO2/nhịp tim)
  - BME280 (nhiệt độ/áp suất/độ ẩm)
  - HC-SR04 (siêu âm đo khoảng cách)
  - OV5640 (module camera)
- **Thiết kế PCB**: Proteus với xuất KiCad để sản xuất
- **Giao tiếp**: WiFi ESP32 + CAN bus cho giao tiếp giữa bo mạch

### 1.3 Lớp Giao Tiếp Phần Cứng ROS2
- **Tạo package `hk07_hardware_interface`**:
  - `esp32_bridge_node.py`: Giao tiếp Serial/UART với ESP32
  - `motor_driver_node.py`: Điều khiển PWM cho động cơ DC và servo
  - `sensor_hardware_node.py`: Tiêu thụ dữ liệu cảm biến trực tiếp
- **Thay thế cảm biến điện thoại** bằng cảm biến phần cứng:
  - IMU: MPU-6050 → `/telemetry/imu` (sensor_msgs/Imu)
  - Vitals: MAX30102 → `/vitals/wristband` (message tùy chỉnh)
  - Môi trường: BME280 → `/sensors/environment/state`
- **Duy trì tương thích topic** với hệ thống agent hiện có

## Giai Đoạn 2: Tích Hợp Cảm Biến & Dữ Liệu (Tháng 4-5)

### 2.1 Dòng Dữ Liệu Cảm Biến Thật
```
[Cảm Biến Phần Cứng] → [ESP32] → [Serial/UART] → [esp32_bridge_node] → [ROS2 Topics]
                                                              ↓
[Camera Module] → [CSI/I2C] → [vision_processing_node] → [rPPG/Pose] → ROS2
```

### 2.2 Nâng Cấp Hệ Thống Thị Giác
- **Phần cứng**: Raspberry Pi Camera Module 3 hoặc ESP32-CAM
- **Xử lý**: Chuyển MediaPipe sang thiết bị biên (Raspberry Pi 4)
- **Topics**:
  - `/sensors/camera/raw` → Transport hình ảnh
  - `/sensors/camera/thermal_rppg` → Dữ liệu rPPG đã xử lý
  - `/perception/pose_landmarks` → Dữ liệu tư thế MediaPipe
- **Mục tiêu độ trễ**: <100ms end-to-end

### 2.3 Nâng Cấp Sensor Fusion
- **Triển khai EKF (Bộ lọc Kalman mở rộng)** cho sensor fusion IMU
- **Dự phòng đa cảm biến**: Cảm biến điện thoại + cảm biến phần cứng
- **Cơ chế dự phòng**: Tự động chuyển sang cảm biến điện thoại nếu phần cứng lỗi
- **Hiệu chuẩn**: Quy trình hiệu chuẩn tự động cho bù lệch IMU

## Giai Đoạn 3: Thao Tác & Điều Khiển Chuyển Động (Tháng 6-7)

### 3.1 Tích Hợp Điều Khiển Động Cơ
- **Động cơ nền**: 2 động cơ DC với encoder cho dẫn động vi sai
- **Servo tay**: 4 servo mô-men xoắn cao (2 mỗi tay)
- **Hệ thống khí nén**: Bơm khí + van solenoid cho suit bơm hơi
- **Tích hợp ROS2**:
  - Mở rộng `hugo_action_controller_node` với đầu ra PWM phần cứng
  - Triển khai bộ điều khiển PID cho kiểm soát tốc độ bánh xe
  - Thêm giới hạn an toàn (giám sát dòng điện, bảo vệ nhiệt độ)

### 3.2 Lập Trình Chuyển Động
- **Điều hướng**: Mở rộng APF (Trường Tiềm Nhân Tạo) với LiDAR thật
- **Phần cứng**: RPLIDAR A1 hoặc YDLIDAR X4
- **Bản đồ**: SLAM với cartographer hoặc hector_slam
- **Lập trình đường đi**: Nav2 stack với điều hướng costmap

### 3.3 Hệ Thống An Toàn
- **E-Stop**: Nút dừng khẩn cấp phần cứng
- **Watchdog**: Giám sát heartbeat phần cứng (ESP32)
- **Phát hiện va chạm**: Hợp nhất siêu âm + LiDAR
- **Phòng ngừa ngã**: Hiệu chỉnh cân bằng dự phòng dựa trên IMU

## Giai Đoạn 4: Tích Hợp AI & Phối Hợp Agent (Tháng 8-9)

### 4.1 Cầu Nối Webapp-Phần Cứng
- **Duy trì kiến trúc hiện có**: hk07-dashboard → hk07-core → hk07-agent → ROS2
- **Thêm endpoint trạng thái phần cứng**:
  - `/api/v1/hardware/status` → Pin, sức khỏe động cơ, trạng thái cảm biến
  - `/api/v1/hardware/control` → Ghi đè thủ công, hiệu chuẩn
- **Tích hợp WebSocket**: Telemetry phần cứng thời gian thực trong dashboard

### 4.2 Thực Thi Lệnh Agent
- **Mở rộng `hugo_action_controller_node`**:
  - Thêm server dịch vụ cho lệnh agent: `/robot/execute_action`
  - Loại hành động: DI CHUYỂN, CẦM NẮM, PHUN, ÔM, DỪNG KHẨN CẤP
  - Cơ chế phản hồi: Báo cáo trạng thái hành động cho agents
- **Tích hợp CareDecisionRouter**:
  - Ánh xạ hành động chăm sóc thành lệnh phần cứng
  - Ví dụ: `COMFORTING_HUG` → Thực thi chuỗi ôm với bơm hơi

### 4.3 Giọng Nói & Tương Tác
- **Loa phần cứng**: Đầu ra âm thanh chất lượng cao cho TTS
- **Microphone**: Mảng micro cho định vị giọng nói
- **Pipeline giọng nói**: Web Speech API → Agent → TTS → Loa phần cứng
- **Nhận diện cử chỉ**: Lệnh cử chỉ dựa trên camera

## Giai Đoạn 5: Kiểm Thử & Tối Ưu Hóa (Tháng 10-12)

### 5.1 Kiểm Thử Hardware-in-the-Loop
- **Kiểm thử đơn vị**: Xác thực cảm biến/actuator riêng lẻ
- **Kiểm thử tích hợp**: Phối hợp node ROS2 hệ thống đầy đủ
- **Kiểm thử an toàn**: E-stop, phát hiện va chạm, phòng ngừa ngã
- **Kiểm thử hiệu năng**: Độ trễ, tiêu thụ năng lượng, quản lý nhiệt

### 5.2 Kiểm Thử Thực Địa
- **Kiểm thử môi trường**: Ánh sáng khác nhau, mặt sàn, chướng ngại vật
- **Kiểm thử người dùng**: Kịch bản chăm sóc sức khỏe thực tế với tình nguyện viên
- **Kiểm thử thời gian dài**: Hoạt động liên tục 24+ giờ
- **Tối ưu hóa pin**: Chiến lược quản lý năng lượng

### 5.3 Triển Khai Sản Xuất
- **Thiết kế vỏ**: Bảo vệ thời tiết, quản lý cáp
- **Sản xuất**: Gia công PCB, quy trình lắp ráp
- **Tài liệu**: Sơ đồ phần cứng, hướng dẫn hiệu chuẩn, hướng dẫn bảo trì
- **Tuân thủ quy định**: Chứng nhận an toàn, tương thích điện từ

## Thông Số Kỹ Thuật

### Yêu Cầu Phần Cứng
- **Tính toán**: Raspberry Pi 4 (4GB) + ESP32-S3 cho sensor fusion
- **Năng lượng**: Pin Li-ion 24V 10Ah (mục tiêu hoạt động 24h)
- **Động cơ**: 2 động cơ DC 12V + 4 servo mô-men xoắn cao
- **Cảm biến**: IMU, SpO2, cảm biến môi trường, LiDAR, camera
- **Giao tiếp**: WiFi 6, CAN bus, UART/Serial

### Kiến Trúc Phần Mềm
- **ROS2**: Humble Hawksbill trên Ubuntu 22.04
- **Thời gian thực**: Patch kernel PREEMPT_RT cho điều khiển độ trễ thấp
- **Webapp**: Stack Vue3 + SpringBoot + FastAPI hiện có
- **AI**: Hệ thống multi-agent hiện có với dự phòng SLM cục bộ

### Mục Tiêu Hiệu Năng
- **Vòng điều khiển**: 50Hz (20ms) cho điều khiển động cơ
- **Sensor fusion**: 100Hz cho IMU, 10Hz cho môi trường
- **Xử lý thị giác**: 30FPS cho phát hiện tư thế, 10FPS cho rPPG
- **Độ trễ end-to-end**: <200ms từ cảm biến đến tác động
- **Tiêu thụ năng lượng**: <50W trung bình, <100W đỉnh

## Giảm Thiểu Rủi Ro

### Rủi Ro Kỹ Thuật
- **Nhiễu cảm biến**: Triển khai EKF + dự phòng với cảm biến điện thoại
- **Hỏng động cơ**: Thêm giám sát dòng điện + bảo vệ nhiệt độ
- **Mất giao tiếp**: Tự chủ cục bộ + timer watchdog
- **Hết pin**: Quản lý năng lượng + chế độ tiêu thụ thấp

### Rủi Ro Tích Hợp
- **Tương thích ROS2**: Duy trì tương thích topic/message
- **Tích hợp webapp**: Thêm lớp trừu tượng hóa phần cứng
- **Phối hợp agent**: Mở rộng CareDecisionRouter hiện có
- **Hệ thống an toàn**: Dự phòng phần cứng + phần mềm

## Chỉ Số Thành Công

- **Chức năng**: Tất cả lệnh agent thực thi trên phần cứng
- **Hiệu năng**: Độ trễ <200ms, thời lượng pin 24h
- **An toàn**: Không có sự cố không an toàn trong 100+ giờ kiểm thử
- **Độ tin cậy**: Uptime 99.9% trong hoạt động liên tục
- **Trải nghiệm người dùng**: Tương tác tự nhiên, phản hồi nhạy bén

## Kết Luận

Lộ trình này tận dụng kiến trúc ROS2 tinh vi và hệ thống multi-agent hiện có đồng thời tích hợp có hệ thống các thành phần phần cứng thực. Cách tiếp cận theo giai đoạn đảm bảo mỗi hệ thống con được xác thực trước khi tích hợp, giảm thiểu rủi ro đồng thời tối đa hóa việc sử dụng cơ sở hạ tầng phần mềm hiện có.
