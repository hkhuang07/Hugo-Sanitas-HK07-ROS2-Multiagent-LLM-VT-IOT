/*
 * HK-07 Sensor Manager Header
 * Manages all sensor interfaces and data acquisition
 */

#ifndef SENSOR_MANAGER_H
#define SENSOR_MANAGER_H

#include "esp_err.h"
#include <stdint.h>

// Sensor data structure
typedef struct {
    // IMU data (MPU-6050)
    float accel_x, accel_y, accel_z;
    float gyro_x, gyro_y, gyro_z;
    float quaternion_w, quaternion_x, quaternion_y, quaternion_z;
    
    // Vitals data (MAX30102)
    uint16_t heart_rate;
    uint8_t spo2;
    float temperature;
    
    // Environment data (BME280)
    float ambient_temp;
    float pressure;
    float humidity;
    
    // Ultrasonic data (HC-SR04)
    float distance_cm;
    
    // System status
    uint32_t timestamp;
    uint8_t sensor_status; // Bitmask of sensor health
} SensorData;

class SensorManager {
public:
    SensorManager();
    ~SensorManager();
    
    // Initialize all sensors
    esp_err_t init();
    
    // Read all sensor data
    SensorData readSensors();
    
    // Calibrate sensors
    esp_err_t calibrateSensors();
    
    // Get sensor health status
    uint8_t getSensorStatus();
    
private:
    // Sensor initialization
    esp_err_t initIMU();
    esp_err_t initSpO2();
    esp_err_t initEnvironment();
    esp_err_t initUltrasonic();
    
    // Sensor reading functions
    void readIMU(SensorData* data);
    void readSpO2(SensorData* data);
    void readEnvironment(SensorData* data);
    void readUltrasonic(SensorData* data);
    
    // Calibration data
    float imu_offset[6]; // accel/gyro offsets
    uint8_t sensor_health;
};

#endif // SENSOR_MANAGER_H
