# BẢN ĐẶC TẢ HỆ THỐNG THIẾT KẾ UI/UX (CYBER-CINEMATIC DESIGN SYSTEM)
**Dự án:** Hugo-Sanitas HK-07
**Vị trí lưu trữ:** `docs/01-system-design/frontend/design-system.md`
**Nguồn cảm hứng cốt lõi:** Ngôn ngữ thiết kế giao diện không gian (Spatial Computing) từ Big Hero 6.

Tài liệu này hợp nhất các phân tích kỹ thuật từ tài liệu `ui-ux-bighero6.md` và các bằng chứng thị giác trực tiếp từ chuỗi hình ảnh thực tế để thiết lập tiêu chuẩn thiết kế Front-end cho Bảng điều khiển sinh tồn của HK-07.

---

## 1. TRIẾT LÝ BỐ CỤC KHÔNG GIAN (SPATIAL LAYOUT PHILOSOPHY)

Dựa trên các phân tích hình ảnh (đặc biệt là không gian làm việc Holographic và các màn hình chẩn đoán), hệ thống lưới của HK-07 từ bỏ sự đối xứng truyền thống để ưu tiên **Tải nhận thức theo ngữ cảnh (Contextual Cognitive Load)**.

### A. Lưới Bất đối xứng (Asymmetric Grid 30/70 & 40/60)
* **Tham chiếu:** Bố cục màn hình nạp chip dữ liệu và Bảng thiết kế của Hiro.
* **Ứng dụng:** Màn hình Dashboard của HK-07 sẽ chia làm 2 phân khu chính. Bên trái (30%) dành cho Khung mô phỏng 3D (Wireframe) của robot hoặc chủ nhân. Bên phải (70%) là luồng dữ liệu sinh tồn (Data Stream) và bảng điều khiển. Sự bất đối xứng giúp điều hướng mắt người dùng tập trung vào dữ liệu động.

### B. Bố cục Quét Đồng tâm (Concentric HUD Ring)
* **Tham chiếu:** Màn hình chẩn đoán y tế khóa mục tiêu vào bệnh nhân.
* **Ứng dụng:** Khi HK-07 phát hiện dấu hiệu sinh tồn nguy hiểm, giao diện sẽ tự động chuyển sang chế độ "Khóa mục tiêu". Một hệ tọa độ tròn cực (Polar Coordinate) xuất hiện ở giữa màn hình, làm mờ các thông tin râu ria xung quanh (Focus Isolation) để hiển thị nổi bật thông số nhịp tim/huyết áp khẩn cấp.

---

## 2. HỆ THỐNG MÀU SẮC ĐIỆN ẢNH (CINEMATIC COLOR PALETTE)

Không sử dụng các màu bệt (Flat colors), UI của HK-07 sử dụng hiệu ứng phát sáng neon (Glow/Bloom) trên nền tối tuyệt đối để giả lập màn hình Hologram công suất cao.

* **Midnight Deep Blue / True Black (`#000000` đến `#001133`):** Màu nền chủ đạo, mang lại cảm giác không gian đa chiều, làm chìm các vùng trống và giúp tiết kiệm pin (OLED).
* **Base Cyan Glow (`#00E5FF`):** Màu nhận diện cốt lõi. Dùng cho lưới tọa độ, đường viền component, văn bản trạng thái và các trục Radar. Kèm hiệu ứng `drop-shadow` cường độ 4-8px.
* **Hardware Emerald Green (`#00FF66`):** Màu của trạng thái tích cực, đồng bộ hoàn tất, thông số sức khỏe ổn định.
* **Cyber Orange (`#FF6600`) / Matrix Red (`#FF3333`):** Các dải màu cảnh báo cường độ cao, sử dụng cho thanh Loading khi hệ thống quá tải hoặc chỉ số y tế chạm ngưỡng nguy hiểm (Bereavement/Strength drops).

---

## 3. THƯ VIỆN COMPONENT ĐẶC THÙ (SIGNATURE COMPONENTS)

Sự kết hợp giữa phân tích lý thuyết và thực tế hình ảnh định hình ra các UI Component sau cho HK-07:

### A. Khối lượng Sinh trắc học & Y tế (Bio-Telemetry Dashboard)
* **Đồ thị sóng điện tử liên tục (Continuous Sine-Wave Graph):** (Tham chiếu từ bảng sóng não). Các đường line phát sáng liên tục trôi từ phải sang trái, đại diện cho nhịp tim (ECG) hoặc nhịp thở thời gian thực.
* **Biểu đồ Cột Phân đoạn (Segmented Density Bar):** (Tham chiếu từ các cột DOP, SER, EPI). Thay vì dùng thanh trượt trơn, sử dụng các khối chữ nhật phát sáng xếp chồng lên nhau (như đèn LED vật lý), tạo cảm giác phần cứng công nghiệp mạnh mẽ.

### B. Đồ thị Liên kết Mạng lưới (Social Node Network)
* **Tham chiếu:** Bản đồ quan hệ liệu pháp tâm lý.
* **Ứng dụng:** Frontend sử dụng `D3.js` để render các đồ thị Node phi tuyến tính biểu diễn trạng thái tâm lý hoặc sự kết nối giữa các Agent (Empathetic, Medical, Safety) bên trong "não bộ" của HK-07. Các Node kích hoạt sẽ có hiệu ứng `Glow Rings` gợn sóng lan tỏa.

### C. Cơ chế Hiển thị Tiến trình kiểu Terminal (CLI Progress Bars)
* **Thanh Tiến trình Matrix-style:** (Tham chiếu `PARSING: BLOCK`). Tiến trình nạp dữ liệu không chạy theo dải trơn mà chia thành các "vạch" (blocks).
* **Terminal Logs Output:** Các sự kiện hệ thống (quét khuôn mặt, khởi động cảm biến) sẽ được xuất ra màn hình dưới dạng luồng Text chạy liên tục ở góc giao diện (ví dụ: `>>> CORE_PARSING_BLOCK_SEQUENCE: SUCCESS`), giả lập một hệ điều hành nhúng RTOS chuyên nghiệp.

---

## 4. TƯƠNG TÁC NGƯỜI DÙNG & GIAO DIỆN CHUẨN NUI

* **Tương tác lướt Không gian (Spatial Scrolling):** Lược bỏ hoàn toàn thanh cuộn (Scrollbar) truyền thống. Giao diện ưu tiên thao tác vuốt (swipe) và kéo thả khối dữ liệu trên màn hình cảm ứng hoặc chuột.
* **Trạng thái Kính trong suốt (Glassmorphism & Transparency):** Các Panel chứa dữ liệu không có nền đặc hoàn toàn. Sử dụng CSS `backdrop-filter: blur(8px)` kết hợp màu nền `rgba(0, 0, 0, 0.6)` để lộ các lớp layer chìm bên dưới, tạo chiều sâu 3D cho giao diện.
* **Popup Ngữ cảnh (Contextual Activation):** (Tham chiếu màn hình trên ngực Baymax). Bảng điều khiển chính chỉ tự động kích hoạt hiển thị đầy đủ thông số khi chủ nhân tiếp cận gần thiết bị, nếu không sẽ thu gọn thành màn hình chờ (Idle Status) tối giản.

---
**[CHỈ THỊ CHO FRONTEND AGENT]:** Mọi dòng code React/Vue/TailwindCSS được triển khai trong `source/frontend/` BẮT BUỘC phải đối chiếu với các nguyên tắc thị giác trong tài liệu này. Ưu tiên sử dụng thẻ `<canvas>` cho đồ thị nặng để đảm bảo tốc độ khung hình (60 FPS) cho hiệu ứng Cyber-Cinematic.