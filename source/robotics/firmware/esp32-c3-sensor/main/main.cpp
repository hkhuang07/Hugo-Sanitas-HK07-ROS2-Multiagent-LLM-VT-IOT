/**
 * @file main.cpp — ESP32-C3 Sensor Hub Entry Point
 */
#include "sensor_hub.h"
#include "esp_log.h"

extern "C" void app_main(void)
{
    sensor_hub_init();
}
