/**
 * @file hk07_main_controller.h
 * @brief HK-07 ESP32-S3 Main Controller
 * 
 * Architecture:
 *   Core 0 (Protocol): WiFi, MQTT, SNTP, OTA HTTP
 *   Core 1 (Real-time): CAN Bus, Heartbeat, State Machine, Sensor Fusion
 *
 * Safety features:
 *   - CAN Heartbeat 0x301 every 100ms (Dead Man's Switch sender)
 *   - SNTP epoch timestamp on all MQTT telemetry
 *   - OTA: WiFi HTTP for S3, CAN-proxy for C3 nodes
 *   - Core Pinning via xTaskCreatePinnedToCore
 */
#pragma once

#include <stdint.h>
#include <stdbool.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_timer.h"

// ─── Configuration ────────────────────────────────────────────────────────────
#define HK07_WIFI_SSID          "YOUR_SSID"
#define HK07_WIFI_PASSWORD      "YOUR_PASSWORD"
#define HK07_MQTT_BROKER_IP     "192.168.1.100"
#define HK07_MQTT_BROKER_PORT   1883
#define HK07_MQTT_CLIENT_ID     "hk07-s3-main"
#define HK07_OTA_HTTP_PORT      8070

// CAN Bus configuration
#define HK07_CAN_TX_GPIO        43
#define HK07_CAN_RX_GPIO        44
#define HK07_CAN_SPEED_KBPS     500000

// CAN Frame IDs
#define CAN_ID_MOTOR_CMD        0x100   // S3 → C3 Motor
#define CAN_ID_SENSOR_DATA      0x200   // C3 Sensor → S3
#define CAN_ID_ESTOP            0x300   // Broadcast E-Stop
#define CAN_ID_HEARTBEAT        0x301   // S3 → C3 Motor (100ms)
#define CAN_ID_OTA_CMD          0x7E0   // S3 → C3 (OTA chunks)
#define CAN_ID_OTA_RESP         0x7E1   // C3 → S3 (OTA ack)

// Task pinning
#define PROTOCOL_CORE           0   // PRO_CPU: WiFi/MQTT/SNTP/OTA
#define REALTIME_CORE           1   // APP_CPU: CAN/Heartbeat/StateMachine
#define PROTOCOL_TASK_PRIORITY  5
#define REALTIME_TASK_PRIORITY  10  // Higher than WiFi driver

// Heartbeat
#define HEARTBEAT_INTERVAL_US   100000  // 100ms

// Inter-core queue sizes
#define CAN_TO_MQTT_QUEUE_SIZE  16
#define MQTT_TO_CAN_QUEUE_SIZE  8

// ─── Data Structures ──────────────────────────────────────────────────────────

/** Raw sensor frame from C3 Sensor via CAN — NO timestamp */
typedef struct {
    float robot_accel_x, robot_accel_y, robot_accel_z;
    float robot_gyro_x, robot_gyro_y, robot_gyro_z;
    float heart_rate;
    float spo2;
    float body_temperature;
    float env_temperature;
    float humidity;
    float pressure;
    float dist_front, dist_left, dist_right;
} can_sensor_frame_t;

/** MQTT telemetry payload — S3 adds SNTP epoch timestamp */
typedef struct {
    int64_t timestamp_ms;       // SNTP epoch, NOT millis()
    can_sensor_frame_t sensor;
    uint8_t heartbeat_seq;
    uint8_t system_state;
} mqtt_telemetry_t;

/** CAN command from MQTT → dispatched to C3 Motor */
typedef struct {
    uint8_t command;
    float param1;
    float param2;
    uint8_t priority;
} can_command_t;

/** Robot system states */
typedef enum {
    STATE_BOOT      = 0,
    STATE_IDLE      = 1,
    STATE_MOVING    = 2,
    STATE_ESTOP     = 3,
    STATE_OTA       = 4,
    STATE_ERROR     = 5,
} robot_state_t;

// ─── Controller Class ─────────────────────────────────────────────────────────

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize the main controller.
 * Must be called once from app_main().
 * Performs: WiFi → SNTP → CAN → MQTT → OTA → Core Pinning → Heartbeat
 */
void hk07_controller_init(void);

/**
 * Get current robot state.
 */
robot_state_t hk07_controller_get_state(void);

/**
 * Trigger broadcast E-Stop on CAN bus.
 */
void hk07_controller_estop(void);

#ifdef __cplusplus
}
#endif
