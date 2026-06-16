## 📄 TÀI LIỆU ĐẶC TẢ KIẾN TRÚC TRÍ THÔNG MINH (Hugo MAS Intelligence Specification)

# HK-07 Robot Companion - Multi-Agent System (MAS) Intelligence Specification
**Version:** 2.0.0-PROD  
**Target Architecture:** Supervisor-Router Framework with Multi-Modal Sensor Fusion  
**Author:** Huỳnh Quốc Huy  

---

## 1. Bối Cảnh Hệ Thống & Hiện Trạng (System Context & Gaps)

Hệ thống **HugoSanitas HK-07** hiện tại đang bị cô lập giữa tầng suy luận ngôn ngữ (LLM) và tầng nhận thức phần cứng (Hardware Perception), dẫn đến hiện tượng phản hồi sai lệch (Hallucination), mù thị giác máy tính và ngắt kết nối không gian không lưu vết.

Tài liệu này đặc tả kiến trúc kết nối thời gian thực giữa lõi điều phối `hk07-core` (Spring Boot), công cụ xử lý Agent `hk07-agent` (Python-FastAPI) và hai cổng dữ liệu mô phỏng phần cứng:
- **Perception Gateway (Telemetry):** `http://localhost:3000/sensor-telemetry` (Nhịp tim, IMU từ SensorLog).
- **Vision Gateway (Thị giác):** `http://localhost:3000/vision` (Hình ảnh từ IPWebcam mjpeg stream).

---

## 2. Kiến Trúc Phân Tầng Hệ Thống (Subsumption Architecture)

Kiến trúc điều khiển của HK-07 vận hành theo mô hình phân tầng phản xạ (Reactive Subsumption). Các tầng có độ ưu tiên thấp (An toàn) luôn có quyền đè bọc (Subsume) và vô hiệu hóa tầng có độ ưu tiên cao (Hội thoại).




```

+-------------------------------------------------------------+
| TẦNG 2: THẤU CẢM & HỘI THOẠI (Empathy / LLM Engine)        | --> Độ ưu tiên thấp nhất
+-------------------------------------------------------------+
| (Bị đè bọc nếu có Alert)
v
+-------------------------------------------------------------+
| TẦNG 1: CHẨN ĐOÁN Y TẾ (Medical Agent / Vitals Monitor)     |
+-------------------------------------------------------------+
| (Bị đè bọc nếu có Va chạm)
v
+-------------------------------------------------------------+
| TẦNG 0: AN TOÀN TUYỆT ĐỐI (Safety Agent / LiDAR / Subsumption)| --> Độ ưu tiên cao nhất
+-------------------------------------------------------------+

```

### Quy tắc triệt tiêu hành vi (Inhibition Rules):
- **TẦNG 0 (Safety):** Đọc luồng dữ liệu LiDAR liên tục. Nếu khoảng cách vật cản $< 20\text{ cm}$, phát tín hiệu `CRITICAL_STOP`, triệt tiêu toàn bộ lệnh di chuyển từ Tầng 1 và phát âm thanh cảnh báo an toàn.
- **TẦNG 1 (Medical):** Quét chỉ số tim mạch (`vitals`). Nếu nhịp tim $> 120\text{ bpm}$ hoặc $< 50\text{ bpm}$, tự động kích hoạt trạng thái `MEDICAL_ALERT`, đè lệnh hội thoại thông thường để chuyển sang quy trình sơ cứu khẩn cấp.

---

## 3. Đặc Tả Thiết Lập Thị Giác (Vision) & Không Gian (LiDAR)

Hệ thống bắt buộc phải tích hợp cả hai cảm biến để đạt trạng thái Hợp nhất cảm biến (Sensor Fusion):

1. **IPWebCam (Thị Giác Máy Tính):**
   - **Chức năng:** Định dạng dữ liệu hình ảnh được xử lý qua mô hình YOLOv8 hoặc CLIP nhúng tại `hk07-agent`. Trích xuất các nhãn thực thể (Object Tagging) như: `[vết_thương_hở, khuôn_mặt_buồn, tư_thế_ngã_quỵ]`.
   - **Ứng dụng:** Cung cấp thông tin trạng thái sinh học để LLM chẩn đoán và thay đổi sắc thái giọng nói của Hugo (Thấu cảm).
2. **LiDAR (Định Vị & Bản Đồ):**
   - **Chức năng:** Bắn tia laser quét môi trường 2D/3D dạng Point Cloud, xuất mảng khoảng cách góc `[theta, distance]`.
   - **Ứng dụng:** Dùng để tính toán vận tốc, điều khiển động cơ robot di chuyển đến vị trí người bệnh mà không va chạm. Camera không thể làm nhiệm vụ này vì độ sai số khoảng cách lớn.

---

## 4. Giao Thức Đối Thoại Chuẩn Baymax (Baymax Persona Protocols)

Hệ thống Prompt Lõi (System Prompt) của Hugo phải được khóa cứng các điều kiện phản hồi, ép buộc tuân thủ quy trình y tế nghiêm ngặt, loại bỏ hoàn toàn các câu trả lời sáo rỗng.

### Kịch Bản Chẩn Đoán Chuẩn (Deterministic Diagnostic Sequence):
1. **Chào mừng & Kích hoạt quét:** *"Xin chào, tôi là Hugo, robot đồng hành chăm sóc sức khỏe của bạn. Tôi sẽ tiến hành quét chỉ số sinh tồn của bạn ngay bây giờ."*
2. **Đọc dữ liệu thật:** Gọi Tool `get_sensor_telemetry`. Tuyệt đối cấm bịa đặt chỉ số nếu API lỗi hoặc trả về trống.
3. **Phân tích Sắc thái & Đưa ra Thang đo đau:**
   - *"Kết quả phân tích cho thấy nồng độ chất dẫn truyền thần kinh của bạn đang rất cao, có vẻ bạn đang gặp căng thẳng."*
   - *"Từ thang điểm từ 1 đến 10, bạn đánh giá cơn đau của mình ở mức nào?"*
4. **Đưa ra giải pháp & Giải thích hoạt chất:** *"Tôi sẽ dùng thuốc phun để làm dịu vết thương cho bạn. Thành phần chính của thuốc là kháng sinh để ngăn ngừa nhiễm trùng."*

---

## 5. Đặc Tả Tích Hợp Kỹ Thuật (Data Flow & Tool Calling)

Hệ thống Agent xử lý hội thoại sử dụng cơ chế **Tool Calling** (Function Calling) thông qua LiteLLM để ép AI chỉ được đưa ra kết luận sau khi đã đọc dữ liệu phần cứng.


```

[Browser/Frontend] -> (Axios JWT) -> [hk07-core] -> (gRPC/REST) -> [hk07-agent]
|
+-------------------------------------------------------------------+
|
v
[LLM (Groq Llama 3.3 / Gemini Pro)]
|
+---> Cần dữ liệu sinh tồn? ----> Gọi Tool: `fetch_sensor_telemetry()` -> Đọc localhost:3000/sensor-telemetry
|
+---> Cần dữ liệu hình ảnh?  ----> Gọi Tool: `capture_vision_payload()` -> Đọc localhost:3000/vision

```

### Định dạng Payload đồng bộ (JSON Schema):
Khi AI gọi dữ liệu Sensor, kết quả trả về phải map chính xác cấu trúc sau:
```json
{
  "status": "SUCCESS",
  "telemetry": {
    "heartRate": 78,
    "bloodOxygen": 98,
    "imu": { "x": 0.02, "y": -0.91, "z": 0.12 },
    "timestamp": "2026-06-13T19:20:00Z"
  }
}

```

