# ĐẶC TẢ KIẾN TRÚC ĐA TÁC NHÂN (MULTI-AGENT ARCHITECTURE)
**Mã hiệu Kiến trúc:** Mutil-Agent-HK07--MAS-STANDARD
**Dự án:** HK-07 Hugo Sanitas
**Framework triển khai:** Python FastAPI + LangGraph (hoặc Routing tự xây dựng thuần túy)

## 1. TRIẾT LÝ THIẾT KẾ (THE PHILOSOPHY)
Hệ thống không sử dụng một LLM "ôm đồm" mọi thứ. Thay vào đó, áp dụng cơ chế Phân rã Trách nhiệm (Separation of Concerns) theo mô hình Node-Router. Hệ thống bao gồm 1 Agent Điều phối (Supervisor/Router) và 3 Agent Chuyên biệt.

## 2. SƠ ĐỒ ĐỊNH TUYẾN (AGENT ROUTING TOPOLOGY)
Khi có một Request (từ User Voice, Text, hoặc Sensor Data) bay vào hệ thống, luồng xử lý BẮT BUỘC tuân thủ:

### [NODE 0] SUPERVISOR AGENT (Bộ Não Điều Phối)
- **Nhiệm vụ:** Phân loại ý định của input đầu vào cực nhanh (Classification).
- **Quyết định (Routing logic):**
  - Nếu input là dữ liệu cảm biến (Gia tốc, SpO2, HR) -> Chuyển luồng sang `[NODE 1]`.
  - Nếu input là câu hỏi y tế, khai báo triệu chứng đau ốm -> Chuyển luồng sang `[NODE 2]`.
  - Nếu input là tâm sự buồn chán, câu hỏi giao tiếp thông thường -> Chuyển luồng sang `[NODE 3]`.

### [NODE 1] SAFETY & HARDWARE AGENT (Tác nhân An toàn Cơ học - Tầng Subsumption)
- **LLM Usage:** KHÔNG SỬ DỤNG LLM (Đảm bảo độ trễ < 5ms).
- **Nhiệm vụ:** Xử lý thuần túy bằng code Logic/Toán học.
- **Hành động:** Tính toán tọa độ IMU, LiDAR. Nếu phát hiện vật cản hoặc té ngã -> Bắn thẳng lệnh `INHIBIT / SOS` qua MQTT. Không cần giao tiếp với người.

### [NODE 2] MEDICAL AGENT (Tác nhân Lâm sàng)
- **LLM Usage:** Mô hình suy luận logic cao (vd: Llama-3 / Groq).
- **System Prompt:** "Bạn là một bác sĩ chẩn đoán. Phân tích các chỉ số sinh tồn và triệu chứng."
- **Nhiệm vụ:** Nhận dữ liệu sinh tồn từ Node 1 hoặc triệu chứng từ Node 0. So sánh với Data Ngưỡng Y tế (Dynamic Thresholds).
- **Hành động:** Trả về kết luận chẩn đoán (JSON format) và cảnh báo y tế nếu cần thiết.

### [NODE 3] EMPATHETIC AGENT (Tác nhân Thấu cảm & Tâm lý)
- **LLM Usage:** Mô hình thiên về ngôn ngữ tự nhiên, cảm xúc (vd: Gemini 1.5 Flash/Pro).
- **System Prompt:** "Bạn là Baymax, một trợ lý chăm sóc sức khỏe. Giọng điệu ấm áp, xoa dịu (There, there)."
- **Hành động:** Truy vấn LanceDB (Vector Database) để nhớ lại ngữ cảnh bệnh nhân. Tạo ra câu trả lời xoa dịu, hướng dẫn hít thở, hoặc phản hồi thông thường.

## 3. RÀNG BUỘC KỸ THUẬT (STRICT CONSTRAINTS)
1. **Fallback Mechanism:** Bất kỳ LLM Agent nào gọi API bị lỗi (HTTP 429/500) phải lập tức tự động fallback sang LLM dự phòng (Groq <-> Gemini).
2. **State Management:** Trạng thái của biểu đồ hội thoại (Graph State) phải truyền qua lại giữa các Node dưới dạng cấu trúc `TypedDict` chuẩn xác (chứa `messages`, `vitals`, `current_agent`).
3. **No Code Spaghettification:** Mỗi Agent phải nằm trong một file Python riêng biệt (vd: `agents/medical_agent.py`, `agents/empathetic_agent.py`, `agents/router_agent.py`).  