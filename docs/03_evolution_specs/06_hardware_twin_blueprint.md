# ĐẶC TẢ KIẾN TRÚC PHẦN CỨNG IOT VÀ BẢN SAO KỸ THUẬT SỐ 3D (HOLOGRAPHIC TWIN)
**Mã dự án:** HK-07 // BAYMAX-INTELLIGENCE
**Phiên bản:** 2.0 (Advanced Sensor & Digital Twin Integration)

## 1. MỤC TIÊU KIẾN TRÚC (ARCHITECTURAL GOALS)
Chuyển đổi từ mô phỏng ngẫu nhiên (Random Mocking) sang **Bản sao Kỹ thuật số Dựa trên Vật lý (Physics-based Digital Twin)**. Mọi dữ liệu IOT (từ bo mạch thật hoặc điện thoại giả lập) đều phải được phản ánh lập tức lên mô hình 3D trên Web, đồng thời Camera phải nâng cấp để "Đọc hiểu y khoa" thay vì chỉ quét hình học.

## 2. KIẾN TRÚC IOT & PHẦN CỨNG (SENSORS & BOARDS)

### Giai đoạn 1: Edge Computing (Tận dụng Thiết bị thông minh làm Sensor Node)
Thay vì chờ thiết kế PCB mạch cứng, hệ thống lập tức tái sử dụng Smartphone/Tablet như một Edge Node:
* **IMU & Spatial Node:** Gửi Quaternion (Pitch, Yaw, Roll), Gia tốc tuyến tính (x, y, z) qua WebSockets/MQTT để đồng bộ với chuyển động của trục tọa độ 3D trên web.
* **Optical Vitals Node:** Sử dụng Flashlight + Camera điện thoại (PPG - Photoplethysmography) để quét nhịp tim thật thay vì số ngẫu nhiên.
* **Acoustic Stress Node:** Phân tích cường độ âm giọng nói qua Microphone để đánh giá Stress_Index.

### Giai đoạn 2: Thiết kế Custom PCB (Baymax Bio-Board)
* **MCU lõi:** ESP32-S3 (Tích hợp WiFi/BLE + AI vector instructions).
* **Thermal Grid:** MLX90640 (Camera nhiệt hồng ngoại 32x24) quét thân nhiệt không chạm.
* **Tactile & Pneumatic:** Cảm biến áp lực màng mỏng (FSR) bọc quanh khung + Cảm biến áp suất BMP280 để đo độ "ôm" (Hug Force) và độ căng của giáp khí nén.

## 3. NÂNG CẤP NHẬN THỨC THỊ GIÁC ĐA PHƯƠNG THỨC (MULTIMODAL VISION)
Nâng cấp `hk07_sensor_fusion.py`:
* **Lớp 1 - Real-time Kinematics (MediaPipe):** Duy trì tracking khung xương với độ trễ thấp (<30ms).
* **Lớp 2 - Clinical & Environment Vision (LLM Vision API):** Chụp snapshot 1 frame mỗi 3-5 giây gửi cho Vision LLM (Gemini 1.5 Flash / GPT-4o).
    * *Nhiệm vụ quét:* Nhận diện vết xước/máu, phân tích sắc mặt (tái nhợt/đổ mồ hôi), và phân tích rủi ro vật lý (có vật sắc nhọn, nguy cơ vấp ngã).

## 4. KIẾN TRÚC FRONTEND: THE "HOLOGRAPHIC_TWIN" MODULE
PHÁT TRIỂN xử lý phản ánh chuyển động trong Tab/Component `[ HOLOGRAPHIC_TWIN ]` bằng **Three.js** (hoặc TresJS cho Vue) để trực quan hóa robot:
* **3D Kinematics Rendering:** Import mô hình 3D (.gltf / .glb) dạng Wireframe/Hologram. 
* **Real-time Bone Sync:** Khớp cổ, vai, hông của mô hình 3D trên màn hình sẽ xoay chính xác theo ma trận góc (Quaternion/Euler) gửi về từ IOT Node (điện thoại hoặc board mạch).
* **Pneumatic UI Overlay:** Dựng một Heatmap (Bản đồ nhiệt) bọc quanh mô hình 3D. Khi lực ép (Hug force) từ MQTT gửi về cao, các vùng trên mô hình 3D sẽ chuyển từ màu Xanh Lục (Emerald) sang Cam (Amber) báo hiệu giáp mềm đang chịu lực.