/**
 * @file main.cpp — ESP32-C3 Motor Controller Entry Point
 */
#include "motor_controller.h"
#include "esp_log.h"

extern "C" void app_main(void)
{
    motor_controller_init();
    // Watchdog + CAN receive tasks handle everything
}
