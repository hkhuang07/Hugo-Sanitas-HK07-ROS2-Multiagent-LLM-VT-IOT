/**
 * @file sntp_manager.cpp
 * @brief SNTP Epoch Time Synchronization Implementation
 */
#include "sntp_manager.h"
#include "esp_sntp.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <time.h>
#include <sys/time.h>

static const char* TAG = "SNTP";
static volatile bool s_synced = false;

static void sntp_sync_callback(struct timeval* tv)
{
    s_synced = true;
    ESP_LOGI(TAG, "★ SNTP synced — epoch: %ld.%06ld s", tv->tv_sec, tv->tv_usec);
}

void sntp_manager_init(void)
{
    esp_sntp_setoperatingmode(SNTP_OPMODE_POLL);
    esp_sntp_setservername(0, "pool.ntp.org");
    esp_sntp_setservername(1, "time.google.com");
    esp_sntp_set_time_sync_notification_cb(sntp_sync_callback);
    esp_sntp_init();

    ESP_LOGI(TAG, "Waiting for SNTP sync...");
    uint32_t retries = 0;
    while (!s_synced && retries < 60) {
        vTaskDelay(pdMS_TO_TICKS(500));
        retries++;
    }

    if (!s_synced) {
        ESP_LOGE(TAG, "SNTP sync FAILED after 30s — timestamps will be invalid!");
    }
}

int64_t sntp_manager_get_epoch_ms(void)
{
    if (!s_synced) return 0;
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return (int64_t)tv.tv_sec * 1000LL + (int64_t)tv.tv_usec / 1000LL;
}

bool sntp_manager_is_synced(void)
{
    return s_synced;
}
