/**
 * @file can_bootloader.h / can_bootloader.cpp
 * @brief CAN-OTA Bootloader for ESP32-C3
 *
 * Receives firmware chunks from S3 via CAN 0x7E0 and flashes them
 * to the OTA partition. Shared between C3-Motor and C3-Sensor.
 *
 * Protocol:
 *   RX 0x7E0 [0x01] → START   : Enter flash mode, ACK 0xAA
 *   RX 0x7E0 [0x02 + 7B] → CHUNK : Write 7 bytes to flash, ACK 0xAA
 *   RX 0x7E0 [0x03 + 4B] → CRC  : Verify CRC32, ACK 0xAA or NACK 0xFF
 *   RX 0x7E0 [0x04] → REBOOT  : Set boot partition, reboot
 */
#pragma once
#include "driver/twai.h"

#ifdef __cplusplus
extern "C" {
#endif

void can_bootloader_init(void);
void can_bootloader_handle_frame(const twai_message_t* msg);

#ifdef __cplusplus
}
#endif
