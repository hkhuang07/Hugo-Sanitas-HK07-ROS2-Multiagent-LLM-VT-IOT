# [ĐẶC TẢ YÊU CẦU] NGHIỆP VỤ & KỸ THUẬT CỐT LÕI (PRD)
**Dự án:** Robot Companion Hugo-Sanitas HK-07  
**Mã hiệu hệ thống:** HK.Huang07  
**Phiên bản tài liệu:** 1.0 (Hyper-Drive Edition)

Tài liệu này xác định các yêu cầu nghiệp vụ khắt khe, giới hạn hệ thống vật lý và các tiêu chuẩn bảo mật cấp cao nhất để định hình sự phát triển của HK-07. Mọi mã nguồn được sinh ra bắt buộc phải đối chiếu với tài liệu này.

---

## I. TẦM NHÌN VÀ PHẠM VI ỨNG DỤNG (VISION & SCOPE)

* **Bản chất Sản phẩm:** Một thực thể Robot Bạn đồng hành (Companion Robot). **TUYỆT ĐỐI KHÔNG** thiết kế logic hoạt động cho môi trường bệnh viện.
* **Môi trường Hoạt động:** Không gian công cộng (quán cà phê, đường phố, công viên) và không gian cá nhân (nhà ở).
* **Sứ mệnh:** Đi cùng, bảo vệ an toàn sinh tồn, chăm sóc sức khỏe chủ động và chia sẻ cảm xúc tinh thần với chủ nhân thông qua một bộ não AI phi tập trung.

---

## II. YÊU CẦU TÍNH NĂNG CỐT LÕI (CORE FUNCTIONALITIES)

### 2.1. Trí tuệ Nhân tạo Đa Tác nhân (MiroFish Multi-Agent Engine)
Hệ thống không sử dụng một AI nguyên khối (Monolithic AI) để tránh nghẽn luồng xử lý. Bộ não phải được phân rã thành 3 Tác nhân (Agents) chạy ẩn độc lập trên RAM:
1. **Empathetic Agent (Cảm xúc):** Nhận diện sắc thái giọng nói, biểu cảm khuôn mặt để giao tiếp và an ủi chủ nhân.
2. **Medical Agent (Y tế):** Phân tích liên tục dữ liệu sinh tồn (nhịp tim, huyết áp), nhắc nhở uống thuốc và cảnh báo đột quỵ.
3. **Safety Agent (An toàn):** Quét môi trường vật lý (LiDAR, Camera độ sâu) để phát hiện vật cản, hố sâu hoặc thời tiết xấu.
* **Quy tắc phối hợp:** Các Agent giao tiếp thông qua Đồ thị Tri thức nội bộ (GraphRAG) và chốt quyết định qua một module Điều phối viên (Arbitrator).

### 2.2. Nhận thức & Điều hướng (Navigation & Subsumption Architecture)
* **Cơ chế Lấn át quyền lực (Subsumption Override):** Tầng An toàn (Safety) được cấp quyền tối thượng. Khi phát hiện nguy cơ vật lý (ví dụ: mép cầu thang, xe cộ), nó bắt buộc phải phát tín hiệu ngắt (Inhibit) các chức năng di chuyển hoặc trò chuyện ở tầng dưới trong thời gian **< 5ms** để bảo vệ robot và chủ nhân.

### 2.3. Chuyển động Thời gian thực (Game Netcode Mechanics)
* **Client-Side Prediction (Dự đoán phía Client):** Robot phải tự dự đoán quỹ đạo di chuyển của chủ nhân trong 500ms tương lai để bước đi song hành tức thời (Tần suất xử lý 60Hz), không chờ đợi cảm biến.
* **Lag Compensation (Bù trừ độ trễ):** Hệ thống lưu lại một bộ đệm 2 giây (`Buffer`) dữ liệu sinh tồn và vị trí. Khi phát hiện sự cố khẩn cấp (như vấp ngã), AI tự động "quay ngược thời gian" 2 giây trước đó để phân tích nguyên nhân gốc rễ và phản xạ cứu hộ.

### 2.4. Giao diện Cyber-Cinematic (User Interface)
* **Thiết kế Thị giác:** Áp dụng phong cách UI Không gian số (Spatial Computing) mang hơi hướng công nghệ tương lai / Hacker (Tông Đen sâu `#000000`, Neon Xanh lá `#00FF66`, Cyan `#00E5FF`).
* **Bố cục Không gian:** Sử dụng lưới bất đối xứng (30/70), Đồ thị quét HUD đồng tâm, Đồ thị luồng sóng sinh tồn liên tục chạy bằng `<canvas>` để đảm bảo mượt mà 60FPS.

---

## III. RÀNG BUỘC KỸ THUẬT VÀ TÀI NGUYÊN (HARDWARE LIMITS & TECH STACK)

* **Giới hạn Máy trạm (Host Machine):** Dell Latitude E7270, **8GB RAM** (Thực tế khả dụng ~3.3GB), CPU Dual-Core 1.6GHz.
* **Chiến lược Zero-Budget & Tối ưu hóa:**
  1. **Môi trường OS:** WSL 2 (Giới hạn tài nguyên ở mức 3GB RAM/4 Cores).
  2. **Backend Engine:** Spring Boot (Bắt buộc dùng **Java Virtual Threads** để xử lý hàng ngàn luồng cảm biến mà không tạo Thread hệ điều hành), hoặc Node.js (tối đa 512MB RAM heap).
  3. **Môi trường Giả lập:** Bắt buộc dùng **Webots** (Siêu nhẹ) thay cho Gazebo hay Isaac Sim.
  4. **AI Cloud:** Sử dụng các Serverless API miễn phí (Groq API, Gemini API) cho tính toán ngôn ngữ. Tuyệt đối không chạy mô hình LLM tại máy nội bộ.
  5. **Ký ức Dài hạn:** Sử dụng **LanceDB** (Vector Database tĩnh, không chạy nền) để lưu dữ liệu sức khỏe định kỳ.

---

## IV. TIÊU CHUẨN BẢO MẬT & QUYỀN RIÊNG TƯ (SECURITY PROTOCOLS)

Robot hoạt động tại môi trường công cộng (nguy cơ dính Evil Twin, ARP Spoofing) nên yêu cầu thiết lập bảo mật cấp quân sự:
1. **Bootrom Read-Only Policy:** Phân vùng chứa hệ điều hành ROS 2 và mã nguồn hệ thống bị khóa cứng ở chế độ "Chỉ đọc". Bất khả xâm phạm với phần mềm độc hại.
2. **Volatile Data (Dọn dẹp RAM):** Lịch sử quét IP, MAC, thông tin Wi-Fi quán cà phê hay dữ liệu hội thoại ngắn hạn chỉ được lưu tạm trên RAM (`Virtual Threads`). Khi khởi động lại hoặc sau chu kỳ 4 tiếng, toàn bộ dấu vết phải bị xóa sổ vĩnh viễn (Wiped).
3. **Mạng lưới Mã hóa (Network Isolation):** 100% gói tin sinh tồn gửi từ vòng tay về Robot hoặc từ Robot lên Cloud phải được đóng gói qua đường hầm **VPN**, áp dụng **AP Isolation** và mã hóa MQTT, vô hiệu hóa hoàn toàn kỹ thuật đọc trộm dữ liệu thô (Packet Sniffing).