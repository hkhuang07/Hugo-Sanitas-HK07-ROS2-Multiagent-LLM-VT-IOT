/**
 * @file can_interface.cpp
 * @brief TWAI CAN Bus Driver Implementation for ESP32-S3
 */
#include "can_interface.h"
#include "esp_log.h"

static const char* TAG = "CAN";

void can_interface_init(int tx_gpio, int rx_gpio, uint32_t speed_bps)
{
    twai_general_config_t g_config = TWAI_GENERAL_CONFIG_DEFAULT(
        (gpio_num_t)tx_gpio, (gpio_num_t)rx_gpio, TWAI_MODE_NORMAL);

    // Choose timing based on speed
    twai_timing_config_t t_config;
    if (speed_bps == 500000) {
        t_config = TWAI_TIMING_CONFIG_500KBITS();
    } else if (speed_bps == 250000) {
        t_config = TWAI_TIMING_CONFIG_250KBITS();
    } else {
        t_config = TWAI_TIMING_CONFIG_500KBITS(); // default
    }

    // Accept all frames (filtering done in application layer)
    twai_filter_config_t f_config = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    ESP_ERROR_CHECK(twai_driver_install(&g_config, &t_config, &f_config));
    ESP_ERROR_CHECK(twai_start());
    ESP_LOGI(TAG, "★ CAN Bus ready at %d kbps (TX: GPIO%d, RX: GPIO%d)",
             speed_bps / 1000, tx_gpio, rx_gpio);
}

esp_err_t can_interface_transmit(twai_message_t* msg, TickType_t ticks_to_wait)
{
    return twai_transmit(msg, ticks_to_wait);
}

esp_err_t can_interface_receive(twai_message_t* msg, TickType_t ticks_to_wait)
{
    return twai_receive(msg, ticks_to_wait);
}
