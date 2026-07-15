/**
 * @file motor_controller.cpp
 * @brief HK-07 ESP32-C3 Motor Controller — Dead Man's Switch Implementation
 *
 * ★ BOOT BEHAVIOR: safetyLocked = true
 *   Robot CANNOT move until 3 consecutive heartbeats from S3 received.
 *   This ensures S3 is online and SNTP is synced before motion is possible.
 *
 * ★ WATCHDOG: FreeRTOS task at configMAX_PRIORITIES-1
 *   Checks every 50ms if CAN heartbeat was received within 500ms.
 *   If timeout → emergencyStop() fires regardless of other tasks.
 */
#include "motor_controller.h"
#include "can_bootloader.h"

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/twai.h"
#include "driver/ledc.h"
#include "driver/gpio.h"
#include "driver/adc.h"
#include "esp_log.h"
#include "esp_timer.h"

#include <string.h>
#include <math.h>

static const char* TAG = "MOTOR-C3";

// ─── Safety State ─────────────────────────────────────────────────────────────
static volatile uint32_t s_last_heartbeat_ms = 0;
static volatile bool s_safety_locked = true;  // ★ Boot in LOCKED state
static volatile uint8_t s_recovery_count = 0;

// ─── PWM Configuration ────────────────────────────────────────────────────────
#define PWM_FREQ_HZ     20000   // 20kHz (inaudible)
#define PWM_RESOLUTION  LEDC_TIMER_10_BIT  // 0-1023
#define SERVO_FREQ_HZ   50      // 50Hz for servos
#define SERVO_MIN_US    500
#define SERVO_MAX_US    2500

// LEDC channels
#define CH_MOTOR_A_PWM  LEDC_CHANNEL_0
#define CH_MOTOR_B_PWM  LEDC_CHANNEL_1
#define CH_SERVO_1      LEDC_CHANNEL_2
#define CH_SERVO_2      LEDC_CHANNEL_3

// ─── Hardware Initialization ──────────────────────────────────────────────────
static void gpio_init(void)
{
    // TB6612FNG control pins
    gpio_config_t io_conf = {};
    io_conf.mode = GPIO_MODE_OUTPUT;
    io_conf.pin_bit_mask = ((1ULL << MOTOR_AIN1) | (1ULL << MOTOR_AIN2) |
                             (1ULL << MOTOR_BIN1) | (1ULL << MOTOR_BIN2) |
                             (1ULL << MOTOR_STBY));
    gpio_config(&io_conf);

    // Start in STANDBY (motors off) — fail-safe default
    gpio_set_level((gpio_num_t)MOTOR_STBY, 0);   // STBY LOW = motors disabled
    gpio_set_level((gpio_num_t)MOTOR_AIN1, 0);
    gpio_set_level((gpio_num_t)MOTOR_AIN2, 0);
    gpio_set_level((gpio_num_t)MOTOR_BIN1, 0);
    gpio_set_level((gpio_num_t)MOTOR_BIN2, 0);
}

static void pwm_init(void)
{
    // Motor PWM timer
    ledc_timer_config_t motor_timer = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = PWM_RESOLUTION,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = PWM_FREQ_HZ,
        .clk_cfg = LEDC_AUTO_CLK
    };
    ledc_timer_config(&motor_timer);

    // Motor A PWM
    ledc_channel_config_t ch_a = {
        .gpio_num = MOTOR_APWM,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = CH_MOTOR_A_PWM,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
        .hpoint = 0
    };
    ledc_channel_config(&ch_a);

    // Motor B PWM
    ledc_channel_config_t ch_b = ch_a;
    ch_b.gpio_num = MOTOR_BPWM;
    ch_b.channel = CH_MOTOR_B_PWM;
    ledc_channel_config(&ch_b);

    // Servo PWM timer (50Hz)
    ledc_timer_config_t servo_timer = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_14_BIT,
        .timer_num = LEDC_TIMER_1,
        .freq_hz = SERVO_FREQ_HZ,
        .clk_cfg = LEDC_AUTO_CLK
    };
    ledc_timer_config(&servo_timer);

    // Servo 1
    ledc_channel_config_t sv1 = {
        .gpio_num = SERVO_1_GPIO,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = CH_SERVO_1,
        .timer_sel = LEDC_TIMER_1,
        .duty = 0,
        .hpoint = 0
    };
    ledc_channel_config(&sv1);

    // Servo 2
    ledc_channel_config_t sv2 = sv1;
    sv2.gpio_num = SERVO_2_GPIO;
    sv2.channel = CH_SERVO_2;
    ledc_channel_config(&sv2);
}

static void can_init(void)
{
    twai_general_config_t g_cfg = TWAI_GENERAL_CONFIG_DEFAULT(
        (gpio_num_t)CAN_TX_GPIO, (gpio_num_t)CAN_RX_GPIO, TWAI_MODE_NORMAL);
    twai_timing_config_t t_cfg = TWAI_TIMING_CONFIG_500KBITS();
    twai_filter_config_t f_cfg = TWAI_FILTER_CONFIG_ACCEPT_ALL();

    ESP_ERROR_CHECK(twai_driver_install(&g_cfg, &t_cfg, &f_cfg));
    ESP_ERROR_CHECK(twai_start());
    ESP_LOGI(TAG, "CAN Bus ready at 500kbps");
}

// ─── Motor Control ────────────────────────────────────────────────────────────
void motor_set_speed(uint8_t motor_id, float speed_pct)
{
    if (s_safety_locked) {
        ESP_LOGD(TAG, "Motor command BLOCKED — safety locked");
        return;
    }

    // Clamp speed
    if (speed_pct > 100.0f) speed_pct = 100.0f;
    if (speed_pct < -100.0f) speed_pct = -100.0f;

    uint32_t duty = (uint32_t)(fabsf(speed_pct) / 100.0f * 1023);  // 10-bit PWM
    bool forward = (speed_pct >= 0.0f);

    if (motor_id == 0) {
        // Motor A (left wheel)
        gpio_set_level((gpio_num_t)MOTOR_AIN1, forward ? 1 : 0);
        gpio_set_level((gpio_num_t)MOTOR_AIN2, forward ? 0 : 1);
        ledc_set_duty(LEDC_LOW_SPEED_MODE, CH_MOTOR_A_PWM, duty);
        ledc_update_duty(LEDC_LOW_SPEED_MODE, CH_MOTOR_A_PWM);
    } else {
        // Motor B (right wheel)
        gpio_set_level((gpio_num_t)MOTOR_BIN1, forward ? 1 : 0);
        gpio_set_level((gpio_num_t)MOTOR_BIN2, forward ? 0 : 1);
        ledc_set_duty(LEDC_LOW_SPEED_MODE, CH_MOTOR_B_PWM, duty);
        ledc_update_duty(LEDC_LOW_SPEED_MODE, CH_MOTOR_B_PWM);
    }
}

void servo_set_angle(uint8_t servo_id, float angle_deg)
{
    if (s_safety_locked) return;

    // Clamp angle
    if (angle_deg < 0.0f) angle_deg = 0.0f;
    if (angle_deg > 180.0f) angle_deg = 180.0f;

    // Map angle to pulse width (500us - 2500us)
    uint32_t pulse_us = SERVO_MIN_US + (uint32_t)(angle_deg / 180.0f *
                        (SERVO_MAX_US - SERVO_MIN_US));

    // Convert to 14-bit duty for 50Hz timer (20ms period)
    // duty = pulse_us / 20000 * 2^14
    uint32_t duty = (uint32_t)(pulse_us * 16384UL / 20000UL);

    ledc_channel_t ch = (servo_id == 0) ? CH_SERVO_1 : CH_SERVO_2;
    ledc_set_duty(LEDC_LOW_SPEED_MODE, ch, duty);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, ch);
}

// ─── ★ Dead Man's Switch — Emergency Stop ─────────────────────────────────────
void motor_emergency_stop(void)
{
    // 1. Short-brake both motors (AINx = HIGH/HIGH = brake)
    gpio_set_level((gpio_num_t)MOTOR_AIN1, 1);
    gpio_set_level((gpio_num_t)MOTOR_AIN2, 1);
    gpio_set_level((gpio_num_t)MOTOR_BIN1, 1);
    gpio_set_level((gpio_num_t)MOTOR_BIN2, 1);
    ledc_set_duty(LEDC_LOW_SPEED_MODE, CH_MOTOR_A_PWM, 0);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, CH_MOTOR_A_PWM);
    ledc_set_duty(LEDC_LOW_SPEED_MODE, CH_MOTOR_B_PWM, 0);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, CH_MOTOR_B_PWM);

    // 2. Lock servos at current position (duty stays, just set locked)
    // Servos will hold their physical position

    // 3. Cut motor power: TB6612FNG STBY = LOW
    gpio_set_level((gpio_num_t)MOTOR_STBY, 0);

    // 4. Set safety lock
    s_safety_locked = true;
    s_recovery_count = 0;

    ESP_LOGE(TAG, "★ DEAD MAN'S SWITCH — EMERGENCY STOP ACTIVATED");
}

bool motor_is_safety_locked(void)
{
    return s_safety_locked;
}

// ─── CAN Message Processor ────────────────────────────────────────────────────
static void process_can_frame(const twai_message_t* msg)
{
    switch (msg->identifier) {

        case CAN_ID_HEARTBEAT: {
            // ★ Received heartbeat from S3
            s_last_heartbeat_ms = (uint32_t)(esp_timer_get_time() / 1000);

            if (s_safety_locked) {
                s_recovery_count++;
                ESP_LOGD(TAG, "[HB] Recovery %d/%d", s_recovery_count, RECOVERY_THRESHOLD);

                if (s_recovery_count >= RECOVERY_THRESHOLD) {
                    // ★ 3 consecutive heartbeats = safe to unlock
                    s_safety_locked = false;
                    gpio_set_level((gpio_num_t)MOTOR_STBY, 1);  // Enable motors
                    ESP_LOGI(TAG, "★ Safety UNLOCKED — motors enabled");
                }
            } else {
                // Reset recovery counter while locked is a bug — just update timestamp
            }
            break;
        }

        case CAN_ID_MOTOR_CMD: {
            if (s_safety_locked) {
                ESP_LOGD(TAG, "Motor CMD ignored — safety locked");
                break;
            }
            // Parse command: byte[0]=cmd, bytes[1-4]=param1 (float), bytes[5-8]=param2
            motor_command_t cmd = (motor_command_t) msg->data[0];
            float param1 = 0.0f, param2 = 0.0f;
            memcpy(&param1, &msg->data[1], sizeof(float));
            memcpy(&param2, &msg->data[5], sizeof(float));

            switch (cmd) {
                case MOTOR_CMD_MOVE_FORWARD:
                    motor_set_speed(0, param1);
                    motor_set_speed(1, param1);
                    break;
                case MOTOR_CMD_MOVE_BACK:
                    motor_set_speed(0, -param1);
                    motor_set_speed(1, -param1);
                    break;
                case MOTOR_CMD_TURN_LEFT:
                    motor_set_speed(0, -param1);
                    motor_set_speed(1, param1);
                    break;
                case MOTOR_CMD_TURN_RIGHT:
                    motor_set_speed(0, param1);
                    motor_set_speed(1, -param1);
                    break;
                case MOTOR_CMD_ARM_EXTEND:
                    servo_set_angle(0, param1);
                    break;
                case MOTOR_CMD_ARM_RETRACT:
                    servo_set_angle(0, 90.0f);  // neutral
                    break;
                case MOTOR_CMD_STOP:
                    motor_set_speed(0, 0.0f);
                    motor_set_speed(1, 0.0f);
                    break;
                case MOTOR_CMD_ESTOP:
                    motor_emergency_stop();
                    break;
                default:
                    break;
            }
            break;
        }

        case CAN_ID_ESTOP:
            // Broadcast E-Stop from S3
            motor_emergency_stop();
            break;

        case CAN_ID_OTA_CMD:
            // Delegate to CAN bootloader
            can_bootloader_handle_frame(msg);
            break;

        default:
            break;
    }
}

// ─── ★ Watchdog Task — FreeRTOS Highest Priority ──────────────────────────────
static void watchdog_task(void* arg)
{
    ESP_LOGI(TAG, "★ Watchdog task started at priority %d",
             uxTaskPriorityGet(NULL));

    // Initialize last heartbeat to current time to prevent immediate E-Stop on boot
    s_last_heartbeat_ms = (uint32_t)(esp_timer_get_time() / 1000);

    while (true) {
        uint32_t now_ms = (uint32_t)(esp_timer_get_time() / 1000);
        uint32_t elapsed = now_ms - s_last_heartbeat_ms;

        if (!s_safety_locked && elapsed > HEARTBEAT_TIMEOUT_MS) {
            ESP_LOGE(TAG, "★ HEARTBEAT TIMEOUT (%d ms > %d ms) — EMERGENCY STOP",
                     elapsed, HEARTBEAT_TIMEOUT_MS);
            motor_emergency_stop();
        }

        vTaskDelay(pdMS_TO_TICKS(WATCHDOG_CHECK_MS));
    }
}

// ─── CAN Receive Task ─────────────────────────────────────────────────────────
static void can_receive_task(void* arg)
{
    ESP_LOGI(TAG, "CAN receive task started");

    while (true) {
        twai_message_t msg = {};
        if (twai_receive(&msg, pdMS_TO_TICKS(100)) == ESP_OK) {
            process_can_frame(&msg);
        }
    }
}

// ─── Public Init ──────────────────────────────────────────────────────────────
void motor_controller_init(void)
{
    ESP_LOGI(TAG, "========================================");
    ESP_LOGI(TAG, "  HK-07 C3 Motor Controller Booting");
    ESP_LOGI(TAG, "  ★ Safety: LOCKED until 3 heartbeats");
    ESP_LOGI(TAG, "========================================");

    gpio_init();
    pwm_init();
    can_init();
    can_bootloader_init();

    // ★ Watchdog task at HIGHEST priority on single core (C3 is single-core)
    xTaskCreate(
        watchdog_task,
        "hk07_watchdog",
        2048,
        NULL,
        configMAX_PRIORITIES - 1,  // ★ Highest priority
        NULL
    );

    // CAN receive task
    xTaskCreate(
        can_receive_task,
        "hk07_can_rx",
        4096,
        NULL,
        configMAX_PRIORITIES - 2,
        NULL
    );

    ESP_LOGI(TAG, "★ Motor Controller READY — waiting for S3 heartbeat...");
}
