/**
 * useSensorTelemetryStore — Pinia Store
 *
 * Single source of truth for all 13 mobile phone sensor streams.
 * Data pipeline:
 *   [Phone: SensorLogs App]
 *   → WiFi Hotspot POST → vivo_http_mqtt_bridge.py
 *   → MQTT → hk07-core Spring Boot → WebSocket STOMP
 *   → useSensorTelemetryStore → SensorTelemetryView.vue
 *
 * Topics:
 *   /topic/hk07/sensors/imu        → IMU 9-DOF
 *   /topic/hk07/sensors/environment → Light + Barometer
 *   /topic/hk07/sensors/location    → GPS
 *   /topic/hk07/sensors/activity    → Pedometer + Activity
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// ── History ring size for all chart arrays ──────────────────────────────────
const HISTORY_SIZE = 100

// ── Type Definitions ─────────────────────────────────────────────────────────

export interface ImuSnapshot {
  orientation: { w: number; x: number; y: number; z: number }
  angular_velocity: { x: number; y: number; z: number }
  linear_acceleration: { x: number; y: number; z: number }
  magnetometer: { x: number; y: number; z: number }
  compass_heading: number
  position: { x: number; y: number; z: number }
  timestamp_ms: number
}

export interface EnvironmentSnapshot {
  ambient_light: number
  barometric_pressure: number
  pressure_delta_hpa: number
  timestamp_ms: number
}

export interface LocationSnapshot {
  latitude: number
  longitude: number
  altitude: number
  timestamp_ms: number
}

export interface ActivitySnapshot {
  pedometer_steps: number
  activity_type: string
  wrist_motion: number[]
  timestamp_ms: number
}

export interface TimestampedValue {
  value: number
  ts: number
}

// ── Default states ────────────────────────────────────────────────────────────

const DEFAULT_IMU: ImuSnapshot = {
  orientation: { w: 1, x: 0, y: 0, z: 0 },
  angular_velocity: { x: 0, y: 0, z: 0 },
  linear_acceleration: { x: 0, y: 0, z: 0 },
  magnetometer: { x: 0, y: 0, z: 0 },
  compass_heading: 0,
  position: { x: 0, y: 0, z: 0 },
  timestamp_ms: 0,
}

const DEFAULT_ENV: EnvironmentSnapshot = {
  ambient_light: 0,
  barometric_pressure: 1013.25,
  pressure_delta_hpa: 0,
  timestamp_ms: 0,
}

const DEFAULT_LOCATION: LocationSnapshot = {
  latitude: 0,
  longitude: 0,
  altitude: 0,
  timestamp_ms: 0,
}

const DEFAULT_ACTIVITY: ActivitySnapshot = {
  pedometer_steps: 0,
  activity_type: 'unknown',
  wrist_motion: [],
  timestamp_ms: 0,
}

// ── Helper ───────────────────────────────────────────────────────────────────
function pushHistory<T>(arr: T[], item: T): T[] {
  const next = [...arr, item]
  if (next.length > HISTORY_SIZE) next.shift()
  return next
}

export const useSensorTelemetryStore = defineStore('sensorTelemetry', () => {
  // ── Current Snapshots ───────────────────────────────────────────────────────
  const imu = ref<ImuSnapshot>({ ...DEFAULT_IMU })
  const environment = ref<EnvironmentSnapshot>({ ...DEFAULT_ENV })
  const location = ref<LocationSnapshot>({ ...DEFAULT_LOCATION })
  const activity = ref<ActivitySnapshot>({ ...DEFAULT_ACTIVITY })

  // ── Live status ─────────────────────────────────────────────────────────────
  const lastImuMs = ref(0)
  const lastEnvMs = ref(0)
  const lastLocMs = ref(0)
  const lastActMs = ref(0)
  const isLive = ref(false)

  // ── Rolling history arrays for charts ───────────────────────────────────────
  // IMU — accel XYZ
  const accelXHistory = ref<TimestampedValue[]>([])
  const accelYHistory = ref<TimestampedValue[]>([])
  const accelZHistory = ref<TimestampedValue[]>([])
  // IMU — gyro XYZ
  const gyroXHistory = ref<TimestampedValue[]>([])
  const gyroYHistory = ref<TimestampedValue[]>([])
  const gyroZHistory = ref<TimestampedValue[]>([])
  // IMU — compass heading
  const compassHistory = ref<TimestampedValue[]>([])
  // Environment
  const lightHistory = ref<TimestampedValue[]>([])
  const pressureHistory = ref<TimestampedValue[]>([])
  const pressureDeltaHistory = ref<TimestampedValue[]>([])
  // Activity
  const stepsHistory = ref<TimestampedValue[]>([])
  const wristMagHistory = ref<TimestampedValue[]>([])

  // ── Stale watchdog — marks isLive=false after 60 seconds of no IMU data ──────
  setInterval(() => {
    const now = Date.now()
    if (isLive.value && now - lastImuMs.value > 60000 && now - lastEnvMs.value > 60000) {
      isLive.value = false
    }
  }, 1000)

  // ── Computed sensors status per channel ──────────────────────────────────────
  const imuStatus = computed<'LIVE' | 'STALE' | 'OFFLINE'>(() => {
    const age = Date.now() - lastImuMs.value
    if (lastImuMs.value === 0) return 'OFFLINE'
    if (age < 60000) return 'LIVE'
    return 'STALE'
  })
  const envStatus = computed<'LIVE' | 'STALE' | 'OFFLINE'>(() => {
    const age = Date.now() - lastEnvMs.value
    if (lastEnvMs.value === 0) return 'OFFLINE'
    if (age < 60000) return 'LIVE'
    return 'STALE'
  })
  const locStatus = computed<'LIVE' | 'STALE' | 'OFFLINE'>(() => {
    const age = Date.now() - lastLocMs.value
    if (lastLocMs.value === 0) return 'OFFLINE'
    if (age < 60000) return 'LIVE'
    return 'STALE'
  })
  const actStatus = computed<'LIVE' | 'STALE' | 'OFFLINE'>(() => {
    const age = Date.now() - lastActMs.value
    if (lastActMs.value === 0) return 'OFFLINE'
    if (age < 60000) return 'LIVE'
    return 'STALE'
  })

  // ── Derived: Euler angles from quaternion (degrees) ──────────────────────────
  const eulerAngles = computed(() => {
    const { w, x, y, z } = imu.value.orientation
    // Roll
    const sinr = 2 * (w * x + y * z)
    const cosr = 1 - 2 * (x * x + y * y)
    const roll = Math.atan2(sinr, cosr) * (180 / Math.PI)
    // Pitch
    const sinp = 2 * (w * y - z * x)
    const pitch = Math.abs(sinp) >= 1
      ? (sinp > 0 ? 90 : -90)
      : Math.asin(sinp) * (180 / Math.PI)
    // Yaw
    const siny = 2 * (w * z + x * y)
    const cosy = 1 - 2 * (y * y + z * z)
    const yaw = Math.atan2(siny, cosy) * (180 / Math.PI)
    return {
      roll: parseFloat(roll.toFixed(1)),
      pitch: parseFloat(pitch.toFixed(1)),
      yaw: parseFloat(yaw.toFixed(1)),
    }
  })

  // ── Derived: wrist motion magnitude ─────────────────────────────────────────
  const wristMagnitude = computed(() => {
    const arr = activity.value.wrist_motion
    if (!arr.length) return 0
    const sum = arr.reduce((a, v) => a + v * v, 0)
    return parseFloat(Math.sqrt(sum).toFixed(3))
  })

  // ── Actions ──────────────────────────────────────────────────────────────────

  function updateImu(data: any) {
    const now = Date.now()
    lastImuMs.value = now
    isLive.value = true

    imu.value = {
      orientation: data.orientation ?? DEFAULT_IMU.orientation,
      angular_velocity: data.angular_velocity ?? DEFAULT_IMU.angular_velocity,
      linear_acceleration: data.linear_acceleration ?? DEFAULT_IMU.linear_acceleration,
      magnetometer: data.magnetometer ?? DEFAULT_IMU.magnetometer,
      compass_heading: data.compass_heading ?? 0,
      position: data.position ?? DEFAULT_IMU.position,
      timestamp_ms: data.header?.stamp
        ? data.header.stamp.sec * 1000 + Math.floor(data.header.stamp.nanosec / 1e6)
        : now,
    }

    const ts = now
    const la = imu.value.linear_acceleration
    const av = imu.value.angular_velocity
    accelXHistory.value = pushHistory(accelXHistory.value, { value: la.x, ts })
    accelYHistory.value = pushHistory(accelYHistory.value, { value: la.y, ts })
    accelZHistory.value = pushHistory(accelZHistory.value, { value: la.z, ts })
    gyroXHistory.value  = pushHistory(gyroXHistory.value,  { value: av.x, ts })
    gyroYHistory.value  = pushHistory(gyroYHistory.value,  { value: av.y, ts })
    gyroZHistory.value  = pushHistory(gyroZHistory.value,  { value: av.z, ts })
    compassHistory.value = pushHistory(compassHistory.value, { value: imu.value.compass_heading, ts })
  }

  function updateEnvironment(data: any) {
    const now = Date.now()
    lastEnvMs.value = now
    isLive.value = true

    environment.value = {
      ambient_light: data.ambient_light ?? 0,
      barometric_pressure: data.barometric_pressure ?? 1013.25,
      pressure_delta_hpa: data.pressure_delta_hpa ?? 0,
      timestamp_ms: data.timestamp_ms ?? now,
    }

    const ts = now
    lightHistory.value = pushHistory(lightHistory.value, { value: environment.value.ambient_light, ts })
    pressureHistory.value = pushHistory(pressureHistory.value, { value: environment.value.barometric_pressure, ts })
    pressureDeltaHistory.value = pushHistory(pressureDeltaHistory.value, { value: environment.value.pressure_delta_hpa, ts })
  }

  function updateLocation(data: any) {
    lastLocMs.value = Date.now()
    isLive.value = true
    location.value = {
      latitude: data.latitude ?? 0,
      longitude: data.longitude ?? 0,
      altitude: data.altitude ?? 0,
      timestamp_ms: data.timestamp_ms ?? Date.now(),
    }
  }

  function updateActivity(data: any) {
    const now = Date.now()
    lastActMs.value = now
    isLive.value = true

    activity.value = {
      pedometer_steps: data.pedometer_steps ?? 0,
      activity_type: data.activity_type ?? 'unknown',
      wrist_motion: Array.isArray(data.wrist_motion) ? data.wrist_motion : [],
      timestamp_ms: data.timestamp_ms ?? now,
    }

    stepsHistory.value = pushHistory(stepsHistory.value, { value: activity.value.pedometer_steps, ts: now })
    wristMagHistory.value = pushHistory(wristMagHistory.value, { value: wristMagnitude.value, ts: now })
  }

  function reset() {
    imu.value = { ...DEFAULT_IMU }
    environment.value = { ...DEFAULT_ENV }
    location.value = { ...DEFAULT_LOCATION }
    activity.value = { ...DEFAULT_ACTIVITY }
    lastImuMs.value = 0
    lastEnvMs.value = 0
    lastLocMs.value = 0
    lastActMs.value = 0
    isLive.value = false
    accelXHistory.value = []
    accelYHistory.value = []
    accelZHistory.value = []
    gyroXHistory.value = []
    gyroYHistory.value = []
    gyroZHistory.value = []
    compassHistory.value = []
    lightHistory.value = []
    pressureHistory.value = []
    pressureDeltaHistory.value = []
    stepsHistory.value = []
    wristMagHistory.value = []
  }

  return {
    // State
    imu, environment, location, activity,
    isLive, lastImuMs, lastEnvMs, lastLocMs, lastActMs,
    // History
    accelXHistory, accelYHistory, accelZHistory,
    gyroXHistory, gyroYHistory, gyroZHistory,
    compassHistory,
    lightHistory, pressureHistory, pressureDeltaHistory,
    stepsHistory, wristMagHistory,
    // Computed
    imuStatus, envStatus, locStatus, actStatus,
    eulerAngles, wristMagnitude,
    // Actions
    updateImu, updateEnvironment, updateLocation, updateActivity, reset,
    HISTORY_SIZE,
  }
})
