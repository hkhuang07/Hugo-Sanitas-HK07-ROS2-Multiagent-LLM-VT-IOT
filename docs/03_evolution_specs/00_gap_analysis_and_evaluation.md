# GAP ANALYSIS & SYSTEM EVALUATION: HK-07 VS BAYMAX IDEAL
**Project:** Hugo Sanitas HK-07  
**Date:** June 6, 2026  
**Auditor:** Antigravity (10x Principal AI Agent)

---

## 📊 SYSTEM STATUS MATRIX

| Trụ cột công nghệ (Tech Stack Pillar) | Tính năng theo Ý tưởng gốc (Original Idea) | Trạng thái hiện tại (Current Status) | Đánh giá mức độ hoàn thành |
| :--- | :--- | :--- | :--- |
| **1. Soft Robotics (Phần cứng)** | Lớp vỏ Hypalon co giãn, cơ khí nén McKibben, da điện tử e-Skin cảm biến lực, phản hồi tiêm thuốc | **Giả lập hoàn toàn (Simulated)**: telemetry sinh ngẫu nhiên áp suất L/R, `hug_force` phản hồi màu sắc giáp trên mô hình 3D Twin | 🔴 **15%** (Chỉ mô phỏng dữ liệu) |
| **2. Computer Vision (Thị giác)** | Vision-Language-Action (VLA) điều khiển tay, Quét nhiệt (Thermal), Đo nhịp tim rPPG từ mặt | **MediaPipe Rule-based + Vision LLM**: MediaPipe Pose check tư thế ngã đơn giản; Gemini Flash (OpenRouter) phân tích ảnh tĩnh mỗi 5 giây | 🟡 **40%** (Đã có frame analyzer nhưng chưa có rPPG/Thermal/VLA) |
| **3. AI Y tế & Thấu cảm (LLMs)** | Med-PaLM/BioBERT lâm sàng, RAG kết nối EHR (FHIR), Multimodal Voice-to-Voice không qua text | **Multi-Agent Router (Groq/Gemini)**: Định tuyến qua API Cloud; RAG cơ bản qua LanceDB; Voice-to-Text-to-Voice truyền thống | 🟡 **50%** (Dùng Cloud API; chưa chạy Local Edge AI, chưa có FHIR EHR) |
| **4. ROS 2 & Middleware** | ROS 2 Nodes thời gian thực, DDS routing, RTOS seL4/QNX tách biệt phần cứng với AI | **ROS 2 JSON Parity**: Cấu trúc payload chuẩn ROS2 (`sensor_msgs/*`) truyền qua MQTT Mosquitto broker và STOMP WebSockets | 🟡 **45%** (Tương thích định dạng thông điệp, chưa có hạ tầng ROS 2 thực tế) |

---

## 🔍 CHI TIẾT CÁC HẠN CHẾ & THIẾU SÓT LỚN CỦA DỰ ÁN HỒ SƠ HK-07

### 1. Vấn đề ROS 2 (Hệ điều hành Robot)
* **Ý tưởng gốc:** Sử dụng ROS 2 để quản lý phân tán các node cảm biến, actuator, điều khiển áp suất thời gian thực thông qua giao thức DDS (Data Distribution Service) với độ trễ cực thấp.
* **Thực tế dự án:**
  - Dự án **CHƯA cài đặt hoặc chạy môi trường ROS 2 thật**.
  - Hệ thống hiện tại chỉ đạt được **"Định dạng ROS 2 (Message Parity)"** bằng cách cấu trúc payload JSON gửi qua MQTT khớp với schema của `sensor_msgs/Imu`, `sensor_msgs/PointCloud2`, `geometry_msgs/Twist`, và `sensor_msgs/JointState`.
  - **Hệ quả:** Dữ liệu chạy qua MQTT Broker (Mosquitto) dạng JSON có độ trễ lớn, hao phí CPU để encode/decode chuỗi text JSON, không đảm bảo tính năng thời gian thực cứng (Hard Real-Time) và thiếu khả năng điều khiển trực tiếp các driver động cơ/van khí nén của robot thật.

### 2. Vấn đề Computer Vision (Thị giác máy tính)
* **Ý tưởng gốc:** Sử dụng mô hình VLA (Vision-Language-Action) dịch chuyển trực tiếp hình ảnh thành hành động tay robot; Quét nhiệt hồng ngoại phát hiện sốt; Đo nhịp tim rPPG bằng cách phân tích biến đổi màu sắc vi mạch da mặt từ video.
* **Thực tế dự án:**
  - **Chỉ có MediaPipe cục bộ:** File `hk07_sensor_fusion.py` sử dụng thư viện MediaPipe để lấy tọa độ khung xương (Pose Landmarks). Thuật toán phát hiện ngã cực kỳ thô sơ bằng cách kiểm tra xem tọa độ mũi (`NOSE.y`) có thấp hơn hông (`hip_y`) hay không.
  - **Chưa có VLA / rPPG / Thermal:** Hoàn toàn không có tích hợp camera nhiệt vật lý, chưa xây dựng module rPPG xử lý ảnh tần số cao để bóc tách nhịp tim, và chưa có mô hình hành động VLA (phải điều khiển IK cánh tay thủ công bằng giải thuật hình học 2-link trong node vật lý Python backend).

### 3. Vấn đề LLM (Trí tuệ nhân tạo & Mô hình ngôn ngữ)
* **Ý tưởng gốc:** Bộ não Edge AI chạy offline (nhỏ gọn như card chip y tế của Baymax) kết nối RAG EHR tiêu chuẩn FHIR; Giao tiếp đa phương thức âm thanh (Multimodal Speech AI) nghe trực tiếp tông giọng/tiếng khóc để thấu cảm không qua trung gian text.
* **Thực tế dự án:**
  - **Phụ thuộc 100% vào Cloud API (Gemini/OpenRouter/Groq):** Nếu mất kết nối Internet, "bộ não" của HK-07 sẽ bị tê liệt hoàn toàn do không có mô hình LLM chạy Local/Edge (như ONNX LLaMA2-7B fallback từng được đề xuất).
  - **Độ trễ giao tiếp lớn:** Luồng xử lý âm thanh vẫn phải chạy tuần tự: *User Audio -> Speech-To-Text (Whisper) -> Text LLM -> Text-To-Speech*, gây ra độ trễ từ 2-4 giây, làm mất đi tính tự nhiên "giọng nói ấm áp phản xạ tức thì" của Baymax.
  - **Thiếu chuẩn Y tế EHR:** LanceDB mới lưu trữ các vector tri thức thô, chưa tích hợp cổng kết nối EHR/FHIR lâm sàng thực tế để truy xuất bệnh án.

### 4. Vấn đề Phần cứng & RTOS An toàn (Fail-Safe)
* **Ý tưởng gốc:** Lớp vỏ hơi mềm tự xả khí nhũn ra an toàn khi AI bị treo nhờ RTOS (QNX/seL4) chạy tách biệt ở tầng vi điều khiển.
* **Thực tế dự án:**
  - Toàn bộ cơ chế an toàn deterministic (E-STOP, Subsumption Inhibit) đang chạy bằng code ứng dụng Java (Spring Boot) và Python ở tầng Middleware.
  - Nếu hệ điều hành Windows/Linux bị đơ hoặc tiến trình Java/Python bị crash, robot sẽ mất hoàn toàn khả năng tự vệ và không thể kích hoạt van xả khí khẩn cấp.

---

## 🛠️ ĐỀ XUẤT LỘ TRÌNH KHẮC PHỤC (ROADMAP TO REAL BAYMAX)

```
[Mục tiêu: Baymax Thực tế]
       │
       ├─► [Ngay lập tức]: Tích hợp cục bộ micro-ROS hoặc ROS 2 Foxy/Humble Python nodes, 
       │                  chuyển đổi MQTT JSON sang DDS Binary Serialized để giảm latency.
       │
       ├─► [Trung hạn]: Triển khai Local LLM (Llama-3-8B-Instruct quantized ONNX/TensorRT) 
       │                chạy offline trên NVIDIA Jetson Orin để không bị phụ thuộc vào Cloud.
       │
       └─► [Dài hạn]: Tích hợp OpenCV rPPG để đo HR qua camera thường; thiết lập firmware RTOS 
                      (FreeRTOS) trên vi điều khiển ESP32 quản lý van xả khí độc lập.
```
