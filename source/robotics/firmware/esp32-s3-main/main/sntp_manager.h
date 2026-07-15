/**
 * @file sntp_manager.h / sntp_manager.cpp
 * @brief SNTP Epoch Time Synchronization
 *
 * Blocks until NTP time is obtained. Provides millisecond-precision
 * epoch timestamps for MQTT telemetry stamping.
 */
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize SNTP and block until time is synchronized.
 * Must be called after WiFi is connected.
 */
void sntp_manager_init(void);

/**
 * Get current epoch time in milliseconds.
 * Returns 0 if SNTP not yet synced.
 */
int64_t sntp_manager_get_epoch_ms(void);

/**
 * Check if SNTP is currently synchronized.
 */
bool sntp_manager_is_synced(void);

#ifdef __cplusplus
}
#endif
