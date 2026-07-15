/*
 * HK-07 Data Fusion Header
 * Implements Extended Kalman Filter for sensor fusion
 */

#ifndef DATA_FUSION_H
#define DATA_FUSION_H

#include "esp_err.h"
#include "sensor_manager.h"

class DataFusion {
public:
    DataFusion();
    ~DataFusion();
    
    // Initialize EKF filter
    esp_err_t init();
    
    // Process raw sensor data and return fused data
    SensorData process(const SensorData& raw);
    
    // Reset filter state
    void reset();
    
private:
    // EKF state variables
    float state[10]; // Position (3), Velocity (3), Orientation (4 quaternion)
    float covariance[100]; // 10x10 covariance matrix
    
    // EKF prediction step
    void predict(float dt);
    
    // EKF update step
    void update(const SensorData& measurement);
    
    // Helper functions
    void normalizeQuaternion(float* q);
    void quaternionMultiply(const float* q1, const float* q2, float* result);
    void quaternionToRotationMatrix(const float* q, float* R);
};

#endif // DATA_FUSION_H
