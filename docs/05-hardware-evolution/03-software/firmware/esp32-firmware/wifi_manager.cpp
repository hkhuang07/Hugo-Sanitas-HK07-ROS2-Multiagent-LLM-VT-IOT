/*
 * HK-07 WiFi Manager Implementation
 * Manages WiFi connectivity for MQTT fallback communication
 */

#include "wifi_manager.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_wifi.h"
#include "esp_netif.h"

static const char* TAG = "WiFiManager";

WiFiManager::WiFiManager() : connected(false) {
}

WiFiManager::~WiFiManager() {
    disconnect();
}

esp_err_t WiFiManager::init() {
    ESP_LOGI(TAG, "Initializing WiFi Manager");
    
    // Initialize TCP/IP stack
    esp_netif_init();
    
    // Initialize event loop
    esp_event_loop_create_default();
    
    // Create default WiFi station
    esp_netif_create_default_wifi_sta();
    
    // Initialize WiFi
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    esp_err_t ret = esp_wifi_init(&cfg);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "WiFi initialization failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Register event handlers
    esp_event_handler_instance_register(WIFI_EVENT,
                                        ESP_EVENT_ANY_ID,
                                        &WiFiManager::wifi_event_handler,
                                        this,
                                        nullptr);
    
    ESP_LOGI(TAG, "WiFi Manager initialized successfully");
    return ESP_OK;
}

esp_err_t WiFiManager::connect(const char* ssid, const char* password) {
    ESP_LOGI(TAG, "Connecting to WiFi: %s", ssid);
    
    // Configure WiFi station
    wifi_config_t wifi_config = {};
    strncpy((char*)wifi_config.sta.ssid, ssid, sizeof(wifi_config.sta.ssid));
    strncpy((char*)wifi_config.sta.password, password, sizeof(wifi_config.sta.password));
    
    esp_err_t ret = esp_wifi_set_mode(WIFI_MODE_STA);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set WiFi mode: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ret = esp_wifi_set_config(WIFI_IF_STA, &wifi_config);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to set WiFi config: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ret = esp_wifi_start();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to start WiFi: %s", esp_err_to_name(ret));
        return ret;
    }
    
    return ESP_OK;
}

bool WiFiManager::isConnected() {
    return connected;
}

esp_err_t WiFiManager::disconnect() {
    ESP_LOGI(TAG, "Disconnecting WiFi");
    
    esp_err_t ret = esp_wifi_stop();
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to stop WiFi: %s", esp_err_to_name(ret));
        return ret;
    }
    
    connected = false;
    return ESP_OK;
}

void WiFiManager::wifi_event_handler(void* arg, esp_event_base_t event_base,
                                      int32_t event_id, void* event_data) {
    WiFiManager* mgr = static_cast<WiFiManager*>(arg);
    
    if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_START) {
        ESP_LOGI(TAG, "WiFi started, connecting...");
        esp_wifi_connect();
    } else if (event_base == WIFI_EVENT && event_id == WIFI_EVENT_STA_DISCONNECTED) {
        ESP_LOGW(TAG, "WiFi disconnected, reconnecting...");
        mgr->connected = false;
        esp_wifi_connect();
    } else if (event_base == IP_EVENT && event_id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t* event = (ip_event_got_ip_t*)event_data;
        ESP_LOGI(TAG, "Got IP: " IPSTR, IP2STR(&event->ip_info.ip));
        mgr->connected = true;
    }
}
