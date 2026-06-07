# ĐẶC TẢ KIẾN TRÚC TÁCH RỜI LOGIC VÀ TRỰC QUAN HÓA SLAM
**Phase:** 15 // Real-world Robotics Parity

## 1. TÁCH RỜI KIẾN TRÚC (ARCHITECTURAL DECOUPLING)
- **Chuyển giao "Não bộ":** Xóa bỏ hoàn toàn engine vật lý `cannon-es` và giải thuật tính lực APF khỏi Vue Frontend.
- **Python Physics Node:** Xây dựng một node Python giả lập (`hk07_physics_node.py`) nằm ở Backend. Node này nhận PointCloud, tự tính toán va chạm, tự giải quyết IK (hoặc tính toán lực), sau đó chỉ đẩy kết quả cuối cùng (Góc của từng khớp) lên MQTT qua chuẩn `sensor_msgs/JointState`.
- **Frontend Ngu (Dumb Render):** `HolographicTwin.vue` chỉ việc subscribe vào topic `JointState` và cập nhật góc xoay xương (Bones).

## 2. CHUYỂN ĐỔI SANG MÔ HÌNH CHUẨN (GLTF/URDF)
- Rời bỏ việc khởi tạo `BoxGeometry` / `CylinderGeometry`.
- Tích hợp `GLTFLoader` của Three.js. Yêu cầu hệ thống load một file `baymax_mock.glb` (có thể dùng khối lưới tạm thời nhưng phải có cấu trúc Armature/Bones chuẩn).
- Áp dụng góc xoay từ `JointState` trực tiếp vào các node xương (`scene.getObjectByName("mixamorig_RightArm")`).

## 3. TRỰC QUAN HÓA SLAM TẦNG 2D (OCCUPANCY GRID MAP)
- Hệ thống PointCloud hiện tại là 3D. Cần thêm một mặt phẳng Lưới 2D dưới chân Robot.
- Xây dựng module biến PointCloud thành **Voxel Grid**. Các ô vuông trên sàn nếu nằm dưới Point Cloud sẽ đổi màu đỏ (Vùng cấm đi), các ô trống màu xanh (Vùng an toàn).