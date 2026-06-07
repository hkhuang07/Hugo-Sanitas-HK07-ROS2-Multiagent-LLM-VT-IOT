/**
 * useTelemetryStore — Pinia Store
 *
 * Single source of truth for real-time biometric telemetry.
 *
 * Data pipeline contract:
 *   MockSensorService ──┐
 *   WebSocketService  ──┼──► useTelemetryStore ──► UI components
 *   REST polling      ──┘
 *
 * Switching to a real stream = call store.update() from WebSocket handler.
 * UI components (VitalSignsMonitor, EcgWaveform) NEVER import service code.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface TelemetrySnapshot {
  deviceId: string
  heartRate: number
  spo2: number
  systolic: number
  diastolic: number
  bodyTemperature: number
  alertLevel: 'NORMAL' | 'WARNING' | 'CRITICAL' | 'STROKE'
  epochTimestampMs: number
  /** Pre-computed ECG waveform sample array (normalized -0.2 … 1.0) */
  ecgPoints: number[]
}

/** How many ECG snapshots to keep in history ring for the canvas */
const ECG_RING_SIZE = 200

const DEFAULT_SNAPSHOT: TelemetrySnapshot = {
  deviceId: '',
  heartRate: 0,
  spo2: 0,
  systolic: 0,
  diastolic: 0,
  bodyTemperature: 0,
  alertLevel: 'NORMAL',
  epochTimestampMs: 0,
  ecgPoints: Array(ECG_RING_SIZE).fill(0),
}

export const useTelemetryStore = defineStore('telemetry', () => {
  // ── State ──────────────────────────────────────────────────────────────────
  const current  = ref<TelemetrySnapshot>({ ...DEFAULT_SNAPSHOT })
  const isMock   = ref(false)   // Deactivated mock telemetry completely

  /** Source label for UI display */
  const sourceLabel = computed(() => isMock.value ? 'OFFLINE_SIM' : 'STREAMING')

  // ── Derived vitals status ─────────────────────────────────────────────────
  const alertLevel = computed(() => current.value.alertLevel)
  const isEmergency = computed(() =>
    alertLevel.value === 'CRITICAL' || alertLevel.value === 'STROKE'
  )

  const hrStatus = computed<'normal' | 'warning' | 'critical'>(() => {
    const hr = current.value.heartRate
    if (!hr) return 'normal'
    if (hr < 50 || hr > 120) return 'critical'
    if (hr < 60 || hr > 100) return 'warning'
    return 'normal'
  })
  const spo2Status = computed<'normal' | 'warning' | 'critical'>(() => {
    const s = current.value.spo2
    if (!s) return 'normal'
    if (s < 90) return 'critical'
    if (s < 94) return 'warning'
    return 'normal'
  })
  const bpStatus = computed<'normal' | 'warning' | 'critical'>(() => {
    const sys = current.value.systolic
    if (!sys) return 'normal'
    if (sys > 140 || sys < 90) return 'critical'
    return 'normal'
  })
  const tempStatus = computed<'normal' | 'warning' | 'critical'>(() => {
    const t = current.value.bodyTemperature
    if (!t) return 'normal'
    if (t > 38.5 || t < 35.5) return 'critical'
    if (t > 37.5 || t < 36.0) return 'warning'
    return 'normal'
  })

  // ── Actions ───────────────────────────────────────────────────────────────
  /**
   * Called by MockSensorService OR real WebSocket adapter.
   * Identical call signature — no UI changes needed when swapping data source.
   */
  function update(snapshot: TelemetrySnapshot) {
    current.value = snapshot
  }

  /** Mark whether data is from mock or live source (drives STREAMING / OFFLINE_SIM badge) */
  function setLive(live: boolean) {
    isMock.value = false // Hardcoded to false
  }

  function reset() {
    current.value = { ...DEFAULT_SNAPSHOT }
    isMock.value = false // Hardcoded to false
  }

  return {
    current,
    isMock,
    sourceLabel,
    alertLevel,
    isEmergency,
    hrStatus,
    spo2Status,
    bpStatus,
    tempStatus,
    update,
    setLive,
    reset,
    ECG_RING_SIZE,
  }
})
