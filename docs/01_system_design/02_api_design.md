# [STATUS: DONE] THIẾT KẾ API & MQTT TOPOLOGY
**Phiên bản:** 1.0 | **Ký duyệt:** HK.Huang07 Autonomous Engine

---

## I. REST API ENDPOINTS (Spring Boot — Port 8888)

**Base URL:** `http://localhost:8888/api/v1`

### 🔐 Auth Module
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/auth/login` | Đăng nhập, trả JWT |
| POST | `/auth/refresh` | Làm mới Access Token |
| POST | `/auth/logout` | Hủy Refresh Token |

### 👤 User Module
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/users/me` | Lấy profile bản thân |
| PUT | `/users/me` | Cập nhật profile |
| PUT | `/users/me/wristband` | Cập nhật cấu hình vòng tay |
| GET | `/users/{id}` | Lấy profile user (OPERATOR+) |

### 💓 Health Module
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/health/vitals/latest` | Chỉ số sinh tồn mới nhất của owner |
| GET | `/health/records` | Lịch sử sức khỏe (phân trang) |
| GET | `/health/records/{id}` | Chi tiết bản ghi sức khỏe |
| GET | `/health/alerts/active` | Danh sách cảnh báo đang kích hoạt |

### 🤖 Agent Module
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/agents/logs` | Nhật ký quyết định 3 Agent |
| POST | `/agents/empathetic/interact` | Gửi câu thoại, nhận phản hồi cảm xúc |
| GET | `/agents/status` | Trạng thái 3 Agent (ACTIVE/IDLE) |

### 🛡️ Safety Module
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/safety/alerts` | Lịch sử cảnh báo an toàn |
| GET | `/safety/subsumption/status` | Trạng thái Subsumption override hiện tại |
| GET | `/safety/lidar/snapshot` | Dữ liệu LiDAR 360° gần nhất |

### 🕹️ Robot Control Module
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/robot/state` | Trạng thái hệ thống (SystemState enum) |
| POST | `/robot/command/hold` | Dừng khẩn cấp (OPERATOR+) |
| POST | `/robot/command/resume` | Tiếp tục di chuyển (OPERATOR+) |
| POST | `/robot/command/shutdown` | Tắt robot an toàn (OWNER only) |

---

## II. WEBSOCKET ENDPOINTS (Real-time)

**Base URL:** `ws://localhost:8888/ws`

| Topic | Direction | Tần suất | Dữ liệu |
|-------|-----------|---------|---------|
| `/topic/vitals` | Server→Client | 60Hz (16ms) | `VitalSignDto` |
| `/topic/agent-events` | Server→Client | Event-driven | `AgentEventDto` |
| `/topic/safety-alerts` | Server→Client | Event-driven | `SafetyAlertDto` |
| `/topic/motion-state` | Server→Client | 60Hz | `MotionStateDto` |
| `/topic/system-state` | Server→Client | On-change | `SystemState` |
| `/app/interact` | Client→Server | On-demand | `{ message: string }` |

---

## III. MQTT TOPIC TOPOLOGY (Mosquitto — Port 1883)

```
hk07/
├── sensors/
│   ├── wristband/{deviceId}/vitals      <- RAW vital signs từ vòng tay BLE
│   ├── lidar/scan                        <- ROS 2 LaserScan data (JSON encoded)
│   ├── camera/depth/obstacles            <- Detected obstacle list
│   └── imu/state                         <- Acceleration, gyro, fall detection
├── agents/
│   ├── empathetic/output                 <- Kết quả phân tích cảm xúc
│   ├── medical/output                    <- Kết quả phân tích y tế
│   └── safety/output                     <- Kết quả phân tích an toàn + Subsumption signal
├── arbitrator/
│   └── decision                          <- Quyết định điều phối tổng hợp từ 3 Agent
├── control/
│   ├── motion/command                    <- Lệnh điều khiển bánh xe (vel.linear, vel.angular)
│   └── subsumption/inhibit               <- Tín hiệu ngắt khẩn cấp (payload: AgentType)
└── system/
    ├── state                             <- Trạng thái tổng thể (SystemState)
    └── heartbeat                         <- Ping/pong giám sát uptime (1Hz)
```

**QoS Policy:**
- `hk07/control/subsumption/inhibit`: QoS 2 (Exactly Once) — Tín hiệu an toàn tối thượng
- `hk07/sensors/wristband/*/vitals`: QoS 0 (At Most Once) — Dữ liệu liên tục, chấp nhận mất gói lẻ
- `hk07/agents/*/output`: QoS 1 (At Least Once) — Đảm bảo quyết định Agent được nhận

---

## IV. GIỚI HẠN TÀI NGUYÊN ĐÃ TÍCH HỢP

```yaml
# Mosquitto config (docker/mosquitto.conf)
max_queued_messages 100        # Tránh RAM bị ăn mòn
max_packet_size 65536          # 64KB max payload
log_type error                 # Chỉ log lỗi, không log tất cả
```
