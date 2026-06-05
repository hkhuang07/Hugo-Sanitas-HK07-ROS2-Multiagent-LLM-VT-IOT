/**
 * MockSensorService.ts
 *
 * Generates continuous mock telemetry data for VITAL_SIGNS_MONITOR and
 * VITAL_STREAM_ECG when no real WebSocket stream is available.
 *
 * Architecture contract:
 *  - This service writes ONLY to useTelemetryStore.
 *  - UI components read ONLY from useTelemetryStore.
 *  - Swapping to a real WebSocket stream = replace this file's `start()` body.
 *    Zero UI changes required.
 *
 * Data model:
 *  - HR:   60–100 BPM, slow sinusoidal drift + gaussian noise
 *  - SpO2: 96–100%, very slow drift
 *  - BP:   110–130 systolic, 70–85 diastolic, slow random walk
 *  - Temp: 36.2–37.2°C, slow drift
 *  - ECG:  Pre-computed Lead-II morphology points (P-QRS-T)
 */

import { useTelemetryStore } from '../stores/telemetry'

// ─── ECG Morphology Constants ────────────────────────────────────────────────
const P_AMP  = 0.08
const Q_AMP  = -0.10
const R_AMP  = 1.00
const S_AMP  = -0.15
const T_AMP  = 0.25
const P_DUR  = 0.08
const PQ_DUR = 0.06
const QRS_DUR= 0.06
const ST_DUR = 0.06
const T_DUR  = 0.14

function ecgSample(t: number): number {
  if (t < P_DUR) return P_AMP * Math.sin((t / P_DUR) * Math.PI)
  const pqEnd = P_DUR + PQ_DUR
  if (t < pqEnd) return 0
  const qrsEnd = pqEnd + QRS_DUR
  if (t < qrsEnd) {
    const u = (t - pqEnd) / QRS_DUR
    if (u < 0.15) return Q_AMP * Math.sin((u / 0.15) * Math.PI)
    if (u < 0.45) return R_AMP * Math.sin(((u - 0.15) / 0.30) * Math.PI)
    return S_AMP * Math.sin(((u - 0.45) / 0.55) * Math.PI)
  }
  const stEnd = qrsEnd + ST_DUR
  if (t < stEnd) return 0
  const tEnd = stEnd + T_DUR
  if (t < tEnd) return T_AMP * Math.sin(((t - stEnd) / T_DUR) * Math.PI)
  return 0
}

// ─── Gaussian noise helper ───────────────────────────────────────────────────
function gauss(mean: number, std: number): number {
  const u = 1 - Math.random()
  const v = Math.random()
  return mean + std * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

// ─── Service State ────────────────────────────────────────────────────────────
let intervalId: ReturnType<typeof setInterval> | null = null
let phaseHr    = Math.random() * Math.PI * 2
let phaseSpo2  = Math.random() * Math.PI * 2
let phaseBp    = Math.random() * Math.PI * 2
let phaseTemp  = Math.random() * Math.PI * 2
let tick       = 0

const ECG_SAMPLES = 200  // ECG waveform point count

export const MockSensorService = {
  /**
   * Start continuous mock telemetry at ~10Hz (every 100ms).
   * Idempotent: calling multiple times has no effect.
   */
  start(): void {
    if (intervalId !== null) return

    intervalId = setInterval(() => {
      const store = useTelemetryStore()
      tick++

      // ── Advance phases ───────────────────────────────────────────────────
      phaseHr   += 0.04
      phaseSpo2 += 0.007
      phaseBp   += 0.025
      phaseTemp += 0.005

      // ── Compute vitals ───────────────────────────────────────────────────
      const hr   = Math.round(Math.max(50, Math.min(115,
        78 + 12 * Math.sin(phaseHr) + gauss(0, 1.2))))
      const spo2 = Math.max(95, Math.min(100,
        parseFloat((98.5 + 0.8 * Math.sin(phaseSpo2) + gauss(0, 0.1)).toFixed(1))))
      const sys  = Math.round(Math.max(105, Math.min(135,
        118 + 8 * Math.sin(phaseBp) + gauss(0, 1.5))))
      const dia  = Math.round(Math.max(65, Math.min(88,
        74 + 5 * Math.sin(phaseBp + 0.5) + gauss(0, 1.0))))
      const temp = Math.max(36.0, Math.min(37.5,
        parseFloat((36.7 + 0.2 * Math.sin(phaseTemp) + gauss(0, 0.03)).toFixed(1))))

      // ── Alert level logic ────────────────────────────────────────────────
      let alertLevel: 'NORMAL' | 'WARNING' | 'CRITICAL' | 'STROKE' = 'NORMAL'
      if (hr > 110 || hr < 52 || spo2 < 96) alertLevel = 'WARNING'
      if (hr > 120 || spo2 < 93) alertLevel = 'CRITICAL'

      // ── Generate ECG waveform points ──────────────────────────────────────
      // 2 cardiac cycles, HR-driven
      const cycles = (hr / 60) * 2
      const ecgPoints: number[] = []
      for (let i = 0; i < ECG_SAMPLES; i++) {
        const t = ((i / ECG_SAMPLES) * cycles) % 1.0
        ecgPoints.push(ecgSample(t))
      }

      // ── Push to Pinia store ───────────────────────────────────────────────
      store.update({
        deviceId: 'MOCK-SIM-HK07',
        heartRate: hr,
        spo2,
        systolic: sys,
        diastolic: dia,
        bodyTemperature: temp,
        alertLevel,
        epochTimestampMs: Date.now(),
        ecgPoints,
      })
    }, 100)   // 10 Hz
  },

  /**
   * Stop the mock data generator.
   * Call this when a real WebSocket connection is established.
   */
  stop(): void {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  },

  get isRunning(): boolean {
    return intervalId !== null
  }
}
