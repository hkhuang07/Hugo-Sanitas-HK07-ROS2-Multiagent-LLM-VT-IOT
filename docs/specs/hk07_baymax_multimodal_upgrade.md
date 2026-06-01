# ĐẶC TẢ KIẾN TRÚC ĐA PHƯƠNG THỨC & AI CHỦ ĐỘNG (BAYMAX MULTIMODAL STANDARD)
**Mã tài liệu:** HK07-BAYMAX-V3
**Mục tiêu:** Nâng cấp HK-07 thành một Robot Y tế Đa phương thức (Multimodal), có khả năng Nghe - Nói (VUI), Chủ động phát cảnh báo (Proactive) và Nhìn - Chẩn đoán qua hình ảnh thực tế (Vision), trong khi vẫn duy trì độ ổn định của giao diện điều khiển bằng văn bản (Text).

## MŨI NHỌN 1: GIAO THỨC SONG SONG (DUAL-MODE TEXT & VOICE VUI)
Bổ sung năng lực giọng nói song hành cùng văn bản. Người dùng có thể linh hoạt chọn phương thức giao tiếp tùy bối cảnh.
* **Frontend (Vue 3):**
  * **Giữ nguyên luồng Text:** Khung nhập liệu (Input box) và nút Gửi (Send) bằng văn bản phải được giữ nguyên hoàn toàn.
  * **Tích hợp Web Speech API (SpeechRecognition):** Thêm một nút Micro (Hold to Talk) nằm bên cạnh ô nhập Text. Khi nhấn giữ, ghi âm và tự động parse thành Text, điền vào ô input hoặc gửi thẳng lên Backend.
  * **Tích hợp SpeechSynthesis API (Text-to-Speech):** Khi Backend trả về câu chẩn đoán, dòng Text vẫn hiển thị trên màn hình, đồng thời Frontend tự động gọi API để đọc to câu trả lời bằng giọng nam/trầm ấm.

## MŨI NHỌN 2: AI CHỦ ĐỘNG BÁO ĐỘNG (PROACTIVE INTERRUPTION)
AI không chờ người dùng hỏi. Nó phải tự thức giấc khi sinh mệnh chủ nhân bị đe dọa.
* **Python Agent & Orchestrator:**
  * Giám sát liên tục luồng Vitals từ MQTT. Nếu `MedicalAgent` đánh giá sinh hiệu rơi vào trạng thái `CRITICAL` (VD: Nhịp tim tụt đột ngột, SpO2 < 90%), Agent **được quyền bypass luồng Chat thông thường**.
  * Phát một tín hiệu khẩn cấp (Push Event) có tên `AI_EMERGENCY_WAKEUP` kèm theo thông điệp y tế.
* **Frontend (Dashboard):**
  * Lắng nghe tín hiệu WebSocket `AI_EMERGENCY_WAKEUP`.
  * Khi nhận được: Tự động kích hoạt loa ngoài đọc to lời cảnh báo (VD: *"Phát hiện nhịp tim tụt nguy hiểm. Bạn có ổn không?"*).
  * Hiển thị một Modal đếm ngược 10 giây (SOS Countdown). Nếu người dùng không bấm "Hủy", Frontend tự động gọi một API Webhook để kích hoạt gửi SMS/Email cấp cứu đến *Emergency Contacts*.

## MŨI NHỌN 3: TÍCH HỢP THỊ GIÁC MÁY TÍNH (VISION-LANGUAGE MODEL)
Kích hoạt "Đôi mắt" thực sự cho HK-07 thay vì chỉ tính toán ma trận khung xương.
* **Giao tiếp Cảm biến (Sensor Fusion):**
  * Script `hk07_sensor_fusion.py` phải duy trì một biến bộ đệm (buffer) chứa khung hình (frame) mới nhất từ luồng Camera điện thoại.
* **Luồng Tool Calling (Python Agent):**
  * Khi nhận diện ý định "Quét tôi ngay" hoặc "Tôi trông thế nào", Agent kích hoạt Tool `execute_visual_scan()`.
  * Tool này sẽ trích xuất frame ảnh mới nhất từ buffer, encode thành định dạng Base64.
  * Gửi Base64 image + Chỉ số sinh tồn hiện tại lên **Gemini 1.5 Pro/Flash Vision API** với Prompt chuyên sâu: *"Đóng vai bác sĩ cấp cứu. Quan sát màu da, biểu cảm khuôn mặt, các vết thương hở (nếu có) trong ảnh. Kết hợp với chỉ số sinh hiệu [X] để đưa ra chẩn đoán nhanh và hướng dẫn sơ cứu."*
  * Trả kết quả về Frontend để hiển thị Text và phát âm thanh.