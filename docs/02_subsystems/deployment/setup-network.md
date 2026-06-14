## PHẦN 1: TÀI LIỆU ĐẶC TẢ HẠ TẦNG MẠNG (Dành cho Đồ án)

### 1. Sơ đồ kiến trúc mạng lai (Hybrid Network Ingestion Pipeline)

Hệ thống giám sát sinh hiệu nâng cao tích hợp đa Agent (MAS) hoạt động dựa trên mô hình định tuyến luồng dữ liệu 3 chặng qua ranh giới Sandbox của WSL2:

```text
[Thiết bị Ngoại vi (Vivo)] 
       │ (Mạng Vật lý Wi-Fi Hotspot: 192.168.133.x)
       ▼
[Windows Host (Cổng Phản chiếu Network Interface)]
       │ (Cơ chế Port Forwarding qua IP Loopback)
       ▼
[WSL2 Ubuntu Sandbox (Môi trường Lõi ROS 2 Humble)] ◄───► [FastAPI Multi-Agent Engine]
       │ (Cổng WebSocket Suite: 9090)
       ▼
[Web Dashboard Trình duyệt (Frontend Vue3/React)]

```

### 2. Nguyên lý thông tuyến và Giải quyết xung đột trạng thái

* **Chặng 1 (Ingestion):** Ứng dụng SensorLogs trên điện thoại Vivo đóng gói ma trận dữ liệu cảm biến thành chuỗi JSON thô, phát phát tán qua giao thức HTTP POST định kỳ $10\text{Hz}$ hướng về địa chỉ IP vật lý của máy trạm Windows.
* **Chặng 2 (Tunneling):** Trình biên dịch mạng Windows (`netsh interface portproxy`) tóm giữ gói tin tại cổng `5005/5006`, trung chuyển xuyên qua nhân Hyper-V dải IP ảo `172.20.x.x` để rót thẳng vào tiến trình `hugo_perception_bridge_node` đang chờ sẵn trong Ubuntu.
* **Chặng 3 (Synchronization):** Dữ liệu sau khi trích xuất và chuẩn hóa toán học đơn vị gia tốc về hệ $g$ sẽ được gộp vào thông điệp `JointState` (41 thuộc tính) đẩy lên WebSocket của Rosbridge. Frontend kết nối vào cổng này để cập nhật trạng thái ô hiển thị sang nhãn **`LIVE`** thời gian thực.

---

## PHẦN 2: FILE SCRIPT TỰ ĐỘNG KHAI THÔNG MẠNG (`hugo_network_arm.bat`)

Bạn hãy mở phần mềm **Notepad** trên Windows, sao chép toàn bộ đoạn mã kịch bản tự động hóa cấp cao dưới đây, dán vào và lưu tệp với tên là **`hugo_network_arm.bat`** (Bắt buộc đuôi mở rộng phải là `.bat`, không phải `.txt`).

```batch
@echo off
:: ==============================================================================
:: HUGO SANITAS HK-07 - AUTOMATED NETWORK TUNNELING SCRIPT FOR WSL2 & MOBILE INGESTION
:: Class: DH23TH1 - An Giang University
:: ==============================================================================
title HUGO SYSTEM NETWORK ARMED TOOL V2

:: Kiểm tra quyền Administrator của Windows (Bắt buộc để chạy netsh)
net session >nul 2>&1
if %errorLevel% == 0 (
    goto :init_setup
) else (
    echo =====================================================================
    echo [ERR] BAN CHUA CHAY FILE BAN QUYEN ADMIN!
    echo Vui long chuot phai vao file bat va chon 'Run as Administrator'.
    echo =====================================================================
    pause
    exit /b
)

:init_setup
cls
echo +----------------------------------------------------------------------+
echo |             HUGO SANITAS HK-07 NETWORK AUTO-TUNNEL ACTIVATED         |
echo |     Tu dong tim kiem va cau hinh lop mang Hotspot di dong moi        |
echo +----------------------------------------------------------------------+
echo.

:: Tự động bóc tách IP Wi-Fi hiện tại của Windows để tránh nhập thủ công
set "WIFI_IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address" ^| findstr /r "192\.168\."') do (
    set "RAW_IP=%%a"
    goto :strip_spaces
)

:strip_spaces
:: Loại bỏ khoảng trắng thừa của biến IP thu được từ ipconfig
for /f "tokens=1" %%b in ("%RAW_IP%") do set "WIFI_IP=%%b"

if "%WIFI_IP%"=="" (
    echo [CRITICAL ERROR] Khong tim thay dai IP Wi-Fi hop le ^(192.168.x.x^).
    echo Vui long kiem tra xem Laptop da ket noi vao Wi-Fi cua dien thoai chua!
    echo.
    pause
    exit /b
)

echo [INFO] Phat hien IP mang Wi-Fi Hotspot hien tai: %WIFI_IP%
echo [INFO] Dang tien hanh lam sach cac duong ong proxy cu...
netsh interface portproxy reset

echo [INFO] Dang duc duong truyen SensorLogs chặng chinh (Port 5005) -> WSL2...
netsh interface portproxy add v4tov4 listenport=5005 listenaddress=%WIFI_IP% connectport=5005 connectaddress=127.0.0.1

echo [INFO] Dang duc duong truyen SensorLogs du phong (Port 5006) -> WSL2...
netsh interface portproxy add v4tov4 listenport=5006 listenaddress=%WIFI_IP% connectport=5006 connectaddress=127.0.0.1

echo [INFO] Dang mo khoa cong phan phoi du lieu Rosbridge WebSockets (Port 9090)...
netsh interface portproxy add v4tov4 listenport=9090 listenaddress=127.0.0.1 connectport=9090 connectaddress=127.0.0.1

echo.
echo =====================================================================
echo [OK] HE THONG PORT FORWARDING DA THONG SUOT!
echo =====================================================================
echo [-] DIEN THOAI: Thay doi Target URL trong app SensorLogs thanh:
echo     http://%WIFI_IP%:5005/data  (Hoac :5006/data neu cores bao nhay)
echo.
echo [-] TRINH DUYET FRONTEND: Mo tab an danh hoac bam [Ctrl + F5] de xoa cache.
echo =====================================================================
echo.
echo Nhan phim bat ky de kiem tra danh sach cac cong da duoc anh xa...
pause
netsh interface portproxy show all
echo.
echo Kich hoat phien thanh cong! Ban co the tat cua so nay va mo 3 Terminal de chay code.
pause
exit

```

---

## 🧭 QUY TRÌNH VẬN HÀNH SAU KHI MỞ MÁY (Daily Operational Workflow)

Mỗi lần khởi động lại máy tính để tiếp tục làm đồ án, bạn chỉ cần thực hiện đúng 4 bước theo chuỗi sau:

1. **Chạy Kịch bản:** Chuột phải vào file `hugo_network_arm.bat` -> Chọn **Run as Administrator**. (Kịch bản sẽ tự động quét dải IP `192.168.133.x` và đục cổng sang WSL2 chỉ trong 1 giây).
2. **Đồng bộ Điện thoại:** Nhìn vào dòng địa chỉ IP hiển thị trên màn hình file `.bat` vừa in ra, nhập chính xác chuỗi URL đó vào mục Settings của app SensorLogs trên máy Vivo.
3. **Kích hoạt 3 Terminal Hệ thống:**
* **Terminal 1 (WSL2):** Chạy `ros2 launch rosbridge_server rosbridge_websocket_launch.xml`
* **Terminal 2 (CMD Windows thô):** Chạy lệnh bật Agent: `cd D:\Study\...` -> `python main.py`
* **Terminal 3 (WSL2):** Chạy lệnh bật Lõi điều phối Robot Core: `ros2 run sensors hk07_runtime_orchestrator`


4. **Mở Trình duyệt:** Nhấn **`Ctrl + F5`** tại trang `/sensor-telemetry` để dọn sạch WebSocket Session cũ. Toàn bộ 12 ô cảm biến sẽ lập tức chuyển màu và cập nhật số liệu động ổn định.