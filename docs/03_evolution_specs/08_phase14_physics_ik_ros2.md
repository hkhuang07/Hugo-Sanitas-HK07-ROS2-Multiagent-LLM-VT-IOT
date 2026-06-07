# ĐẶC TẢ KIẾN TRÚC VẬT LÝ VÀ CHUẨN HÓA DỮ LIỆU ROS2
**Phase:** 14 // Physical Reality & Articulation

## 1. HỆ THỐNG ĐỘNG HỌC NGƯỢC (FULL-BODY INVERSE KINEMATICS)
- **Mục tiêu:** Rời bỏ việc xoay nguyên khối. Mô phỏng cử động khớp (Joint Articulation).
- **Kiến trúc:** Áp dụng `THREE.CCDIKSolver` (hoặc CCD-IK) vào `HolographicTwin.vue`.
- **Cơ chế:** Khai báo cấu trúc xương (Bones) cho Baymax: Spine -> Shoulder -> Elbow -> Hand. Khi tọa độ mục tiêu (Target Effector) thay đổi (ví dụ: khi đưa tay ra ôm hoặc đỡ đòn), hệ thống IK sẽ tự động tính toán góc xoay (Quaternion) của cùi chỏ và vai mà không cần backend gửi từng góc.

## 2. ENGINE VẬT LÝ THỜI GIAN THỰC (REAL-TIME PHYSICS ENGINE)
- **Mục tiêu:** Tích hợp tương tác vật lý thật thay vì chỉ vẽ mũi tên vector.
- **Kiến trúc:** Tích hợp `cannon-es` (hoặc `rapier3d`) vào luồng render của Vue/Three.js.
- **Cơ chế:** - Gắn `Trimesh` hoặc `CylinderCollider` bao quanh các bộ phận của robot.
  - Các hạt Point Cloud từ LiDAR giả lập sẽ được gắn `SphereCollider`.
  - Khi Point Cloud va chạm vào tay robot, Physics Engine sẽ tạo ra lực phản hồi (Impulse Force), khiến hệ thống IK tự động rụt tay lại (Phản xạ tủy sống - Subsumption Layer 0).

## 3. CHUẨN HÓA ROS2 MESSAGE QUA MQTT (ROS2 BRIDGE PREPARATION)
- **Mục tiêu:** Đảm bảo Backend và Frontend nói ngôn ngữ của Robot thật. Sẵn sàng 100% cho Micro-ROS.
- **Kiến trúc:** Refactor toàn bộ payload MQTT.
  - LiDAR Point Cloud -> Chuyển sang format `sensor_msgs/PointCloud2`.
  - IMU Quaternion -> Chuyển sang format `sensor_msgs/Imu`.
  - Lệnh di chuyển động cơ -> Chuyển sang format `geometry_msgs/Twist` (bao gồm linear và angular velocity).