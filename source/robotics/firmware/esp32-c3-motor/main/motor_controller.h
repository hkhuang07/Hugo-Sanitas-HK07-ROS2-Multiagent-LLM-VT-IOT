/**
 * @file motor_controller.h
 * @brief HK-07 ESP32-C3 Motor Controller with Dead Man's Switch
 *
 * Safety Architecture:
 *   - Boots into safetyLocked=true — motors CANNOT move until 3 heartbeats received
 *   - FreeRTOS watchdog task monitors CAN 0x301 heartbeat from S3
 *   - If no heartbeat for 500ms → emergencyStop() fires automatically
 *   - Recovery: 3 consecutive heartbeats (300ms) required to unlock
 *
 * Hardware: TB6612FNG motor driver + MG996R servos
 * CAN: WiFi/BT DISABLED — CAN bus only communication
 *
 * Star Grounding NOTE for assembly:
 *   GND_MOTOR (TB6612FNG + DC motors) must connect directly to BMS star point
 *   NEVER daisy-chain GND_MOTOR through GND_LOGIC (S3/C3-Sensor board)
 */
#pragma once
#include <stdint.h>
#include <stdbool.h>

// ─── Pin Configuration ────────────────────────────────────────────────────────
// TB6612FNG Motor Driver
#define MOTOR_AIN1      2
#define MOTOR_AIN2      3
#define MOTOR_APWM      4
#define MOTOR_BIN1      5
#define MOTOR_BIN2      6
#define MOTOR_BPWM      7
#define MOTOR_STBY      8   // Active HIGH = enable motors

// Servo (PWM)
#define SERVO_1_GPIO    9
#define SERVO_2_GPIO    10

// CAN Bus (SN65HVD230 transceiver)
#define CAN_TX_GPIO     0
#define CAN_RX_GPIO     1

// Current sensor (ACS712)
#define CURRENT_ADC     ADC1_CHANNEL_0  // GPIO 0 on C3

// ─── Safety Constants ─────────────────────────────────────────────────────────
#define HEARTBEAT_TIMEOUT_MS    500     // 500ms — if S3 silent, E-Stop
#define RECOVERY_THRESHOLD      3       // 3 consecutive heartbeats to unlock
#define WATCHDOG_CHECK_MS       50      // Check every 50ms

// CAN Frame IDs
#define CAN_ID_MOTOR_CMD        0x100
#define CAN_ID_ESTOP            0x300
#define CAN_ID_HEARTBEAT        0x301
#define CAN_ID_OTA_CMD          0x7E0
#define CAN_ID_OTA_RESP         0x7E1

// ─── Motor Commands ───────────────────────────────────────────────────────────
typedef enum {
    MOTOR_CMD_STOP         = 0x00,
    MOTOR_CMD_MOVE_FORWARD = 0x01,
    MOTOR_CMD_MOVE_BACK    = 0x02,
    MOTOR_CMD_TURN_LEFT    = 0x03,
    MOTOR_CMD_TURN_RIGHT   = 0x04,
    MOTOR_CMD_ARM_EXTEND   = 0x10,
    MOTOR_CMD_ARM_RETRACT  = 0x11,
    MOTOR_CMD_HUG_START    = 0x20,
    MOTOR_CMD_HUG_STOP     = 0x21,
    MOTOR_CMD_ESTOP        = 0xFF,
} motor_command_t;

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize motor controller.
 * Boots into safetyLocked=true.
 * Starts watchdog FreeRTOS task at highest priority.
 */
void motor_controller_init(void);

/**
 * Set DC motor speed. Range: -100.0 to +100.0 (% of max PWM).
 * Silently ignored if safetyLocked == true.
 */
void motor_set_speed(uint8_t motor_id, float speed_pct);

/**
 * Set servo angle. Range: 0.0 to 180.0 degrees.
 * Silently ignored if safetyLocked == true.
 */
void servo_set_angle(uint8_t servo_id, float angle_deg);

/**
 * ★ Emergency stop — called by watchdog on heartbeat timeout.
 * Applies short-brake to motors, locks servos, sets STBY LOW.
 */
void motor_emergency_stop(void);

/**
 * Returns true if motors are safety-locked (no heartbeat received).
 */
bool motor_is_safety_locked(void);

#ifdef __cplusplus
}
#endif
