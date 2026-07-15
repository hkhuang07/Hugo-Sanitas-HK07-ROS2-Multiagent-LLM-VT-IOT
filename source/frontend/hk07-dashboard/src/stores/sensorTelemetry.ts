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
  magnetometer: { x: number | null; y: number | null; z: number | null }
  compass_heading: number | null
  position: { x: number; y: number; z: number }
  timestamp_ms: number
}

export interface EnvironmentSnapshot {
  ambient_light: number
  // null = sensor not available on this hardware (e.g. Vivo phone has no barometer)
  barometric_pressure: number | null
  // null = cannot compute delta when barometer absent
  pressure_delta_hpa: number | null
  battery_level: number | null
  battery_temp: number | null
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

export interface HearingSnapshot {
  frequency: string
  intensity: number
  intensity_label: string
  rhythm: string
  direction: string
  transcript: string
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
  magnetometer: { x: null, y: null, z: null },
  compass_heading: null,
  position: { x: 0, y: 0, z: 0 },
  timestamp_ms: 0,
}

const DEFAULT_ENV: EnvironmentSnapshot = {
  ambient_light: 0,
  barometric_pressure: null,  // null = no barometer hardware
  pressure_delta_hpa: null,   // null = no barometer hardware
  battery_level: null as number | null,
  battery_temp: null as number | null,
  timestamp_ms: 0,
}

const DEFAULT_LOCATION: LocationSnapshot = {
  latitude: 10.3955,
  longitude: 105.4213,
  altitude: 0,
  timestamp_ms: 0,
}

const DEFAULT_ACTIVITY: ActivitySnapshot = {
  pedometer_steps: 0,
  activity_type: 'unknown',
  wrist_motion: [],
  timestamp_ms: 0,
}

const DEFAULT_HEARING: HearingSnapshot = {
  frequency: 'trầm',
  intensity: -120,
  intensity_label: 'im lặng',
  rhythm: 'chậm',
  direction: 'xa',
  transcript: '',
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
  const hearing = ref<HearingSnapshot>({ ...DEFAULT_HEARING })

  // ── Live status ─────────────────────────────────────────────────────────────
  const lastImuMs = ref(0)
  const lastEnvMs = ref(0)
  const lastLocMs = ref(0)
  const lastActMs = ref(0)
  const lastHearingMs = ref(0)
  const isLive = ref(false)

  const isImuSimulated = ref(false)
  const isEnvSimulated = ref(false)
  const isLocSimulated = ref(false)
  const isActSimulated = ref(false)
  const isHearingSimulated = ref(false)

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

  // ── Stale watchdog — resets channel values to defaults when they go stale ──────
  setInterval(() => {
    const now = Date.now()
    const STALE_TIMEOUT = 15000  // 15 seconds
    const GPS_TIMEOUT = 60000    // 60 seconds

    if (lastImuMs.value !== 0 && now - lastImuMs.value > STALE_TIMEOUT) {
      imu.value = { ...DEFAULT_IMU }
    }
    if (lastEnvMs.value !== 0 && now - lastEnvMs.value > STALE_TIMEOUT) {
      environment.value = { ...DEFAULT_ENV }
    }
    if (lastLocMs.value !== 0 && now - lastLocMs.value > GPS_TIMEOUT) {
      location.value = { ...DEFAULT_LOCATION }
    }
    if (lastActMs.value !== 0 && now - lastActMs.value > STALE_TIMEOUT) {
      activity.value = { ...DEFAULT_ACTIVITY }
    }
    if (lastHearingMs.value !== 0 && now - lastHearingMs.value > STALE_TIMEOUT) {
      hearing.value = { ...DEFAULT_HEARING }
    }

    if (isLive.value && now - lastImuMs.value > 30000 && now - lastEnvMs.value > 30000) {
      isLive.value = false
    }
  }, 1000)

  // ── Computed sensors status per channel ──────────────────────────────────────
  const imuStatus = computed<'LIVE' | 'SIMULATED' | 'STALE' | 'OFFLINE'>(() => {
    const age = Date.now() - lastImuMs.value
    if (lastImuMs.value === 0) return 'OFFLINE'
    if (age > 15000) return 'STALE'
    return isImuSimulated.value ? 'SIMULATED' : 'LIVE'
  })
  const envStatus = computed<'LIVE' | 'SIMULATED' | 'STALE' | 'OFFLINE'>(() => {
    const age = Date.now() - lastEnvMs.value
    if (lastEnvMs.value === 0) return 'OFFLINE'
    if (age > 15000) return 'STALE'
    return isEnvSimulated.value ? 'SIMULATED' : 'LIVE'
  })
  const locStatus = computed<'LIVE' | 'SIMULATED' | 'STALE' | 'OFFLINE'>(() => {
    const age = Date.now() - lastLocMs.value
    if (lastLocMs.value === 0) return 'OFFLINE'
    if (age > 60000) return 'STALE'
    return isLocSimulated.value ? 'SIMULATED' : 'LIVE'
  })
  const actStatus = computed<'LIVE' | 'SIMULATED' | 'STALE' | 'OFFLINE'>(() => {
    const age = Date.now() - lastActMs.value
    if (lastActMs.value === 0) return 'OFFLINE'
    if (age > 15000) return 'STALE'
    return isActSimulated.value ? 'SIMULATED' : 'LIVE'
  })
  const hearingStatus = computed<'LIVE' | 'SIMULATED' | 'STALE' | 'OFFLINE'>(() => {
    const age = Date.now() - lastHearingMs.value
    if (lastHearingMs.value === 0) return 'OFFLINE'
    if (age > 15000) return 'STALE'
    return isHearingSimulated.value ? 'SIMULATED' : 'LIVE'
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
    isImuSimulated.value = data.is_simulated ?? false

    // Magnetometer: phone may send {x:0,y:0,z:0} when sensor is in duty-cycle off state.
    // Keep last known valid magnetometer values to prevent flip-flopping to null/NO HW.
    const rawMag = data.magnetometer ?? DEFAULT_IMU.magnetometer
    const magIsValid = rawMag && (rawMag.x !== 0 || rawMag.y !== 0 || rawMag.z !== 0 || rawMag.x === null)
    const resolvedMag = magIsValid
      ? rawMag
      : (imu.value.magnetometer.x !== null ? imu.value.magnetometer : DEFAULT_IMU.magnetometer)

    // compass_heading: preserve previous value when bridge sends null/0 (no new reading).
    // A null from bridge means the compass parser found no valid magneticBearing this cycle.
    const incomingHeading = data.compass_heading
    const resolvedHeading = (incomingHeading !== null && incomingHeading !== undefined && incomingHeading !== 0)
      ? incomingHeading
      : imu.value.compass_heading  // keep last known valid heading

    // Resolve orientation schema: supports both nested and flat layouts, with fallback to last known valid values
    const orient = data.orientation || {}
    const isNum = (v: any) => v !== undefined && v !== null && !isNaN(Number(v))
    const resolvedOrient = {
      w: isNum(data.qw) ? Number(data.qw) : (isNum(orient.w) ? Number(orient.w) : (isNum(orient.qw) ? Number(orient.qw) : imu.value.orientation.w)),
      x: isNum(data.qx) ? Number(data.qx) : (isNum(orient.x) ? Number(orient.x) : (isNum(orient.qx) ? Number(orient.qx) : imu.value.orientation.x)),
      y: isNum(data.qy) ? Number(data.qy) : (isNum(orient.y) ? Number(orient.y) : (isNum(orient.qy) ? Number(orient.qy) : imu.value.orientation.y)),
      z: isNum(data.qz) ? Number(data.qz) : (isNum(orient.z) ? Number(orient.z) : (isNum(orient.qz) ? Number(orient.qz) : imu.value.orientation.z)),
    }

    imu.value = {
      orientation: resolvedOrient,
      angular_velocity: data.angular_velocity ?? DEFAULT_IMU.angular_velocity,
      linear_acceleration: data.linear_acceleration ?? DEFAULT_IMU.linear_acceleration,
      magnetometer: resolvedMag,
      compass_heading: resolvedHeading,
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
    
    // Only push compass history when we have a valid non-zero heading
    if (imu.value.compass_heading !== null && imu.value.compass_heading !== 0) {
      compassHistory.value = pushHistory(compassHistory.value, { value: imu.value.compass_heading, ts })
    }
  }

  function updateEnvironment(data: any) {
    const now = Date.now()
    lastEnvMs.value = now
    isLive.value = true
    isEnvSimulated.value = data.is_simulated ?? false

    // barometric_pressure arrives as null from bridge when phone has no barometer hardware.
    // We preserve null rather than defaulting to 1013.25 to avoid displaying fake data.
    const baro = data.barometric_pressure !== undefined ? data.barometric_pressure : null
    const baroδ = data.pressure_delta_hpa !== undefined ? data.pressure_delta_hpa : null

    // Keep last known battery level and temp to prevent flip-flopping to defaults
    const batLvl = (data.battery_level !== undefined && data.battery_level !== null)
      ? data.battery_level
      : environment.value.battery_level
    
    const batTemp = (data.battery_temp !== undefined && data.battery_temp !== null)
      ? data.battery_temp
      : environment.value.battery_temp

    environment.value = {
      ambient_light: data.ambient_light ?? 0,
      barometric_pressure: baro,
      pressure_delta_hpa: baroδ,
      battery_level: batLvl,
      battery_temp: batTemp,
      timestamp_ms: data.timestamp_ms ?? now,
    }

    const ts = now
    lightHistory.value = pushHistory(lightHistory.value, { value: environment.value.ambient_light, ts })
    // Only chart barometric data when we have a real sensor reading (not null)
    if (baro !== null) {
      pressureHistory.value = pushHistory(pressureHistory.value, { value: baro, ts })
    }
    if (baroδ !== null) {
      pressureDeltaHistory.value = pushHistory(pressureDeltaHistory.value, { value: baroδ, ts })
    }
  }

  function updateLocation(data: any) {
    lastLocMs.value = Date.now()
    isLive.value = true
    isLocSimulated.value = data.is_simulated ?? false
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
    isActSimulated.value = data.is_simulated ?? false

    activity.value = {
      pedometer_steps: data.pedometer_steps ?? 0,
      activity_type: data.activity_type ?? 'unknown',
      wrist_motion: Array.isArray(data.wrist_motion) ? data.wrist_motion : [],
      timestamp_ms: data.timestamp_ms ?? now,
    }

    stepsHistory.value = pushHistory(stepsHistory.value, { value: activity.value.pedometer_steps, ts: now })
    wristMagHistory.value = pushHistory(wristMagHistory.value, { value: wristMagnitude.value, ts: now })
  }

  function updateHearing(data: any) {
    const now = Date.now()
    lastHearingMs.value = now
    isLive.value = true
    isHearingSimulated.value = data.is_simulated ?? false
    hearing.value = {
      frequency: data.frequency ?? DEFAULT_HEARING.frequency,
      intensity: data.intensity ?? DEFAULT_HEARING.intensity,
      intensity_label: data.intensity_label ?? DEFAULT_HEARING.intensity_label,
      rhythm: data.rhythm ?? DEFAULT_HEARING.rhythm,
      direction: data.direction ?? DEFAULT_HEARING.direction,
      transcript: data.transcript ?? DEFAULT_HEARING.transcript,
      timestamp_ms: data.timestamp_ms ?? now
    }
  }

  function reset() {
    imu.value = { ...DEFAULT_IMU }
    environment.value = { ...DEFAULT_ENV }
    location.value = { ...DEFAULT_LOCATION }
    activity.value = { ...DEFAULT_ACTIVITY }
    hearing.value = { ...DEFAULT_HEARING }
    lastImuMs.value = 0
    lastEnvMs.value = 0
    lastLocMs.value = 0
    lastActMs.value = 0
    lastHearingMs.value = 0
    isLive.value = false
    isImuSimulated.value = false
    isEnvSimulated.value = false
    isLocSimulated.value = false
    isActSimulated.value = false
    isHearingSimulated.value = false
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
    imu, environment, location, activity, hearing,
    isLive, lastImuMs, lastEnvMs, lastLocMs, lastActMs, lastHearingMs,
    isImuSimulated, isEnvSimulated, isLocSimulated, isActSimulated, isHearingSimulated,
    // History
    accelXHistory, accelYHistory, accelZHistory,
    gyroXHistory, gyroYHistory, gyroZHistory,
    compassHistory,
    lightHistory, pressureHistory, pressureDeltaHistory,
    stepsHistory, wristMagHistory,
    // Computed
    imuStatus, envStatus, locStatus, actStatus, hearingStatus,
    eulerAngles, wristMagnitude,
    // Actions
    updateImu, updateEnvironment, updateLocation, updateActivity, updateHearing, reset,
    HISTORY_SIZE,
  }
})
