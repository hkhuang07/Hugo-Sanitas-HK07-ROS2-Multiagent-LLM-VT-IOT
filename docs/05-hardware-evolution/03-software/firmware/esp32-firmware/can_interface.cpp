/*
 * HK-07 CAN Interface Implementation
 * Manages CAN bus communication using MCP2515 controller
 */

#include "can_interface.h"
#include "sensor_manager.h"
#include "esp_log.h"
#include "driver/spi_master.h"
#include <string.h>

static const char* TAG = "CANInterface";

// SPI Configuration for MCP2515
#define CAN_SPI_HOST       SPI2_HOST
#define CAN_SPI_MISO_GPIO  11
#define CAN_SPI_MOSI_GPIO  12
#define CAN_SPI_SCLK_GPIO  10
#define CAN_SPI_CS_GPIO    13
#define CAN_INT_GPIO       14

// MCP2515 Registers
#define MCP2515_RXB0CTRL   0x60
#define MCP2515_RXB1CTRL   0x70
#define MCP2515_CANCTRL    0x0F
#define MCP2515_CNF3       0x28
#define MCP2515_CNF2       0x29
#define MCP2515_CNF1       0x2A
#define MCP2515_CANINTE    0x2B
#define MCP2515_TXB0CTRL   0x30
#define MCP2515_TXB0SIDH   0x31
#define MCP2515_TXB0DLC    0x35
#define MCP2515_TXB0D0     0x36

CANInterface::CANInterface() : can_handle(nullptr) {
}

CANInterface::~CANInterface() {
    if (can_handle) {
        spi_device_remove_device((spi_device_handle_t)can_handle);
    }
}

esp_err_t CANInterface::init() {
    ESP_LOGI(TAG, "Initializing CAN Interface");
    
    // Configure SPI for MCP2515
    spi_bus_config_t buscfg = {
        .miso_io_num = CAN_SPI_MISO_GPIO,
        .mosi_io_num = CAN_SPI_MOSI_GPIO,
        .sclk_io_num = CAN_SPI_SCLK_GPIO,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = 4096,
    };
    
    spi_device_interface_config_t devcfg = {
        .command_bits = 0,
        .address_bits = 8,
        .dummy_bits = 0,
        .mode = 0, // SPI mode 0
        .duty_cycle_pos = 128,
        .cs_ena_pretrans = 0,
        .cs_ena_posttrans = 0,
        .clock_speed_hz = 8000000, // 8 MHz
        .spics_io_num = CAN_SPI_CS_GPIO,
        .flags = 0,
        .queue_size = 1,
        .pre_cb = nullptr,
        .post_cb = nullptr,
    };
    
    esp_err_t ret = spi_bus_initialize(CAN_SPI_HOST, &buscfg, SPI_DMA_CH_AUTO);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI bus initialization failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    ret = spi_bus_add_device(CAN_SPI_HOST, &devcfg, (spi_device_handle_t*)&can_handle);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "SPI device add failed: %s", esp_err_to_name(ret));
        return ret;
    }
    
    // Configure MCP2515 for 250 kbps (8 MHz crystal)
    // CNF3 = 0x05 (PHSEG2 = 3 TQ, Sample point = 87.5%)
    // CNF2 = 0x90 (BTLMODE = 1, PHSEG1 = 2 TQ, PRSEG = 2 TQ)
    // CNF1 = 0x03 (SJW = 1 TQ, BRP = 3, total TQ = 16)
    uint8_t config_cmd[] = {0x02, MCP2515_CNF3, 0x05};
    spi_transaction_t t = {
        .length = 24,
        .tx_data = (uint8_t*)config_cmd,
        .rx_data = nullptr,
    };
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    config_cmd[1] = MCP2515_CNF2;
    config_cmd[2] = 0x90;
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    config_cmd[1] = MCP2515_CNF1;
    config_cmd[2] = 0x03;
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    // Enable receive interrupts
    config_cmd[1] = MCP2515_CANINTE;
    config_cmd[2] = 0x03; // Enable RX0 and RX1 interrupts
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    // Set to normal mode
    config_cmd[1] = MCP2515_CANCTRL;
    config_cmd[2] = 0x00;
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    ESP_LOGI(TAG, "CAN Interface initialized successfully (250 kbps)");
    return ESP_OK;
}

esp_err_t CANInterface::publishTelemetry(const SensorData& data) {
    publishIMU(data);
    publishVitals(data);
    publishEnvironment(data);
    publishUltrasonic(data);
    publishStatus(data.sensor_status);
    return ESP_OK;
}

esp_err_t CANInterface::publishIMU(const SensorData& data) {
    IMUData imu_msg;
    imu_msg.accel_x = data.accel_x;
    imu_msg.accel_y = data.accel_y;
    imu_msg.accel_z = data.accel_z;
    imu_msg.gyro_x = data.gyro_x;
    imu_msg.gyro_y = data.gyro_y;
    imu_msg.gyro_z = data.gyro_z;
    imu_msg.quaternion_w = data.quaternion_w;
    imu_msg.quaternion_x = data.quaternion_x;
    imu_msg.quaternion_y = data.quaternion_y;
    imu_msg.quaternion_z = data.quaternion_z;
    imu_msg.timestamp = data.timestamp;
    
    // Load TX buffer
    uint8_t tx_cmd[14];
    tx_cmd[0] = 0x02; // Write command
    tx_cmd[1] = MCP2515_TXB0SIDH;
    tx_cmd[2] = (CAN_ID_IMU_DATA >> 3) & 0xFF;
    tx_cmd[3] = ((CAN_ID_IMU_DATA << 5) & 0xE0) | 0x08; // Extended flag + DLC
    tx_cmd[4] = sizeof(IMUData); // DLC
    
    memcpy(&tx_cmd[5], &imu_msg, sizeof(IMUData));
    
    spi_transaction_t t = {
        .length = 14 * 8,
        .tx_data = tx_cmd,
        .rx_data = nullptr,
    };
    
    // Request to send
    uint8_t rts_cmd[] = {0x02, MCP2515_TXB0CTRL, 0x08};
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    rts_cmd[1] = MCP2515_TXB0CTRL;
    spi_transaction_t t_rts = {
        .length = 24,
        .tx_data = rts_cmd,
        .rx_data = nullptr,
    };
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t_rts);
    
    return ESP_OK;
}

esp_err_t CANInterface::publishVitals(const SensorData& data) {
    VitalsData vitals_msg;
    vitals_msg.heart_rate = data.heart_rate;
    vitals_msg.spo2 = data.spo2;
    vitals_msg.temperature = data.temperature;
    vitals_msg.timestamp = data.timestamp;
    
    uint8_t tx_cmd[10];
    tx_cmd[0] = 0x02;
    tx_cmd[1] = MCP2515_TXB0SIDH;
    tx_cmd[2] = (CAN_ID_VITALS_DATA >> 3) & 0xFF;
    tx_cmd[3] = ((CAN_ID_VITALS_DATA << 5) & 0xE0) | 0x08;
    tx_cmd[4] = sizeof(VitalsData);
    
    memcpy(&tx_cmd[5], &vitals_msg, sizeof(VitalsData));
    
    spi_transaction_t t = {
        .length = 10 * 8,
        .tx_data = tx_cmd,
        .rx_data = nullptr,
    };
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    return ESP_OK;
}

esp_err_t CANInterface::publishEnvironment(const SensorData& data) {
    EnvData env_msg;
    env_msg.temperature = data.ambient_temp;
    env_msg.pressure = data.pressure;
    env_msg.humidity = data.humidity;
    env_msg.timestamp = data.timestamp;
    
    uint8_t tx_cmd[10];
    tx_cmd[0] = 0x02;
    tx_cmd[1] = MCP2515_TXB0SIDH;
    tx_cmd[2] = (CAN_ID_ENV_DATA >> 3) & 0xFF;
    tx_cmd[3] = ((CAN_ID_ENV_DATA << 5) & 0xE0) | 0x08;
    tx_cmd[4] = sizeof(EnvData);
    
    memcpy(&tx_cmd[5], &env_msg, sizeof(EnvData));
    
    spi_transaction_t t = {
        .length = 10 * 8,
        .tx_data = tx_cmd,
        .rx_data = nullptr,
    };
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    return ESP_OK;
}

esp_err_t CANInterface::publishUltrasonic(const SensorData& data) {
    UltrasonicData us_msg;
    us_msg.distance_cm = data.distance_cm;
    us_msg.timestamp = data.timestamp;
    
    uint8_t tx_cmd[7];
    tx_cmd[0] = 0x02;
    tx_cmd[1] = MCP2515_TXB0SIDH;
    tx_cmd[2] = (CAN_ID_ULTRASONIC_DATA >> 3) & 0xFF;
    tx_cmd[3] = ((CAN_ID_ULTRASONIC_DATA << 5) & 0xE0) | 0x08;
    tx_cmd[4] = sizeof(UltrasonicData);
    
    memcpy(&tx_cmd[5], &us_msg, sizeof(UltrasonicData));
    
    spi_transaction_t t = {
        .length = 7 * 8,
        .tx_data = tx_cmd,
        .rx_data = nullptr,
    };
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    return ESP_OK;
}

esp_err_t CANInterface::publishStatus(uint8_t status) {
    uint8_t tx_cmd[6];
    tx_cmd[0] = 0x02;
    tx_cmd[1] = MCP2515_TXB0SIDH;
    tx_cmd[2] = (CAN_ID_SENSOR_STATUS >> 3) & 0xFF;
    tx_cmd[3] = ((CAN_ID_SENSOR_STATUS << 5) & 0xE0) | 0x08;
    tx_cmd[4] = 1; // DLC
    tx_cmd[5] = status;
    
    spi_transaction_t t = {
        .length = 6 * 8,
        .tx_data = tx_cmd,
        .rx_data = nullptr,
    };
    spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    return ESP_OK;
}

void CANInterface::processMessages() {
    // Check for received messages
    // This is a simplified implementation - actual implementation should use interrupts
    
    uint8_t read_cmd[] = {0x03, MCP2515_RXB0CTRL};
    uint8_t rx_data[14];
    
    spi_transaction_t t = {
        .length = 16,
        .tx_data = read_cmd,
        .rx_data = rx_data,
    };
    
    esp_err_t ret = spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
    
    if (ret == ESP_OK && (rx_data[1] & 0x80)) {
        // Message received in RXB0
        uint8_t can_id = (rx_data[2] << 3) | (rx_data[3] >> 5);
        uint8_t dlc = rx_data[4] & 0x0F;
        
        if (can_id == CAN_ID_MOTOR_COMMAND && dlc == sizeof(MotorCommand)) {
            receiveMotorCommand(&rx_data[5], dlc);
        } else if (can_id == CAN_ID_SERVO_COMMAND) {
            receiveServoCommand(&rx_data[5], dlc);
        } else if (can_id == CAN_ID_PNEUMATIC_CMD) {
            receivePneumaticCommand(&rx_data[5], dlc);
        } else if (can_id == CAN_ID_EMERGENCY_STOP) {
            ESP_LOGW(TAG, "Emergency stop received!");
            // Handle emergency stop
        }
    }
}

void CANInterface::receiveMotorCommand(const uint8_t* data, uint8_t len) {
    if (len != sizeof(MotorCommand)) return;
    
    MotorCommand cmd;
    memcpy(&cmd, data, sizeof(MotorCommand));
    
    ESP_LOGI(TAG, "Motor command: L=%.2f, R=%.2f, Action=%d", 
             cmd.left_velocity, cmd.right_velocity, cmd.action_code);
    
    // Process motor command (would be sent to STM32 via CAN or handled locally)
}

void CANInterface::receiveServoCommand(const uint8_t* data, uint8_t len) {
    ESP_LOGI(TAG, "Servo command received");
    // Process servo command
}

void CANInterface::receivePneumaticCommand(const uint8_t* data, uint8_t len) {
    ESP_LOGI(TAG, "Pneumatic command received");
    // Process pneumatic command
}

esp_err_t CANInterface::sendEmergencyStop() {
    uint8_t tx_cmd[5];
    tx_cmd[0] = 0x02;
    tx_cmd[1] = MCP2515_TXB0SIDH;
    tx_cmd[2] = (CAN_ID_EMERGENCY_STOP >> 3) & 0xFF;
    tx_cmd[3] = ((CAN_ID_EMERGENCY_STOP << 5) & 0xE0) | 0x08;
    tx_cmd[4] = 0; // DLC = 0
    
    spi_transaction_t t = {
        .length = 5 * 8,
        .tx_data = tx_cmd,
        .rx_data = nullptr,
    };
    
    return spi_device_polling_transmit((spi_device_handle_t)can_handle, &t);
}
