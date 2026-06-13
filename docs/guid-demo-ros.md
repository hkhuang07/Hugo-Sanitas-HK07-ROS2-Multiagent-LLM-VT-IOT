>>> [ROS2_DEMO_EXECUTION_GUIDE]

Dưới đây là các bước chi tiết để chạy kiểm thử (demo) các node ROS 2 trong môi trường WSL (Windows Subsystem for Linux):

### 📋 Bước 1: Mở Terminal WSL và Nạp Môi trường ROS 2
Mở terminal WSL (Ubuntu) và chạy lệnh sau để thiết lập môi trường toàn cục cho ROS 2 Humble:
```bash
source /opt/ros/humble/setup.bash
```

### 🛠️ Bước 2: Di chuyển vào Robotics Workspace và Build Package
Di chuyển tới thư mục robotics của dự án và thực hiện build package `sensors`:
```bash
cd /mnt/d/Study/HK.Huang_Lab/hugo-sanitas-hk-07/hk-07/source/robotics
colcon build --packages-select sensors
```
*Lưu ý:* Sau khi build thành công, nạp overlay của workspace để đăng ký các executable node mới vào ROS 2:
```bash
source install/setup.bash
```

### 🚀 Bước 3: Khởi chạy các Node Mô phỏng & Cầu nối

Mở **3 tab terminal WSL** khác nhau, nạp môi trường (`source /opt/ros/humble/setup.bash` và `source install/setup.bash`) rồi chạy các lệnh sau:

#### Terminal 1: Chạy mô phỏng cảm biến rPPG & Nhiệt độ (Thermal)
```bash
ros2 run sensors rppg_thermal_node
```
*(Node này sẽ bắt đầu sinh dữ liệu mô phỏng nhịp tim rPPG, nhiệt độ cơ thể và Fever Alert ở tần số 1Hz)*

#### Terminal 2: Chạy ROS 2 - MQTT Bridge Node
```bash
ros2 run sensors ros2_mqtt_bridge_node
```
*(Node cầu nối này sẽ lắng nghe dữ liệu từ topic ROS 2 `/sensors/camera/thermal_rppg`, parse dữ liệu và publish lên MQTT broker local tại cổng 1883)*

#### Terminal 3: Kiểm tra dữ liệu thô truyền trên ROS 2 DDS
Để kiểm tra xem dữ liệu có truyền thực tế trên ROS 2 hay không, chạy lệnh lắng nghe topic:
```bash
ros2 topic echo /sensors/camera/thermal_rppg
```

### 🖥️ Bước 4: Kiểm tra hiển thị trên Web Dashboard
1. Đảm bảo Backend Spring Boot và Frontend Dashboard (`npm run dev`) đang hoạt động.
2. Truy cập vào trang **Companion View** trên giao diện dashboard.
3. Quan sát mục `[ VISION_SENSORS_FEED ]` để thấy các thông số nhiệt độ trán (`Thermal Temp`), nhịp tim (`rPPG HR`) và cảnh báo sốt (`Fever Alert`) cập nhật thời gian thực từ ROS 2.