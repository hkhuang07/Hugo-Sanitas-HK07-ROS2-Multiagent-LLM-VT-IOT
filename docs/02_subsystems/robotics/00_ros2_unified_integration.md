
## 📄 TÀI LIỆU ĐẶC TẢ TÁI CẤU TRÚC HỆ THỐNG TRỰC TIẾP (Direct ROS2 Unified Integration Spec)

# HK-07 ROS2 Direct Integration & Action Controller Specification
**Target State:** Zero-MQTT Intermediate Layer / Native rclpy Telemetry & Vision / Web-ROS2 Control Matrix  

---

## 1. Loại Bỏ Các Cầu Nối Trung Gian (De-bloating Middleware)
Để tối ưu hóa hiệu năng real-time, toàn bộ các cầu nối sau sẽ bị xóa bỏ hoàn toàn khỏi mã nguồn hệ thống:
1. **Xóa bỏ Flask Server (`vivo_http_mqtt_bridge.py`)**: Không nhận HTTP POST trung gian rồi bắn qua Mosquitto.
2. **Xóa bỏ MQTT Bridge (`ros2_mqtt_bridge_node.py`)**: Triệt tiêu việc dịch dịch-chuyển giữa ROS2 Topic và MQTT JSON.
3. **Xóa bỏ luồng MQTT tại FastAPI (`hk07_sensor_fusion.py`)**: Sát nhập luồng tính toán thị giác vào hệ sinh thái node ROS2 chính thức.

---

## 2. Thiết Lập Luồng Kết Nối Cảm Biến & Camera Thật 100% (Native Real-time Ingestion)


```

[Điện thoại: SensorLogs App] --------> (Dòng HTTP Stream) ----------> [hugo_perception_bridge_node] (ROS2 Humble)
|--> Publish: /telemetry/imu
|--> Publish: /vitals/wristband

[Điện thoại: IP Webcam App] ---------> (Dòng MJPEG Stream) ---------> [hk07_sensor_fusion_node] (ROS2 Humble)
|--> Thị giác máy tính (MediaPipe/OpenCV)
|--> Publish: /sensors/camera/thermal_rppg

```

### A. Tầng Cảm Biến (Mobile Gateway Node):
- Gói `mobile_gateway` được viết lại thành một Node ROS2 chính thức (`hugo_perception_bridge_node`).
- Node này trực tiếp mở socket lắng nghe dòng dữ liệu từ ứng dụng *SensorLogs* phát ra, giải mã JSON và lập tức thực hiện `self.create_publisher` phát thẳng vào các ROS2 Topic nội bộ: `/telemetry/imu` (kiểu `sensor_msgs/msg/Imu`) và `/vitals/wristband` (kiểu dữ liệu custom).

### B. Tầng Thị Giác (Vision Sensor Node):
- Gói `vision_sensor` được chuyển đổi thành `hk07_sensor_fusion_node` (Kế thừa từ `rclpy.node.Node`).
- Sử dụng trực tiếp luồng stream MJPEG thật từ camera IPWebcam thông qua `cv2.VideoCapture("http://<IP_DIEN_THOAI>:8080/video")`. 
- Tính toán xử lý ảnh thời gian thực, xuất tọa độ ngã, rPPG nhịp tim và phát vào topic `/sensors/camera/thermal_rppg`.

---

## 3. Bộ Điều Khiển Mô Phỏng Hành Động Robot (Kinematics & Action Controller)

Do robot chưa lắp động cơ vật lý, hệ thống sẽ xây dựng một Node mô phỏng động học hình học tương đối (`hugo_kinematic_controller_node`) để xử lý các lệnh thực thi từ bộ não AI:

- **Hành động Di chuyển (Bước, Đi, Chạy, Dừng):** Sử dụng bộ tích phân Euler để thay đổi tọa độ vị trí dựa trên vận tốc tuyến tính truyền về từ bộ điều hướng. Cập nhật trạng thái `joint_states` của chân robot (Mô phỏng khớp háng, khớp gối dao động theo hàm sin $A \cdot \sin(\omega t)$ để tạo dáng đi thực tế).
- **Hành động Tương tác (Cầm nắm, Ôm, Phun thuốc):** Sử dụng lời giải Động học ngược (Inverse Kinematics) dựa trên định luật hàm cos đã xây dựng tại `hk07_physics_node.py` để di chuyển tọa độ đầu cánh tay (`L1`, `L2`) tiệm cận đến tọa độ của vật thể hoặc vị trí vết thương của người dùng.

---

## 4. Giao Diện Web Điều Khiển Hệ Thống (Web-ROS2 Dashboard Gate)
- Sử dụng thư viện **`rosbridge_suite`** (mở cổng WebSocket tại port `9090` trên môi trường ROS2).
- Phía Frontend Vue3 (`hk07-dashboard`) sử dụng thư viện **`roslibjs`** để thiết lập kết nối trực tiếp đến `ws://localhost:9090`.
- **Tính năng giao diện:** 1. Hiển thị bảng điều khiển Telemetry (Nhịp tim, góc nghiêng IMU, hình ảnh camera stream lấy từ ROS2 topic).
  2. Xây dựng một bộ Joystick ảo hoặc hệ thống nút bấm hành động (`Đi`, `Dừng`, `Ôm`, `Phun thuốc`). Khi bấm nút, `roslibjs` sẽ phát trực tiếp một thông điệp điều khiển `geometry_msgs/msg/Twist` hoặc gọi một ROS2 Service xuống thẳng lõi Robot.

```

---

