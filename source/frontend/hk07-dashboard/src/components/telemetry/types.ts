/**
 * HUGO BIO-TELEMETRY PAYLOAD TYPE DEFINITIONS
 * Cyber-cinematic real-time sensor fusion interface
 */

export interface RawAccelerometerVector {
  x: number;
  y: number;
  z: number;
  magnitude?: number;
}

export interface SensorStatus {
  hrValid: boolean;
  spo2Valid?: boolean;
  lightValid?: boolean;
  pressureValid?: boolean;
  yawValid?: boolean;
  accelValid?: boolean;
}

export interface RobotTelemetry {
  messageId: string;
  sessionId: string;
  deviceId: string;
  // Clinical Vitals (Part A)
  hr: number;
  spO2: number;
  // Environmental Sensors (Part B)
  light: number;
  pressure: number;
  pressureDelta?: number;
  // Spatial Safety - 9-DoF IMU (Part C)
  yaw: number;
  pitch?: number;
  roll?: number;
  // Emergency Location (Part D)
  latitude?: number;
  longitude?: number;
  altitude?: number;
  // Activity Metrics (Part E)
  steps?: number;
  activityType?: string;
  // Fall Detection State
  fallState: boolean;
  fallConfidence?: number;
  gForceMagnitude?: number;
  // Raw Accelerometer Data
  rawAccel: RawAccelerometerVector;
  // Hardware Status
  sensorStatus: SensorStatus;
  // Timestamp
  timestamp: number;
}

export interface WidgetTheme {
  backgroundColor: string;      // #000000
  textPrimary: string;          // #F0F8FF
  borderCyan: string;           // #00FFCC
  successGreen: string;         // #00FF66
  warningOrange: string;        // #FF6600
  dangerRed: string;            // #FF3333
}

export const HUGO_THEME: WidgetTheme = {
  backgroundColor: '#000000',
  textPrimary: '#F0F8FF',
  borderCyan: '#00FFCC',
  successGreen: '#00FF66',
  warningOrange: '#FF6600',
  dangerRed: '#FF3333'
};

export const BAYMAX_THEME = HUGO_THEME;
