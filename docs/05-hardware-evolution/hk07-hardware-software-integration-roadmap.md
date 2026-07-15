# HK-07 Hardware-Software Integration Roadmap
Kế hoạch chuyển đổi từ phần mềm simulation sang sản phẩm phần cứng thực tế với budget constraints (<150k VND/board), sử dụng ESP32-based architecture và Altium Designer cho PCB design.

## Kiến Trúc Hardware-Software Integration

### Tổng Quan Hệ Thống
```
HK-07 Hardware Integration Architecture
┌─────────────────────────────────────────────────────────────────┐
│                        LAYER 5: Cloud/Edge                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ hk07-agent    │  │ hk07-core    │  │ hk07-dashboard│         │
│  │ (WSL Python)  │  │ (Windows)    │  │ (Vue 3)      │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼──────────────────┼──────────────────┼─────────────────┘
          │                  │                  │
          │ MQTT/WebSocket   │ HTTP/REST        │ WebSocket
          │                  │                  │
┌─────────┼──────────────────┼──────────────────┼─────────────────┐
│         │                  │                  │                  │
│  ┌──────▼──────────────────▼──────────────────▼──────┐          │
│  │              LAYER 4: Communication Bridge         │          │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │          │
│  │  │ MQTT Broker │  │ ROSbridge   │  │ HTTP Server│  │          │
│  │  │ (Mosquitto) │  │ (WebSocket) │  │ (FastAPI)  │  │          │
│  │  └─────────────┘  └─────────────┘  └────────────┘  │          │
│  └────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────┘
          │                  │
          │ CAN Bus          │ WiFi/BLE
          │                  │
┌─────────┼──────────────────┼─────────────────────────────────────┐
│         │                  │                                      │
│  ┌──────▼──────────────────▼──────────────────────────────────┐ │
│  │              LAYER 3: Main Controller (ESP32-S3)             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌────────────┐          │ │
│  │  │ Sensor Hub   │  │ Motor Ctrl   │  │ Comm Mgr   │          │ │
│  │  │ (I2C/SPI)    │  │ (PWM/CAN)    │  │ (WiFi/MQTT) │          │ │
│  │  └─────────────┘  └─────────────┘  └────────────┘          │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
          │                  │
          │ I2C/SPI          │ GPIO/PWM
          │                  │
┌─────────┼──────────────────┼─────────────────────────────────────┐
│         │                  │                                      │
│  ┌──────▼──────────────────▼──────────────────────────────────┐ │
│  │              LAYER 2: Sensor Array                          │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │ │
│  │  │ MPU-6050 │ │MAX30102  │ │ BME280   │ │ HC-SR04  │     │ │
│  │  │ (IMU)    │ │ (SpO2)   │ │ (Env)    │ │ (Ultrasonic)│  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘     │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                   │ │
│  │  │ GPS Module│ │Current   │ │ Voltage  │                   │ │
│  │  │ (Location)│ │ Sensor   │ │ Sensor   │                   │ │
│  │  └──────────┘ └──────────┘ └──────────┘                   │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
          │
          │ PWM/Servo
          │
┌─────────┼────────────────────────────────────────────────────────┐
│         │                                                        │
│  ┌──────▼──────────────────────────────────────────────────┐   │
│  │              LAYER 1: Actuators                          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │   │
│  │  │ DC Motors│ │ Servos    │ │ Pneumatic│ │ LEDs     │   │   │
│  │  │ (Mobility)│ │ (Arms)   │ │ (Hug)    │ │ (Status) │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Component Mapping

**1. Main Controller (ESP32-S3 - WiFi/MQTT Gateway)**
- **Role**: Central WiFi/MQTT gateway và CAN bus router
- **Functions**: WiFi/MQTT communication, CAN routing, data aggregation
- **Price**: ~80k VND (Shopee)
- **Specs**: Dual-core 240MHz, WiFi/BLE, 512KB SRAM, 8MB PSRAM
- **Note**: Only node with WiFi/MQTT capability

**2. Sensor Hub (ESP32-C3 - CAN-only)**
- **Role**: Dedicated sensor data acquisition (CAN bus only)
- **Functions**: I2C sensor reading, CAN communication
- **Price**: ~60k VND (Shopee)
- **Specs**: Single-core 160MHz, 400KB SRAM, WiFi/BT DISABLED
- **Note**: WiFi/BT disabled to prevent RAM overflow

**3. Motor Controller (ESP32-C3 + TB6612FNG - CAN-only)**
- **Role**: PWM generation cho motors và servos (CAN bus only)
- **Functions**: Motor speed control, servo position control, CAN communication
- **Price**: ~90k VND (ESP32-C3: 60k + TB6612FNG: 30k)
- **Specs**: 4-channel PWM, MOSFET driver (low voltage drop)
- **Note**: WiFi/BT disabled to prevent RAM overflow

## Safety & Synchronization Protocols

### 1. Dead Man's Switch (CAN Heartbeat)

**Kịch bản rủi ro**: Router WiFi treo → S3 mất kết nối Laptop → C3 Motor vẫn nhớ lệnh CAN cuối (PWM = tiến) → Robot đâm tường, cháy động cơ.

**Giải pháp**: Heartbeat Signal bắt buộc trên CAN Bus.

```
S3 (Main) ──[CAN ID 0x301 Heartbeat]──▶ C3 (Motor)   mỗi 100ms
                                          │
                                    Watchdog Timer
                                    ┌─────────────────┐
                                    │ >500ms no beat?  │
                                    │ → emergencyStop()│
                                    │ → lock servos    │
                                    │ → cut DC power   │
                                    │ → LED blink RED  │
                                    └─────────────────┘
```

**Quy tắc**:
- S3 gửi CAN frame `ID 0x301`, data = `[seq_number, system_state]` mỗi **100ms**
- C3 Motor có hardware Watchdog Timer = **500ms timeout**
- Nếu quá 500ms không nhận Heartbeat → `emergencyStop()` tự động
- Sau khi E-Stop, C3 chỉ được phục hồi khi nhận lại Heartbeat liên tục 3 frame (300ms)
- Chi phí bổ sung: **0 VND** (pure firmware, dùng TWAI controller có sẵn trên ESP32)

### 2. SNTP Timestamp Synchronization

**Kịch bản rủi ro**: ESP32 `millis()` bắt đầu từ 0 khi cấp điện. ROS2 trên WSL dùng Epoch Time (Linux). Gán ESP32 timestamp cho ROS2 Message → TF (Transform) báo lỗi "time travel" → loại bỏ toàn bộ dữ liệu sensor.

**Giải pháp**: S3 đồng bộ SNTP, đóng dấu timestamp chuẩn cho mọi gói tin.

```
[Boot Sequence - S3 Main Controller]
1. Power ON
2. WiFi Connect
3. ★ SNTP Sync (pool.ntp.org) → Epoch Time ± 1ms
4. CAN Bus Init
5. MQTT Connect
6. ★ Heartbeat Timer Start (100ms)
7. Ready

[Data Flow - Timestamp Stamping]
C3 Sensor ──[CAN: raw data, NO timestamp]──▶ S3
                                              │
                                        S3 đóng dấu:
                                        sntp_epoch_ms + data
                                              │
                                        MQTT Publish
                                              │
                                        ROS2 Bridge:
                                        msg.header.stamp = 
                                          rclpy.time.Time(
                                            sec=epoch_s,
                                            nanosec=epoch_ns
                                          )
```
    
**Quy tắc**:
- C3 (Sensor/Motor) gửi CAN frame **KHÔNG có timestamp** — chỉ raw sensor ID + data
- S3 nhận CAN frame → gắn `sntp_get_epoch_ms()` → đẩy qua MQTT
- `hardware_bridge_node` (ROS2) dùng timestamp từ S3 (epoch) để tạo `builtin_interfaces/Time`
- SNTP re-sync mỗi **60 giây** để chống drift
- Chi phí bổ sung: **0 VND** (ESP-IDF có sẵn `esp_sntp` component)

### 3. OTA Firmware Update (Over-The-Air)

**Kịch bản rủi ro**: 3 board ESP32 (S3, C3, C3) lắp sâu bên trong thân robot 1 mét, bọc vỏ TPU. Có bug firmware → phải tháo tung toàn bộ lớp vỏ và ốc vít chỉ để cắm USB-C nạp code.

**Giải pháp**: OTA Update cho cả 3 vi điều khiển — không bao giờ phải mở vỏ.

```
[OTA Architecture]

Laptop (HTTP Server)              ESP32-S3 (WiFi)              ESP32-C3 x2 (CAN-only)
┌────────────────┐           ┌──────────────────┐          ┌──────────────────┐
│  .bin firmware  │──WiFi──▶│  S3 OTA Receiver  │          │  C3 CAN Bootloader│
│  upload via     │  HTTP   │  ┌──────────────┐ │          │  ┌──────────────┐│
│  browser/curl   │         │  │ Self-flash   │ │          │  │ CAN-OTA Recv ││
│                 │         │  │ (esp_ota_ops)│ │          │  │ (UDS protocol)││
│                 │         │  └──────────────┘ │          │  └──────────────┘│
│                 │         │  ┌──────────────┐ │──CAN──▶│  ┌──────────────┐│
│                 │         │  │ CAN-OTA Proxy│ │  0x7E0  │  │ Flash writer ││
│                 │         │  │ (chunk relay)│ │  chunks  │  │ (4KB blocks) ││
│                 │         │  └──────────────┘ │          │  └──────────────┘│
└────────────────┘          └──────────────────┘          └──────────────────┘
```

**S3 OTA (WiFi HTTP)**:
- ESP-IDF `esp_https_ota` component — built-in, 0 VND
- Laptop chạy HTTP server local (`python3 -m http.server 8070`)
- S3 nhận file `.bin` qua WiFi → flash vào OTA partition → reboot
- Dual OTA partition: `ota_0` + `ota_1` (rollback nếu boot fail)

**C3 OTA (CAN-based UDS)**:
- S3 nhận file `.bin` của C3 qua WiFi
- S3 chia nhỏ thành chunks 4KB → gửi qua CAN Bus
- CAN IDs cho OTA:
  - `0x7E0`: OTA command (start, chunk, verify, reboot)
  - `0x7E1`: OTA response (ack, nack, progress)
- C3 có custom bootloader: nhận chunks → ghi vào flash → verify CRC32 → reboot
- Timeout: 30s per chunk, 5 retries

**Quy tắc**:
- OTA chỉ hoạt động khi robot ở trạng thái `IDLE` (không đang di chuyển)
- C3 Motor phải `emergencyStop()` trước khi bắt đầu OTA flash
- Rollback tự động nếu firmware mới không boot trong 10s
- Chi phí bổ sung: **0 VND** (ESP-IDF built-in + custom CAN bootloader)

### 4. Star Grounding (Chống Ground Loop)

**Kịch bản rủi ro**: Nguồn 7.4V pin chung cực Âm (GND). Nếu GND Motor C3 nối tiếp sang GND S3, dòng Stall Current của 2 DC Motor + 2 Servo gây trồi sụt điện áp tham chiếu → ESP32 Brownout Reset liên tục.

**Giải pháp**: Star Grounding — tất cả GND quy về 1 điểm sao duy nhất.

```
[Star Grounding Topology]

                    ┌───────────────────┐
                    │   BMS 2S 20A      │
                    │   Cọc Âm (-)      │
                    │   ★ STAR POINT ★  │
                    └───────┬───────────┘
                            │
              ┌─────────────┼─────────────┐
              │             │             │
         GND_LOGIC     GND_MOTOR     GND_SERVO
         (AWG 22)      (AWG 18)      (AWG 20)
              │             │             │
    ┌─────────▼─────┐ ┌────▼────┐  ┌─────▼─────┐
    │ S3 + C3 Sensor│ │TB6612FNG│  │ MG996R x2 │
    │ (< 500mA)     │ │+ DC x2 │  │ (< 2A)    │
    │               │ │(< 5A)  │  │           │
    └───────────────┘ └────────┘  └───────────┘

  ✗ TUYỆT ĐỐI KHÔNG nối tiếp GND motor → GND logic
  ✗ TUYỆT ĐỐI KHÔNG để dòng hồi motor chạy qua board logic
  ✓ Mỗi nhánh GND kéo riêng về cọc âm BMS (Star Point)
```

**Quy tắc Altium Designer**:
- Star Point = cọc âm của BMS (nơi dòng lớn nhất)
- GND_LOGIC: dây AWG 22 (0.33mm²) — S3, C3 Sensor, I2C sensors
- GND_MOTOR: dây AWG 18 (0.82mm²) — TB6612FNG, 2x DC Motor
- GND_SERVO: dây AWG 20 (0.52mm²) — 2x MG996R
- Bypass capacitor 100µF + 100nF tại mỗi ESP32 VIN pin
- Chi phí bổ sung: **0 VND** (chỉ thay đổi cách đi dây, không cần linh kiện mới)

### 5. FreeRTOS Core Pinning (Chống Heartbeat Jitter)

**Kịch bản rủi ro**: ESP32-S3 dual-core. WiFi/TCP/IP/MQTT stack nặng và ngắt quãng. FreeRTOS tự do phân bổ → WiFi biến động → CAN Bus + Heartbeat bị trễ (jitter) → Dead Man's Switch kích hoạt nhầm → robot tự E-Stop dù không lỗi.

**Giải pháp**: Pin cứng mỗi task vào core cụ thể bằng `xTaskCreatePinnedToCore`.

```
[ESP32-S3 Dual-Core Task Assignment]

┌─────────────────────────────────────────────────┐
│  Core 0 (Protocol Core)    │  Core 1 (RT Core)  │
│  PRO_CPU                   │  APP_CPU            │
│────────────────────────────│────────────────────│
│  ★ WiFi Driver (system)    │  ★ CAN Bus TX/RX   │
│  ★ TCP/IP Stack (lwIP)     │  ★ Heartbeat Timer │
│  ★ MQTT Client             │  ★ State Machine   │
│  ★ SNTP Sync               │  ★ Sensor Fusion   │
│  ★ OTA HTTP Receiver       │  ★ CAN-OTA Proxy   │
│  ★ Telemetry MQTT Pub      │  ★ Command Router  │
│                            │                    │
│  Priority: Normal (5)      │  Priority: High(10)│
│  Jitter: Acceptable        │  Jitter: < 1ms ★   │
│  Can be interrupted        │  NEVER interrupted │
│                            │  by WiFi           │
└─────────────────────────────────────────────────┘
```

**Quy tắc**:
- Core 0: **TẤT CẢ** network stack — WiFi, MQTT, SNTP, OTA HTTP
- Core 1: **TẤT CẢ** real-time tasks — CAN, Heartbeat, State Machine, Sensor Fusion
- Heartbeat timer chạy trên Core 1 → không bị WiFi reconnect delay ảnh hưởng
- Inter-core communication qua `xQueueSendFromISR` (lock-free)
- Chi phí bổ sung: **0 VND** (FreeRTOS API có sẵn trên ESP-IDF)

## BOM (Bill of Materials) - Budget Constrained

### Main Components (Total: ~780k VND - SAFETY OPTIMIZED)

| Component | Qty | Unit (VND) | Total (VND) | Notes |
|-----------|-----|-----------|-------------|-------|
| **ESP32-S3-WROOM-1** | 1 | 80,000 | 80,000 | Main controller + SNTP + Heartbeat sender |
| **ESP32-C3-SuperMini** | 2 | 60,000 | 120,000 | Sensor hub + Motor ctrl (CAN-only) |
| **MPU-6050 IMU** | 1 | 15,000 | 15,000 | Robot IMU only (Owner IMU = phone SensorLogs) |
| **MAX30102 SpO2** | 1 | 25,000 | 25,000 | Heart rate + SpO2 |
| **BME280** | 1 | 20,000 | 20,000 | Temp, humidity, pressure |
| **HC-SR04 Ultrasonic** | 3 | 8,000 | 24,000 | Front + Left + Right (rear = camera) |
| **TB6612FNG Motor Driver** | 1 | 30,000 | 30,000 | Dual-channel cho 2 DC motors |
| **MG996R Servo** | 2 | 35,000 | 70,000 | Shoulder joints only (MVP) |
| **DC Motor 12V** | 2 | 25,000 | 50,000 | Mobility (L/R wheels) |
| **Current Sensor ACS712** | 1 | 12,000 | 12,000 | Total battery current only |
| **Voltage Divider (resistor)** | 1 | 1,000 | 1,000 | 2 resistors thay voltage sensor module |
| **Li-Ion Battery 18650** | 4 | 15,000 | 60,000 | 2S2P configuration (7.4V) |
| **608ZZ Bearing** | 4 | 5,000 | 20,000 | Shoulder + wheel bearings (MVP) |
| **BMS 2S 20A** | 1 | 25,000 | 25,000 | Battery protection |
| **XL4015 Buck Converter 5A** | 1 | 15,000 | 15,000 | 7.4V→5V/6V for servos |
| **SN65HVD230 CAN Transceiver** | 2 | 15,000 | 30,000 | CAN bus communication |
| **LED RGB WS2812B** | 5 | 3,000 | 15,000 | Status (1 data pin, daisy-chain) |
| **Buzzer** | 1 | 5,000 | 5,000 | Audio feedback |
| **PCB Fabrication** | 3 | 15,000 | 45,000 | JLCPCB 5pcs/order ≈ 15k/board |
| **Connectors/Wires** | 1 set | 20,000 | 20,000 | JST-XH + Dupont |
| **120Ω Resistor (CAN term.)** | 2 | 500 | 1,000 | CAN bus termination |
| **TOTAL** | | | **683,000** | **Tiết kiệm 173k vs bản cũ** |

**COST OPTIMIZATION v2 (Tiết kiệm 173k VND)**:
- ❌ Removed: MPU-6050 x1 (Owner IMU dùng SensorLogs phone — đã có sẵn, 0 VND)
- ❌ Removed: HC-SR04 x1 (rear sensor thay bằng camera IPWebCam có sẵn)
- ❌ Removed: Voltage Sensor module x2 (thay bằng voltage divider 2 resistor = 1k VND)
- ❌ Removed: MG996R x2 (MVP chỉ cần 2 shoulder, elbow thêm sau)
- ❌ Removed: TB6612FNG x1 (1 module dual-channel đủ cho 2 DC motors)
- ❌ Removed: Current Sensor x1 (1 sensor tổng battery current là đủ)
- ❌ Removed: 608ZZ x4 (MVP chỉ cần 4 bearings: 2 shoulder + 2 wheel)
- ❌ Removed: LED RGB x5 + Buzzer x1 (giảm số lượng, dùng WS2812B daisy-chain)
- ✅ Added: Dead Man's Switch Heartbeat (0 VND — pure firmware)
- ✅ Added: SNTP Timestamp Sync (0 VND — ESP-IDF built-in)
- ✅ Added: CAN termination resistors 120Ω x2 (1k VND)
- ✅ Kept: SN65HVD230 x2 (CAN transceiver — bắt buộc)
- ✅ Kept: BMS 2S + XL4015 Buck (battery safety — bắt buộc)

**SAFETY FEATURES (0 VND THÊM)**:
- 🛡️ CAN Heartbeat 0x301 mỗi 100ms (S3 → C3 Motor)
- 🛡️ Watchdog Timer 500ms trên C3 Motor (auto E-Stop)
- 🛡️ SNTP sync epoch timestamp (S3 đóng dấu, tránh ROS2 time-travel)
- 🛡️ 3-frame recovery protocol (chống false-positive E-Stop)

### 3D Printing Materials (Total: ~450k VND)

| Material | Quantity | Unit Price (VND) | Total (VND) | Notes |
|----------|----------|------------------|-------------|-------|
| PETG Filament (White) | 1kg | 200,000 | 200,000 | Structural parts |
| TPU Filament (Black) | 0.5kg | 250,000 | 125,000 | Flexible joints |
| PLA Filament (Red) | 0.5kg | 150,000 | 75,000 | Accent parts |
| **TOTAL** | | | **400,000** | |

> **Note**: PLA chỉ dùng cho accent cosmetics, KHÔNG dùng cho structural. Nếu budget tight, bỏ PLA và dùng PETG sơn đỏ → tiết kiệm thêm 75k VND.

### Tools & Equipment (One-time: ~300k VND)

| Item | Price (VND) | Notes |
|------|-------------|-------|
| Soldering Iron Kit | 80,000 | Basic soldering |
| Multimeter | 100,000 | Voltage/current measurement |
| Wire Stripper | 30,000 | Wire preparation |
| Screwdriver Set | 50,000 | Assembly |
| Hot Glue Gun | 40,000 | Temporary mounting |
| **TOTAL** | **300,000** | |

### Grand Total: ~1,383,000 VND (~$55 USD)

> **So sánh**: Bản cũ 1,556k → Bản mới 1,383k = **Tiết kiệm 173k VND (11%)** mà **thêm 2 safety features critical** (Heartbeat + SNTP).

## PCB Design Specifications (Altium Designer)

### PCB 1: ESP32-S3 Main Controller Board

**Dimensions**: 50mm x 50mm (2-layer)
**Layers**: Top (Signal + Power), Bottom (GND plane)

**Components Placement**:
```
┌───────────────────────────────────┐
│  [ESP32-S3]              [USB-C]  │
│  ┌─────────┐                      │
│  │         │  [Antenna]           │
│  │         │                      │
│  └─────────┘                      │
│  [I2C] [SPI] [UART] [GPIO]        │
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐          │
│  │   │ │   │ │   │ │   │          │
│  └───┘ └───┘ └───┘ └───┘          │
│  [Power LED] [Status LED]         │
└───────────────────────────────────┘
```

**Pinout**:
- I2C: GPIO 21 (SDA), GPIO 22 (SCL)
- SPI: GPIO 5 (SCK), GPIO 18 (MISO), GPIO 23 (MOSI), GPIO 19 (CS)
- UART: GPIO 1 (TX), GPIO 3 (RX)
- CAN TX: GPIO 43
- CAN RX: GPIO 44
- PWM: GPIO 4, 16, 17 (Motor control)
- ADC: GPIO 34, 35, 36 (Analog sensors)

**Power Distribution (★ Star Grounding)**:
- 7.4V input (2S battery) → XL4015 Buck → 5V/6V for servos
- 7.4V → 3.3V LDO (AMS1117) for ESP32 and sensors
- 7.4V direct to TB6612FNG for DC motors
- **★ Star Ground**: tất cả GND quy về 1 điểm = cọc âm BMS
  - GND_LOGIC (AWG 22): S3 + C3 Sensor + I2C sensors
  - GND_MOTOR (AWG 18): TB6612FNG + DC Motors
  - GND_SERVO (AWG 20): MG996R Servos
  - **TUYỆT ĐỐI KHÔNG nối tiếp GND motor → GND logic**
- Bypass cap: 100µF + 100nF tại mỗi ESP32 VIN pin

### PCB 2: ESP32-C3 Sensor Hub Board

**Dimensions**: 40mm x 40mm (2-layer)
**Purpose**: Dedicated sensor data acquisition

**Sensor Connections**:
```
┌─────────────────────────────────┐
│  [ESP32-C3]                     │
│  ┌─────────┐                    │
│  │         │  [Antenna]         │
│  └─────────┘                    │
│  I2C Bus:                       │
│  ┌─────┐ ┌─────┐ ┌─────┐        │
│  │IMU  │ │SpO2 │ │Env  │        │
│  └─────┘ └─────┘ └─────┘        │
│  GPIO:                          │
│  ┌─────┐ ┌─────┐                │
│  │Ultrasonic│ │GPS  │           │
│  └─────┘ └─────┘                │
└─────────────────────────────────┘
```

**I2C Address Assignment**:
- MPU-6050: 0x68 (Robot IMU), 0x69 (Owner IMU)
- MAX30102: 0x57
- BME280: 0x76 or 0x77

**CAN Bus Integration**:
- CAN TX: GPIO 6
- CAN RX: GPIO 7
- SN65HVD230 transceiver for differential signaling
- 120Ω termination resistor

### PCB 3: Motor Controller Board

**Dimensions**: 60mm x 40mm (2-layer)
**Purpose**: PWM generation and motor driving

**Circuit**:
```
┌─────────────────────────────────┐
│  [ESP32-C3]                     │
│  ┌─────────┐                    │
│  │         │                    │
│  └─────────┘                    │
│  PWM Outputs:                   │
│  ┌─────┐ ┌─────┐ ┌─────┐        │
│  │TB6612FNG│ │Servo│ │Servo│    │
│  │Ch1  │ │1    │ │2    │        │
│  └─────┘ └─────┘ └─────┘        │
│  ┌─────┐ ┌─────┐                │
│  │TB6612FNG│ │Servo│            │
│  │Ch2  │ │3    │                │
│  └─────┘ └─────┘                │
│  [Current Sensors]              │
│  [SN65HVD230 CAN Transceiver]   │
└─────────────────────────────────┘
```

**TB6612FNG Pinout**:
- AIN1, AIN2, APWM → Motor A control
- BIN1, BIN2, BPWM → Motor B control
- VM → Motor power (7.4V)
- VCC → Logic power (3.3V)
- GND → Ground
- STBY → Enable (active high)

## 3D Printing Specifications (0.5:1 Baymax Scale)

### Scale Calculations
- **Baymax Full Size**: ~2.0m height, ~1.0m width
- **HK-07 Target Scale**: 0.5:1
- **HK-07 Dimensions**: ~1.0m height, ~0.5m width

### Part Breakdown

**1. Body Structure (PETG)**
- Torso: 300mm x 200mm x 250mm
- Head: 200mm diameter sphere
- Arms: 400mm length x 80mm diameter
- Legs: 350mm length x 100mm diameter

**2. Joints (Hybrid Structure)**
- **Load-Bearing Core (PETG)**: Shoulder, Elbow, Hip, Knee - 8x
- **Aesthetic Shell (TPU)**: Shoulder, Elbow, Hip, Knee covers - 8x
- **Bearings**: 608ZZ x8 for smooth rotation

**3. Mounting Plates (PETG)**
- Electronics bay: 150mm x 100mm x 50mm
- Battery compartment: 100mm x 80mm x 40mm
- Sensor mounts: Various sizes

### Print Settings

**PETG (Structural)**:
- Nozzle: 0.4mm
- Layer height: 0.2mm
- Infill: 20% (gyroid)
- Supports: Yes (for overhangs >45°)
- Bed temp: 80°C
- Nozzle temp: 240°C

**PETG (Load-Bearing Core)**:
- Nozzle: 0.4mm
- Layer height: 0.2mm
- Infill: 40% (gyroid) - higher for strength
- Walls: 4 perimeters
- Supports: Yes for bearing holes
- Bed temp: 80°C
- Nozzle temp: 240°C
- Post-processing: Drill bearing holes to precise size

**TPU (Aesthetic Shell)**:
- Nozzle: 0.4mm (hardened)
- Layer height: 0.3mm
- Infill: 20% (grid) - flexible
- Walls: 2 perimeters
- Supports: No (flexible material)
- Bed temp: 50°C
- Nozzle temp: 220°C
- Print speed: 20mm/s (slow)

## Firmware Architecture

### ESP32-S3 Main Controller (C++)

**Framework**: ESP-IDF v5.0

**Key Components**:
```cpp
// Main Controller — Heartbeat, SNTP, OTA, Core Pinning
class HK07MainController {
private:
    // ── Core 0 (Protocol) ──
    WiFiManager* wifiManager;
    MQTTClient* mqttClient;
    SNTPManager* sntpManager;
    OTAManager* otaManager;            // ★ WiFi OTA + CAN-OTA Proxy
    
    // ── Core 1 (Real-time) ──
    CANInterface* canInterface;
    esp_timer_handle_t heartbeatTimer;
    uint8_t heartbeatSeqNum = 0;
    SensorFusion* sensorFusion;
    RobotStateMachine* stateMachine;
    
    // ── Inter-core Queue ──
    QueueHandle_t canToMqttQueue;      // Core1→Core0: sensor data for MQTT publish
    QueueHandle_t mqttToCanQueue;      // Core0→Core1: commands for CAN dispatch
    
public:
    void initialize() {
        // ── Phase 1: Network (runs on Core 0 by default) ──
        wifiManager->connect();
        sntpManager->syncTime();           // ★ SNTP sync FIRST
        mqttClient->connect();
        otaManager->initHTTPServer(8070);  // ★ OTA HTTP endpoint
        
        // ── Phase 2: Real-time bus ──
        canInterface->begin(500000);       // 500kbps CAN
        canToMqttQueue = xQueueCreate(16, sizeof(CANSensorFrame));
        mqttToCanQueue = xQueueCreate(8, sizeof(CANCommand));
        
        // ── Phase 3: Pin tasks to cores ──
        // Core 0 — Protocol (WiFi, MQTT, SNTP, OTA)
        xTaskCreatePinnedToCore(
            protocolTask, "protocol", 8192, this,
            5,      // Normal priority
            nullptr,
            0       // ★ Core 0 = PRO_CPU
        );
        
        // Core 1 — Real-time (CAN, Heartbeat, StateMachine)
        xTaskCreatePinnedToCore(
            realtimeTask, "realtime", 4096, this,
            10,     // ★ High priority — NEVER preempted by WiFi
            nullptr,
            1       // ★ Core 1 = APP_CPU
        );
        
        startHeartbeatTimer();  // ★ esp_timer runs on Core 1
    }
    
private:
    // ── Core 0: Protocol Task ──
    // WiFi/MQTT/SNTP/OTA — can jitter, no safety impact
    static void protocolTask(void* arg) {
        auto* self = static_cast<HK07MainController*>(arg);
        CANSensorFrame frame;
        while (true) {
            // Receive sensor data from Core 1 via queue (lock-free)
            if (xQueueReceive(self->canToMqttQueue, &frame, pdMS_TO_TICKS(50))) {
                // ★ Stamp SNTP epoch timestamp HERE (Core 0 owns SNTP)
                int64_t epoch_ms = self->sntpManager->getEpochMs();
                MQTTPayload payload;
                payload.timestamp_ms = epoch_ms;
                payload.sensor = frame;
                self->mqttClient->publish("hk07/robot/telemetry", payload);
            }
            self->mqttClient->loop();  // MQTT keepalive
            self->otaManager->poll();  // Check for OTA requests
        }
    }
    
    // ── Core 1: Real-time Task ──
    // CAN Bus + State Machine — zero jitter, safety critical
    static void realtimeTask(void* arg) {
        auto* self = static_cast<HK07MainController*>(arg);
        while (true) {
            // Read CAN frames from Sensor Hub
            CANFrame rx;
            if (self->canInterface->receive(&rx, pdMS_TO_TICKS(10))) {
                if (rx.id == 0x200) {
                    // Sensor data → enqueue for Core 0 to MQTT publish
                    CANSensorFrame sf = parseSensorFrame(rx);
                    xQueueSend(self->canToMqttQueue, &sf, 0); // non-blocking
                }
            }
            
            // Process commands from MQTT (Core 0 → Core 1)
            CANCommand cmd;
            if (xQueueReceive(self->mqttToCanQueue, &cmd, 0)) {
                self->canInterface->send(cmd.toCANFrame());
            }
            
            self->stateMachine->update();
        }
    }
    
    // ★ Heartbeat: runs on esp_timer (ISR context, Core 1)
    static void heartbeatCallback(void* arg) {
        auto* self = static_cast<HK07MainController*>(arg);
        CANFrame hb;
        hb.id = 0x301;
        hb.data[0] = self->heartbeatSeqNum++;
        hb.data[1] = static_cast<uint8_t>(self->stateMachine->getState());
        self->canInterface->send(hb);  // ★ CAN send from Core 1 — no WiFi contention
    }
    
    void startHeartbeatTimer() {
        esp_timer_create_args_t args = {
            .callback = heartbeatCallback,
            .arg = this,
            .name = "heartbeat"
        };
        esp_timer_create(&args, &heartbeatTimer);
        esp_timer_start_periodic(heartbeatTimer, 100000); // 100ms
    }
};
```

**Boot Sequence (CRITICAL ORDER)**:
```
1. Power ON → Hardware Init
2. WiFi Connect (retry 5x, 2s interval)
3. ★ SNTP Sync (pool.ntp.org) → wait until epoch valid
4. CAN Bus Init (500kbps)
5. MQTT Connect (Mosquitto broker)
6. ★ OTA HTTP Server Start (port 8070)
7. ★ Create inter-core queues (canToMqtt, mqttToCan)
8. ★ Pin protocolTask → Core 0 (WiFi, MQTT, SNTP, OTA)
9. ★ Pin realtimeTask → Core 1 (CAN, StateMachine)
10. ★ Heartbeat Timer Start (100ms, Core 1 context)
11. Subscribe to hk07/robot/command
12. System READY → LED GREEN
```

**Communication Protocol**:
- MQTT Topics:
  - `hk07/robot/telemetry` → Publish sensor data **(with SNTP epoch timestamp)**
  - `hk07/robot/command` → Subscribe to commands
  - `hk07/robot/status` → Publish robot state + heartbeat status
- CAN Bus:
  - ID 0x100: Motor commands (S3 → C3 Motor)
  - ID 0x200: Sensor data (C3 Sensor → S3) **(NO timestamp, raw only)**
  - ID 0x300: Emergency stop (broadcast)
  - **ID 0x301: Heartbeat (S3 → C3 Motor, every 100ms)** ★
  - ID 0x7E0: OTA command (S3 → C3, firmware chunks) ★
  - ID 0x7E1: OTA response (C3 → S3, ack/progress) ★

### ESP32-C3 Sensor Hub (C++)

**Key Components**:
```cpp
class SensorHub {
private:
    I2CBus* i2cBus;
    MPU6050* robotIMU;
    MPU6050* ownerIMU;
    MAX30102* spo2Sensor;
    BME280* envSensor;
    UltrasonicArray* ultrasonicSensors;
    GPSModule* gpsModule;
    
public:
    void initializeSensors();
    SensorData readAllSensors();
    void preprocessData();
    void sendDataToMain();
};
```

**Data Structure**:
```cpp
// ★ C3 Sensor gửi raw data qua CAN — KHÔNG có timestamp
struct CANSensorFrame {
    // Robot IMU (MPU-6050 on-board)
    float robotAccelX, robotAccelY, robotAccelZ;
    float robotGyroX, robotGyroY, robotGyroZ;
    
    // Owner IMU: ĐÃ LOẠI BỎ — dùng SensorLogs phone (qua MQTT trực tiếp)
    
    // Vitals (MAX30102)
    float heartRate;
    float spo2;
    float bodyTemperature; // từ MAX30102 die temperature
    
    // Environment (BME280)
    float envTemperature;
    float humidity;
    float pressure;
    
    // Ultrasonic (HC-SR04 x3)
    float distFront, distLeft, distRight;
    
    // ★ KHÔNG CÓ TIMESTAMP — S3 sẽ đóng dấu SNTP epoch khi relay qua MQTT
};

// ★ Gói tin MQTT từ S3 (đã có timestamp chuẩn)
struct MQTTTelemetryPayload {
    int64_t timestamp_ms;  // SNTP epoch milliseconds — S3 đóng dấu
    CANSensorFrame sensor;
    uint8_t heartbeat_seq; // Heartbeat sequence number hiện tại
    uint8_t system_state;  // Robot state machine state
};
```

### ESP32-C3 Motor Controller (C++) — with Dead Man's Switch

**Key Components**:
```cpp
// ★ Motor Controller with Watchdog Dead Man's Switch
class MotorController {
private:
    TB6612FNGDriver* motorDriver;  // ★ TB6612FNG thay L298N
    ServoDriver* servoDriver;
    CurrentSensor* batteryCurrent;  // ★ 1 sensor tổng (thay vì 2)
    CANInterface* canInterface;
    
    // ★ Dead Man's Switch — Watchdog
    volatile uint32_t lastHeartbeatMs = 0;
    volatile bool safetyLocked = true;  // Boot vào trạng thái LOCKED
    uint8_t recoveryCount = 0;
    static const uint32_t HEARTBEAT_TIMEOUT_MS = 500;  // 500ms timeout
    static const uint8_t RECOVERY_THRESHOLD = 3;       // 3 frames liên tục
    
public:
    void initialize() {
        canInterface->begin(500000);
        canInterface->setFilter(0x100, 0x301); // Chỉ nhận Motor cmd + Heartbeat
        startWatchdogTask();
    }
    
    void setMotorSpeed(int motorId, float speed);
    void setServoAngle(int servoId, float angle);
    MotorStatus getStatus();
    
    // ★ Hardware E-Stop: ngắt toàn bộ actuator
    void emergencyStop() {
        motorDriver->brake();           // Short-brake (không coast)
        servoDriver->lockAll();         // Giữ vị trí hiện tại
        motorDriver->setStandby(true);  // TB6612FNG STBY = LOW → cut power
        safetyLocked = true;
        recoveryCount = 0;
        // LED blink RED pattern
    }
    
private:
    // ★ CAN Receive ISR — xử lý Heartbeat
    void onCANReceive(CANFrame& frame) {
        if (frame.id == 0x301) {  // Heartbeat from S3
            lastHeartbeatMs = millis();
            if (safetyLocked) {
                recoveryCount++;
                if (recoveryCount >= RECOVERY_THRESHOLD) {
                    safetyLocked = false;  // Phục hồi sau 3 heartbeat liên tục (300ms)
                    motorDriver->setStandby(false); // Re-enable motors
                }
            }
        } else if (frame.id == 0x100 && !safetyLocked) {
            // Motor command — chỉ xử lý khi KHÔNG bị safety lock
            processMotorCommand(frame);
        } else if (frame.id == 0x300) {
            emergencyStop(); // Broadcast E-Stop
        }
    }
    
    // ★ Watchdog Task — chạy trên FreeRTOS task riêng
    static void watchdogTask(void* arg) {
        auto* self = static_cast<MotorController*>(arg);
        while (true) {
            if ((millis() - self->lastHeartbeatMs) > HEARTBEAT_TIMEOUT_MS) {
                self->emergencyStop();  // ★ DEAD MAN'S SWITCH ACTIVATED
            }
            vTaskDelay(pdMS_TO_TICKS(50)); // Check every 50ms
        }
    }
    
    void startWatchdogTask() {
        xTaskCreate(watchdogTask, "watchdog", 2048, this, 
                    configMAX_PRIORITIES - 1, nullptr); // Highest priority
    }
};
```

> ⚠️ **CRITICAL**: C3 Motor boot vào trạng thái `safetyLocked = true`. Robot KHÔNG THỂ di chuyển cho đến khi nhận đủ 3 Heartbeat liên tục từ S3. Đây là hành vi mong muốn — đảm bảo S3 đã online và SNTP đã sync trước khi robot được phép vận hành.

## ROS2 Integration

### ROS2 Node: Hardware Bridge

**Purpose**: Bridge between ESP32 hardware and ROS2 ecosystem

**Topics**:
```python
# Subscribed Topics (from ESP32 via MQTT)
/hardware/sensors/imu/robot → sensor_msgs/Imu
/hardware/sensors/imu/owner → sensor_msgs/Imu
/hardware/sensors/vitals → sensor_msgs/JointState
/hardware/sensors/environment → sensor_msgs/JointState
/hardware/sensors/location → sensor_msgs/NavSatFix
/hardware/sensors/ultrasonic → sensor_msgs/Range

# Published Topics (to ESP32 via MQTT)
/hardware/control/motors → geometry_msgs/Twist
/hardware/control/servos → std_msgs/Float32MultiArray
/hardware/control/emergency → std_msgs/Empty
```

**Node Implementation** (Python) — **with SNTP Timestamp Integration**:
```python
from builtin_interfaces.msg import Time
import math

class HardwareBridgeNode(Node):
    def __init__(self):
        super().__init__('hardware_bridge_node')
        
        # MQTT Client
        self.mqtt_client = MQTTClient()
        
        # ROS2 Publishers
        self.imu_robot_pub = self.create_publisher(Imu, '/sensors/imu/robot', 10)
        # ★ Owner IMU comes from SensorLogs phone via separate MQTT topic
        self.vitals_pub = self.create_publisher(JointState, '/vitals/wristband', 10)
        
        # ROS2 Subscribers
        self.motor_sub = self.create_subscription(
            Twist, '/control/motors', self.motor_callback, 10)
        
        # Timers
        self.timer = self.create_timer(0.05, self.publish_sensor_data)
    
    def publish_sensor_data(self):
        # Read from MQTT — payload already contains SNTP epoch timestamp from S3
        payload = self.mqtt_client.receive('hk07/robot/telemetry')
        
        # ★ Convert S3's SNTP epoch_ms to ROS2 builtin_interfaces/Time
        # This ensures TF tree never sees "time travel" errors
        epoch_ms = payload['timestamp_ms']
        ros_stamp = Time()
        ros_stamp.sec = int(epoch_ms // 1000)
        ros_stamp.nanosec = int((epoch_ms % 1000) * 1_000_000)
        
        # Build IMU message with correct timestamp
        imu_msg = Imu()
        imu_msg.header.stamp = ros_stamp  # ★ SNTP epoch, NOT ESP32 millis()
        imu_msg.header.frame_id = 'robot_imu_link'
        imu_msg.linear_acceleration.x = payload['sensor']['robotAccelX']
        imu_msg.linear_acceleration.y = payload['sensor']['robotAccelY']
        imu_msg.linear_acceleration.z = payload['sensor']['robotAccelZ']
        imu_msg.angular_velocity.x = payload['sensor']['robotGyroX']
        imu_msg.angular_velocity.y = payload['sensor']['robotGyroY']
        imu_msg.angular_velocity.z = payload['sensor']['robotGyroZ']
        
        self.imu_robot_pub.publish(imu_msg)
        
        # ★ Monitor heartbeat status from S3
        if payload.get('system_state') == 'E_STOP':
            self.get_logger().warn('⚠️ Dead Man Switch ACTIVATED — motors locked')
```

## Agent-Hardware Integration

### Command Flow

```
User Voice Command
    ↓
hk07-agent (LLM Processing)
    ↓
Intent Classification
    ↓
Command Generation (JSON)
    ↓
hk07-core (Business Logic)
    ↓
MQTT Publish (hk07/robot/command)
    ↓
ESP32-S3 Main Controller
    ↓
Motor Controller (ESP32-C3)
    ↓
Actuators (Motors/Servos)
    ↓
Physical Action
```

### Command Format

**JSON Command Structure**:
```json
{
  "command": "MOVE_FORWARD",
  "parameters": {
    "speed": 0.5,
    "duration": 5.0
  },
  "priority": "NORMAL",
  "timestamp": 1720789200
}
```

**Supported Commands**:
- `MOVE_FORWARD`, `MOVE_BACKWARD`, `TURN_LEFT`, `TURN_RIGHT`
- `ARM_EXTEND`, `ARM_RETRACT`, `ARM_ROTATE`
- `HUG_START`, `HUG_STOP`
- `EMERGENCY_STOP`
- `SCAN_ENVIRONMENT`
- `GO_TO_LOCATION`

### Feedback Loop

```
Sensor Data → ESP32 → MQTT → ROS2 → Blackboard → Agent Analysis
    ↓
Response Generation → MQTT → ESP32 → Action Execution
    ↓
Result Feedback → MQTT → ROS2 → Agent Confirmation
```

## Implementation Phases

### Phase 1: Hardware Procurement (Week 1)
1. Order components from Shopee (including bearings)
2. Order PCB fabrication (JLCPCB) - updated designs
3. Purchase 3D printing materials (PETG + TPU)
4. Acquire tools and equipment
5. Order optional P82B715 if I2C >15cm needed

### Phase 2: PCB Assembly (Week 2)
1. Solder ESP32-S3 main board
2. Solder ESP32-C3 sensor hub
3. Solder ESP32-C3 motor controller
4. Test power distribution
5. Verify I2C/SPI communication

### Phase 3: Firmware Development (Week 3-4)
1. ESP-IDF environment setup (partition table: factory + ota_0 + ota_1)
2. **★ S3: Implement SNTP sync (pool.ntp.org) — FIRST PRIORITY**
3. **★ S3: Implement CAN Heartbeat timer (100ms, ID 0x301)**
4. **★ S3: Implement Core Pinning (Core 0: Protocol, Core 1: Real-time)**
5. **★ C3 Motor: Implement Watchdog Dead Man's Switch (500ms timeout)**
6. S3: Implement WiFi/MQTT gateway + CAN routing (inter-core queues)
7. S3: Implement timestamp stamping on MQTT telemetry (Core 0)
8. **★ S3: Implement WiFi OTA HTTP server (port 8070)**
9. **★ S3: Implement CAN-OTA Proxy (relay .bin chunks to C3 via 0x7E0)**
10. **★ C3: Implement CAN Bootloader (receive chunks, flash, verify CRC32)**
11. C3 Sensor: Implement sensor drivers (I2C, raw CAN output, NO timestamp)
12. C3 Motor: Implement TB6612FNG driver + servo control
13. Implement CAN bus protocol (all nodes, 500kbps)
14. Unit testing each module
15. **★ Safety test: kill WiFi → verify C3 Motor E-Stops within 500ms**
16. **★ Core Pinning test: WiFi reconnect storm → verify Heartbeat jitter <1ms**
17. **★ OTA test: flash C3 firmware via CAN without opening robot shell**
18. RAM usage testing (C3 <200KB)

### Phase 4: 3D Printing (Week 4-5)
1. Design parts in CAD (Fusion 360 Free)
2. Slice parts (Cura/PrusaSlicer)
3. Print structural parts (PETG)
4. Print flexible joints (TPU)
5. Post-processing (sanding, assembly)

### Phase 5: Mechanical Assembly (Week 5-6)
1. Mount electronics in body (C3 sensors <15cm from I2C devices)
2. Install motors and servos with bearings
3. Attach sensors (I2C wires <15cm)
4. Wire all components (CAN bus, power)
5. Install battery system (2S2P)
6. Assemble hybrid joints (PETG core + TPU shell)
7. Mechanical testing

### Phase 6: ROS2 Integration (Week 6-7)
1. Develop hardware bridge node
2. Implement MQTT-ROS2 topics
3. Test sensor data flow
4. Test command execution
5. Integrate with existing system

### Phase 7: Agent Integration (Week 7-8)
1. Implement command routing
2. Add hardware commands to agent
3. Test voice-to-action pipeline
4. Implement feedback loop
5. End-to-end testing

### Phase 8: Calibration & Tuning (Week 8-9)
1. Sensor calibration
2. Motor PID tuning (with rigid joints)
3. Balance control tuning (no oscillation)
4. CAN bus latency testing (<1ms)
5. I2C signal integrity testing
6. RAM usage verification (C3 <200KB)
7. Navigation testing
8. Healthcare workflow testing

### Phase 9: Documentation (Week 9-10)
1. Wiring diagrams
2. Pinout documentation
3. Firmware documentation
4. User manual
5. Maintenance guide

## Testing & Validation

### Hardware Tests
- **Power Consumption**: Measure current draw at different states
- **Sensor Accuracy**: Compare with reference sensors
- **Motor Performance**: Test speed, torque, precision
- **Communication**: Test MQTT/CAN reliability
- **Thermal**: Test under continuous operation

### Software Tests
- **Unit Tests**: Each firmware module
- **Integration Tests**: ROS2 node communication
- **End-to-End Tests**: Voice command to action
- **Stress Tests**: Continuous operation 24h
- **Safety Tests**: Emergency stop functionality

### ★ Safety-Critical Tests (MANDATORY before first run)
- **Dead Man's Switch**: Rút nguồn S3 → C3 Motor phải E-Stop trong <500ms
- **WiFi Kill Test**: Tắt router → S3 mất MQTT → Heartbeat vẫn chạy (CAN local) → Robot vẫn an toàn
- **Full Blackout**: Tắt Laptop + Router → CAN heartbeat vẫn chạy → Robot dừng từ từ
- **Recovery Test**: Sau E-Stop, bật lại S3 → C3 phải nhận đủ 3 heartbeat (300ms) trước khi unlock
- **SNTP Drift Test**: Chạy 24h → drift <10ms
- **ROS2 TF Test**: `ros2 run tf2_tools view_frames` → không có time-travel warning

### ★ Production-Hardening Tests (MANDATORY before sealing robot shell)
- **OTA WiFi Test**: Flash S3 firmware mới qua WiFi HTTP → verify auto-rollback nếu boot fail
- **OTA CAN Test**: Flash C3 firmware qua CAN (0x7E0) từ S3 proxy → verify CRC32 + rollback
- **OTA Under Load**: Flash C3 trong khi sensor data vẫn stream → verify không mất data
- **Ground Loop Test**: Khởi động 2 DC Motor + 2 Servo đồng thời → S3 không brownout reset
- **Stall Current Test**: Chặn bánh xe (stall) → verify S3 voltage không sụt <3.0V
- **Core Pinning Test**: Gây WiFi reconnect storm (bật/tắt router 20 lần/phút) → Heartbeat jitter <1ms
- **Core Isolation Test**: Đo thời gian Heartbeat callback trung bình khi WiFi bận vs WiFi rảnh → delta <0.5ms

### System Tests
- **Navigation**: Obstacle avoidance, path following
- **Manipulation**: Object grasping, hugging
- **Healthcare**: Vitals monitoring, fall detection
- **Communication**: Voice interaction, feedback
- **Battery**: Runtime estimation, charging

## Risk Mitigation

### Technical Risks
- **Sensor Noise**: Implement filtering (Kalman, complementary)
- **Communication Loss**: ★ Dead Man's Switch auto E-Stop trong 500ms
- **Power Failure**: ★ C3 Motor boot vào safetyLocked=true (fail-safe default)
- **Motor Failure**: Implement current monitoring (ACS712)
- **Firmware Bugs**: ★ FreeRTOS watchdog task ở highest priority
- **Timestamp Drift**: ★ SNTP re-sync mỗi 60s, drift <10ms/24h
- **Firmware Maintenance**: ★ OTA update cho cả 3 board — không mở vỏ robot
- **Ground Loop/Brownout**: ★ Star Grounding topology — GND riêng biệt motor/logic
- **Heartbeat False Positive**: ★ Core Pinning — WiFi stack không ảnh hưởng CAN/Heartbeat

### Budget Risks
- **Price Increases**: Buy in bulk when possible
- **Component Failure**: Buy spares (10% extra)
- **Shipping Delays**: Order early, use local suppliers

### Timeline Risks
- **3D Printing Failures**: Test print before full batch
- **PCB Errors**: Order prototype first
- **Firmware Delays**: Use existing libraries
- **Integration Issues**: Test incrementally

## Success Criteria

### Functional
- All sensors reading accurately
- Motors responding to commands
- Voice commands executing correctly
- Healthcare workflow operational
- Battery life >2 hours
- **★ Dead Man's Switch E-Stop <500ms on communication loss**
- **★ ROS2 TF tree: zero time-travel errors over 24h**
- **★ OTA firmware update: cả 3 board không cần mở vỏ**
- **★ Zero brownout reset dưới full motor load**

### Performance
- Sensor latency <100ms
- CAN latency <1ms
- CAN Heartbeat jitter **<1ms** (Core Pinning, giảm từ <5ms)
- Command response <500ms
- Navigation accuracy >90%
- Fall detection >95% accuracy
- Uptime >99%
- C3 SRAM usage <200KB
- I2C bus capacitance <400pF
- Joint deflection <2mm under 5kg load
- **★ SNTP drift <10ms/24h**
- **★ E-Stop recovery time = 300ms (3 heartbeat frames)**
- **★ OTA flash time: S3 <30s (WiFi), C3 <60s (CAN)**
- **★ S3 VIN voltage drop <0.3V under full motor stall (Star Ground)**

### Budget
- Total cost <1.4M VND (giảm từ 1.6M)
- No component >150k VND (except bulk)
- PCB fabrication <50k VND total
- 3D printing <500k VND total
- Safety features: 0 VND thêm (pure firmware)
- Bearings included in budget
