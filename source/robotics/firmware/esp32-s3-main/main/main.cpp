/**
 * @file main.cpp
 * @brief HK-07 ESP32-S3 Entry Point
 */
#include "hk07_main_controller.h"
#include "esp_log.h"

extern "C" void app_main(void)
{
    hk07_controller_init();
    // All work is done in pinned FreeRTOS tasks
    // app_main can exit — tasks keep running
}
