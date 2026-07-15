/**
 * @file can_bootloader.cpp
 * @brief CAN-OTA Bootloader Implementation for ESP32-C3
 */
#include "can_bootloader.h"
#include "esp_ota_ops.h"
#include "esp_log.h"
#include "driver/twai.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <string.h>

static const char* TAG = "CAN-BOOT";

#define OTA_CMD_START   0x01
#define OTA_CMD_CHUNK   0x02
#define OTA_CMD_CRC     0x03
#define OTA_CMD_REBOOT  0x04
#define OTA_ACK         0xAA
#define OTA_NACK        0xFF

#define CAN_ID_OTA_RESP 0x7E1

static esp_ota_handle_t s_ota_handle = 0;
static bool s_ota_active = false;
static uint32_t s_bytes_written = 0;

static void send_ota_response(uint8_t status)
{
    twai_message_t resp = {};
    resp.identifier = CAN_ID_OTA_RESP;
    resp.data_length_code = 2;
    resp.data[0] = status;
    resp.data[1] = (uint8_t)(s_bytes_written & 0xFF);  // progress byte
    twai_transmit(&resp, pdMS_TO_TICKS(50));
}

void can_bootloader_init(void)
{
    s_ota_active = false;
    s_ota_handle = 0;
    s_bytes_written = 0;
    ESP_LOGI(TAG, "CAN Bootloader ready (waiting for OTA_CMD_START 0x7E0)");
}

void can_bootloader_handle_frame(const twai_message_t* msg)
{
    if (msg->data_length_code < 1) return;

    uint8_t cmd = msg->data[0];

    switch (cmd) {
        case OTA_CMD_START: {
            // Enter OTA flash mode
            const esp_partition_t* ota_part = esp_ota_get_next_update_partition(NULL);
            if (!ota_part) {
                ESP_LOGE(TAG, "No OTA partition found!");
                send_ota_response(OTA_NACK);
                return;
            }
            esp_err_t ret = esp_ota_begin(ota_part, OTA_SIZE_UNKNOWN, &s_ota_handle);
            if (ret != ESP_OK) {
                ESP_LOGE(TAG, "esp_ota_begin failed: %s", esp_err_to_name(ret));
                send_ota_response(OTA_NACK);
                return;
            }
            s_ota_active = true;
            s_bytes_written = 0;
            ESP_LOGI(TAG, "★ OTA START — entering flash mode");
            send_ota_response(OTA_ACK);
            break;
        }

        case OTA_CMD_CHUNK: {
            if (!s_ota_active || s_ota_handle == 0) {
                send_ota_response(OTA_NACK);
                return;
            }
            uint8_t* data = (uint8_t*)(msg->data + 1);
            uint8_t len = msg->data_length_code - 1;

            esp_err_t ret = esp_ota_write(s_ota_handle, data, len);
            if (ret != ESP_OK) {
                ESP_LOGE(TAG, "esp_ota_write failed at %d bytes", s_bytes_written);
                send_ota_response(OTA_NACK);
                return;
            }
            s_bytes_written += len;
            send_ota_response(OTA_ACK);
            break;
        }

        case OTA_CMD_CRC: {
            if (!s_ota_active) {
                send_ota_response(OTA_NACK);
                return;
            }
            // End OTA writing (validates internal CRC)
            esp_err_t ret = esp_ota_end(s_ota_handle);
            if (ret != ESP_OK) {
                ESP_LOGE(TAG, "esp_ota_end failed — firmware corrupt");
                s_ota_active = false;
                send_ota_response(OTA_NACK);
                return;
            }

            // Set new partition as boot target
            const esp_partition_t* ota_part = esp_ota_get_next_update_partition(NULL);
            esp_ota_set_boot_partition(ota_part);

            ESP_LOGI(TAG, "★ OTA CRC OK — %d bytes flashed", s_bytes_written);
            send_ota_response(OTA_ACK);
            break;
        }

        case OTA_CMD_REBOOT: {
            ESP_LOGI(TAG, "★ OTA COMPLETE — rebooting to new firmware...");
            vTaskDelay(pdMS_TO_TICKS(500));
            esp_restart();
            break;
        }

        default:
            ESP_LOGW(TAG, "Unknown OTA cmd: 0x%02X", cmd);
            send_ota_response(OTA_NACK);
            break;
    }
}
