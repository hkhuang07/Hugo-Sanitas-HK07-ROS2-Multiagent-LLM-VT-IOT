/**
 * @file sensor_hub.cpp
 * @brief HK-07 ESP32-C3 Sensor Hub Implementation
 *
 * Reads all sensors at 20Hz and transmits raw data via CAN to S3.
 * ★ NO TIMESTAMP in CAN frames — S3 adds SNTP epoch timestamp.
 *
 * CAN Multi-frame Protocol (1 sensor reading = 4 frames, 50ms interval):
 *   Frame 0x200 data[0]=0x01: IMU data (accel + gyro, 6 floats = 24B → 4 CAN frames)
 *   Frame 0x200 data[0]=0x02: Vitals (HR, SpO2, temp, 3 floats)
 *   Frame 0x200 data[0]=0x03: Environment (temp, humidity, pressure, 3 floats)
 *   Frame 0x200 data[0]=0x04: Ultrasonic (front, left, right, 3 floats)
 */
#include "sensor_hub.h"
#include "can_bootloader.h"

#include "driver/i2c.h"
#include "driver/twai.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include <string.h>
#include <math.h>

static const char* TAG = "SENSOR-C3";

// ─── CAN Protocol Constants ───────────────────────────────────────────────────
#define CAN_ID_SENSOR_DATA  0x200
#define CAN_ID_OTA_CMD      0x7E0
#define FRAME_IMU           0x01
#define FRAME_VITALS        0x02
#define FRAME_ENV           0x03
#define FRAME_ULTRASONIC    0x04

// ─── I2C Initialization ───────────────────────────────────────────────────────
static void i2c_master_init(void)
{
    i2c_config_t conf = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = I2C_MASTER_SDA,
        .scl_io_num = I2C_MASTER_SCL,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master = { .clk_speed = I2C_MASTER_FREQ }
    };
    i2c_param_config(I2C_NUM_0, &conf);
    ESP_ERROR_CHECK(i2c_driver_install(I2C_NUM_0, I2C_MODE_MASTER, 0, 0, 0));
    ESP_LOGI(TAG, "I2C bus ready at %d kHz (SDA: GPIO%d, SCL: GPIO%d)",
             I2C_MASTER_FREQ / 1000, I2C_MASTER_SDA, I2C_MASTER_SCL);
}

// ─── MPU-6050 Read ────────────────────────────────────────────────────────────
static void mpu6050_read_raw(float* ax, float* ay, float* az,
                              float* gx, float* gy, float* gz)
{
    // Wake up MPU-6050 first (write 0x00 to PWR_MGMT_1 = 0x6B)
    uint8_t wake_cmd[] = {0x6B, 0x00};
    i2c_master_write_to_device(I2C_NUM_0, MPU6050_ADDR, wake_cmd, 2, pdMS_TO_TICKS(I2C_TIMEOUT_MS));

    // Read 14 bytes starting at ACCEL_XOUT_H (0x3B)
    uint8_t reg = 0x3B;
    uint8_t raw[14] = {};
    i2c_master_write_read_device(I2C_NUM_0, MPU6050_ADDR,
                                  &reg, 1, raw, 14,
                                  pdMS_TO_TICKS(I2C_TIMEOUT_MS));

    // Parse raw values (big-endian 16-bit signed)
    int16_t ax_raw = (int16_t)((raw[0] << 8) | raw[1]);
    int16_t ay_raw = (int16_t)((raw[2] << 8) | raw[3]);
    int16_t az_raw = (int16_t)((raw[4] << 8) | raw[5]);
    int16_t gx_raw = (int16_t)((raw[8] << 8) | raw[9]);
    int16_t gy_raw = (int16_t)((raw[10] << 8) | raw[11]);
    int16_t gz_raw = (int16_t)((raw[12] << 8) | raw[13]);

    // Convert to physical units (±2g range, ±250°/s range)
    *ax = ax_raw / 16384.0f;   // m/s² approximation (×9.81 for true m/s²)
    *ay = ay_raw / 16384.0f;
    *az = az_raw / 16384.0f;
    *gx = gx_raw / 131.0f * (3.14159f / 180.0f);  // rad/s
    *gy = gy_raw / 131.0f * (3.14159f / 180.0f);
    *gz = gz_raw / 131.0f * (3.14159f / 180.0f);
}

// ─── MAX30102 Read (simplified) ───────────────────────────────────────────────
static void max30102_read(float* hr, float* spo2, float* temp)
{
    // Simplified: production would use full MAX30102 algorithm library
    // Read die temperature from register 0x1F (TINTEGER) and 0x20 (TFRAC)
    uint8_t reg = 0x1F;
    uint8_t raw[2] = {};
    i2c_master_write_read_device(I2C_NUM_0, MAX30102_ADDR,
                                  &reg, 1, raw, 2,
                                  pdMS_TO_TICKS(I2C_TIMEOUT_MS));
    float die_temp = (float)raw[0] + (float)raw[1] * 0.0625f;  // °C

    // HR and SpO2 require full photodiode signal processing
    // Production: use library like Maxim AN6409 algorithm
    *hr = 0.0f;    // Populated by library — placeholder
    *spo2 = 0.0f;  // Populated by library — placeholder
    *temp = die_temp;
}

// ─── BME280 Read (simplified) ─────────────────────────────────────────────────
static void bme280_read(float* temp, float* humidity, float* pressure)
{
    // Simplified: production would read trimming params and apply compensation
    // BME280 raw register read starting at 0xF7 (press_msb)
    uint8_t reg = 0xF7;
    uint8_t raw[8] = {};
    i2c_master_write_read_device(I2C_NUM_0, BME280_ADDR,
                                  &reg, 1, raw, 8,
                                  pdMS_TO_TICKS(I2C_TIMEOUT_MS));
    // Full compensation formula from datasheet section 4.2.3
    // Production: use Bosch BSP library
    *temp = 25.0f;      // Placeholder
    *humidity = 60.0f;  // Placeholder
    *pressure = 1013.0f; // Placeholder
}

// ─── HC-SR04 Ultrasonic ───────────────────────────────────────────────────────
static float hcsr04_measure_cm(int trig_gpio, int echo_gpio)
{
    // Trigger: 10us HIGH pulse
    gpio_set_level((gpio_num_t)trig_gpio, 0);
    esp_rom_delay_us(2);
    gpio_set_level((gpio_num_t)trig_gpio, 1);
    esp_rom_delay_us(10);
    gpio_set_level((gpio_num_t)trig_gpio, 0);

    // Wait for echo HIGH
    uint32_t timeout = 25000;  // ~4m max range
    uint32_t start_us = (uint32_t)(esp_timer_get_time() & 0xFFFFFFFF);

    while (!gpio_get_level((gpio_num_t)echo_gpio) && --timeout);
    uint32_t t1 = (uint32_t)(esp_timer_get_time() & 0xFFFFFFFF);

    timeout = 25000;
    while (gpio_get_level((gpio_num_t)echo_gpio) && --timeout);
    uint32_t t2 = (uint32_t)(esp_timer_get_time() & 0xFFFFFFFF);

    if (timeout == 0) return -1.0f;  // Out of range

    float duration_us = (float)(t2 - t1);
    return (duration_us * 0.0343f) / 2.0f;  // Speed of sound: 343 m/s → cm
}

static void ultrasonic_gpio_init(void)
{
    // Trigger pins = output
    gpio_config_t out_conf = {};
    out_conf.mode = GPIO_MODE_OUTPUT;
    out_conf.pin_bit_mask = ((1ULL << HC_SR04_FRONT_TRIG) |
                              (1ULL << HC_SR04_LEFT_TRIG)  |
                              (1ULL << HC_SR04_RIGHT_TRIG));
    gpio_config(&out_conf);

    // Echo pins = input
    gpio_config_t in_conf = {};
    in_conf.mode = GPIO_MODE_INPUT;
    in_conf.pull_down_en = GPIO_PULLDOWN_ENABLE;
    in_conf.pin_bit_mask = ((1ULL << HC_SR04_FRONT_ECHO) |
                             (1ULL << HC_SR04_LEFT_ECHO)  |
                             (1ULL << HC_SR04_RIGHT_ECHO));
    gpio_config(&in_conf);
}

// ─── CAN Transmit Helper ──────────────────────────────────────────────────────
/** Send 3 floats as a CAN frame with frame_type identifier byte */
static void can_send_float3(uint8_t frame_type, float a, float b, float c)
{
    twai_message_t msg = {};
    msg.identifier = CAN_ID_SENSOR_DATA;
    msg.data_length_code = 8;  // 1 type byte + first float (4B) + 2 bytes (next float partial)
    msg.data[0] = frame_type;

    // Pack: type(1B) + float_a(4B) + float_b_lo(3B) = 8B total
    // Production: use proper multi-frame fragmentation (ISO 15765-2 style)
    // Simplified: pack what fits in single frame
    memcpy(&msg.data[1], &a, 4);
    memcpy(&msg.data[5], &b, 3);  // partial — production splits across frames
    twai_transmit(&msg, pdMS_TO_TICKS(10));

    // Send continuation frame for float_b remainder + float_c
    twai_message_t msg2 = {};
    msg2.identifier = CAN_ID_SENSOR_DATA;
    msg2.data_length_code = 5;
    msg2.data[0] = frame_type | 0x80;  // continuation flag
    msg2.data[1] = ((uint8_t*)&b)[3];  // last byte of b
    memcpy(&msg2.data[2], &c, 4);
    twai_transmit(&msg2, pdMS_TO_TICKS(10));
}

// ─── Sensor Task ──────────────────────────────────────────────────────────────
static void sensor_task(void* arg)
{
    ESP_LOGI(TAG, "Sensor task started — reading at 20Hz");

    while (true) {
        sensor_data_t data = {};

        // 1. MPU-6050 IMU
        mpu6050_read_raw(&data.accel_x, &data.accel_y, &data.accel_z,
                          &data.gyro_x, &data.gyro_y, &data.gyro_z);
        can_send_float3(FRAME_IMU, data.accel_x, data.accel_y, data.accel_z);
        vTaskDelay(pdMS_TO_TICKS(2));
        can_send_float3(FRAME_IMU | 0x40, data.gyro_x, data.gyro_y, data.gyro_z);

        // 2. MAX30102 Vitals
        max30102_read(&data.heart_rate, &data.spo2, &data.body_temperature);
        can_send_float3(FRAME_VITALS, data.heart_rate, data.spo2, data.body_temperature);

        // 3. BME280 Environment
        bme280_read(&data.env_temperature, &data.humidity, &data.pressure);
        can_send_float3(FRAME_ENV, data.env_temperature, data.humidity, data.pressure);

        // 4. HC-SR04 Distances
        data.dist_front = hcsr04_measure_cm(HC_SR04_FRONT_TRIG, HC_SR04_FRONT_ECHO) / 100.0f;
        data.dist_left  = hcsr04_measure_cm(HC_SR04_LEFT_TRIG, HC_SR04_LEFT_ECHO) / 100.0f;
        data.dist_right = hcsr04_measure_cm(HC_SR04_RIGHT_TRIG, HC_SR04_RIGHT_ECHO) / 100.0f;
        can_send_float3(FRAME_ULTRASONIC, data.dist_front, data.dist_left, data.dist_right);

        ESP_LOGD(TAG, "Sensor TX: IMU[%.2f,%.2f,%.2f] HR:%.1f SpO2:%.1f Dist:[%.2f,%.2f,%.2f]",
                 data.accel_x, data.accel_y, data.accel_z,
                 data.heart_rate, data.spo2,
                 data.dist_front, data.dist_left, data.dist_right);

        // 20Hz = 50ms period
        vTaskDelay(pdMS_TO_TICKS(50));
    }
}

// ─── CAN Receive Task (for OTA commands from S3) ──────────────────────────────
static void can_receive_task(void* arg)
{
    while (true) {
        twai_message_t msg = {};
        if (twai_receive(&msg, pdMS_TO_TICKS(100)) == ESP_OK) {
            if (msg.identifier == CAN_ID_OTA_CMD) {
                can_bootloader_handle_frame(&msg);
            }
        }
    }
}

// ─── Public Init ──────────────────────────────────────────────────────────────
void sensor_hub_init(void)
{
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "  HK-07 C3 Sensor Hub Booting");
    ESP_LOGI(TAG, "  Sensors: MPU6050 + MAX30102 + BME280");
    ESP_LOGI(TAG, "  Ultrasonic: HC-SR04 x3");
    ESP_LOGI(TAG, "========================================");

    i2c_master_init();
    ultrasonic_gpio_init();

    // CAN Bus init
    twai_general_config_t g_cfg = TWAI_GENERAL_CONFIG_DEFAULT(
        (gpio_num_t)SENSOR_CAN_TX, (gpio_num_t)SENSOR_CAN_RX, TWAI_MODE_NORMAL);
    twai_timing_config_t t_cfg = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t f_cfg = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    ESP_ERROR_CHECK(twai_driver_install(&g_cfg, &t_cfg, &f_cfg));
    ESP_ERROR_CHECK(twai_start());

    can_bootloader_init();

    // Sensor read + CAN TX task (20Hz)
    xTaskCreate(sensor_task, "hk07_sensor", 4096, NULL, 5, NULL);

    // CAN RX task (for OTA commands)
    xTaskCreate(can_receive_task, "hk07_can_rx", 2048, NULL, 4, NULL);

    ESP_LOGI(TAG, "★ Sensor Hub READY — streaming to S3 at 20Hz");
}
