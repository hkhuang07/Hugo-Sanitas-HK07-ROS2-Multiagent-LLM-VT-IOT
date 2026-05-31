# [SỔ TAY VẬN HÀNH] HỆ THỐNG BACKEND & BACKGROUND JOBS
**Dự án:** Hugo-Sanitas HK-07 (Companion Robot System)
**Vai trò tài liệu:** Hướng dẫn khởi chạy, bảo trì và kiểm soát các luồng xử lý ngầm (Background Tasks/Daemons) của hệ thống Backend.

---

## I. TỔNG QUAN KIẾN TRÚC VẬN HÀNH BACKEND

Backend của HK-07 không chỉ là một RESTful API thông thường, mà là một **Hệ thống Phân tán Thu nhỏ (Micro-Distributed System)** chạy trên môi trường cấu hình thấp (WSL 2 / RAM 8GB). Backend đảm nhận 3 vai trò:
1. **IoT Gateway:** Giao tiếp thời gian thực với phần cứng Robot qua MQTT (Eclipse Zenoh / Mosquitto).
2. **AI Orchestrator:** Điều phối luồng dữ liệu bất đồng bộ cho 3 Agent (Empathetic, Medical, Safety) kết nối với Cloud API (Groq/Gemini).
3. **Data Synchronizer:** Đồng bộ hóa dữ liệu từ RAM Volatile (bộ nhớ tạm) sang LanceDB (Ký ức Vector).

---

## II. QUY TRÌNH KHỞI ĐỘNG HỆ THỐNG (STARTUP SEQUENCE)

Khi khởi động hệ thống Backend, hệ thống phải tự động thực thi chuỗi lệnh sau theo đúng thứ tự (Tránh tình trạng Race Condition):

1. **Kích hoạt Môi trường Cách ly (Bootrom Security):**
   - Đảm bảo phân vùng lõi ở chế độ Read-Only.
   - Mount một phân vùng RAM ảo (Ramdisk) kích thước `512MB` để lưu trữ log và session tạm thời.
2. **Khởi chạy Message Broker:**
   - Kích hoạt `Mosquitto MQTT` trên cổng `1883` (Chỉ cho phép local loopback `127.0.0.1`).
3. **Khởi chạy Event Loop & Virtual Threads:**
   - Kích hoạt Backend Server (Spring Boot / Node.js).
   - Thiết lập Pool luồng ảo tối đa để lắng nghe dữ liệu sinh tồn từ vòng tay chủ nhân.
4. **Kết nối Vector DB:**
   - Load tệp tin `LanceDB` từ ổ cứng để khôi phục "Ký ức dài hạn" của Robot.

---

## III. QUẢN LÝ CÁC LUỒNG XỬ LÝ NGẦM (BACKGROUND JOBS)

Đây là các tiến trình chạy ẩn (Cron Jobs / Schedulers) cực kỳ quan trọng để duy trì sự sống và hiệu năng của HK-07.

### 1. Luồng Dọn dẹp Bộ nhớ Tạm (RAM Wiping - Chạy mỗi 4 giờ)
* **Mục đích:** Bảo vệ quyền riêng tư khi ở không gian công cộng (Quán Cafe) và giải phóng RAM cho chiếc laptop 8GB.
* **Logic:** Quét toàn bộ lịch sử hội thoại chưa được đánh dấu là "Quan trọng" trong vòng 4 giờ qua. Nếu không có giá trị Y tế/Cảm xúc lâu dài, thực hiện xóa vĩnh viễn khỏi RAM.

### 2. Luồng Đồng bộ Ký ức (Vector DB Sync - Chạy mỗi 00:00 AM)
* **Mục đích:** Cập nhật sở thích và chỉ số sức khỏe của chủ nhân vào `LanceDB`.
* **Logic:** Tổng hợp dữ liệu từ thư mục `phase-04-timeline` (Nhật ký sức khỏe) và `phase-06-survey` (Đánh giá tương tác). Sử dụng thuật toán Embedding để nén dữ liệu thành Vector và ghi xuống ổ cứng.

### 3. Luồng Cảnh báo Sinh tồn (Safety Watchdog - Real-time 60Hz)
* **Mục đích:** Đảm bảo hệ thống không bị "ngủ quên" khi mất kết nối mạng.
* **Logic:** Liên tục ping đến các cảm biến (`phase-07-notifications`). Nếu mất tín hiệu nhịp tim quá 5 giây hoặc phát hiện té ngã, lập tức kích hoạt luồng khẩn cấp lấn át (Subsumption Override) để dừng bánh xe robot và phát loa cảnh báo.

---

## IV. QUY TRÌNH SELF-HEALING (TỰ PHỤC HỒI KHI CÓ LỖI)

Backend được thiết kế để tự động phục hồi mà không cần con người can thiệp:
* **Mất kết nối Internet:** Backend tự động ngắt kết nối với Cloud AI (Groq/Gemini API), chuyển quyền điều khiển hội thoại sang mô hình Edge AI cục bộ (nếu có) hoặc kích hoạt chế độ "Im lặng đồng hành".
* **Tràn bộ nhớ (Memory Leak):** Cảm biến hệ thống (Health Check) giám sát RAM. Nếu mức sử dụng Backend vượt quá `1.5GB RAM`, hệ thống tự động lưu trạng thái (State Snapshot) và Graceful Restart tiến trình Backend trong vòng 200ms.

---
**[HỆ THỐNG AI AGENT LƯU Ý]:** Bất kỳ Agent nào khi nhận nhiệm vụ lập trình tính năng tại `docs/02-backend/`, bắt buộc phải đăng ký tiến trình ngầm của mình vào tệp tài liệu này để Trưởng nhóm (Architect) kiểm soát tổng thể tài nguyên bộ nhớ.