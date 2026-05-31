# [STATUS: DONE] ĐỊNH NGHĨA CẤU TRÚC DỮ LIỆU DÙNG CHUNG (SHARED DTOs)
**Phiên bản:** 1.0 | **Ký duyệt:** HK.Huang07 Autonomous Engine

---

## I. CẤU TRÚC PHẢN HỒI API CHUẨN (API RESPONSE WRAPPER)

### Java DTO — `ApiResponse<T>`
```java
@Data
@Builder
public class ApiResponse<T> {
    private boolean success;
    private String message;
    private T data;
    private String timestamp;  // ISO-8601
    private String traceId;    // UUID cho debug
}
```

### TypeScript Interface
```typescript
interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
  timestamp: string;
  traceId: string;
}
```

---

## II. PHÂN HỆ USER (OPERATOR/OWNER)

### Java DTO — `UserDto`
```java
@Data
public class UserDto {
    private UUID id;
    private String displayName;
    private String email;
    private UserRole role;          // OWNER | OPERATOR | EMERGENCY_CONTACT
    private WristbandConfigDto wristbandConfig;
    private LocalDateTime createdAt;
    private LocalDateTime lastSeenAt;
}
```

### Java DTO — `WristbandConfigDto`
```java
@Data
public class WristbandConfigDto {
    private String deviceId;        // MAC address hoặc BLE UUID của vòng tay
    private String mqttTopic;       // Topic MQTT nhận dữ liệu sinh tồn
    private int heartRateThresholdMin;  // Default: 50 BPM
    private int heartRateThresholdMax;  // Default: 120 BPM
    private float bloodPressureSystolicMax;  // Default: 140 mmHg
    private boolean strokeAlertEnabled;
}
```

---

## III. PHÂN HỆ SỨC KHỎE (VITAL SIGNS & HEALTH)

### Java DTO — `VitalSignDto` (Dữ liệu thô từ MQTT)
```java
@Data
public class VitalSignDto {
    private String deviceId;
    private int heartRate;          // BPM
    private float systolic;         // mmHg
    private float diastolic;        // mmHg
    private float bodyTemperature;  // Celsius
    private float spo2;             // %SpO2 (0-100)
    private long epochTimestampMs;  // Unix timestamp milliseconds
}
```

### Java DTO — `HealthRecordDto` (Sau khi lưu DB)
```java
@Data
public class HealthRecordDto {
    private UUID id;
    private UUID userId;
    private VitalSignDto vitals;
    private String agentAnalysis;   // Text output từ Medical Agent
    private AlertLevel alertLevel;  // NORMAL | WARNING | CRITICAL | STROKE
    private LocalDateTime recordedAt;
}
```

### TypeScript Interface
```typescript
interface VitalSign {
  deviceId: string;
  heartRate: number;
  systolic: number;
  diastolic: number;
  bodyTemperature: number;
  spo2: number;
  epochTimestampMs: number;
}

interface HealthRecord {
  id: string;
  userId: string;
  vitals: VitalSign;
  agentAnalysis: string;
  alertLevel: 'NORMAL' | 'WARNING' | 'CRITICAL' | 'STROKE';
  recordedAt: string;
}
```

---

## IV. PHÂN HỆ AGENT (AI EVENT LOG)

### Java DTO — `AgentEventDto`
```java
@Data
public class AgentEventDto {
    private UUID id;
    private AgentType agentType;    // EMPATHETIC | MEDICAL | SAFETY
    private String inputContext;    // Ngữ cảnh đầu vào kích hoạt Agent
    private String outputDecision;  // Quyết định / phản hồi
    private String llmProvider;     // GROQ | GEMINI | LOCAL
    private int latencyMs;          // Độ trễ phản hồi (ms)
    private LocalDateTime triggeredAt;
}
```

### TypeScript Interface
```typescript
interface AgentEvent {
  id: string;
  agentType: 'EMPATHETIC' | 'MEDICAL' | 'SAFETY';
  inputContext: string;
  outputDecision: string;
  llmProvider: 'GROQ' | 'GEMINI' | 'LOCAL';
  latencyMs: number;
  triggeredAt: string;
}
```

---

## V. PHÂN HỆ AN TOÀN (SAFETY & NAVIGATION)

### Java DTO — `SafetyAlertDto`
```java
@Data
public class SafetyAlertDto {
    private UUID id;
    private AlertLevel level;           // INFO | WARNING | CRITICAL
    private SafetyTrigger trigger;      // OBSTACLE | FALL_RISK | CLIFF | TRAFFIC | WEATHER
    private float distanceMeters;       // Khoảng cách đến vật cản (m)
    private float[] lidarScanSnapshot;  // Mảng 360 điểm LiDAR (radians, meters)
    private boolean subsumptionActivated; // true = đã ngắt di chuyển
    private long responseTimeMs;        // Phải < 5ms
    private LocalDateTime detectedAt;
}
```

---

## VI. PHÂN HỆ NETCODE (MOTION PREDICTION BUFFER)

### Java DTO — `MotionStateDto` (Client-Side Prediction)
```java
@Data
public class MotionStateDto {
    private UUID sessionId;
    private float[] ownerPosition;      // [x, y, z] meters
    private float[] ownerVelocity;      // [vx, vy, vz] m/s
    private float[] predictedPosition;  // Vị trí dự đoán 500ms tương lai
    private long serverTimestampMs;
    private int sequenceNumber;         // Để Reconciliation
}
```

### TypeScript Interface (60Hz Buffer Ring)
```typescript
interface MotionState {
  sessionId: string;
  ownerPosition: [number, number, number];
  ownerVelocity: [number, number, number];
  predictedPosition: [number, number, number];
  serverTimestampMs: number;
  sequenceNumber: number;
}

// Ring buffer 2 giây @ 60Hz = 120 frames tối đa
type LagCompensationBuffer = MotionState[];
```
