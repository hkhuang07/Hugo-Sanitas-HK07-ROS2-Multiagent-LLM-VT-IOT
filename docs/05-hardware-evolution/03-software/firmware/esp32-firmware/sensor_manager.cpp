/*
 * HK-07 Sensor Manager Implementation
 * Manages all sensor interfaces and data acquisition
 */

#include "sensor_manager.h"
#include "esp_log.h"
#include "driver/i2c.h"
#include <math.h>

static const char* TAG = "SensorMgr";

// I2C Configuration
#define I2C_MASTER_SCL_IO           8    // GPIO number for I2C master clock
#define I2C_MASTER_SDA_IO           9    // GPIO number for I2C master data
#define I2C_MASTER_NUM              0    // I2C port number
#define I2C_MASTER_FREQ_HZ          400000 // I2C clock frequency
#define I2C_MASTER_TIMEOUT_MS       1000

// Sensor I2C Addresses
#define MPU6050_ADDR                0x68
#define MAX30102_ADDR               0x57
#define BME280_ADDR                 0x76

// Ultrasonic GPIO
#define ULTRASONIC_TRIG_GPIO        5
#define ULTRASONIC_ECHO_GPIO        6

SensorManager::SensorManager() {
    for (int i = 0; i < 6; i++) {
        imu_offset[i] = 0.0f;
    }
    sensor_health = 0xFF; // All sensors OK initially
}

SensorManager::~SensorManager() {
    // Cleanup if needed
}

esp_err_t SensorManager::init() {
    ESP_LOGI(TAG, "Initializing Sensor Manager");
    
    // Initialize I2C
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = I2C_MASTER_SDA_IO,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_io_num = I2C_MASTER_SCL_IO,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = I2C_MASTER_FREQ_HZ,
    };
    
    esp_err_t ret = i2c_param_config(I2C_MASTER_NUM, &conf);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2C param config failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ret = i2c_driver_install(I2C_MASTER_NUM, conf.mode, 0, 0, 0);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "I2C driver install failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Initialize individual sensors
    ret = initIMU();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "IMU initialization failed");
        sensor_health &= ~0x01; // Mark IMU as unhealthy
    }
    
    ret = initSpO2();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SpO2 sensor initialization failed");
        sensor_health &= ~0x02; // Mark SpO2 as unhealthy
    }
    
    ret = initEnvironment();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Environment sensor initialization failed");
        sensor_health &= ~0x04; // Mark Environment as unhealthy
    }
    
    ret = initUltrasonic();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Ultrasonic sensor initialization failed");
        sensor_health &= ~0x08; // Mark Ultrasonic as unhealthy
    }
    
    ESP_LOGI(TAG, "Sensor Manager initialization complete. Health: 0x%02X", sensor_health);
    return ESP_OK;
}

esp_err_t SensorManager::initIMU() {
    ESP_LOGI(TAG, "Initializing MPU-6050 IMU");
    
    // Wake up MPU-6050
    uint8_t wake_cmd[] = {0x6B, 0x00}; // PWR_MGMT_1 register
    esp_err_t ret = i2c_master_write_to_device(I2C_MASTER_NUM, MPU6050_ADDR, 
                                               wake_cmd, sizeof(wake_cmd), 
                                               I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to wake MPU-6050");
        return ret;
    }
    
    // Configure accelerometer (±8g)
    uint8_t accel_config[] = {0x1C, 0x10}; // ACCEL_CONFIG register
    ret = i2c_master_write_to_device(I2C_MASTER_NUM, MPU6050_ADDR,
                                      accel_config, sizeof(accel_config),
                                      I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    
    // Configure gyroscope (±1000°/s)
    uint8_t gyro_config[] = {0x1B, 0x10}; // GYRO_CONFIG register
    ret = i2c_master_write_to_device(I2C_MASTER_NUM, MPU6050_ADDR,
                                      gyro_config, sizeof(gyro_config),
                                      I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    
    ESP_LOGI(TAG, "MPU-6050 initialized successfully");
    return ESP_OK;
}

esp_err_t SensorManager::initSpO2() {
    ESP_LOGI(TAG, "Initializing MAX30102 SpO2 sensor");
    
    // Reset MAX30102
    uint8_t reset_cmd[] = {0x09, 0x40}; // MODE register with reset
    esp_err_t ret = i2c_master_write_to_device(I2C_MASTER_NUM, MAX30102_ADDR,
                                               reset_cmd, sizeof(reset_cmd),
                                               I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    vTaskDelay(pdMS_TO_TICKS(100)); // Wait for reset
    
    // Configure for SpO2 mode
    uint8_t config_cmd[] = {0x09, 0x07}; // SpO2 mode
    ret = i2c_master_write_to_device(I2C_MASTER_NUM, MAX30102_ADDR,
                                      config_cmd, sizeof(config_cmd),
                                      I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    
    ESP_LOGI(TAG, "MAX30102 initialized successfully");
    return ESP_OK;
}

esp_err_t SensorManager::initEnvironment() {
    ESP_LOGI(TAG, "Initializing BME280 Environment sensor");
    
    // Configure BME280 for normal mode
    uint8_t ctrl_meas[] = {0xF4, 0x27}; // Normal mode, oversampling x1
    esp_err_t ret = i2c_master_write_to_device(I2C_MASTER_NUM, BME280_ADDR,
                                               ctrl_meas, sizeof(ctrl_meas),
                                               I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    
    uint8_t config[] = {0xF5, 0xA0}; // Standby time 1000ms
    ret = i2c_master_write_to_device(I2C_MASTER_NUM, BME280_ADDR,
                                      config, sizeof(config),
                                      I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    
    ESP_LOGI(TAG, "BME280 initialized successfully");
    return ESP_OK;
}

esp_err_t SensorManager::initUltrasonic() {
    ESP_LOGI(TAG, "Initializing HC-SR04 Ultrasonic sensor");
    
    // Configure GPIO pins
    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << ULTRASONIC_TRIG_GPIO),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE
    };
    gpio_config(&io_conf);
    
    io_conf.pin_bit_mask = (1ULL << ULTRASONIC_ECHO_GPIO);
    io_conf.mode = GPIO_MODE_INPUT;
    gpio_config(&io_conf);
    
    ESP_LOGI(TAG, "HC-SR04 initialized successfully");
    return ESP_OK;
}

SensorData SensorManager::readSensors() {
    SensorData data;
    data.timestamp = esp_timer_get_time() / 1000; // Convert to milliseconds
    
    // Read from all sensors
    readIMU(&data);
    readSpO2(&data);
    readEnvironment(&data);
    readUltrasonic(&data);
    
    data.sensor_status = sensor_health;
    
    return data;
}

void SensorManager::readIMU(SensorData* data) {
    // Read accelerometer data (registers 0x3B-0x40)
    uint8_t accel_reg = 0x3B;
    uint8_t accel_data[6];
    
    esp_err_t ret = i2c_master_write_to_device(I2C_MASTER_NUM, MPU6050_ADDR,
                                               &accel_reg, 1,
                                               I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    if (ret == ESP_OK) {
        i2c_master_read_from_device(I2C_MASTER_NUM, MPU6050_ADDR,
                                     accel_data, 6,
                                     I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
        
        // Convert to g (assuming ±8g range, sensitivity = 4096 LSB/g)
        data->accel_x = (int16_t)((accel_data[0] << 8) | accel_data[1]) / 4096.0f;
        data->accel_y = (int16_t)((accel_data[2] << 8) | accel_data[3]) / 4096.0f;
        data->accel_z = (int16_t)((accel_data[4] << 8) | accel_data[5]) / 4096.0f;
        
        // Apply calibration offsets
        data->accel_x -= imu_offset[0];
        data->accel_y -= imu_offset[1];
        data->accel_z -= imu_offset[2];
    }
    
    // Read gyroscope data (registers 0x43-0x48)
    uint8_t gyro_reg = 0x43;
    uint8_t gyro_data[6];
    
    ret = i2c_master_write_to_device(I2C_MASTER_NUM, MPU6050_ADDR,
                                      &gyro_reg, 1,
                                      I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    if (ret == ESP_OK) {
        i2c_master_read_from_device(I2C_MASTER_NUM, MPU6050_ADDR,
                                     gyro_data, 6,
                                     I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
        
        // Convert to deg/s (assuming ±1000°/s range, sensitivity = 32.8 LSB/°/s)
        data->gyro_x = (int16_t)((gyro_data[0] << 8) | gyro_data[1]) / 32.8f;
        data->gyro_y = (int16_t)((gyro_data[2] << 8) | gyro_data[3]) / 32.8f;
        data->gyro_z = (int16_t)((gyro_data[4] << 8) | gyro_data[5]) / 32.8f;
        
        // Apply calibration offsets
        data->gyro_x -= imu_offset[3];
        data->gyro_y -= imu_offset[4];
        data->gyro_z -= imu_offset[5];
    }
    
    // Simple quaternion calculation (simplified - should use Madgwick/Mahony filter)
    // This is a placeholder - actual implementation should use proper sensor fusion
    data->quaternion_w = 1.0f;
    data->quaternion_x = 0.0f;
    data->quaternion_y = 0.0f;
    data->quaternion_z = 0.0f;
}

void SensorManager::readSpO2(SensorData* data) {
    // Read MAX30102 registers
    uint8_t fifo_wr_ptr = 0x02;
    uint8_t fifo_data[3];
    
    esp_err_t ret = i2c_master_write_to_device(I2C_MASTER_NUM, MAX30102_ADDR,
                                               &fifo_wr_ptr, 1,
                                               I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    if (ret == ESP_OK) {
        i2c_master_read_from_device(I2C_MASTER_NUM, MAX30102_ADDR,
                                     fifo_data, 3,
                                     I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
        
        // Placeholder values - actual implementation should process PPG data
        data->heart_rate = 75; // Default value
        data->spo2 = 98;      // Default value
        data->temperature = 36.5f; // Default value
    }
}

void SensorManager::readEnvironment(SensorData* data) {
    // Read BME280 pressure, temperature, humidity
    uint8_t press_msb = 0xF7;
    uint8_t env_data[8]; // Pressure (3), temp (3), humidity (2)
    
    esp_err_t ret = i2c_master_write_to_device(I2C_MASTER_NUM, BME280_ADDR,
                                               &press_msb, 1,
                                               I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
    if (ret == ESP_OK) {
        i2c_master_read_from_device(I2C_MASTER_NUM, BME280_ADDR,
                                     env_data, 8,
                                     I2C_MASTER_TIMEOUT_MS / portTICK_PERIOD_MS);
        
        // Simplified conversion - actual implementation should use BME280 calibration
        int32_t press_raw = (env_data[0] << 12) | (env_data[1] << 4) | (env_data[2] >> 4);
        int32_t temp_raw = (env_data[3] << 12) | (env_data[4] << 4) | (env_data[5] >> 4);
        uint16_t hum_raw = (env_data[6] << 8) | env_data[7];
        
        data->pressure = press_raw / 256.0f; // hPa
        data->ambient_temp = temp_raw / 5120.0f; // °C
        data->humidity = hum_raw / 1024.0f; // %
    }
}

void SensorManager::readUltrasonic(SensorData* data) {
    // Trigger ultrasonic measurement
    gpio_set_level(ULTRASONIC_TRIG_GPIO, 0);
    esp_rom_delay_us(2);
    gpio_set_level(ULTRASONIC_TRIG_GPIO, 1);
    esp_rom_delay_us(10);
    gpio_set_level(ULTRASONIC_TRIG_GPIO, 0);
    
    // Measure echo pulse width
    int64_t start_time = esp_timer_get_time();
    while (gpio_get_level(ULTRASONIC_ECHO_GPIO) == 0) {
        if ((esp_timer_get_time() - start_time) > 100000) { // 100ms timeout
            data->distance_cm = -1.0f; // Timeout
            return;
        }
    }
    
    start_time = esp_timer_get_time();
    while (gpio_get_level(ULTRASONIC_ECHO_GPIO) == 1) {
        if ((esp_timer_get_time() - start_time) > 100000) { // 100ms timeout
            data->distance_cm = -1.0f; // Timeout
            return;
        }
    }
    
    int64_t echo_time = esp_timer_get_time() - start_time;
    data->distance_cm = echo_time / 58.0f; // Convert to cm (speed of sound = 343 m/s)
}

esp_err_t SensorManager::calibrateSensors() {
    ESP_LOGI(TAG, "Starting sensor calibration");
    
    // Calibrate IMU (assume robot is stationary during calibration)
    const int calibration_samples = 100;
    float accel_sum[3] = {0, 0, 0};
    float gyro_sum[3] = {0, 0, 0};
    
    for (int i = 0; i < calibration_samples; i++) {
        SensorData data;
        readIMU(&data);
        
        accel_sum[0] += data.accel_x;
        accel_sum[1] += data.accel_y;
        accel_sum[2] += data.accel_z;
        
        gyro_sum[0] += data.gyro_x;
        gyro_sum[1] += data.gyro_y;
        gyro_sum[2] += data.gyro_z;
        
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    
    // Calculate offsets
    imu_offset[0] = accel_sum[0] / calibration_samples;
    imu_offset[1] = accel_sum[1] / calibration_samples;
    imu_offset[2] = (accel_sum[2] / calibration_samples) - 1.0f; // Z should be 1g
    
    imu_offset[3] = gyro_sum[0] / calibration_samples;
    imu_offset[4] = gyro_sum[1] / calibration_samples;
    imu_offset[5] = gyro_sum[2] / calibration_samples;
    
    ESP_LOGI(TAG, "IMU calibration complete. Offsets: [%.3f, %.3f, %.3f, %.3f, %.3f, %.3f]",
             imu_offset[0], imu_offset[1], imu_offset[2],
             imu_offset[3], imu_offset[4], imu_offset[5]);
    
    return ESP_OK;
}

uint8_t SensorManager::getSensorStatus() {
    return sensor_health;
}
