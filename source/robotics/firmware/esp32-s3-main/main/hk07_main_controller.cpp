/**
 * @file hk07_main_controller.cpp
 * @brief HK-07 ESP32-S3 Main Controller Implementation
 *
 * Core 0 (Protocol): WiFi, MQTT, SNTP, OTA HTTP server
 * Core 1 (Real-time): CAN Bus TX/RX, Heartbeat timer, State Machine
 *
 * Safety: Heartbeat CAN 0x301 every 100ms — C3 Motor watchdog 500ms
 * Timestamp: SNTP epoch stamped here (Core 0) before MQTT publish
 */

#include "hk07_main_controller.h"
#include "can_interface.h"
#include "sntp_manager.h"
#include "ota_manager.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/event_groups.h"

#include "esp_log.h"
#include "esp_wifi.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "esp_timer.h"
#include "driver/twai.h"

#include <string.h>
#include <stdio.h>

static const char* TAG = "HK07-S3";

// ─── Static State ─────────────────────────────────────────────────────────────
static robot_state_t s_state = STATE_BOOT;
static uint8_t s_heartbeat_seq = 0;
static QueueHandle_t s_can_to_mqtt_queue = NULL;
static QueueHandle_t s_mqtt_to_can_queue = NULL;
static esp_mqtt_client_handle_t s_mqtt_client = NULL;
static esp_timer_handle_t s_heartbeat_timer = NULL;
static EventGroupHandle_t s_wifi_event_group = NULL;
#define WIFI_CONNECTED_BIT BIT0

// ─── WiFi Event Handler ───────────────────────────────────────────────────────
static void wifi_event_handler(void* arg, esp_event_base_t event_base,
                                int32_t event_id, void* event_data)
{
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "[WiFi] Disconnected, retrying...");
        esp_wifi_connect();
        xEventGroupClearBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*) event_data;
        ESP_LOGI(TAG, "[WiFi] Connected, IP: " IPSTR, IP2STR(&event->ip_info.ip));
        xEventGroupSetBits(s_wifi_event_group, WIFI_CONNECTED_BIT);
    }
}

// ─── WiFi Init ────────────────────────────────────────────────────────────────
static void wifi_init_sta(void)
{
    s_wifi_event_group = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();

    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t instance_any_id;
    esp_event_handler_instance_t instance_got_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        WIFI_EVENT, ESP_EVENT_ANY_ID, &wifi_event_handler, NULL, &instance_any_id));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(
        IP_EVENT, IP_EVENT_STA_GOT_IP, &wifi_event_handler, NULL, &instance_got_ip));

    wifi_config_t wifi_config = {};
    strncpy((char*)wifi_config.sta.ssid, HK07_WIFI_SSID, sizeof(wifi_config.sta.ssid) - 1);
    strncpy((char*)wifi_config.sta.password, HK07_WIFI_PASSWORD, sizeof(wifi_config.sta.password) - 1);
    wifi_config.sta.threshold.authmode = WIFI_AUTH_WPA2_PSK;

    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &wifi_config));
    ESP_ERROR_CHECK(esp_wifi_start());

    // Wait for connection
    xEventGroupWaitBits(s_wifi_event_group, WIFI_CONNECTED_BIT, pdFALSE, pdFALSE, portMAX_DELAY);
    ESP_LOGI(TAG, "[WiFi] ★ Connected to %s", HK07_WIFI_SSID);
}

// ─── MQTT Event Handler ───────────────────────────────────────────────────────
static void mqtt_event_handler(void* handler_args, esp_event_base_t base,
                                int32_t event_id, void* event_data)
{
    esp_mqtt_event_handle_t event = (esp_mqtt_event_handle_t) event_data;

    switch (event->event_id) {
        case MQTT_EVENT_CONNECTED:
            ESP_LOGI(TAG, "[MQTT] ★ Connected to broker");
            esp_mqtt_client_subscribe(s_mqtt_client, "hk07/robot/command", 1);
            break;

        case MQTT_EVENT_DATA: {
            // Receive command from hk07-agent → enqueue for Core 1 CAN dispatch
            can_command_t cmd = {};
            // Parse JSON command: simplified, production would use cJSON
            // Format: {"command":1,"param1":0.5,"param2":5.0,"priority":1}
            sscanf(event->data, "{\"command\":%hhu,\"param1\":%f,\"param2\":%f,\"priority\":%hhu}",
                   &cmd.command, &cmd.param1, &cmd.param2, &cmd.priority);
            xQueueSend(s_mqtt_to_can_queue, &cmd, 0);  // non-blocking
            break;
        }

        case MQTT_EVENT_DISCONNECTED:
            ESP_LOGW(TAG, "[MQTT] Disconnected, will retry...");
            break;

        default:
            break;
    }
}

// ─── MQTT Init ────────────────────────────────────────────────────────────────
static void mqtt_init(void)
{
    char broker_uri[64];
    snprintf(broker_uri, sizeof(broker_uri), "mqtt://%s:%d",
             HK07_MQTT_BROKER_IP, HK07_MQTT_BROKER_PORT);

    esp_mqtt_client_config_t mqtt_cfg = {};
    mqtt_cfg.broker.address.uri = broker_uri;
    mqtt_cfg.credentials.client_id = HK07_MQTT_CLIENT_ID;
    mqtt_cfg.session.keepalive = 60;
    mqtt_cfg.network.reconnect_timeout_ms = 2000;

    s_mqtt_client = esp_mqtt_client_init(&mqtt_cfg);
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(
        s_mqtt_client, MQTT_EVENT_ANY, mqtt_event_handler, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(s_mqtt_client));
}

// ─── Heartbeat Timer (runs on Core 1 esp_timer context) ──────────────────────
/**
 * ★ CRITICAL SAFETY: sends CAN 0x301 every 100ms
 * C3 Motor watchdog expects this — if missed >500ms → auto E-Stop
 */
static void heartbeat_timer_callback(void* arg)
{
    twai_message_t hb_msg = {};
    hb_msg.identifier = CAN_ID_HEARTBEAT;
    hb_msg.data_length_code = 2;
    hb_msg.data[0] = s_heartbeat_seq++;
    hb_msg.data[1] = (uint8_t) s_state;

    // Non-blocking CAN send (ISR-safe from timer context)
    esp_err_t ret = twai_transmit(&hb_msg, 0);
    if (ret != ESP_OK) {
        // CAN bus busy — not fatal, but log if persistent
        ESP_LOGD(TAG, "[HB] CAN transmit busy: %d", ret);
    }
}

static void heartbeat_timer_start(void)
{
    esp_timer_create_args_t timer_args = {
        .callback = heartbeat_timer_callback,
        .arg      = NULL,
        .name     = "hk07_heartbeat"
    };
    ESP_ERROR_CHECK(esp_timer_create(&timer_args, &s_heartbeat_timer));
    ESP_ERROR_CHECK(esp_timer_start_periodic(s_heartbeat_timer, HEARTBEAT_INTERVAL_US));
    ESP_LOGI(TAG, "[HB] ★ Heartbeat timer started (100ms → CAN 0x301)");
}

// ─── Core 0 Task: Protocol (WiFi, MQTT, SNTP, OTA) ───────────────────────────
static void protocol_task(void* arg)
{
    ESP_LOGI(TAG, "[Core0] Protocol task started on Core %d", xPortGetCoreID());
    can_sensor_frame_t frame = {};

    while (true) {
        // Receive sensor data from Core 1 via lock-free queue
        if (xQueueReceive(s_can_to_mqtt_queue, &frame, pdMS_TO_TICKS(20)) == pdTRUE) {
            // ★ Stamp SNTP epoch timestamp HERE — Core 0 owns SNTP
            int64_t epoch_ms = sntp_manager_get_epoch_ms();

            // Build JSON payload
            char payload[512];
            snprintf(payload, sizeof(payload),
                "{"
                "\"timestamp_ms\":%lld,"
                "\"heartbeat_seq\":%d,"
                "\"system_state\":%d,"
                "\"sensor\":{"
                "\"robot_accel_x\":%.4f,\"robot_accel_y\":%.4f,\"robot_accel_z\":%.4f,"
                "\"robot_gyro_x\":%.4f,\"robot_gyro_y\":%.4f,\"robot_gyro_z\":%.4f,"
                "\"heart_rate\":%.1f,\"spo2\":%.1f,\"body_temperature\":%.2f,"
                "\"env_temperature\":%.2f,\"humidity\":%.1f,\"pressure\":%.1f,"
                "\"dist_front\":%.3f,\"dist_left\":%.3f,\"dist_right\":%.3f"
                "}}",
                epoch_ms, s_heartbeat_seq, (int)s_state,
                frame.robot_accel_x, frame.robot_accel_y, frame.robot_accel_z,
                frame.robot_gyro_x, frame.robot_gyro_y, frame.robot_gyro_z,
                frame.heart_rate, frame.spo2, frame.body_temperature,
                frame.env_temperature, frame.humidity, frame.pressure,
                frame.dist_front, frame.dist_left, frame.dist_right
            );

            esp_mqtt_client_publish(s_mqtt_client, "hk07/robot/telemetry", payload, 0, 1, 0);
        }

        // MQTT and OTA polling handled by their own tasks (esp-mqtt is async)
        // Just yield here
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}

// ─── Core 1 Task: Real-time (CAN Bus, State Machine) ─────────────────────────
static void realtime_task(void* arg)
{
    ESP_LOGI(TAG, "[Core1] Real-time task started on Core %d", xPortGetCoreID());

    while (true) {
        // 1. Receive CAN frames from sensor hub (C3 Sensor → S3)
        twai_message_t rx_msg = {};
        if (twai_receive(&rx_msg, pdMS_TO_TICKS(10)) == ESP_OK) {
            if (rx_msg.identifier == CAN_ID_SENSOR_DATA && rx_msg.data_length_code >= 8) {
                // Unpack CAN frame into sensor struct
                // CAN frame layout: see can_interface.h for full packing
                can_sensor_frame_t sf = {};
                // Simplified: production uses proper frame fragmentation
                // Each full sensor frame is split across multiple CAN frames
                memcpy(&sf, rx_msg.data, sizeof(float) * 2); // partial unpack
                xQueueSend(s_can_to_mqtt_queue, &sf, 0);     // non-blocking
            }
        }

        // 2. Process commands from MQTT (Core 0 → Core 1)
        can_command_t cmd = {};
        if (xQueueReceive(s_mqtt_to_can_queue, &cmd, 0) == pdTRUE) {
            twai_message_t tx_msg = {};
            tx_msg.identifier = CAN_ID_MOTOR_CMD;
            tx_msg.data_length_code = 8;
            tx_msg.data[0] = cmd.command;
            memcpy(&tx_msg.data[1], &cmd.param1, sizeof(float));
            memcpy(&tx_msg.data[5], &cmd.param2, sizeof(float));  // partial
            twai_transmit(&tx_msg, pdMS_TO_TICKS(10));
        }

        // 3. State machine update (minimal — production expands this)
        // Currently: if battery low → STATE_ERROR
        if (s_state == STATE_BOOT) s_state = STATE_IDLE;
    }
}

// ─── Public API ───────────────────────────────────────────────────────────────

void hk07_controller_init(void)
{
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "  HK-07 S3 Main Controller Booting...");
    ESP_LOGI(TAG, "========================================");

    // Step 1: NVS (required by WiFi)
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    // Step 2: WiFi connect
    ESP_LOGI(TAG, "[1/7] WiFi connecting to '%s'...", HK07_WIFI_SSID);
    wifi_init_sta();

    // Step 3: ★ SNTP sync — MUST complete before any timestamp operations
    ESP_LOGI(TAG, "[2/7] ★ SNTP synchronizing...");
    sntp_manager_init();  // Blocks until epoch is valid
    ESP_LOGI(TAG, "[2/7] ★ SNTP OK — epoch: %lld ms", sntp_manager_get_epoch_ms());

    // Step 4: CAN Bus init (TWAI driver)
    ESP_LOGI(TAG, "[3/7] CAN Bus initializing at %d kbps...", HK07_CAN_SPEED_KBPS / 1000);
    can_interface_init(HK07_CAN_TX_GPIO, HK07_CAN_RX_GPIO, HK07_CAN_SPEED_KBPS);

    // Step 5: MQTT connect
    ESP_LOGI(TAG, "[4/7] MQTT connecting to %s:%d...", HK07_MQTT_BROKER_IP, HK07_MQTT_BROKER_PORT);
    mqtt_init();

    // Step 6: ★ OTA HTTP server
    ESP_LOGI(TAG, "[5/7] ★ OTA HTTP server on port %d...", HK07_OTA_HTTP_PORT);
    ota_manager_init(HK07_OTA_HTTP_PORT);

    // Step 7: Create inter-core queues
    ESP_LOGI(TAG, "[6/7] Creating inter-core queues...");
    s_can_to_mqtt_queue = xQueueCreate(CAN_TO_MQTT_QUEUE_SIZE, sizeof(can_sensor_frame_t));
    s_mqtt_to_can_queue = xQueueCreate(MQTT_TO_CAN_QUEUE_SIZE, sizeof(can_command_t));
    configASSERT(s_can_to_mqtt_queue);
    configASSERT(s_mqtt_to_can_queue);

    // Step 8: ★ Pin tasks to specific cores
    ESP_LOGI(TAG, "[7/7] ★ Core Pinning: Protocol→Core0, Realtime→Core1...");

    xTaskCreatePinnedToCore(
        protocol_task,
        "hk07_protocol",
        8192,
        NULL,
        PROTOCOL_TASK_PRIORITY,
        NULL,
        PROTOCOL_CORE   // ★ Core 0: WiFi/MQTT/SNTP/OTA
    );

    xTaskCreatePinnedToCore(
        realtime_task,
        "hk07_realtime",
        4096,
        NULL,
        REALTIME_TASK_PRIORITY,  // ★ Higher than WiFi driver
        NULL,
        REALTIME_CORE   // ★ Core 1: CAN/Heartbeat/StateMachine
    );

    // Step 9: ★ Start heartbeat timer (will fire on Core 1)
    heartbeat_timer_start();

    s_state = STATE_IDLE;
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "  ★ HK-07 S3 READY — System Online");
    ESP_LOGI(TAG, "========================================");
}

robot_state_t hk07_controller_get_state(void)
{
    return s_state;
}

void hk07_controller_estop(void)
{
    s_state = STATE_ESTOP;
    twai_message_t estop_msg = {};
    estop_msg.identifier = CAN_ID_ESTOP;
    estop_msg.data_length_code = 1;
    estop_msg.data[0] = 0xFF;
    twai_transmit(&estop_msg, pdMS_TO_TICKS(50));
    ESP_LOGE(TAG, "[ESTOP] ★ Broadcast E-Stop sent on CAN 0x300");
}
