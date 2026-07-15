/*
 * HK-07 Data Fusion Implementation
 * Implements Extended Kalman Filter for sensor fusion
 */

#include "data_fusion.h"
#include "esp_log.h"
#include <math.h>

static const char* TAG = "DataFusion";

DataFusion::DataFusion() {
    // Initialize state to zero
    for (int i = 0; i < 10; i++) {
        state[i] = 0.0f;
    }
    
    // Initialize covariance matrix (identity)
    for (int i = 0; i < 100; i++) {
        covariance[i] = 0.0f;
    }
    for (int i = 0; i < 10; i++) {
        covariance[i * 10 + i] = 1.0f;
    }
    
    // Initial orientation (identity quaternion)
    state[6] = 1.0f; // w
    state[7] = 0.0f; // x
    state[8] = 0.0f; // y
    state[9] = 0.0f; // z
}

DataFusion::~DataFusion() {
}

esp_err_t DataFusion::init() {
    ESP_LOGI(TAG, "Initializing Data Fusion (EKF)");
    
    // Initialize filter parameters
    // Process noise covariance
    float Q[10] = {0.01f, 0.01f, 0.01f,  // Position noise
                   0.1f, 0.1f, 0.1f,      // Velocity noise
                   0.01f, 0.01f, 0.01f, 0.01f}; // Orientation noise
    
    // Measurement noise covariance
    float R[9] = {0.1f, 0.1f, 0.1f,  // Accelerometer noise
                 0.05f, 0.05f, 0.05f, // Gyroscope noise
                 0.5f, 0.5f, 0.5f};   // Magnetometer noise (if available)
    
    ESP_LOGI(TAG, "Data Fusion initialized successfully");
    return ESP_OK;
}

SensorData DataFusion::process(const SensorData& raw) {
    SensorData fused = raw;
    
    // Apply EKF prediction and update
    predict(0.01f); // 10ms dt
    update(raw);
    
    // Update fused data with filter state
    fused.quaternion_w = state[6];
    fused.quaternion_x = state[7];
    fused.quaternion_y = state[8];
    fused.quaternion_z = state[9];
    
    // Normalize quaternion
    normalizeQuaternion(&fused.quaternion_w);
    
    return fused;
}

void DataFusion::predict(float dt) {
    // State transition (simplified kinematics)
    // Position += Velocity * dt
    state[0] += state[3] * dt;
    state[1] += state[4] * dt;
    state[2] += state[5] * dt;
    
    // Orientation update using gyroscope data
    // This is a simplified implementation - should use proper quaternion integration
    
    // Update covariance matrix (simplified)
    // P = F * P * F^T + Q
    for (int i = 0; i < 10; i++) {
        covariance[i * 10 + i] += 0.01f * dt; // Add process noise
    }
}

void DataFusion::update(const SensorData& measurement) {
    // Measurement update using accelerometer for orientation
    // This is a simplified implementation
    
    // Calculate expected gravity vector from current orientation
    float gravity[3] = {0.0f, 0.0f, 1.0f};
    float R[9];
    quaternionToRotationMatrix(&state[6], R);
    
    float expected_accel[3];
    expected_accel[0] = R[0] * gravity[0] + R[1] * gravity[1] + R[2] * gravity[2];
    expected_accel[1] = R[3] * gravity[0] + R[4] * gravity[1] + R[5] * gravity[2];
    expected_accel[2] = R[6] * gravity[0] + R[7] * gravity[1] + R[8] * gravity[2];
    
    // Calculate measurement residual
    float residual[3];
    residual[0] = measurement.accel_x - expected_accel[0];
    residual[1] = measurement.accel_y - expected_accel[1];
    residual[2] = measurement.accel_z - expected_accel[2];
    
    // Calculate Kalman gain (simplified)
    float K[10];
    for (int i = 0; i < 10; i++) {
        K[i] = 0.1f; // Simplified constant gain
    }
    
    // Update state
    // This is a very simplified update - proper EKF would use full matrix operations
    for (int i = 0; i < 3; i++) {
        state[i] += K[i] * residual[i];
    }
    
    // Update covariance
    // P = (I - K * H) * P
    for (int i = 0; i < 10; i++) {
        for (int j = 0; j < 10; j++) {
            covariance[i * 10 + j] *= 0.9f; // Simplified covariance update
        }
    }
}

void DataFusion::reset() {
    // Reset state to initial values
    for (int i = 0; i < 10; i++) {
        state[i] = 0.0f;
    }
    state[6] = 1.0f; // Identity quaternion
    
    // Reset covariance
    for (int i = 0; i < 100; i++) {
        covariance[i] = 0.0f;
    }
    for (int i = 0; i < 10; i++) {
        covariance[i * 10 + i] = 1.0f;
    }
}

void DataFusion::normalizeQuaternion(float* q) {
    float norm = sqrtf(q[0]*q[0] + q[1]*q[1] + q[2]*q[2] + q[3]*q[3]);
    if (norm > 0.0001f) {
        q[0] /= norm;
        q[1] /= norm;
        q[2] /= norm;
        q[3] /= norm;
    }
}

void DataFusion::quaternionMultiply(const float* q1, const float* q2, float* result) {
    result[0] = q1[0]*q2[0] - q1[1]*q2[1] - q1[2]*q2[2] - q1[3]*q2[3];
    result[1] = q1[0]*q2[1] + q1[1]*q2[0] + q1[2]*q2[3] - q1[3]*q2[2];
    result[2] = q1[0]*q2[2] - q1[1]*q2[3] + q1[2]*q2[0] + q1[3]*q2[1];
    result[3] = q1[0]*q2[3] + q1[1]*q2[2] - q1[2]*q2[1] + q1[3]*q2[0];
}

void DataFusion::quaternionToRotationMatrix(const float* q, float* R) {
    float w = q[0], x = q[1], y = q[2], z = q[3];
    
    R[0] = 1 - 2*y*y - 2*z*z;
    R[1] = 2*x*y - 2*z*w;
    R[2] = 2*x*z + 2*y*w;
    
    R[3] = 2*x*y + 2*z*w;
    R[4] = 1 - 2*x*x - 2*z*z;
    R[5] = 2*y*z - 2*x*w;
    
    R[6] = 2*x*z - 2*y*w;
    R[7] = 2*y*z + 2*x*w;
    R[8] = 1 - 2*x*x - 2*y*y;
}
