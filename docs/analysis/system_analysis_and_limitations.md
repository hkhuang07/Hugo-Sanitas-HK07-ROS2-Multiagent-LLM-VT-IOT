# BÁO CÁO PHÂN TÍCH CHỨC NĂNG HỆ THỐNG & 20 HẠN CHẾ TRONG MÃ NGUỒN

> **Dự án:** HK-07 // HUGO SANITAS ROBOT COMPANION
> **Mã hiệu:** SPEC-ANALYSIS-2026-V1
> **Người thực hiện:** Antigravity UI/UX & Lead Architect

---

## PHẦN I: PHÂN TÍCH TOÀN BỘ CHỨC NĂNG HỆ THỐNG HIỆN TẠI

Hệ thống **HK-07 // HUGO SANITAS** hoạt động dưới dạng một hệ thống phần cứng - phần mềm tích hợp (Cyber-Physical System - CPS), chia thành 3 phân vùng xử lý độc lập có sự liên kết chặt chẽ:

### 1. Phân hệ IoT & Simulation Layer (Lớp thiết bị và giả lập)
* **Chức năng:** Thu thập dữ liệu thô (raw signals) từ môi trường vật lý và sinh học của bệnh nhân.
* **Các cảm biến tích hợp:**
  * Vòng đeo tay sức khỏe (BLE Wristband) đo đạc liên tục các chỉ số: nhịp tim (Heart Rate), huyết áp tâm thu/tâm trương (Systolic/Diastolic), nhiệt độ cơ thể (Body Temperature), nồng độ oxy trong máu (SpO2), và một nút bấm khẩn cấp y tế (SOS Button).
  * Cảm biến chuyển động (IMU) trên người bệnh nhân để phát hiện ngã (Fall detection).
  * Cảm biến LiDAR và đo khoảng cách hồng ngoại trên Robot HK-07 để quét vật cản và địa hình.
* **Nguyên lý:** Dữ liệu được mã hóa JSON và phát với tần số từ 10Hz - 20Hz qua giao thức MQTT đến Broker Mosquitto trung tâm.

### 2. Phân hệ Backend Core - Spring Boot 3.2 (Java 21 Virtual Threads)
* **Chức năng:** Đóng vai trò là "Trung tâm chỉ huy chính", điều phối dòng thông tin thời gian thực, lưu trữ dữ liệu y tế, và thực thi các phản xạ bảo vệ.
* **Các module chính:**
  * **MQTT Listener Bridge:** Lắng nghe trực tiếp các sự kiện từ cảm biến.
  * **Bảo mật (Security & JWT):** Phân quyền người dùng (Owner/Medic/Guest), bảo mật toàn diện các HTTP API và luồng WebSocket STOMP bằng bộ lọc Inbound Channel Interceptor.
  * **Database Engine:** Sử dụng MariaDB lưu trữ lâu dài bệnh án lịch sử, cấu hình của Robot. Sử dụng Redis để quản lý vòng đời Session token và chống spam tin nhắn (Throttling).
  * **Emergency Reflex Loop:** Phân tích ngưỡng cứng của các chỉ số sinh tồn. Khi phát hiện biến cố nguy hiểm, ngay lập tức gửi lệnh Inhibit qua MQTT để phanh Robot khẩn cấp trong thời gian `< 5ms`.

### 3. Phân hệ AI Multi-Agent Engine (Python FastAPI)
* **Chức năng:** Đóng vai trò là "Khối óc nhận thức lâm sàng và thấu cảm". Sử dụng mô hình tác nhân lập luận kết hợp mô hình Subsumption Architecture:
  * **Tầng 0 (Safety Agent):** Giám sát LiDAR và IMU để kích hoạt phanh khẩn cấp cục bộ (Không sử dụng LLM để tránh độ trễ).
  * **Tầng 1 (Medical Agent):** Phân tích y học dựa trên ngưỡng y tế kết hợp LLM (Groq Llama 3) để đưa ra chẩn đoán và cảnh báo đột quỵ/đột quỵ tim.
  * **Tầng 2 (Empathetic Agent):** Sử dụng các mô hình ngôn ngữ lớn (Gemini Pro/Llama 3) để trò chuyện, thấu cảm tâm lý, và hướng dẫn bệnh nhân bình tĩnh trong các tình huống nguy cấp.

### 4. Phân hệ Frontend Dashboard (Vue 3 + Vite + TypeScript)
* **Chức năng:** Trực quan hóa dữ liệu telemetry, cung cấp bảng điều khiển trung tâm cho Bác sĩ (Medic) và Người nhà (Owner).
* **Các màn hình chức năng:**
  * **Vitals Dashboard:** Hiển thị thời gian thực các chỉ số sinh tồn và vẽ biểu đồ sóng điện tâm đồ (ECG Waveform) mượt mà 60FPS bằng Canvas.
  * **Companion View:** Khung chat tương tác trực tiếp với robot trợ lý y tế.
  * **Agents System Log:** Hiển thị trực quan luồng quyết định, độ trễ và log của từng tác nhân AI.
  * **Safety Coordinates:** Radar hiển thị lưới chướng ngại vật và hệ thống nút ngắt chuyển động thủ công.
  * **Historical Metrics:** Tra cứu, tổng hợp dữ liệu sức khỏe trong lịch sử.

---

## PHẦN II: 20 HẠN CHẾ KỸ THUẬT HIỆN TẠI TRONG MÃ NGUỒN (SRC)

Qua rà soát và đánh giá sâu cấu trúc mã nguồn hiện tại, dưới đây là 20 hạn chế kỹ thuật cần được tối ưu hóa trong các phiên bản tiếp theo:

### 1. Hạn chế trên lớp Frontend (Vue 3)

1. **Biểu đồ sóng ECG là dữ liệu giả lập (ECG Waveform Simulation):**
   * *Mô tả:* Biểu đồ ECG trong component `EcgWaveform.vue` được vẽ bằng công thức toán học nội sinh (Hàm Sine/Cosine kết hợp noise) chứ chưa thực sự phân tách và vẽ từ chuỗi dữ liệu nhịp tim thô nhận về từ cảm biến IoT.
2. **Cơ chế tái kết nối WebSocket dạng tuyến tính (Linear Reconnect Policy):**
   * *Mô tả:* Khi mất kết nối mạng, dịch vụ `websocket.ts` thực hiện kết nối lại sau mỗi khoảng thời gian cố định. Điều này dễ gây ra hiện tượng nghẽn mạng dây chuyền (Connection storm) lên Server khi hệ thống khôi phục. Cần chuyển sang thuật toán Exponential Backoff (chờ tăng dần).
3. **Thiếu cơ chế đồng bộ đa Client (Multi-Client State Sync):**
   * *Mô tả:* Nếu hai người dùng (ví dụ: 2 Medic) cùng đăng nhập vào Dashboard, hệ thống chưa có cơ chế locking hay đồng bộ trạng thái bật/tắt khẩn cấp thủ công, dễ dẫn đến xung đột thao tác trên Robot.
4. **Không có bộ đệm offline cho dữ liệu sinh tồn (No Offline Client-Side Cache):**
   * *Mô tả:* Khi WebSocket bị mất kết nối tạm thời, các gói dữ liệu nhịp tim phát ra trong thời gian đó bị mất hoàn toàn trên giao diện Vue thay vì được lưu đệm tạm thời vào `IndexedDB` hoặc `LocalStorage` để vẽ bù lại.
5. **Cấu hình Port và Endpoints bị khai báo cứng (Hardcoded Endpoints in Build):**
   * *Mô tả:* Một số file service và cấu hình gọi API vẫn đang tham chiếu cứng đến `localhost` hoặc các cổng port cụ thể (`8888`, `8889`), gây khó khăn cho việc deploy lên staging/production mà không phải build lại mã nguồn frontend.

### 2. Hạn chế trên lớp Backend Core (Spring Boot)

6. **MQTT Listener Bridge hoạt động đơn luồng (Single-threaded MQTT Bridge):**
   * *Mô tả:* Cấu hình nhận tin MQTT của Spring Boot xử lý tất cả các gói tin cảm biến (nhịp tim, LiDAR, IMU) tuần tự trên một luồng listener duy nhất, dễ gây hiện tượng nghẽn cổ chai khi số lượng thiết bị IoT tăng lên.
7. **Thiếu cơ chế tối ưu kết nối DB với luồng ảo (Virtual Threads Connection Pool Tuning):**
   * *Mô tả:* Mặc dù Spring Boot đã kích hoạt Java 21 Virtual Threads, nhưng Connection Pool của MariaDB (HikariCP) vẫn sử dụng cấu hình mặc định, chưa được tối ưu hóa cho mô hình concurrency cực lớn của luồng ảo, dễ gây cạn kiệt kết nối DB tạm thời.
8. **Chưa áp dụng ghi dữ liệu sinh tồn theo lô (No Batch Vitals Inserts):**
   * *Mô tả:* Backend lưu lịch sử nhịp tim vào MariaDB theo cơ chế ghi từng dòng đơn lẻ cho mỗi gói tin MQTT nhận về. Với tần số sensor 10Hz, việc này tạo áp lực I/O cực lớn lên đĩa cứng. Cần chuyển sang ghi theo lô (Batch insert) sau mỗi 5s.
9. **Ngưỡng kiểm tra sức khỏe bị cấu hình cứng (Hardcoded Vitals Thresholds):**
   * *Mô tả:* Các ngưỡng kích hoạt cảnh báo đột quỵ hay nhịp tim nguy hiểm (`HR_MAX = 120`, `SPO2_MIN = 92%`) đang được khai báo dưới dạng hằng số Java tĩnh thay vì tải động từ bảng cấu hình cơ sở dữ liệu của từng người dùng cụ thể.
10. **Thiếu hệ thống giới hạn tần suất yêu cầu trên WebSocket (No WebSocket Rate Limiter):**
    * *Mô tả:* Người dùng có thể gửi vô hạn tin nhắn hoặc lệnh điều hướng qua cổng WebSocket mà không bị kiểm soát tần suất, tạo nguy cơ bị tấn công từ chối dịch vụ (DoS) qua kênh STOMP.
11. **Log kiểm toán y tế chưa được chuẩn hóa cấu trúc (Lack of Structured Audit Logging):**
    * *Mô tả:* Các hành động quan trọng như "Kích hoạt phanh khẩn cấp" hoặc "Hủy trạng thái SOS" chỉ được log ra file text thông thường thay vì ghi vào một bảng dữ liệu Audit Trail có ký số bảo mật phục vụ công tác thanh tra y tế.

### 3. Hạn chế trên lớp Động cơ AI (Python FastAPI Multi-Agent)

12. **Sử dụng thư viện gọi API đồng bộ trong luồng bất đồng bộ (FastAPI Blocking Calls):**
    * *Mô tả:* Một số đoạn mã trong phần tích hợp LLM vẫn sử dụng hàm blocking hoặc đồng bộ ngầm khi xử lý dữ liệu vector lân cận, gây giảm hiệu năng xử lý vòng lặp Event Loop của Python.
13. **Xử lý lỗi API Groq/Gemini chưa có phương án dự phòng (No LLM Fallback):**
    * *Mô tả:* Khi API Groq hoặc Gemini bị lỗi kết nối hoặc hết quota (Rate Limit), Agent lập tức trả về chuỗi lỗi thô hoặc mock rỗng mà chưa có cơ chế tự động chuyển đổi dự phòng sang LLM khác (ví dụ: chuyển từ Groq sang Gemini và ngược lại).
14. **Cơ chế phân tích JSON từ LLM dễ bị lỗi (Brittle LLM JSON Parsing):**
    * *Mô tả:* Medical Agent ép LLM trả về định dạng JSON bằng System Prompt, nhưng nếu LLM trả về kèm các đoạn text hội thoại thừa thãi (ví dụ: "Sure, here is the JSON..."), hàm `json.loads` trong Python sẽ crash và trả về kết quả phân tích thất bại.
15. **Dữ liệu VectorDB chưa có cơ chế dọn dẹp và nén (No LanceDB Compaction):**
    * *Mô tả:* Cơ sở dữ liệu vector LanceDB lưu thông tin ngữ cảnh hội thoại thấu cảm liên tục lưu trữ trên RAM/Disk mà chưa có tác vụ nền tự động nén (Compaction) và xóa các vector ngữ cảnh cũ quá hạn, gây tăng bộ nhớ đệm theo thời gian.
16. **Subsumption Architecture phụ thuộc vào độ ổn định mạng (Network-coupled Subsumption):**
    * *Mô tả:* Quyết định chặn (Inhibit) của Safety Agent gửi đến Spring Boot Core thông qua mạng MQTT. Nếu broker bị lag hoặc mất gói tin, tính năng phanh an toàn sẽ mất tác dụng. Đúng thiết kế công nghiệp, tín hiệu này cần chạy qua kênh truyền trực tiếp (IPC) hoặc phần cứng có dây.

### 4. Hạn chế trên lớp Mô phỏng & Triển khai (Simulation & Deployment)

17. **Cấu hình Broker Mosquitto không xác thực (No MQTT Authentication):**
    * *Mô tả:* File `mosquitto.conf` hiện tại cấu hình `allow_anonymous true` không yêu cầu mật khẩu kết nối. Bất kỳ ai trong mạng nội bộ đều có thể gửi tin giả lập nhịp tim hoặc điều khiển Robot, tạo lỗ hổng bảo mật nghiêm trọng.
18. **Giả lập Webots và ROS 2 là đơn hướng (Unidirectional Simulation Loop):**
    * *Mô tả:* Các script mô phỏng chỉ đẩy dữ liệu cảm biến lên MQTT một chiều mà chưa nhận ngược lại các lệnh điều khiển tốc độ thực tế từ Spring Boot gửi xuống, làm hạn chế khả năng kiểm thử vòng lặp phản hồi đóng (Closed-Loop Testing).
19. **Thiếu cơ chế dự phòng cho MQTT Broker (No Broker Failover):**
    * *Mô tả:* Hệ thống phụ thuộc duy nhất vào 1 instance Mosquitto Broker. Nếu container này gặp lỗi, toàn bộ luồng truyền tin y tế lập tức bị sụp đổ hoàn toàn mà không có Broker phụ cấu hình HA (High Availability).
20. **Thiếu cơ chế kiểm tra sức khỏe phụ thuộc trong Docker Compose (No Healthcheck Dependency):**
    * *Mô tả:* Docker Compose chỉ sử dụng `depends_on` ở mức khởi động container. Điều này khiến `hk07-core` chạy trước khi MariaDB hoặc Redis thực sự sẵn sàng nhận kết nối, dẫn đến lỗi crash ngắt quãng trong quá trình khởi động ban đầu.

---

## PHẦN III: ĐỀ XUẤT LỘ TRÌNH KHẮC PHỤC (ROADMAP)

| Thứ tự ưu tiên | Hạn chế giải quyết | Giải pháp đề xuất |
|:---:|---|---|
| **P0 (Ngay lập tức)** | 17, 20 | Bật xác thực MQTT bằng user/pass; bổ sung `healthcheck` cho DB/Redis trong Docker Compose. |
| **P1 (Quan trọng)** | 1, 8, 14 | Sử dụng dữ liệu nhịp tim thô để render ECG; cài đặt cơ chế Batch Insert cho Vitals; viết hàm Regex bóc tách JSON an toàn từ LLM. |
| **P2 (Trung hạn)** | 2, 6, 9, 13 | Triển khai Exponential Reconnect; đa luồng hóa MQTT bridge; cấu hình ngưỡng động lưu trong DB; thiết lập LLM Fallback Service. |
