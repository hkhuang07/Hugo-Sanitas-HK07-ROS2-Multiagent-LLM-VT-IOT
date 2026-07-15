# HK-07 Comprehensive Hardware Design Specification

Kế hoạch chi tiết thiết kế toàn bộ hệ thống phần cứng robot HK-07 từ phần mềm, chuẩn bị mọi tài liệu kỹ thuật trước khi mua và lắp đặt phần cứng thực tế.

## 1. Kiến Trúc Hệ Thống Tổng Thể

### 1.1 Block Diagram Hệ Thống
```
┌─────────────────────────────────────────────────────────────────┐
│                    HK-07 ROBOT SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│  LỚP TÍNH TOÁN CAO (High-Level Computing)                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │  Raspberry Pi  │  │  ESP32-S3       │  │  STM32H7        │  │
│  │  4 (Main CPU)  │  │  (Sensor Hub)   │  │  (Motor Ctrl)   │  │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘  │
│           │                    │                    │           │
│           │ WiFi 6            │ CAN Bus            │ UART/SPI   │
│           ▼                    ▼                    ▼           │
├─────────────────────────────────────────────────────────────────┤
│  LỚP CẢM BIẾN (Sensor Layer)                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ MPU-6050 │ │MAX30102  │ │ BME280   │ │ HC-SR04  │          │
│  │ (IMU)    │ │(SpO2/HR) │ │(Env)     │ │(Ultrasonic)│         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ OV5640   │ │ RPLIDAR  │ │ Encoder  │ │ Current  │          │
│  │ (Camera) │ │(LiDAR)   │ │(Wheel)   │ │ Sensor   │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
├─────────────────────────────────────────────────────────────────┤
│  LỚP THAO TÁC (Actuator Layer)                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ DC Motor │ │ Servo    │ │ Air Pump │ │ Solenoid │          │
│  │ (2x)     │ │ (4x)     │ │ (Pneumatic)│ (Valves) │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
├─────────────────────────────────────────────────────────────────┤
│  LỚP NĂNG LƯỢNG (Power Layer)                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ 24V Li-ion│ │ BMS      │ │ DC-DC    │ │ LDO      │          │
│  │ Battery  │ │ (Protection)│ Converters│ Regulators│         │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Kiến Trúc Giao Tiếp
```
ROS2 Topics (Humble)
├── /telemetry/imu (sensor_msgs/Imu)
├── /telemetry/joint_states (sensor_msgs/JointState)
├── /vitals/wristband (custom message)
├── /sensors/environment/state (custom message)
├── /sensors/camera/raw (sensor_msgs/Image)
├── /sensors/camera/thermal_rppg (custom message)
├── /control/motion/emergency (geometry_msgs/Twist)
├── /control/motion/balance_cmd_vel (geometry_msgs/Twist)
├── /control/motion/nav_cmd_vel (geometry_msgs/Twist)
├── /robot/execute_action (custom service)
└── /hardware/status (custom message)

Communication Protocols
├── WiFi 6: Raspberry Pi ↔ Laptop/Cloud
├── CAN Bus: ESP32-S3 ↔ STM32H7 ↔ Motor Drivers
├── I2C: ESP32-S3 ↔ Sensors (IMU, SpO2, Env)
├── SPI: ESP32-S3 ↔ Camera Module
├── UART: STM32H7 ↔ Motor Encoders
└── PWM: STM32H7 ↔ Servos/Motor Drivers
```

## 2. Thiết Kế PCB Chi Tiết

### 2.1 PCB 1: ESP32-S3 Sensor Hub Board
**Chức năng**: Thu thập dữ liệu từ tất cả cảm biến và gửi qua CAN Bus

**Specs**:
- MCU: ESP32-S3-WROOM-1 (Dual-core 240MHz, WiFi/BLE)
- Power: 3.3V LDO từ 24V main bus
- Dimensions: 50mm x 70mm, 4-layer

**Components**:
```
Power Section:
├── Input: 24V DC from main power bus
├── DC-DC Converter: LM2596 (24V → 5V)
├── LDO Regulator: AMS1117-3.3 (5V → 3.3V)
├── Capacitors: 100µF, 10µF, 0.1µF filtering
└── LED: Power indicator (red/green)

MCU Section:
├── ESP32-S3-WROOM-1 module
├── Crystal: 40MHz (external)
├── Reset button + debouncing circuit
├── Boot mode selection (GPIO0, GPIO2)
└── USB-C programming port

Sensor Interfaces (I2C):
├── MPU-6050 (IMU): I2C address 0x68
│   ├── VCC: 3.3V, GND, SDA, SCL
│   └── Pull-up resistors: 4.7kΩ
├── MAX30102 (SpO2): I2C address 0x57
│   ├── VCC: 3.3V, GND, SDA, SCL, INT
│   └── Pull-up resistors: 4.7kΩ
├── BME280 (Environment): I2C address 0x76
│   ├── VCC: 3.3V, GND, SDA, SCL
│   └── Pull-up resistors: 4.7kΩ
└── I2C bus buffer: PCA9517 (if needed)

Sensor Interfaces (GPIO):
├── HC-SR04 (Ultrasonic):
│   ├── TRIG: GPIO5, ECHO: GPIO6
│   └── Level shifter: 5V ↔ 3.3V
└── Emergency button: GPIO0 (internal pull-up)

CAN Bus Interface:
├── CAN Controller: MCP2515 (SPI interface)
├── CAN Transceiver: TJA1050
├── Crystal: 8MHz for MCP2515
├── Termination resistor: 120Ω
└── Status LED: TX/RX indicators

Debug/Programming:
├── USB-C port for programming
├── UART0: TX/RX for serial monitor
└── SWD connector for JTAG debugging
```

**PCB Layout**:
- Layer 1: Signal traces (top)
- Layer 2: Ground plane
- Layer 3: Power plane (3.3V, 5V)
- Layer 4: Signal traces (bottom)
- Trace width: 0.2mm (signal), 0.5mm (power)
- Via size: 0.3mm
- Clearance: 0.15mm

### 2.2 PCB 2: STM32H7 Motor Controller Board
**Chức năng**: Điều khiển động cơ DC, servo, và hệ thống khí nén

**Specs**:
- MCU: STM32H743VIT6 (Cortex-M7, 480MHz)
- Power: 5V from main power bus
- Dimensions: 70mm x 100mm, 4-layer

**Components**:
```
Power Section:
├── Input: 24V DC from main power bus
├── DC-DC Converter: LM2596 (24V → 5V)
├── LDO Regulator: AMS1117-3.3 (5V → 3.3V)
├── Capacitors: 470µF, 100µF, 10µF filtering
└── LED: Power indicator + fault LED

MCU Section:
├── STM32H743VIT6 (LQFP100 package)
├── Crystal: 25MHz (HSE)
├── Crystal: 32.768kHz (LSE for RTC)
├── Reset button + debouncing
├── Boot mode selection (BOOT0, BOOT1)
└── USB-C programming port

Motor Driver Section (DC Motors):
├── Driver IC: TB6612FNG (2 channels)
├── Input: 24V motor power
├── Logic: 3.3V control signals
├── PWM frequency: 20kHz
├── Current sensing: ACS712 (5A range)
├── Thermal protection: NTC thermistor
└── Status LEDs: Motor direction indicators

Servo Controller Section:
├── Servo driver: PCA9685 (I2C, 16 channels)
├── External PWM: 50Hz for servos
├── Power: 5V servo power (separate from logic)
├── 4x Servo outputs (MG996R compatible)
└── Current monitoring per servo

Encoder Interface:
├── QuadrATURE decoder: Hardware timer inputs
├── 2x Encoder inputs (TIM2, TIM3)
├── Resolution: 12-bit (0-4095)
└── Index pulse detection

CAN Bus Interface:
├── CAN Controller: Built-in STM32 CAN
├── CAN Transceiver: TJA1050
├── Termination resistor: 120Ω
└── ESD protection: TVS diodes

Pneumatic Control:
├── Solenoid driver: ULN2003 (Darlington array)
├── Air pump control: MOSFET IRF540N
├── Flyback diodes for inductive loads
├── Pressure sensor: MPX5010DP (analog)
└── Status LEDs: Pump/valve indicators

Safety Circuits:
├── E-Stop input: Hardware interrupt
├── Watchdog timer: Independent IWDG
├── Overcurrent protection: Fast shutdown
└── Emergency brake: Hardware brake release
```

**PCB Layout**:
- Layer 1: High-current motor traces (top)
- Layer 2: Ground plane (split analog/digital)
- Layer 3: Power plane (24V, 5V, 3.3V)
- Layer 4: Signal traces (bottom)
- Trace width: 1.0mm (motor power), 0.3mm (signal)
- Via size: 0.4mm (power), 0.3mm (signal)
- Clearance: 0.2mm (power), 0.15mm (signal)

### 2.3 PCB 3: Power Management Board
**Chức năng**: Quản lý năng lượng, BMS, và phân phối điện

**Specs**:
- Input: 24V Li-ion battery pack
- Outputs: 24V (motors), 12V (pump), 5V (electronics), 3.3V (logic)
- Dimensions: 60mm x 80mm, 2-layer

**Components**:
```
Battery Interface:
├── Input: 6S Li-ion pack (22.2V nominal, 25.2V max)
├── BMS IC: BQ34Z100-G1 (fuel gauge)
├── Balance charger interface: 6-cell balance port
├── Main switch: High-current MOSFET switch
├── Precharge circuit: Soft-start for capacitors
└── Fuse: 30A main fuse

DC-DC Converters:
├── 24V → 12V: LM2596 (for air pump)
├── 24V → 5V: LM2596 (for electronics)
├── 5V → 3.3V: AMS1117-3.3 (for logic)
├── Filtering capacitors per output
└── Status LEDs per voltage rail

Protection Circuits:
├── Overvoltage protection: TVS diodes
├── Undervoltage lockout: Comparator circuit
├── Overcurrent protection: Polyfuse per rail
├── Reverse polarity protection: Schottky diode
└── ESD protection: TVS arrays

Monitoring:
├── Voltage sensing: Divider resistors
├── Current sensing: ACS758 (50A range)
├── Temperature sensing: NTC thermistor
└── I2C interface for monitoring data
```

## 3. Firmware Architecture

### 3.1 ESP32-S3 Firmware (C/C++)

**Framework**: ESP-IDF v5.0

**Architecture**:
```cpp
// Main Application Structure
├── main/
│   ├── main.cpp              // Entry point
│   ├── sensor_manager.cpp   // Sensor data acquisition
│   ├── can_interface.cpp    // CAN bus communication
│   ├── data_fusion.cpp       // Sensor fusion algorithms
│   └── wifi_manager.cpp      // WiFi configuration
├── components/
│   ├── sensors/
│   │   ├── mpu6050_driver.cpp    // IMU driver
│   │   ├── max30102_driver.cpp    // SpO2 driver
│   │   ├── bme280_driver.cpp      // Environment driver
│   │   └── ultrasonic_driver.cpp  // Distance sensor
│   ├── communication/
│   │   ├── can_protocol.cpp       // CAN message handling
│   │   └── mqtt_client.cpp        // MQTT fallback
│   └── algorithms/
│       ├── ekf_filter.cpp         // Extended Kalman Filter
│       └── calibration.cpp        // Sensor calibration
└── config/
    └── sdkconfig.defaults         // ESP-IDF configuration
```

**Key Functions**:
```cpp
// Sensor Manager
class SensorManager {
public:
    void init();                          // Initialize all sensors
    void readSensors();                   // Read all sensor data
    SensorData getFusedData();            // Return fused sensor data
    void calibrateSensors();              // Auto-calibration routine
    
private:
    MPU6050 imu;
    MAX30102 spo2;
    BME280 env;
    Ultrasonic us;
    EKFFilter ekf;
};

// CAN Interface
class CANInterface {
public:
    void init();                          // Initialize CAN bus
    void publishTelemetry(SensorData);    // Publish to CAN
    void subscribeCommands();             // Subscribe to commands
    void processMessage(CANMessage);      // Process incoming
    
private:
    MCP2515 canController;
    TJA1050 transceiver;
};

// Main Loop
void app_main() {
    SensorManager sensorMgr;
    CANInterface canIf;
    
    sensorMgr.init();
    canIf.init();
    
    while(1) {
        SensorData data = sensorMgr.readSensors();
        SensorData fused = sensorMgr.getFusedData();
        canIf.publishTelemetry(fused);
        vTaskDelay(pdMS_TO_TICKS(10)); // 100Hz
    }
}
```

**CAN Protocol Definition**:
```cpp
// CAN Message IDs (11-bit standard)
#define CAN_ID_IMU_DATA          0x100
#define CAN_ID_VITALS_DATA       0x101
#define CAN_ID_ENV_DATA          0x102
#define CAN_ID_ULTRASONIC_DATA    0x103
#define CAN_ID_SENSOR_STATUS     0x104
#define CAN_ID_MOTOR_COMMAND     0x200
#define CAN_ID_SERVO_COMMAND     0x201
#define CAN_ID_PNEUMATIC_CMD     0x202
#define CAN_ID_EMERGENCY_STOP    0x300

// Message Structures
struct IMUData {
    float accel_x, accel_y, accel_z;
    float gyro_x, gyro_y, gyro_z;
    float quaternion_w, quaternion_x, quaternion_y, quaternion_z;
    uint32_t timestamp;
};

struct VitalsData {
    uint16_t heart_rate;
    uint8_t spo2;
    float temperature;
    uint32_t timestamp;
};
```

### 3.2 STM32H7 Firmware (C/C++)

**Framework**: STM32CubeIDE + HAL Library

**Architecture**:
```c
// Project Structure
├── Core/
│   ├── Src/
│   │   ├── main.c              // Entry point
│   │   ├── motor_control.c     // Motor control algorithms
│   │   ├── servo_control.c     // Servo PWM generation
│   │   ├── can_handler.c       // CAN message handler
│   │   ├── encoder_reader.c    // Quadrature encoder
│   │   ├── pneumatic_ctrl.c    // Pneumatic system control
│   │   └── safety_monitor.c    // Safety watchdog
│   ├── Inc/
│   │   ├── main.h
│   │   ├── motor_control.h
│   │   └── ...
│   └── Drivers/
│       ├── STM32H7xx_HAL_Driver/
│       └── CMSIS/
├── Middlewares/
│   ├── PID/
│   │   └── pid_controller.c    // PID implementation
│   └── Trajectory/
│       └── trajectory_planner.c // Motion planning
└── USB/
    └── DFU/                    // Device Firmware Upgrade
```

**Key Functions**:
```c
// Motor Control
typedef struct {
    float target_velocity;
    float current_velocity;
    float integral_error;
    float last_error;
    PID pid;
} MotorController;

void MotorControl_Init(MotorController* ctrl);
void MotorControl_SetVelocity(MotorController* ctrl, float vel);
void MotorControl_Update(MotorController* ctrl, float dt);
void MotorControl_EmergencyStop(void);

// Servo Control
void Servo_Init(uint8_t channel);
void Servo_SetPosition(uint8_t channel, float angle_rad);
void Servo_UpdateAll(void);

// CAN Handler
void CAN_Init(void);
void CAN_TransmitMessage(uint32_t id, uint8_t* data, uint8_t len);
void CAN_ReceiveCallback(CAN_RxHeaderTypeDef* header, uint8_t* data);

// Main Loop
while(1) {
    // Read CAN messages
    CAN_ProcessMessages();
    
    // Update motor control (50Hz)
    MotorControl_Update(&left_motor, 0.02f);
    MotorControl_Update(&right_motor, 0.02f);
    
    // Update servos (50Hz)
    Servo_UpdateAll();
    
    // Monitor safety
    Safety_Check();
    
    HAL_Delay(20); // 50Hz loop
}
```

**PID Controller**:
```c
typedef struct {
    float Kp;
    float Ki;
    float Kd;
    float integral;
    float last_error;
    float output_min;
    float output_max;
} PID;

float PID_Update(PID* pid, float setpoint, float measurement, float dt) {
    float error = setpoint - measurement;
    pid->integral += error * dt;
    
    // Anti-windup
    if(pid->integral > pid->output_max) pid->integral = pid->output_max;
    if(pid->integral < pid->output_min) pid->integral = pid->output_min;
    
    float derivative = (error - pid->last_error) / dt;
    pid->last_error = error;
    
    float output = pid->Kp * error + pid->Ki * pid->integral + pid->Kd * derivative;
    
    // Clamp output
    if(output > pid->output_max) output = pid->output_max;
    if(output < pid->output_min) output = pid->output_min;
    
    return output;
}
```

### 3.3 ROS2 Integration (Python)

**Package Structure**:
```
hk07_hardware_interface/
├── hk07_hardware_interface/
│   ├── __init__.py
│   ├── esp32_bridge_node.py      # ESP32 communication
│   ├── stm32_bridge_node.py      # STM32 communication
│   ├── sensor_hardware_node.py   # Hardware sensor publisher
│   ├── motor_hardware_node.py    # Motor control interface
│   └── hardware_manager.py       # Hardware status monitor
├── launch/
│   ├── hardware_bringup.launch   # Launch all hardware nodes
│   └── hardware_test.launch      # Testing launch file
├── config/
│   ├── hardware_params.yaml      # Hardware parameters
│   └── calibration_params.yaml   # Sensor calibration
├── srv/
│   ├── ExecuteAction.srv          # Action execution service
│   └── CalibrateSensors.srv      # Calibration service
├── msg/
│   ├── HardwareStatus.msg        # Hardware status message
│   └── SensorRaw.msg             # Raw sensor data
└── package.xml
```

**ESP32 Bridge Node**:
```python
#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from hk07_hardware_interface.msg import HardwareStatus, SensorRaw
import serial
import can

class ESP32BridgeNode(Node):
    def __init__(self):
        super().__init__('esp32_bridge_node')
        
        # Publishers
        self.imu_pub = self.create_publisher(Imu, '/telemetry/imu', 10)
        self.vitals_pub = self.create_publisher(SensorRaw, '/vitals/wristband', 10)
        self.env_pub = self.create_publisher(SensorRaw, '/sensors/environment/state', 10)
        self.status_pub = self.create_publisher(HardwareStatus, '/hardware/status', 10)
        
        # CAN Bus Interface
        self.can_bus = can.interface.Bus(channel='can0', bustype='socketcan')
        
        # Timer for reading CAN bus (100Hz)
        self.timer = self.create_timer(0.01, self.read_can_bus)
        
        self.get_logger().info('ESP32 Bridge Node Initialized')
    
    def read_can_bus(self):
        try:
            message = self.can_bus.recv(timeout=0.01)
            
            if message.arbitration_id == 0x100:  # IMU Data
                self.process_imu_data(message.data)
            elif message.arbitration_id == 0x101:  # Vitals Data
                self.process_vitals_data(message.data)
            elif message.arbitration_id == 0x102:  # Environment Data
                self.process_env_data(message.data)
                
        except can.CanError:
            pass
    
    def process_imu_data(self, data):
        # Parse CAN data and publish to ROS2
        msg = Imu()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'imu_link'
        
        # Parse binary data (example format)
        import struct
        accel = struct.unpack('fff', data[0:12])
        gyro = struct.unpack('fff', data[12:24])
        quat = struct.unpack('ffff', data[24:40])
        
        msg.linear_acceleration.x = accel[0]
        msg.linear_acceleration.y = accel[1]
        msg.linear_acceleration.z = accel[2]
        msg.angular_velocity.x = gyro[0]
        msg.angular_velocity.y = gyro[1]
        msg.angular_velocity.z = gyro[2]
        msg.orientation.w = quat[0]
        msg.orientation.x = quat[1]
        msg.orientation.y = quat[2]
        msg.orientation.z = quat[3]
        
        self.imu_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = ESP32BridgeNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
```

## 4. Thiết Kế Cơ Khí 3D

### 4.1 Các Bộ Phận Cần Thiết Kế

**A. Cơ sở di động (Mobile Base)**
```
Base Chassis:
├── Material: PETG (độ bền cao, chịu lực tốt)
├── Dimensions: 400mm x 300mm x 150mm
├── Wall thickness: 3mm
├── Features:
│   ├── Motor mounting brackets (2x)
│   ├── Wheel wells (2x)
│   ├── Battery compartment
│   ├── PCB mounting slots
│   └── Cable management channels
└── CAD Software: Fusion 360

Wheels:
├── Type: Mecanum wheels (đa hướng)
├── Diameter: 100mm
├── Material: TPU (linh hoạt, bám sàn tốt)
└── 3D Printing: TPU 95A
```

**B. Khung Robot (Robot Frame)**
```
Main Frame:
├── Material: PETG + Aluminum reinforcement
├── Height: 800mm (tổng thể)
├── Structure: Tubular frame with 3D printed joints
├── Sections:
│   ├── Base section (motor compartment)
│   ├── Mid section (battery + PCBs)
│   ├── Upper section (sensors + camera)
│   └── Head section (display + speakers)
└── Assembly: Bolt-together design

Internal Structure:
├── PCB mounting plates (removable)
├── Cable routing channels
├── Ventilation holes
└── Access panels for maintenance
```

**C. Cánh Tay (Arms)**
```
Arm Structure:
├── DOF: 2 per arm (shoulder, elbow)
├── Length: Upper arm 350mm, forearm 300mm
├── Material: PETG for structure, TPU for joints
├── Actuation: MG996R servos
├── Features:
│   ├── Servo mounting brackets
│   ├── Cable routing inside arm
│   ├── End effector mount (gripper/sprayer)
│   └── Mechanical stops for safety
└── CAD: Fusion 360 + 3D printing

Gripper/Sprayer:
├── Material: PETG
├── Mount: Standard servo horn interface
├── Features:
│   ├── 2-finger gripper (cầm nắm)
│   ├── Spray nozzle mount (phun thuốc)
│   └── Quick-change mechanism
```

**D. Đầu Robot (Robot Head)**
```
Head Assembly:
├── Material: PETG (white, smooth finish)
├── Dimensions: 200mm x 180mm x 150mm
├── Features:
│   ├── Camera mount (OV5640)
│   ├── Speaker array (2x 40mm speakers)
│   ├── Microphone array (4x microphones)
│   ├── LED indicators (eyes)
│   └── Display mount (optional OLED)
└── Design: Baymax-inspired friendly appearance

Neck Mechanism:
├── DOF: 2 (pan, tilt)
├── Actuation: 2x SG90 micro servos
├── Range: ±45° pan, ±30° tilt
└── Smooth motion profile
```

**E. Hệ Thống Khí Nén (Pneumatic System)**
```
Air Reservoir:
├── Material: PETG (thick wall 5mm)
├── Volume: 2 liters
├── Pressure rating: 2 PSI max
├── Features:
│   ├── Air pump mount
│   ├── Pressure sensor port
│   ├── Solenoid valve mounts
│   └── Safety relief valve
└── Design: Cylindrical tank

Soft Suit:
├── Material: TPU (flexible, airtight)
├── Design: Inflatable chambers
├── Features:
│   ├── Multiple inflation zones
│   ├── Quick deflation (E-stop)
│   └── Pressure monitoring
└── Manufacturing: Heat-sealed TPU sheets
```

### 4.2 Bố Trí Nội Thất

```
┌─────────────────────────────────────────┐
│              HEAD (Camera/Speakers)      │
├─────────────────────────────────────────┤
│         UPPER SECTION (Sensors)          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │ Camera  │ │ LiDAR   │ │ Sensors │    │
│  └─────────┘ └─────────┘ └─────────┘    │
├─────────────────────────────────────────┤
│        MID SECTION (Electronics)         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │ RPi 4   │ │ ESP32   │ │ STM32   │    │
│  └─────────┘ └─────────┘ └─────────┘    │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │ PCB 1   │ │ PCB 2   │ │ PCB 3   │    │
│  └─────────┘ └─────────┘ └─────────┘    │
├─────────────────────────────────────────┤
│        LOWER SECTION (Power/Arms)        │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │ Battery │ │ Air     │ │ Servos  │    │
│  │ Pack    │ │ Pump    │ │ (4x)    │    │
│  └─────────┘ └─────────┘ └─────────┘    │
├─────────────────────────────────────────┤
│           BASE (Motors/Wheels)           │
│  ┌─────────┐              ┌─────────┐    │
│  │ Motor L │              │ Motor R │    │
│  └─────────┘              └─────────┘    │
└─────────────────────────────────────────┘
```

## 5. Sơ Đồ Triển Khai Lắp Đặt

### 5.1 Quy Trình Lắp Đặt

**Giai đoạn 1: Chuẩn bị (Pre-assembly)**
```
1. Kiểm tra linh kiện
   ├── Kiểm tra tất cả PCB components
   ├── Test MCU chips (ESP32, STM32)
   ├── Verify sensor functionality
   └── Check mechanical parts dimensions

2. Nạp Firmware
   ├── Flash ESP32 firmware via USB-C
   ├── Flash STM32 firmware via ST-Link
   ├── Verify CAN communication
   └── Test sensor readings

3. Calibrate Sensors
   ├── IMU zero calibration
   ├── SpO2 sensor calibration
   ├── Environmental sensor baseline
   └── Ultrasonic sensor testing
```

**Giai đoạn 2: Lắp Đặt Điện Tử (Electronics Assembly)**
```
1. Power System Assembly
   ├── Solder power management board
   ├── Connect battery pack
   ├── Test voltage outputs
   └── Verify protection circuits

2. Sensor Hub Assembly
   ├── Solder ESP32 sensor board
   ├── Mount sensors (IMU, SpO2, Env, Ultrasonic)
   ├── Connect I2C bus
   ├── Test sensor communication
   └── Verify CAN bus interface

3. Motor Controller Assembly
   ├── Solder STM32 motor board
   ├── Mount motor drivers
   ├── Connect servo headers
   ├── Wire encoder inputs
   └── Test motor control

4. Integration Testing
   ├── Connect all boards via CAN bus
   ├── Power up system
   ├── Verify communication
   └── Test safety systems
```

**Giai đoạn 3: Lắp Đặt Cơ Khí (Mechanical Assembly)**
```
1. Base Assembly
   ├── Assemble chassis frame
   ├── Mount motors
   ├── Install wheels
   ├── Add battery compartment
   └── Install power management board

2. Frame Assembly
   ├── Build vertical frame
   ├── Install mid section
   ├── Add mounting plates
   ├── Route cables
   └── Install electronics

3. Arm Assembly
   ├── Assemble arm segments
   ├── Mount servos
   ├── Install end effectors
   ├── Route servo cables
   └── Test range of motion

4. Head Assembly
   ├── Assemble head structure
   ├── Mount camera
   ├── Install speakers
   ├── Add microphones
   └── Connect to main frame

5. Pneumatic System
   ├── Install air reservoir
   ├── Mount air pump
   ├── Connect solenoid valves
   ├── Install soft suit
   └── Test inflation/deflation
```

**Giai đoạn 4: Tích Hợp Hệ Thống (System Integration)**
```
1. Software Integration
   ├── Install ROS2 on Raspberry Pi
   ├── Deploy hardware interface nodes
   ├── Configure CAN bus
   ├── Start sensor publishers
   └── Test motor control

2. Calibration
   ├── Calibrate IMU orientation
   ├── Tune PID controllers
   ├── Calibrate servo limits
   ├── Test sensor fusion
   └── Verify safety systems

3. Testing
   ├── Unit testing per subsystem
   ├── Integration testing
   ├── Safety system testing
   ├── Performance testing
   └── Field testing
```

### 5.2 Sơ Đố Kết Nối Dây (Wiring Diagram)

```
Power Distribution:
┌─────────────┐
│ 24V Battery │
└──────┬──────┘
       │
       ├──[30A Fuse]──┬──→ Power Management Board
       │              │
       │              ├──→ 24V (Motors)
       │              ├──→ 12V (Air Pump)
       │              ├──→ 5V (Electronics)
       │              └──→ 3.3V (Logic)
       │
       └──→ BMS Monitoring

CAN Bus Network:
┌──────────┐     CAN Bus     ┌──────────┐
│ ESP32-S3 │◄───────────────►│ STM32H7  │
│ Sensor   │   (120Ω term)   │ Motor    │
│   Hub    │                 │ Control  │
└──────────┘                 └──────────┘
       │                           │
       └──→ [Optional] ←───────────┘
              Raspberry Pi
              (via USB-CAN)

Sensor Connections (I2C):
ESP32-S3 Sensor Hub
├── I2C Bus (SDA/SCL)
│   ├── MPU-6050 (0x68)
│   ├── MAX30102 (0x57)
│   └── BME280 (0x76)
├── GPIO
│   ├── HC-SR04 (TRIG/ECHO)
│   └── Emergency Button
└── SPI
    └── OV5640 Camera

Motor Connections:
STM32H7 Motor Controller
├── Motor Drivers (TB6612FNG)
│   ├── Left Motor (PWM1/DIR1)
│   └── Right Motor (PWM2/DIR2)
├── Servo Controller (PCA9685)
│   ├── Left Shoulder
│   ├── Left Elbow
│   ├── Right Shoulder
│   └── Right Elbow
├── Encoders
│   ├── Left Encoder (TIM2)
│   └── Right Encoder (TIM3)
└── Pneumatic
    ├── Air Pump (MOSFET)
    └── Solenoid Valves (ULN2003)
```

## 6. Kế Hoạch Triển Khai Chi Tiết

### 6.1 Giai Đoạn 1: Thiết Kế & Chuẩn Bị (Tuần 1-4)

**Tuần 1: Thiết kế PCB**
- Hoàn thành schematic cho 3 PCB
- Tạo PCB layout trong KiCad
- Export Gerber files cho sản xuất
- Tạo BOM (Bill of Materials)

**Tuần 2: Thiết kế cơ khí 3D**
- Thiết kế base chassis trong Fusion 360
- Thiết kế frame structure
- Thiết kế arm mechanisms
- Thiết kế head assembly

**Tuần 3: Phát triển Firmware**
- Viết ESP32 firmware (sensor hub)
- Viết STM32 firmware (motor control)
- Implement CAN protocol
- Test firmware trên dev boards

**Tuần 4: ROS2 Integration**
- Tạo hardware interface package
- Implement bridge nodes
- Test communication
- Document APIs

### 6.2 Giai Đoạn 2: Mua Linh Kiện & Sản Xuất (Tuần 5-8)

**Tuần 5: Đặt hàng linh kiện**
- Order PCB fabrication
- Order electronic components
- Order 3D printing materials
- Order motors/servos/sensors

**Tuần 6-7: Sản xuất & Lắp ráp**
- Nhận PCB và components
- Solder PCB assembly
- In 3D mechanical parts
- Assemble mechanical structure

**Tuần 8: Testing ban đầu**
- Power up testing
- Sensor functionality
- Motor control testing
- Communication verification

### 6.3 Giai Đoạn 3: Tích Hợp & Calibration (Tuần 9-12)

**Tuần 9: System Integration**
- Install ROS2 on Raspberry Pi
- Deploy all software
- Connect all subsystems
- Initial system testing

**Tuần 10: Calibration**
- Sensor calibration
- PID tuning
- Servo limit calibration
- Safety system testing

**Tuần 11: Comprehensive Testing**
- Unit testing
- Integration testing
- Performance testing
- Safety validation

**Tuần 12: Documentation & Deployment**
- Complete documentation
- User manual
- Maintenance guide
- Final deployment

## 7. Danh Sách Linh Kiện Chi Tiết (BOM)

### 7.1 Linh Kiện Điện Tử

**MCU & Processors**:
- ESP32-S3-WROOM-1 x1
- STM32H743VIT6 x1
- Raspberry Pi 4 (4GB) x1

**Sensors**:
- MPU-6050 (IMU 6-DOF) x1
- MAX30102 (SpO2/Heart Rate) x1
- BME280 (Temperature/Pressure/Humidity) x1
- HC-SR04 (Ultrasonic) x2
- OV5640 (Camera Module) x1
- RPLIDAR A1 (LiDAR) x1
- ACS712 (Current Sensor 5A) x2
- ACS758 (Current Sensor 50A) x1
- MPX5010DP (Pressure Sensor) x1

**Power Management**:
- LM2596 (DC-DC Converter) x3
- AMS1117-3.3 (LDO Regulator) x2
- BQ34Z100-G1 (Battery Fuel Gauge) x1
- TJA1050 (CAN Transceiver) x2
- MCP2515 (CAN Controller) x1

**Motor Control**:
- TB6612FNG (Motor Driver) x1
- PCA9685 (16-Channel PWM/Servo) x1
- ULN2003 (Darlington Array) x1
- IRF540N (MOSFET) x1

**Motors & Actuators**:
- DC Motor 12V with Encoder x2
- MG996R Servo x4
- SG90 Micro Servo x2
- Air Pump 12V x1
- Solenoid Valve 12V x2

**Passive Components**:
- Capacitors (various values)
- Resistors (various values)
- Inductors (for DC-DC)
- Crystals (40MHz, 25MHz, 8MHz, 32.768kHz)
- LEDs (various colors)

**Connectors & Hardware**:
- USB-C connectors x3
- Terminal blocks (various)
- Headers (pin headers, female headers)
- Screw terminals
- Standoffs & spacers
- Nuts & bolts (M3, M4)

### 7.2 Linh Kiện Cơ Khí

**3D Printing Materials**:
- PETG filament (white, black) - 2kg
- TPU filament (95A) - 1kg
- PLA filament (for prototypes) - 500g

**Mechanical Hardware**:
- Aluminum extrusion (2020 profile) - 2m
- Ball bearings (various sizes) - 10pcs
- Shafts (8mm, 6mm) - 0.5m
- Belts & pulleys (if needed)
- Springs (for pneumatic system)

**Fasteners**:
- M3 bolts & nuts - 50pcs
- M4 bolts & nuts - 30pcs
- M5 bolts & nuts - 20pcs
- Washers (various) - 100pcs
- Threaded inserts - 20pcs

### 7.3 Power System

**Battery**:
- 6S Li-ion Battery Pack (22.2V, 10Ah) x1
- Li-ion cells 18650 (3.7V, 3000mAh) x20
- Balance charger (6S) x1

**Cables & Wiring**:
- Silicone wire (various gauges) - 10m
- Shielded cable (for sensors) - 5m
- CAN bus cable (twisted pair) - 3m
- Jumper wires (M-M, M-F, F-F) - 100pcs
- Heat shrink tubing - various sizes

## 8. Tài Liệu Kỹ Thuật

### 8.1 Tài Liệu Cần Tạo

**Schematics & PCB**:
- ESP32 Sensor Board Schematic (.sch)
- STM32 Motor Board Schematic (.sch)
- Power Management Board Schematic (.sch)
- PCB Layout Files (.pcb)
- Gerber Files (.ger)
- BOM (Bill of Materials)

**Mechanical Design**:
- 3D CAD Files (.step, .stp)
- Assembly Drawings (.pdf)
- Part Drawings (.pdf)
- Bill of Materials (mechanical)
- 3D Printing Instructions (.pdf)

**Software**:
- Source Code (C/C++, Python)
- Build Instructions
- API Documentation
- Configuration Files
- Test Scripts

**Integration**:
- Wiring Diagrams (.pdf)
- Pinout Diagrams (.pdf)
- Assembly Instructions (.pdf)
- Calibration Procedures (.pdf)
- Troubleshooting Guide (.pdf)

### 8.2 Cấu Trúc Thư Mục Tài Liệu

```
hk07-hardware-documentation/
├── 01-electrical/
│   ├── schematics/
│   ├── pcb-layouts/
│   ├── gerber-files/
│   └── bom-electrical.xlsx
├── 02-mechanical/
│   ├── cad-files/
│   ├── assembly-drawings/
│   ├── 3d-printing/
│   └── bom-mechanical.xlsx
├── 03-software/
│   ├── firmware/
│   │   ├── esp32-firmware/
│   │   └── stm32-firmware/
│   ├── ros2-nodes/
│   ├── api-docs/
│   └── build-instructions/
├── 04-integration/
│   ├── wiring-diagrams/
│   ├── pinout-diagrams/
│   ├── assembly-guide/
│   ├── calibration/
│   └── troubleshooting/
└── 05-testing/
    ├── test-procedures/
    ├── test-results/
    └── validation-reports/
```

## 9. Chi Phí Ước Tính

### 9.1 Chi Phí Linh Kiện

**Điện tử**: ~$300-400
- MCU & Processors: $80
- Sensors: $100
- Power Management: $50
- Motor Control: $40
- Motors & Actuators: $80
- Passive Components: $30
- PCB Fabrication: $20

**Cơ khí**: ~$200-300
- 3D Printing Materials: $80
- Mechanical Hardware: $100
- Fasteners: $40
- Assembly Hardware: $30

**Năng lượng**: ~$150-200
- Battery Pack: $120
- Charger: $30
- Cables & Wiring: $30

**Tổng cộng**: ~$650-900

### 9.2 Chi Phí Dụng Cụ

**Soldering**: ~$100
- Soldering Iron: $40
- Solder Wire: $20
- Flux: $10
- Helping Hands: $20
- Multimeter: $10

**Testing**: ~$150
- Logic Analyzer: $50
- Oscilloscope: $80
- CAN Analyzer: $20

**3D Printing**: ~$300-500
- 3D Printer (nếu chưa có): $300-500
- Filament: đã tính ở trên

**Tổng cộng dụng cụ**: ~$550-750

## 10. Kết Luận

Kế hoạch này cung cấp thiết kế chi tiết và toàn diện cho việc chuyển đổi HK-07 từ phần mềm sang phần cứng thực tế. Tất cả các khía cạnh kỹ thuật đã được xem xét:

1. **Kiến trúc hệ thống**: Rõ ràng, phân tầng, dễ mở rộng
2. **Thiết kế PCB**: Chi tiết, sẵn sàng sản xuất
3. **Firmware**: Cấu trúc tốt, dễ bảo trì
4. **Thiết kế cơ khí**: Thực tế, có thể in 3D
5. **Quy trình lắp đặt**: Bước-by-bstep, dễ theo dõi
6. **Tài liệu**: Đầy đủ, chuẩn bị sẵn sàng

Với kế hoạch này, bạn có thể chuẩn bị mọi thứ từ phần mềm trước khi mua phần cứng, đảm bảo quá trình triển khai suôn sẻ và hiệu quả.
