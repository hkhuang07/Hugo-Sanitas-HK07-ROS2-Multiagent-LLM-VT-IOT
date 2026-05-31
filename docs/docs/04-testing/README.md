# [ĐẶC TẢ KIỂM THỬ] KỊCH BẢN TESTING HỆ THỐNG TỰ TRỊ
**Dự án:** Robot Companion Hugo-Sanitas HK-07  
**Mã hiệu:** HK.Huang07  
**Phạm vi:** Kiểm thử phân tán cho hệ thống đa tác nhân (Multi-Agent) và các thuật toán đồng bộ Netcode tần suất cao trên môi trường giả lập.

---

## I. CHIẾN LƯỢC KIỂM THỬ KHÔNG GIAN (ZERO-BUDGET TESTING)

Do giới hạn phần cứng nghiêm ngặt (RAM 8GB), quy trình thử nghiệm từ bỏ hoàn toàn các cấu trúc UI test hay Integration test nặng nề, tập trung hoàn toàn vào kiểm thử logic phi tập trung và phản xạ phần cứng thông qua mô phỏng.

1. **Unit Test (Độc lập 100%):** Sử dụng `pytest` cho Python và `gtest` (Google Test) cho C++. Từng Node ROS 2 phải vượt qua các bài kiểm thử biên độc lập trước khi tích hợp.
2. **Simulation Test (Kiểm thử Giả lập):** Chạy trực tiếp trong **Webots** để xác thực thuật toán định vị (SLAM) và né vật cản thời gian thực mà không làm tràn bộ nhớ máy tính.
3. **Mocking Cloud API:** Khi chạy test tự động, toàn bộ các lượt gọi đến Groq API hoặc Gemini API phải được giả lập dữ liệu trả về (Mocking) để tiết kiệm Token và tránh chặn I/O mạng.

---

## II. DANH SÁCH CÁC KỊCH BẢN KIỂM THỬ CỐT LÕI (CRITICAL TEST SUITES)

### 1. Kiểm thử Cơ chế Lấn át Quyền lực (Subsumption Overriding Test)
* **Mục tiêu:** Đảm bảo lớp An toàn (Safety) ngắt lệnh di chuyển ngay lập tức khi xuất hiện nguy hiểm.
* **Kịch bản:** 1. Khởi chạy Node Di chuyển (`phase-04-timeline`) phát lệnh tiến lên với vận tốc $0.5 m/s$.
  2. Kích hoạt giả lập Node An toàn (`phase-07-notifications`) phát tín hiệu phát hiện hố sâu (LiDAR Mock Data).
  3. **Kết quả mong đợi:** Tín hiệu lấn át (Inhibit Signal) đạt độ trễ $< 5ms$, ngắt toàn bộ xung điều khiển mô-tơ, đưa vận tốc robot về $0.0 m/s$ ngay lập tức.

### 2. Kiểm thử Thuật toán Dự đoán và Sửa sai (Netcode Verification)
* **Mục tiêu:** Xác thực độ mượt mà của di chuyển song hành ở tần suất 60Hz.
* **Kịch bản:** 1. Giả lập quỹ đạo di chuyển ngẫu nhiên của chủ nhân.
  2. Ép tạo độ trễ mạng (Network Latency Injector) tăng lên từ 50ms đến 200ms để thử thách thuật toán `Client-Side Prediction`.
  3. **Kết quả mong đợi:** Thuật toán nội suy (`Interpolation`) tự động bù sai số, robot không xuất hiện hiện tượng giật cục (Stuttering), sai lệch khoảng cách song hành với chủ nhân luôn duy trì trong biên độ an toàn $< 15cm$.

### 3. Kiểm thử Rò rỉ Bộ nhớ Bộ não Đa tác nhân (Internal Multi-Agent Stress Test)
* **Mục tiêu:** Đảm bảo hệ thống chạy liên tục cả ngày trên RAM 8GB không bị Crash.
* **Kịch bản:** 1. Gửi liên tục 1.000 yêu cầu tín hiệu sinh tồn và chuỗi hội thoại phức tạp vào `HK07BrainEngine`.
  2. Giám sát dung lượng RAM tiêu thụ của tiến trình thông qua lệnh `top` trong WSL 2.
  3. **Kết quả mong đợi:** Nhờ cơ chế luồng ảo (`Virtual Threads`) và bộ dọn dẹp RAM định kỳ (RAM Wiping), tổng dung lượng RAM của Backend không được vượt quá ngưỡng `1.2 GB` sau 2 tiếng chạy tải liên tục.

---

## III. CHỈ THỊ THỰC THI CHO AI AGENT
* Trước khi đánh dấu bất kỳ Phase nào trong `source/` là hoàn tất, Agent phải tự động chạy lệnh test nội bộ:
  - Backend: `mvn test` hoặc lệnh tương đương.
  - Frontend: `npm run test` hoặc lệnh tương đương.
* Mọi kết quả lỗi (Failures) phải được Agent bắt giữ (Capture Output), tự động phân tích và kích hoạt quy trình tự sửa sai (`Self-Healing Protocol`) tối đa 3 lần theo đúng tinh thần cấu hình `CLAUDE.md`.