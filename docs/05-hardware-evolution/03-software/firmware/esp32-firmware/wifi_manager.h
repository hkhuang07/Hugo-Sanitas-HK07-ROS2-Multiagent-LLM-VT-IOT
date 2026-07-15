/*
 * HK-07 WiFi Manager Header
 * Manages WiFi connectivity for MQTT fallback communication
 */

#ifndef WIFI_MANAGER_H
#define WIFI_MANAGER_H

#include "esp_err.h"

class WiFiManager {
public:
    WiFiManager();
    ~WiFiManager();
    
    // Initialize WiFi
    esp_err_t init();
    
    // Connect to WiFi network
    esp_err_t connect(const char* ssid, const char* password);
    
    // Check connection status
    bool isConnected();
    
    // Disconnect
    esp_err_t disconnect();
    
private:
    bool connected;
    void wifi_event_handler(void* arg, esp_event_base_t event_base,
                            int32_t event_id, void* event_data);
};

#endif // WIFI_MANAGER_H
