# [SỔ TAY VẬN HÀNH] HỆ THỐNG FRONTEND & UI/UX ENGINE
**Dự án:** Hugo-Sanitas HK-07 (Companion Robot System)
**Vai trò tài liệu:** Hướng dẫn kiến trúc Frontend, triết lý thiết kế (Design System) và kiểm soát hiệu năng hiển thị cho các ứng dụng theo dõi (Dashboard/Mobile Web).

---

## I. TỔNG QUAN KIẾN TRÚC FRONTEND

Frontend của HK-07 đóng vai trò là "Cửa sổ Tâm hồn" kết nối giữa Robot và Chủ nhân. Nó được xây dựng dưới dạng Single Page Application (SPA) với các yêu cầu kỹ thuật khắt khe để chạy mượt mà ngay cả trên thiết bị di động cấu hình yếu.

1. **Tech Stack Cốt lõi:** Next.js / React (TypeScript).
2. **State Management (Quản lý trạng thái):** Sử dụng Zustand hoặc Jotai (nhẹ hơn Redux, phù hợp để render dữ liệu sinh tồn thời gian thực 60Hz).
3. **Real-time Engine:** WebSocket (Socket.io) hoặc WebRTC để stream video từ Camera và dữ liệu từ MQTT Broker của Backend.

---

## II. TRIẾT LÝ THIẾT KẾ CYBER-CINEMATIC (DESIGN SYSTEM)

Giao diện không dùng phong cách phẳng (Material/Flat) nhàm chán, mà phải mang hơi hướng công nghệ tương lai, chuyên nghiệp và có tính bảo mật cao (Hacker-style, Sci-fi Medical).

### 1. Bảng màu cốt lõi (Color Palette)
* **Nền (Background):** `True Black (#000000)` hoặc `Deep Gunmetal (#111317)` để tiết kiệm pin màn hình OLED.
* **Màu nhấn chủ đạo (Primary Accent):** `Cyber Green (#00FF41)` hoặc `Electric Cyan (#00E5FF)` dùng cho các chỉ số sinh tồn bình thường và hiệu ứng glowing (phát sáng).
* **Màu cảnh báo (Critical Alert):** `Neon Red (#FF003C)` - Chỉ xuất hiện khi nhịp tim bất thường hoặc va chạm vật lý.

### 2. Typography & Layout
* **Font chữ:** Sử dụng các font Monospace (như *Fira Code*, *JetBrains Mono*) cho các chỉ số nhịp tim, thông số kỹ thuật. Dùng *Inter* hoặc *Roboto* cho văn bản hội thoại thông thường.
* **Biên giới (Borders):** Các Component được bọc trong các viền mỏng (1px), góc cạnh sắc nét (Border-radius nhỏ), kết hợp với hiệu ứng Blur nền (Glassmorphism dạng tối).

### 3. Đồ họa Động (Animations & Transitions)
* Mọi chuyển động (mở Modal, chuyển Route) phải diễn ra trong khoảng `150ms - 200ms` với gia tốc (easing) mượt mà.
* Sử dụng thư viện `Framer Motion` để tạo các hiệu ứng "Gõ chữ terminal" (Typewriter) khi AI Agent (Empathetic/Medical) đưa ra lời khuyên.

---

## III. QUY TRÌNH VẬN HÀNH CÁC PHASE GIAO DIỆN

Khi AI Agent triển khai các tính năng, phải tuân thủ chuẩn tương tác sau:

### Phase 02: Xác thực Sinh trắc học ảo (Cyber-Auth)
* **Quy chuẩn:** Giao diện đăng nhập mô phỏng màn hình Terminal/Hacker. Khi nhập mật khẩu, hiển thị dạng chuỗi hash chạy ngẫu nhiên trước khi báo Success để tăng tính Cinematic.

### Phase 04: Timeline (Bảng điều khiển Sinh tồn - Vitals Dashboard)
* **Quy chuẩn:** Không render toàn bộ list dữ liệu cũ gây tràn RAM browser. Bắt buộc dùng **Virtualization (Kỹ thuật cửa sổ ảo)** để chỉ render 10-20 phần tử đang hiển thị trên màn hình.
* Đồ thị nhịp tim (ECG) phải chạy liên tục (như trong bệnh viện) sử dụng thẻ `<canvas>` để tránh nghẽn DOM rendering.

### Phase 05 & 07: Hội thoại & Thông báo (AI Chat Interface)
* **Quy chuẩn:** Giao diện tách biệt rõ ràng lời nói của 3 Agent (Màu Xanh lá cho Y tế, màu Xanh lam cho Cảm xúc, màu Đỏ cho An toàn).
* Có biểu đồ Radar (Radar Chart) nhỏ ở góc màn hình hiển thị trạng thái cảm xúc (Vui, Buồn, Căng thẳng) của chủ nhân theo thời gian thực.

---

## IV. BẢO MẬT & KIỂM SOÁT HIỆU NĂNG PHÍA CLIENT

1. **Bảo mật XSS (Cross-Site Scripting):** Mọi văn bản từ Chatbot/Agent trả về, nếu có định dạng Markdown/HTML, phải được "làm sạch" (Sanitize) qua thư viện DOMPurify trước khi render.
2. **Quản lý Bộ nhớ Client:** Dữ liệu stream từ Camera robot hoặc lịch sử Chat chỉ được lưu tối đa 50 messages trong RAM của trình duyệt. Nếu dài hơn, tự động cắt bỏ phần đầu để tránh Crash tab trên điện thoại.

---
**[HỆ THỐNG AI AGENT LƯU Ý]:** Frontend Engineer (AI Agent) không chỉ viết Code để chạy được, mà phải đóng vai trò là một **Nghệ sĩ Kỹ xảo (VFX Artist)**. Code xuất ra phải tạo được hiệu ứng thị giác mạnh mẽ, tối ưu CSS GPU-Acceleration (dùng `transform` thay vì `margin/top`) để đạt 60 FPS trên mọi thiết bị.