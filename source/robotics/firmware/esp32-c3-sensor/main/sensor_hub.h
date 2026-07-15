/**
 * @file sensor_hub.h / sensor_hub.cpp
 * @brief HK-07 ESP32-C3 Sensor Hub
 *
 * Reads from all onboard sensors via I2C/GPIO and transmits raw data
 * via CAN Bus to S3. NO timestamp included — S3 stamps SNTP epoch.
 *
 * Sensors:
 *   - MPU-6050   : Robot IMU (accel + gyro) — I2C
 *   - MAX30102   : Heart rate + SpO2 + die temp — I2C
 *   - BME280     : Env temp + humidity + pressure — I2C
 *   - HC-SR04 x3 : Ultrasonic distance (front, left, right) — GPIO
 *
 * CAN Frame Protocol:
 *   ID 0x200, payload split across multiple frames using sequence numbers
 *   Frame type byte: 0x01=IMU, 0x02=vitals, 0x03=env, 0x04=ultrasonic
 */
#pragma once
#include <stdint.h>

// ─── Pin Configuration ────────────────────────────────────────────────────────
// I2C Bus (shared by MPU-6050, MAX30102, BME280)
#define I2C_MASTER_SDA      8
#define I2C_MASTER_SCL      9
#define I2C_MASTER_FREQ     400000  // 400kHz (Fast Mode)
#define I2C_TIMEOUT_MS      100
// I2C constraint: keep wire length <15cm to avoid capacitance drop

// I2C Addresses
#define MPU6050_ADDR        0x68
#define MAX30102_ADDR       0x57
#define BME280_ADDR         0x76

// HC-SR04 Ultrasonic (GPIO trigger/echo pairs)
#define HC_SR04_FRONT_TRIG  2
#define HC_SR04_FRONT_ECHO  3
#define HC_SR04_LEFT_TRIG   4
#define HC_SR04_LEFT_ECHO   5
#define HC_SR04_RIGHT_TRIG  6
#define HC_SR04_RIGHT_ECHO  7

// CAN Bus
#define SENSOR_CAN_TX       0
#define SENSOR_CAN_RX       1

// ─── Sensor Data Structure ────────────────────────────────────────────────────
/** ★ NO TIMESTAMP — S3 adds SNTP epoch when publishing to MQTT */
typedef struct {
    // MPU-6050 Robot IMU
    float accel_x, accel_y, accel_z;   // m/s²
    float gyro_x, gyro_y, gyro_z;      // rad/s

    // MAX30102 Vitals
    float heart_rate;                   // BPM
    float spo2;                         // %
    float body_temperature;             // °C (from MAX30102 die temp, calibrated)

    // BME280 Environment
    float env_temperature;              // °C
    float humidity;                     // %RH
    float pressure;                     // hPa

    // HC-SR04 Distances
    float dist_front;                   // meters
    float dist_left;                    // meters
    float dist_right;                   // meters
} sensor_data_t;

#ifdef __cplusplus
extern "C" {
#endif

void sensor_hub_init(void);

#ifdef __cplusplus
}
#endif
