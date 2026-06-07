# [THÔNG SỐ PHẦN CỨNG] MÔI TRƯỜNG BIÊN DỊCH VÀ PHÁT TRIỂN (DEV ENVIRONMENT)
**Dự án:** Hugo-Sanitas HK-07
**Môi trường Host:** Dell Latitude E7270 (Standalone Workstation)
**Hệ điều hành:** Windows 10 Pro (Build 19045) với Hyper-V / WSL 2 Kích hoạt.

---

## I. CẢNH BÁO TÀI NGUYÊN HỆ THỐNG (SYSTEM BOTTLENECKS)

Hệ thống AI Agent khi thực thi vòng lặp tự trị (Autonomous Loop) phải nhận thức rõ các giới hạn vật lý cực kỳ khắt khe của máy trạm này để tránh gây Crash hệ điều hành:

1. **Giới hạn Bộ nhớ (RAM Critical):**
   - Tổng RAM vật lý: `8,084 MB` (8GB).
   - Dung lượng RAM khả dụng (Available): Chỉ còn `~3,374 MB` (Rất thấp).
   - Bộ nhớ ảo (Pagefile trên ổ D:\): Đang gánh `9,238 MB`. Tránh ghi/đọc (I/O) ổ cứng liên tục để không làm treo máy (Disk Thrashing).
2. **Giới hạn Xử lý (CPU Constraint):**
   - Chipset: Intel 64 Family 6 (Dual-core / 4 Threads), xung nhịp cơ bản rất thấp `~1600 Mhz`.
   - Biên dịch song song (Parallel compiling) sẽ làm CPU quá tải 100%.
3. **Mạng lưới Ảo hóa (Virtualization Overhead):**
   - Có 4 card mạng VMware (VMnet) và vEthernet (WSL) đang chạy ngầm, ngốn thêm tài nguyên xử lý luồng mạng.

---

## II. CHIẾN LƯỢC TỐI ƯU HÓA MÃ NGUỒN (SRC CODE OPTIMIZATION)

Dựa trên cấu hình giới hạn trên, mọi dòng code do AI sinh ra (Backend/Frontend) bắt buộc phải áp dụng các quy chuẩn tối ưu hóa cực đoan sau:

### 1. Tối ưu hóa Backend (Java / Spring Boot / Node.js)
* **Giới hạn Heap Size:** Khi AI tạo các file `Dockerfile` hoặc script chạy (như `package.json`, `pom.xml`), bắt buộc phải gắn cờ giới hạn bộ nhớ:
  - Java: `java -Xms256m -Xmx512m -jar app.jar`
  - Node.js: `node --max-old-space-size=512 server.js`
* **Xử lý Bất đồng bộ (Async/Await & Virtual Threads):** Không sử dụng `Thread.sleep()` hoặc các hàm chặn luồng (Blocking I/O). Tận dụng tối đa `Virtual Threads` (Java 21) để tránh tạo thêm luồng OS vật lý gây nghẽn CPU 1.6GHz.
* **Tắt tính năng Auto-Reload nặng nề:** Cấu hình tắt `spring-boot-devtools` hoặc các cơ chế Hot-Reload sử dụng Polling liên tục trên ổ cứng.

### 2. Tối ưu hóa Frontend (Next.js / React)
* **Tránh rò rỉ RAM trình duyệt:** Các biểu đồ sinh tồn (ECG/Radar) phải vẽ bằng `<canvas>` thuần (như `Chart.js` hoặc WebGL cơ bản), tuyệt đối không dùng hàng nghìn thẻ `<svg>` hay `<div>` DOM element gây tràn RAM.
* **Biên dịch Frontend (Build Phase):** Khi chạy `npm run build`, cấu hình Webpack/Turbopack chỉ được phép chạy trên **1 Worker duy nhất** để không làm CPU 1.6GHz bị quá tải:
  - Bổ sung biến môi trường: `export NODE_OPTIONS="--max_old_space_size=1024"`
  - Cấu hình Next.js: `experimental: { cpucount: 1 }` (nếu dùng Turbopack).

### 3. Tối ưu hóa Cơ sở dữ liệu & Cảm biến (Data Layer)
* **Vector DB (LanceDB):** Cấu hình bộ nhớ đệm (Cache Size) của LanceDB không vượt quá `256MB`. Dữ liệu vector phải được nạp theo lô nhỏ (Batch processing).
* **MQTT Message Broker:** Mosquitto phải cấu hình `max_queued_messages` giới hạn ở mức 100 để RAM không bị ăn mòn nếu Backend tạm thời xử lý không kịp.

---

## III. CHỈ THỊ THỰC THI CHO AI AGENT (EXECUTION LIMITS)

Trong vòng lặp 7 bước (`CLAUDE.md`), AI Agent PHẢI tuân thủ:
1. **Không mở quá 2 Terminal cùng lúc.**
2. **Nghỉ giữa hiệp (Cool-down):** Khi chạy lệnh `npm install`, `mvn clean install`, hoặc biên dịch Docker, AI phải thiết lập thời gian chờ (Sleep) khoảng 3-5 giây sau khi hoàn tất để CPU 1.6GHz hạ nhiệt trước khi thực thi lệnh tiếp theo.
3. **Log File Size:** Các tệp log (như Terminal output) phải được tự động cắt bớt (truncate) nếu vượt quá 1MB, tránh việc đọc/ghi liên tục lên ổ cứng (`D:\pagefile.sys`).