# [STATUS: DONE] ĐỊNH NGHĨA ENUMS HỆ THỐNG (SYSTEM ENUMS)
**Phiên bản:** 1.0 | **Ký duyệt:** HK.Huang07 Autonomous Engine

---

## Java Enums (`com.hk07.common.enums`)

```java
// Phân loại 3 Agent độc lập trong MiroFish Engine
public enum AgentType {
    EMPATHETIC,   // Cảm xúc - Phân tích giọng nói, biểu cảm khuôn mặt
    MEDICAL,      // Y tế - Phân tích sinh tồn, nhắc thuốc, cảnh báo đột quỵ
    SAFETY        // An toàn - Quét LiDAR, phát hiện vật cản (Tầng 0 - Tối thượng)
}

// Mức cảnh báo sức khỏe / an toàn
public enum AlertLevel {
    NORMAL,     // Tất cả chỉ số trong giới hạn an toàn
    INFO,       // Thông tin tham khảo (không hành động ngay)
    WARNING,    // Cần chú ý - thông báo cho chủ nhân
    CRITICAL,   // Nguy hiểm cao - kích hoạt giao thức khẩn
    STROKE      // Cực kỳ nguy hiểm - nghi ngờ đột quỵ / ngã
}

// Trạng thái vòng đời hệ thống
public enum SystemState {
    INITIALIZING,   // Khởi động các Node ROS 2
    ACTIVE,         // Hoạt động bình thường
    PATROL,         // Đang di chuyển tuần tra (Safety Agent dẫn đầu)
    SAFE_HOLD,      // Đang giữ vị trí - Safety Agent đã ngắt di chuyển
    EMERGENCY,      // Khẩn cấp - đang gọi liên hệ khẩn cấp
    MAINTENANCE,    // Đang bảo trì / cập nhật
    SHUTDOWN        // Đang tắt máy an toàn (Volatile RAM Wipe đang chạy)
}

// Loại cảm biến kích hoạt cảnh báo an toàn
public enum SensorType {
    LIDAR_360,      // Quét toàn cảnh 360°
    CAMERA_RGBD,    // Camera RGB-Depth (nhận dạng hố sâu, mép cầu thang)
    ULTRASONIC,     // Cảm biến siêu âm hỗ trợ góc mù
    IMU,            // Inertial Measurement Unit (phát hiện ngã)
    WRISTBAND_BLE   // Dữ liệu sinh tồn từ vòng tay Bluetooth
}

// Loại kích hoạt ngắt an toàn (Subsumption Trigger)
public enum SafetyTrigger {
    OBSTACLE,       // Vật cản chặn đường
    CLIFF,          // Phát hiện mép cao / hố sâu
    FALL_RISK,      // Chủ nhân có nguy cơ ngã
    TRAFFIC,        // Xe cộ đang tiếp cận nhanh
    WEATHER,        // Thời tiết xấu (mưa, sấm sét)
    LOW_BATTERY,    // Pin robot dưới 10%
    OWNER_EMERGENCY // Chủ nhân nhấn nút khẩn cấp
}

// Phân quyền người dùng
public enum UserRole {
    OWNER,              // Chủ nhân - toàn quyền
    OPERATOR,           // Vận hành viên - cấu hình robot
    EMERGENCY_CONTACT,  // Liên hệ khẩn cấp - chỉ nhận cảnh báo
    TECHNICIAN          // Kỹ thuật viên - bảo trì
}

// Nhà cung cấp AI
public enum LlmProvider {
    GROQ,    // groq.com - tốc độ 500-800 tokens/s, miễn phí
    GEMINI,  // Google Gemini Flash/Pro - miễn phí tier
    MOCK     // Mock response để test offline
}
```

## TypeScript Enums (Frontend)

```typescript
export enum AgentType {
  EMPATHETIC = 'EMPATHETIC',
  MEDICAL = 'MEDICAL',
  SAFETY = 'SAFETY'
}

export enum AlertLevel {
  NORMAL = 'NORMAL',
  INFO = 'INFO',
  WARNING = 'WARNING',
  CRITICAL = 'CRITICAL',
  STROKE = 'STROKE'
}

export enum SystemState {
  INITIALIZING = 'INITIALIZING',
  ACTIVE = 'ACTIVE',
  PATROL = 'PATROL',
  SAFE_HOLD = 'SAFE_HOLD',
  EMERGENCY = 'EMERGENCY',
  MAINTENANCE = 'MAINTENANCE',
  SHUTDOWN = 'SHUTDOWN'
}

export const ALERT_LEVEL_COLORS: Record<AlertLevel, string> = {
  [AlertLevel.NORMAL]: '#00FF66',   // Emerald Green
  [AlertLevel.INFO]: '#00D2FF',     // Electric Blue
  [AlertLevel.WARNING]: '#FF6600',  // Cyber Orange
  [AlertLevel.CRITICAL]: '#FF3333', // Crimson Red
  [AlertLevel.STROKE]: '#FF0000'    // Pure Red - cực nguy hiểm
};
```
