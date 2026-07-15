/**
 * @file ota_manager.h / ota_manager.cpp
 * @brief OTA Update Manager
 *
 * Handles:
 *   1. WiFi HTTP OTA for S3 itself (esp_https_ota)
 *   2. CAN-OTA Proxy: receive C3 firmware via HTTP, relay chunks over CAN 0x7E0
 *
 * Usage: OTA only available when robot state == STATE_IDLE
 * Flash C3: POST http://<robot-ip>:8070/ota/c3-sensor?target=sensor
 *           POST http://<robot-ip>:8070/ota/c3-motor?target=motor
 * Flash S3: POST http://<robot-ip>:8070/ota/s3 (self-OTA)
 */
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize OTA HTTP server on specified port.
 */
void ota_manager_init(uint16_t port);

/**
 * Poll OTA state (call from protocol task loop).
 * Handles retries, CRC verification, and reboot scheduling.
 */
void ota_manager_poll(void);

#ifdef __cplusplus
}
#endif
