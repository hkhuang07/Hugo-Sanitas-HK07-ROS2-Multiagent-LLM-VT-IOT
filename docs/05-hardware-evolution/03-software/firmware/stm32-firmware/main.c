/*
 * HK-07 STM32H7 Motor Controller Firmware
 * Main application entry point
 * Framework: STM32CubeIDE + HAL Library
 * MCU: STM32H743VIT6
 */

#include "main.h"
#include "motor_control.h"
#include "servo_control.h"
#include "can_handler.h"
#include "encoder_reader.h"
#include "pneumatic_ctrl.h"
#include "safety_monitor.h"
#include <stdio.h>

// Global objects
MotorController left_motor;
MotorController right_motor;
ServoController servos;
CANHandler can_handler;
EncoderReader encoders;
PneumaticController pneumatic;
SafetyMonitor safety;

// System status
volatile uint8_t system_running = 1;
volatile uint8_t emergency_stop = 0;

int main(void) {
    // HAL initialization
    HAL_Init();
    
    // System clock configuration
    SystemClock_Config();
    
    // Initialize peripherals
    MX_GPIO_Init();
    MX_TIM2_Init();  // Encoder 1
    MX_TIM3_Init();  // Encoder 2
    MX_TIM4_Init();  // PWM for motors
    MX_TIM5_Init();  // PWM for servos
    MX_CAN1_Init();
    MX_I2C1_Init();  // For servo controller
    MX_ADC1_Init();  // For current sensing
    
    printf("=== HK-07 STM32H7 Motor Controller Starting ===\n");
    
    // Initialize subsystems
    MotorControl_Init(&left_motor, 1);
    MotorControl_Init(&right_motor, 2);
    Servo_Init(&servos);
    CAN_Init(&can_handler);
    Encoder_Init(&encoders);
    Pneumatic_Init(&pneumatic);
    Safety_Init(&safety);
    
    printf("=== All subsystems initialized ===\n");
    
    // Main control loop (50Hz)
    uint32_t last_tick = HAL_GetTick();
    const uint32_t loop_period = 20; // 20ms = 50Hz
    
    while (system_running) {
        uint32_t current_tick = HAL_GetTick();
        
        if (current_tick - last_tick >= loop_period) {
            last_tick = current_tick;
            
            // Check emergency stop
            if (emergency_stop) {
                MotorControl_EmergencyStop();
                Pneumatic_EmergencyDeflate();
                continue;
            }
            
            // Process CAN messages
            CAN_ProcessMessages(&can_handler);
            
            // Read encoders
            float left_vel = Encoder_ReadVelocity(&encoders, 1);
            float right_vel = Encoder_ReadVelocity(&encoders, 2);
            
            // Update motor control (50Hz)
            MotorControl_Update(&left_motor, left_vel, 0.02f);
            MotorControl_Update(&right_motor, right_vel, 0.02f);
            
            // Update servos (50Hz)
            Servo_UpdateAll(&servos);
            
            // Monitor safety
            Safety_Check(&safety);
            
            // Publish status via CAN
            CAN_PublishStatus(&can_handler);
        }
    }
    
    printf("=== System shutdown ===\n");
    return 0;
}

// Error handler
void Error_Handler(void) {
    printf("=== ERROR: System halted ===\n");
    while (1) {
        HAL_Delay(1000);
    }
}
