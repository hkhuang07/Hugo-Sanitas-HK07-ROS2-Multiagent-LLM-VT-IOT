# [STATUS: DONE] BIÊN BẢN KHỞI TẠO DỰ ÁN (PROJECT INITIATION)
**Dự án:** Robot Bạn đồng hành Chăm sóc Sức khỏe Hugo-Sanitas HK-07
**Mã hiệu Thương hiệu:** HK.Huang07
**Ngày khởi tạo:** 31/05/2026
**Trạng thái Khởi tạo:** Hoàn tất thiết lập tầm nhìn và cấu trúc kỹ thuật nền tảng.

---

## 1. TẦM NHÌN VÀ ĐỊNH VỊ SẢN PHẨM (CORE VISION)

**Hugo-Sanitas HK-07** KHÔNG phải là một robot phục vụ trong môi trường bệnh viện. Đây là một **Thực thể Robot Bạn đồng hành (Companion Robot)** được thiết kế để đi cùng con người trong môi trường sống hàng ngày (nhà ở, quán cà phê, đường phố). 

Sứ mệnh của HK-07 là cung cấp dịch vụ chăm sóc sức khỏe chủ động, cảnh báo an toàn sinh tồn và sẻ chia cảm xúc tinh thần như một người bạn thực thụ, kết hợp giữa phần cứng cơ điện tử linh hoạt và một "bộ não" Trí tuệ nhân tạo Đa tác nhân (Multi-Agent).

---

## 2. RÀNG BUỘC PHẦN CỨNG VÀ CHIẾN LƯỢC "ZERO-BUDGET"

Dự án được thiết kế với ràng buộc phần cứng phát triển cực kỳ khắt khe: **Laptop Windows 10, RAM 8GB, SSD 256GB**. 
Để hệ thống vận hành mượt mà, AI Agent khi triển khai mã nguồn bắt buộc phải tuân thủ chiến lược "Zero-Budget" (Tối ưu hóa $100\%$ dịch vụ miễn phí và mã nguồn mở siêu nhẹ):

* **Môi trường hệ điều hành:** WSL 2 (Windows Subsystem for Linux) chạy Ubuntu.
* **Môi trường Giả lập 3D:** Sử dụng **Webots** (thay thế cho Gazebo/Isaac Sim) để tiết kiệm RAM.
* **Giao diện Giám sát (Visualize):** Sử dụng **Foxglove Studio** thay cho RViz.
* **Trí tuệ Nhân tạo (Cloud AI):** Khai thác các Serverless API tốc độ cao, miễn phí (Groq API, Gemini API) để xử lý các mô hình LLM/VLM, tuyệt đối không chạy mô hình AI nặng dưới Local.

---

## 3. KIẾN TRÚC HỆ THỐNG CỐT LÕI (CORE ARCHITECTURE)

Hệ thống được thiết kế dựa trên sự giao thoa của 3 tư duy kỹ thuật đỉnh cao:

### 3.1. Nhất thể hóa Hành động bằng Kiến trúc ROS 2 & Subsumption
* Sử dụng **ROS 2 (Robot Operating System 2)** với các *Lifecycle Nodes*.
* Các chức năng (Di chuyển, Camera, Trò chuyện) chạy thành các nút độc lập $100\%$ bằng C++ và Python.
* Áp dụng **Subsumption Architecture**: Phân tầng ưu tiên. Tầng sinh tồn (Né vật cản) luôn có quyền ngắt (Inhibit) các hành động ở tầng thấp hơn (Di chuyển, Trò chuyện) để đảm bảo an toàn tuyệt đối mà không cần đồng bộ dữ liệu phức tạp.

### 3.2. Tư duy Netcode Game (Xử lý Thời gian thực 60Hz)
* **Client-Side Prediction (Dự đoán di chuyển):** Robot dự đoán quỹ đạo của chủ nhân trong 500ms tới để bước đi song hành ngay lập tức.
* **Reconciliation & Interpolation (Nội suy sửa sai):** Tự động điều chỉnh quỹ đạo mượt mà khi có độ trễ từ cảm biến LiDAR/Camera.
* **Lag Compensation (Bù trừ độ trễ):** Lưu bộ đệm (buffer) 2 giây dữ liệu sinh tồn để phân tích nguyên nhân nếu chủ nhân gặp sự cố đột ngột (té ngã).

### 3.3. Bộ não Đa tác nhân nội bộ (MiroFish Multi-Agent Engine)
* Chạy vòng lặp sự kiện bất đồng bộ (Event Loop) trên RAM với 3 Agent cốt lõi:
    * **Empathetic Agent:** Phân tích sắc thái, cảm xúc.
    * **Medical Agent:** Giám sát nhịp tim, giấc ngủ, đưa ra lời khuyên y tế.
    * **Safety Agent:** Quét LiDAR, phân tích môi trường, hố sâu, thời tiết.

---

## 4. BẢO MẬT HỆ THỐNG VÀ QUẢN LÝ DỮ LIỆU (BOOTROM MINDSET)

Robot di chuyển trong môi trường công cộng, do đó cơ chế an toàn mạng được đặt lên hàng đầu (Chống Evil Twin, ARP Spoofing):
* **Read-Only OS:** Phân vùng hệ điều hành chứa nhân ROS 2 và mã nguồn lõi bị đóng băng (chỉ đọc), miễn nhiễm với Trojan/Mã độc.
* **Volatile Memory (RAM-only):** Dữ liệu thu thập ngắn hạn tại quán cà phê/ngoài đường chỉ lưu trên RAM. Khởi động lại robot sẽ xóa sạch $100\%$ dấu vết.
* **Ký ức dài hạn nội bộ:** Sử dụng **LanceDB** (Vector Database tĩnh, siêu nhẹ) để lưu trữ sở thích của chủ nhân.
* **Giao thức truyền thông:** Kết nối với vòng tay sinh tồn qua **MQTT (Mosquitto)** / **Eclipse Zenoh**. Truyền tải dữ liệu qua mạng Wi-Fi công cộng luôn bọc trong đường hầm **VPN** và bật **AP Isolation nội bộ**.

---

## 5. CHỈ THỊ DÀNH CHO AI AGENT (AGENT WORKFLOW DELEGATION)

Tài liệu khởi tạo này đã hoàn tất. Các AI Agent thuộc dự án `INTERNAL_SOCIAL/Hugo-Sanitas HK-07` đọc tài liệu này để nắm rõ giới hạn RAM và Tech Stack.
* **Nhiệm vụ tiếp theo:** Agent hãy chuyển hướng sang thư mục `docs/01-system-design/` để bắt đầu tạo lập các sơ đồ kiến trúc chi tiết, thiết kế DTOs, luồng Node ROS 2 và các API giao tiếp nội bộ.
* **Thẩm mỹ UI/UX:** Khi phát triển các Dashboard giám sát Robot trên nền Web, bắt buộc áp dụng phong cách Cyber-Cinematic (Hacker-style, Dark mode `#000000`, Matrix Green, Neon Cyans).