/*
 * HK-07 CAN Interface Header
 * Manages CAN bus communication for sensor data and motor commands
 */

#ifndef CAN_INTERFACE_H
#define CAN_INTERFACE_H

#include "esp_err.h"
#include <stdint.h>

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

// Message structures
struct IMUData {
    float accel_x, accel_y, accel_z;
    float gyro_x, gyro_y, gyro_z;
    float quaternion_w, quaternion_x, quaternion_y, quaternion_z;
    uint32_t timestamp;
} __attribute__((packed));

struct VitalsData {
    uint16_t heart_rate;
    uint8_t spo2;
    float temperature;
    uint32_t timestamp;
} __attribute__((packed));

struct EnvData {
    float temperature;
    float pressure;
    float humidity;
    uint32_t timestamp;
} __attribute__((packed));

struct UltrasonicData {
    float distance_cm;
    uint32_t timestamp;
} __attribute__((packed));

struct MotorCommand {
    float left_velocity;
    float right_velocity;
    uint8_t action_code; // 0=idle, 1=grasp, 2=spray, 3=hug
    uint32_t timestamp;
} __attribute__((packed));

class CANInterface {
public:
    CANInterface();
    ~CANInterface();
    
    // Initialize CAN bus
    esp_err_t init();
    
    // Publish sensor telemetry
    esp_err_t publishTelemetry(const SensorData& data);
    
    // Subscribe to and process incoming commands
    void processMessages();
    
    // Send emergency stop
    esp_err_t sendEmergencyStop();
    
private:
    // CAN interface handle
    void* can_handle;
    
    // Message publishing functions
    esp_err_t publishIMU(const SensorData& data);
    esp_err_t publishVitals(const SensorData& data);
    esp_err_t publishEnvironment(const SensorData& data);
    esp_err_t publishUltrasonic(const SensorData& data);
    esp_err_t publishStatus(uint8_t status);
    
    // Message receiving
    void receiveMotorCommand(const uint8_t* data, uint8_t len);
    void receiveServoCommand(const uint8_t* data, uint8_t len);
    void receivePneumaticCommand(const uint8_t* data, uint8_t len);
};

#endif // CAN_INTERFACE_H
