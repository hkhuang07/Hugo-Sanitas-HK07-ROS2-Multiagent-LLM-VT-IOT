/**
 * @file can_interface.h / can_interface.cpp
 * @brief CAN Bus (TWAI) interface for ESP32-S3
 *
 * Wraps ESP-IDF TWAI driver with HK-07 specific configuration.
 * Star Grounding note: ensure GND_LOGIC is separate from GND_MOTOR at BMS star point.
 */
#pragma once
#include <stdint.h>
#include "driver/twai.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize CAN (TWAI) bus.
 * @param tx_gpio  GPIO for CAN TX (ESP32-S3: GPIO 43 recommended)
 * @param rx_gpio  GPIO for CAN RX (ESP32-S3: GPIO 44 recommended)
 * @param speed_bps  Bus speed in bps (use 500000 for 500 kbps)
 */
void can_interface_init(int tx_gpio, int rx_gpio, uint32_t speed_bps);

/**
 * Transmit a CAN frame. Non-blocking (ticks_to_wait = 0 for ISR-safe).
 */
esp_err_t can_interface_transmit(twai_message_t* msg, TickType_t ticks_to_wait);

/**
 * Receive a CAN frame. Blocks for up to ticks_to_wait.
 */
esp_err_t can_interface_receive(twai_message_t* msg, TickType_t ticks_to_wait);

#ifdef __cplusplus
}
#endif
