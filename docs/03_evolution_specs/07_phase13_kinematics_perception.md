# ĐẶC TẢ KIẾN TRÚC MÔ PHỎNG CƠ HỌC VÀ NHẬN THỨC KHÔNG GIAN THỰC TẾ
**Phase:** 13 // True Robotics Twin

## 1. HỆ THỐNG ĐỘNG HỌC NGƯỢC (IK) VÀ QUATERNION (KINEMATICS ENGINE)
- **Từ bỏ Euler:** Chuyển toàn bộ luồng truyền tải góc xoay sang **Quaternion** để đảm bảo chuyển động mượt mà 360 độ (Tránh Gimbal Lock).
- **Mạch lọc Sensor Fusion (Edge Node):** Tại gateway của điện thoại (`vivo_http_mqtt_bridge.py`), tích hợp thuật toán lọc bù (Complementary Filter) để xử lý dữ liệu thô (Raw Accel + Gyro) thành Quaternion chuẩn trước khi đẩy lên MQTT.
- **Three.js IK Solver:** Frontend áp dụng thư viện `THREE.CCDIKSolver` (hoặc cấu trúc xương SkinnedMesh). Khi nhận được lệnh "Đưa tay ôm", tọa độ (x,y,z) của bàn tay thay đổi -> Hệ thống tự động tính toán góc gập của cùi chỏ và bả vai.

## 2. TRỰC QUAN HÓA ĐÁM MÂY ĐIỂM (LIDAR POINT CLOUD VISUALIZATION)
Để mô phỏng quá trình quét và né vật thể:
- **LiDAR Mock Stream:** Tạo một script Python `lidar_pointcloud_sim.py` phát ra một mảng các tọa độ 3D (mô phỏng chướng ngại vật đang tiến lại gần).
- **Three.js PointsMaterial:** Trong `HolographicTwin.vue`, hứng stream này và render thành các hạt (Particles) màu Cam/Đỏ xung quanh robot.
- **Raycaster Collision:** Robot sẽ phóng các tia Raycast trong không gian 3D. Nếu tia chạm vào Point Cloud (vật cản), kích hoạt Subsumption Safety Layer.

## 3. TRỰC QUAN HÓA PHẢN XẠ NÉ TRÁNH (OBSTACLE AVOIDANCE VECTORS)
- **Artificial Potential Field (Trường thế nhân tạo):** Khi Subsumption Layer (Tầng 0) quyết định né vật thể, nó sinh ra một lực đẩy (Repulsive Vector).
- **UI Overlay:** Vẽ một mũi tên vector (ArrowHelper) phát sáng màu Đỏ (`#FF3333`) ngay trên giao diện 3D chỉ hướng robot đang bị đẩy ra xa khỏi vật cản, đồng thời kích hoạt chuyển động lùi của mô hình thông qua IK.