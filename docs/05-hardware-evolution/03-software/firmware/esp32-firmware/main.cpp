/*
 * HK-07 ESP32-S3 Sensor Hub Firmware
 * Main application entry point
 * Framework: ESP-IDF v5.0
 * MCU: ESP32-S3-WROOM-1
 */

#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_spi_flash.h"
#include "driver/i2c.h"
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_log.h"

// Custom components
#include "sensor_manager.h"
#include "can_interface.h"
#include "data_fusion.h"
#include "wifi_manager.h"

static const char* TAG = "HK07_MAIN";

// Global objects
SensorManager* g_sensorMgr = nullptr;
CANInterface* g_canIf = nullptr;
DataFusion* g_dataFusion = nullptr;
WiFiManager* g_wifiMgr = nullptr;

// Main task
void main_task(void* pvParameters) {
    ESP_LOGI(TAG, "=== HK-07 ESP32-S3 Sensor Hub Starting ===");
    
    // Initialize components
    g_sensorMgr = new SensorManager();
    g_canIf = new CANInterface();
    g_dataFusion = new DataFusion();
    g_wifiMgr = new WiFiManager();
    
    // Initialize sensor manager
    if (g_sensorMgr->init() != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize sensor manager");
        vTaskDelete(NULL);
        return;
    }
    
    // Initialize CAN interface
    if (g_canIf->init() != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize CAN interface");
        vTaskDelete(NULL);
        return;
    }
    
    // Initialize data fusion
    if (g_dataFusion->init() != ESP_OK) {
        ESP_LOGE(TAG, "Failed to initialize data fusion");
        vTaskDelete(NULL);
        return;
    }
    
    // Initialize WiFi (optional for MQTT fallback)
    g_wifiMgr->init();
    
    ESP_LOGI(TAG, "=== All components initialized successfully ===");
    
    // Main loop - 100Hz sensor reading and CAN publishing
    const TickType_t xFrequency = pdMS_TO_TICKS(10); // 10ms = 100Hz
    TickType_t xLastWakeTime = xTaskGetTickCount();
    
    while(1) {
        // Read raw sensor data
        SensorData rawData = g_sensorMgr->readSensors();
        
        // Apply sensor fusion (EKF)
        SensorData fusedData = g_dataFusion->process(rawData);
        
        // Publish to CAN bus
        g_canIf->publishTelemetry(fusedData);
        
        // Process incoming CAN commands
        g_canIf->processMessages();
        
        // Wait for next cycle
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
    }
}

extern "C" void app_main(void) {
    // Print chip information
    esp_chip_info_t chip_info;
    esp_chip_info(&chip_info);
    printf("This is ESP32-S3 chip with %d CPU cores, WiFi%s%s, ",
           chip_info.cores,
           (chip_info.features & CHIP_FEATURE_BT) ? "/BT" : "",
           (chip_info.features & CHIP_FEATURE_BLE) ? "/BLE" : "");
    printf("silicon revision %d, ", chip_info.revision);
    printf("%dMB %s flash\n", spi_flash_get_chip_size() / (1024 * 1024),
           (chip_info.features & CHIP_FEATURE_EMB_FLASH) ? "embedded" : "external");
    
    // Create main task
    xTaskCreate(main_task, "main_task", 8192, NULL, 5, NULL);
}
