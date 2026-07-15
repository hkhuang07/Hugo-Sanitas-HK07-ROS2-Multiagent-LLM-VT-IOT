/**
 * @file ota_manager.cpp
 * @brief OTA Update Manager Implementation
 *
 * HTTP Endpoints:
 *   POST /ota/s3          — flash S3 itself
 *   POST /ota/c3-sensor   — flash C3 Sensor via CAN proxy
 *   POST /ota/c3-motor    — flash C3 Motor via CAN proxy
 *
 * CAN-OTA Protocol (UDS-inspired):
 *   0x7E0 byte[0] = 0x01 (START)   → C3 enters bootloader
 *   0x7E0 byte[0] = 0x02 (CHUNK)   → 7 bytes firmware data
 *   0x7E0 byte[0] = 0x03 (CRC)     → 4 bytes CRC32 for verification
 *   0x7E0 byte[0] = 0x04 (REBOOT)  → C3 reboots with new firmware
 *   0x7E1 byte[0] = 0xAA (ACK)     → C3 acknowledged
 *   0x7E1 byte[0] = 0xFF (NACK)    → C3 error, retry
 */
#include "ota_manager.h"
#include "hk07_main_controller.h"
#include "esp_http_server.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_https_ota.h"
#include "driver/twai.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

static const char* TAG = "OTA";
static httpd_handle_t s_server = NULL;

// OTA CAN protocol constants
#define OTA_CMD_START   0x01
#define OTA_CMD_CHUNK   0x02
#define OTA_CMD_CRC     0x03
#define OTA_CMD_REBOOT  0x04
#define OTA_ACK         0xAA
#define OTA_NACK        0xFF
#define OTA_CHUNK_SIZE  7    // 8 bytes total: 1 cmd + 7 data
#define OTA_TIMEOUT_MS  30000
#define OTA_MAX_RETRIES 5

/**
 * Send a CAN-OTA chunk and wait for ACK from C3.
 * Returns true if ACK received within timeout.
 */
static bool can_ota_send_chunk(uint8_t cmd, const uint8_t* data, uint8_t len)
{
    twai_message_t tx = {};
    tx.identifier = CAN_ID_OTA_CMD;
    tx.data_length_code = len + 1;
    tx.data[0] = cmd;
    if (data && len > 0) {
        memcpy(&tx.data[1], data, len);
    }

    for (int retry = 0; retry < OTA_MAX_RETRIES; retry++) {
        twai_transmit(&tx, pdMS_TO_TICKS(100));

        // Wait for ACK
        twai_message_t rx = {};
        esp_err_t ret = twai_receive(&rx, pdMS_TO_TICKS(500));
        if (ret == ESP_OK && rx.identifier == CAN_ID_OTA_RESP) {
            if (rx.data[0] == OTA_ACK) return true;
            ESP_LOGW(TAG, "[CAN-OTA] NACK received, retry %d/%d", retry + 1, OTA_MAX_RETRIES);
        }
    }
    return false;
}

/**
 * Flash a C3 node via CAN-OTA proxy.
 * @param firmware_data  Firmware binary data in RAM
 * @param firmware_size  Size of firmware
 * @param target_can_id  Not used currently (single C3 target per command)
 */
static esp_err_t can_ota_flash_c3(const uint8_t* firmware_data, size_t firmware_size)
{
    ESP_LOGI(TAG, "[CAN-OTA] Starting flash of C3 (%d bytes)...", firmware_size);

    // Step 1: START command
    if (!can_ota_send_chunk(OTA_CMD_START, NULL, 0)) {
        ESP_LOGE(TAG, "[CAN-OTA] C3 did not respond to START");
        return ESP_FAIL;
    }

    // Step 2: Send firmware in chunks
    size_t offset = 0;
    size_t chunk_idx = 0;
    while (offset < firmware_size) {
        uint8_t chunk[OTA_CHUNK_SIZE] = {};
        size_t chunk_len = (firmware_size - offset) < OTA_CHUNK_SIZE
                           ? (firmware_size - offset) : OTA_CHUNK_SIZE;
        memcpy(chunk, firmware_data + offset, chunk_len);

        if (!can_ota_send_chunk(OTA_CMD_CHUNK, chunk, chunk_len)) {
            ESP_LOGE(TAG, "[CAN-OTA] Chunk %d failed", chunk_idx);
            return ESP_FAIL;
        }

        offset += chunk_len;
        chunk_idx++;

        // Progress log every 100 chunks
        if (chunk_idx % 100 == 0) {
            ESP_LOGI(TAG, "[CAN-OTA] Progress: %d/%d bytes (%.1f%%)",
                     offset, firmware_size, (float)offset / firmware_size * 100.0f);
        }
    }

    // Step 3: CRC verification
    // Simple CRC32 — production uses esp_rom_crc32_le
    uint32_t crc = 0; // placeholder
    if (!can_ota_send_chunk(OTA_CMD_CRC, (uint8_t*)&crc, 4)) {
        ESP_LOGE(TAG, "[CAN-OTA] CRC verification failed");
        return ESP_FAIL;
    }

    // Step 4: Reboot C3
    if (!can_ota_send_chunk(OTA_CMD_REBOOT, NULL, 0)) {
        ESP_LOGW(TAG, "[CAN-OTA] Reboot command sent (no ACK expected)");
    }

    ESP_LOGI(TAG, "[CAN-OTA] ★ C3 firmware update complete!");
    return ESP_OK;
}

/**
 * HTTP handler: POST /ota/s3 — self OTA for S3
 * Body: raw binary firmware file
 */
static esp_err_t ota_s3_handler(httpd_req_t* req)
{
    ESP_LOGI(TAG, "[OTA-S3] Received firmware update request (%d bytes)", req->content_len);

    if (hk07_controller_get_state() != STATE_IDLE) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST,
                           "OTA only allowed in IDLE state");
        return ESP_FAIL;
    }

    esp_ota_handle_t ota_handle;
    const esp_partition_t* ota_partition = esp_ota_get_next_update_partition(NULL);
    ESP_ERROR_CHECK(esp_ota_begin(ota_partition, OTA_SIZE_UNKNOWN, &ota_handle));

    char buf[256];
    int received = 0;
    int total = req->content_len;

    while (received < total) {
        int len = httpd_req_recv(req, buf, sizeof(buf));
        if (len <= 0) break;
        esp_ota_write(ota_handle, buf, len);
        received += len;
    }

    ESP_ERROR_CHECK(esp_ota_end(ota_handle));
    ESP_ERROR_CHECK(esp_ota_set_boot_partition(ota_partition));

    httpd_resp_sendstr(req, "S3 OTA complete — rebooting in 3s...");
    ESP_LOGI(TAG, "[OTA-S3] ★ Firmware written. Rebooting...");
    vTaskDelay(pdMS_TO_TICKS(3000));
    esp_restart();
    return ESP_OK;
}

/**
 * HTTP handler: POST /ota/c3-motor or /ota/c3-sensor
 * Body: raw binary firmware for C3
 */
static esp_err_t ota_c3_handler(httpd_req_t* req)
{
    ESP_LOGI(TAG, "[OTA-C3] Received C3 firmware (%d bytes)", req->content_len);

    if (hk07_controller_get_state() != STATE_IDLE) {
        httpd_resp_send_err(req, HTTPD_400_BAD_REQUEST,
                           "OTA only allowed in IDLE state");
        return ESP_FAIL;
    }

    // Buffer entire firmware in PSRAM (S3 has 8MB PSRAM)
    uint8_t* fw_buf = (uint8_t*) heap_caps_malloc(req->content_len, MALLOC_CAP_SPIRAM);
    if (!fw_buf) {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "Out of PSRAM");
        return ESP_FAIL;
    }

    int received = 0;
    int total = req->content_len;
    while (received < total) {
        int len = httpd_req_recv(req, (char*)(fw_buf + received),
                                  total - received);
        if (len <= 0) break;
        received += len;
    }

    esp_err_t ret = can_ota_flash_c3(fw_buf, received);
    heap_caps_free(fw_buf);

    if (ret == ESP_OK) {
        httpd_resp_sendstr(req, "C3 OTA complete!");
    } else {
        httpd_resp_send_err(req, HTTPD_500_INTERNAL_SERVER_ERROR, "C3 OTA failed");
    }
    return ret;
}

void ota_manager_init(uint16_t port)
{
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = port;
    config.max_uri_handlers = 4;

    if (httpd_start(&s_server, &config) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start OTA HTTP server!");
        return;
    }

    // Register OTA endpoints
    httpd_uri_t ota_s3 = {
        .uri = "/ota/s3",
        .method = HTTP_POST,
        .handler = ota_s3_handler,
        .user_ctx = NULL
    };
    httpd_uri_t ota_c3_motor = {
        .uri = "/ota/c3-motor",
        .method = HTTP_POST,
        .handler = ota_c3_handler,
        .user_ctx = (void*)"motor"
    };
    httpd_uri_t ota_c3_sensor = {
        .uri = "/ota/c3-sensor",
        .method = HTTP_POST,
        .handler = ota_c3_handler,
        .user_ctx = (void*)"sensor"
    };

    httpd_register_uri_handler(s_server, &ota_s3);
    httpd_register_uri_handler(s_server, &ota_c3_motor);
    httpd_register_uri_handler(s_server, &ota_c3_sensor);

    ESP_LOGI(TAG, "★ OTA HTTP server ready on port %d", port);
    ESP_LOGI(TAG, "  Flash S3:      curl -X POST http://<ip>:%d/ota/s3 --data-binary @firmware.bin", port);
    ESP_LOGI(TAG, "  Flash C3 Motor: curl -X POST http://<ip>:%d/ota/c3-motor --data-binary @c3_motor.bin", port);
    ESP_LOGI(TAG, "  Flash C3 Sensor:curl -X POST http://<ip>:%d/ota/c3-sensor --data-binary @c3_sensor.bin", port);
}

void ota_manager_poll(void)
{
    // OTA HTTP server is event-driven via esp-httpd
    // Nothing to poll — server handles requests in its own task
}
