/**
 * GlobalStreamingService — Singleton App-Level Background Streamer
 *
 * The ONLY service that polls sensor data from the backend. Runs independently
 * of Vue router navigation — data flows continuously regardless of which page
 * is active.
 *
 * Architecture:
 *   - Sensor poll: GET /api/v1/sensor-cache/latest  @ 1000ms  → vitals/imu/kinematics
 *   - Vision poll: GET /api/v1/sensor-cache/vision  @ 5000ms  → perception scan + camera status
 *
 * Store targets:
 *   vitalsStore.updateVitals()
 *   kinematicsStore.updateThermalRppg() + updateKinematics()
 *   sensorStore.updateImu() + updateEnvironment() + updateActivity()
 *   visionStore.updateVisionStatus()
 *
 * Design rules:
 *   - Single instance: created once, never destroyed while app is mounted
 *   - All interval management is internal; App.vue just calls .start() / .stop()
 *   - No connection to Vue component lifecycle (never onMounted/onUnmounted here)
 *   - Gracefully handles Python agent unavailability (stale data, no crashes)
 */

import api from './api'
import { useVitalsStore } from '../stores/vitals'
import { useKinematicsStore } from '../stores/kinematics'
import { useSensorTelemetryStore } from '../stores/sensorTelemetry'
import { useVisionStore } from '../stores/vision'
import { useAuthStore } from '../stores/auth'
import { useSafetyStore } from '../stores/safety'

let _vitalsStore: ReturnType<typeof useVitalsStore> | null = null
let _kinematicsStore: ReturnType<typeof useKinematicsStore> | null = null
let _sensorStore: ReturnType<typeof useSensorTelemetryStore> | null = null
let _visionStore: ReturnType<typeof useVisionStore> | null = null
let _authStore: ReturnType<typeof useAuthStore> | null = null
let _safetyStore: ReturnType<typeof useSafetyStore> | null = null

function resolveStores() {
  if (!_vitalsStore) {
    _vitalsStore     = useVitalsStore()
    _kinematicsStore = useKinematicsStore()
    _sensorStore     = useSensorTelemetryStore()
    _visionStore     = useVisionStore()
    _authStore       = useAuthStore()
    _safetyStore     = useSafetyStore()
  }
}

class GlobalStreamingService {
  private _sensorInterval: ReturnType<typeof setInterval> | null = null
  private _visionInterval: ReturnType<typeof setInterval> | null = null
  private _running: boolean = false

  // Diagnostics
  public sensorPollCount: number = 0
  public visionPollCount: number = 0
  public lastSensorOkMs: number = 0
  public lastVisionOkMs: number = 0

  start() {
    if (this._running) return
    this._running = true
    resolveStores()

    console.log('[GSS] GlobalStreamingService started — sensor@1000ms, vision@5000ms')

    // ── Sensor cache poll ───────────────────────────────────────────────────
    this._sensorInterval = setInterval(() => this._pollSensorCache(), 1000)

    // ── Vision cache poll ────────────────────────────────────────────────────
    // Stagger: start 2s after sensor to avoid simultaneous burst
    setTimeout(() => {
      this._pollVisionCache()
      this._visionInterval = setInterval(() => this._pollVisionCache(), 5000)
    }, 2000)
  }

  stop() {
    if (this._sensorInterval) { clearInterval(this._sensorInterval); this._sensorInterval = null }
    if (this._visionInterval) { clearInterval(this._visionInterval); this._visionInterval = null }
    this._running = false
    console.log('[GSS] GlobalStreamingService stopped.')
  }

  get isRunning() { return this._running }

  // ── Private: Sensor Cache Poll ──────────────────────────────────────────────
  private async _pollSensorCache() {
    try {
      const token = _authStore?.accessToken
      if (!token || token === 'undefined' || token === 'null') return

      const response = await api.get('/sensor-cache/latest')
      const data = response.data?.data ?? response.data

      if (!data || typeof data !== 'object') return
      // Skip error responses from Spring Boot stale-while-revalidate
      if (data.status === 'agent_unavailable' && !data.vitals) return

      this.sensorPollCount++
      this.lastSensorOkMs = Date.now()

      // 1. Update vitals store
      if (data.vitals && Object.keys(data.vitals).length > 0) {
        _vitalsStore!.updateVitals({
          deviceId: 'GlobalStream',
          heartRate: data.vitals.hr ?? data.vitals.heart_rate ?? 0,
          spo2: data.vitals.spo2 ?? 99,
          systolic: data.vitals.systolic ?? 120,
          diastolic: data.vitals.diastolic ?? 80,
          bodyTemperature: data.vitals.temp ?? data.vitals.body_temperature ?? 36.6,
          epochTimestampMs: Date.now(),
          alertLevel: data.vitals.alert_level ?? data.alertLevel ?? 'NORMAL',
        })
      }

      // 2. Update kinematics store (rPPG + thermal)
      _kinematicsStore!.updateThermalRppg({
        rppg_heart_rate: data.vitals?.hr ?? data.vitals?.heart_rate ?? 0,
        thermal_temperature: data.vitals?.temp ?? data.vitals?.body_temperature ?? 36.6,
        fever_alert: data.fever_alert ?? false,
        tracker: data.tracker,
      })

      // 3. Update sensor telemetry store (IMU/environment/activity)
      if (data.imu && Object.keys(data.imu).length > 0) {
        _kinematicsStore!.updateKinematics(data.imu)
        _sensorStore!.updateImu({
          orientation: {
            w: data.imu.qw ?? 1.0,
            x: data.imu.qx ?? 0.0,
            y: data.imu.qy ?? 0.0,
            z: data.imu.qz ?? 0.0,
          },
          angular_velocity: {
            x: data.imu.gyro_x ?? 0.0,
            y: data.imu.gyro_y ?? 0.0,
            z: data.imu.gyro_z ?? 0.0,
          },
          linear_acceleration: {
            x: data.imu.accel_x ?? 0.0,
            y: data.imu.accel_y ?? 0.0,
            z: data.imu.accel_z ?? 0.0,
          },
          magnetometer: {
            x: data.imu.mag_x ?? 0.0,
            y: data.imu.mag_y ?? 0.0,
            z: data.imu.mag_z ?? 0.0,
          },
          compass_heading: data.imu.compass_heading ?? 0,
        })
      }

      // 4. Update environment data if available
      if (data.environment) {
        _sensorStore!.updateEnvironment({
          ambient_light: data.environment.ambient_light ?? 0,
          barometric_pressure: data.environment.barometric_pressure ?? 1013.25,
          pressure_delta_hpa: data.environment.pressure_delta_hpa ?? 0,
          timestamp_ms: Date.now(),
        })
      }

      // 5. Update activity data if available
      if (data.activity) {
        _sensorStore!.updateActivity({
          pedometer_steps: data.activity.steps ?? data.vitals?.step_count ?? 0,
          activity_type: data.activity.type ?? 'unknown',
          wrist_motion: data.activity.wrist_motion ?? [],
          timestamp_ms: Date.now(),
        })
      }

      // 6. Mark stores live when daemon is healthy
      if (data.daemon_status === 'OK') {
        _kinematicsStore!.setLive?.(true)
        _vitalsStore!.isConnected = true
        _sensorStore!.isLive = true
      }

    } catch (err: any) {
      // Suppress 401 (handled by auth interceptor) and CORS errors in dev
      if (err?.response?.status === 401) return
      console.debug('[GSS][SENSOR_POLL_ERR]', err?.message ?? err)
    }
  }

  // ── Private: Vision Cache Poll ──────────────────────────────────────────────
  private async _pollVisionCache() {
    try {
      const token = _authStore?.accessToken
      if (!token || token === 'undefined' || token === 'null') return

      // Call Python FastAPI vision endpoint directly (Spring Boot proxy is optional)
      // Falls back to Spring Boot proxy if Python is accessible through it
      const response = await api.get('/sensor-cache/vision')
      const data = response.data?.data ?? response.data

      if (!data || typeof data !== 'object') return

      this.visionPollCount++
      this.lastVisionOkMs = Date.now()

      // Update vision store with full payload
      _visionStore!.updateVisionStatus(data)

      // Propagate clinical scan to safety store for HUD and alert triggering
      if (data.latest_scan) {
        _safetyStore!.applyClinical(data.latest_scan)
      }

    } catch (err: any) {
      if (err?.response?.status === 401) return
      console.debug('[GSS][VISION_POLL_ERR]', err?.message ?? err)
    }
  }

  // Expose diagnostic snapshot for DevTools
  diagnostics() {
    return {
      running: this._running,
      sensorPollCount: this.sensorPollCount,
      visionPollCount: this.visionPollCount,
      lastSensorOkMs: this.lastSensorOkMs,
      lastVisionOkMs: this.lastVisionOkMs,
    }
  }
}

// ── Singleton export ──────────────────────────────────────────────────────────
const globalStreamingService = new GlobalStreamingService()

// Expose on window for debug access: window.__GSS.diagnostics()
if (typeof window !== 'undefined') {
  (window as any).__GSS = globalStreamingService
}

export default globalStreamingService
