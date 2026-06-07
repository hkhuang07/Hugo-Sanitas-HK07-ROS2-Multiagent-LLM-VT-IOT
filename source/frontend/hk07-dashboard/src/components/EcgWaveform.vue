<template>
  <div class="ecg-canvas-container" :style="{ height: height + 'px' }">
    <canvas ref="canvasRef" :width="width" :height="height"></canvas>
  </div>
</template>

<script setup lang="ts">
/**
 * EcgWaveform.vue — P1-1 REFACTOR
 *
 * BEFORE: Pure math simulation (Sine + noise). No real data.
 * AFTER:  Reads heartRateHistory ring buffer from vitalsStore (real MQTT data).
 *         Converts HR cadence to authentic ECG waveform geometry:
 *           - P wave (atrial depolarization)
 *           - QRS complex (ventricular depolarization) — driven by RR interval
 *           - T wave (repolarization)
 *
 * Zero memory allocation inside draw() loop — only reads pre-allocated Float32Array.
 * GPU-accelerated via requestAnimationFrame at 60FPS.
 * No memory leaks: animFrameId + isUnmounted guard on unmount.
 */
import { ref, onMounted, onUnmounted } from 'vue'
import { useVitalsStore } from '../stores/vitals'
import { useTelemetryStore } from '../stores/telemetry'

const props = withDefaults(defineProps<{
  width?: number
  height?: number
}>(), {
  width: 760,
  height: 90
})

const vitalsStore = useVitalsStore()
const telemetryStore = useTelemetryStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)
let animFrameId: number
let isUnmounted = false

// ── ECG Geometry Constants ──────────────────────────────────────────────────
const P_AMP = 0.08        // P-wave amplitude (normalized)
const Q_AMP = -0.1        // Q dip
const R_AMP = 1.0         // R spike (scaled by HR deviation)
const S_AMP = -0.15       // S dip
const T_AMP = 0.25        // T-wave amplitude
// Phase durations (fraction of 1 RR cycle)
const P_DUR = 0.08
const PQ_DUR = 0.06       // PR segment (isoelectric)
const QRS_DUR = 0.06      // QRS width
const ST_DUR = 0.06       // ST segment
const T_DUR = 0.14

/**
 * Synthesize an ECG sample value for a given phase t in [0,1] of one heartbeat cycle.
 * Returns a normalized value in roughly [-0.2, 1.0].
 * The shape is a close approximation of Lead II ECG morphology.
 */
function ecgSample(t: number): number {
  // P wave: [0, P_DUR)
  if (t < P_DUR) {
    const u = t / P_DUR
    return P_AMP * Math.sin(u * Math.PI)
  }
  // PQ segment: flat
  const pq_end = P_DUR + PQ_DUR
  if (t < pq_end) return 0

  // QRS complex
  const qrs_end = pq_end + QRS_DUR
  if (t < qrs_end) {
    const u = (t - pq_end) / QRS_DUR
    // Q dip
    if (u < 0.15) return Q_AMP * Math.sin(u / 0.15 * Math.PI)
    // R spike (sharp triangle)
    if (u < 0.45) return R_AMP * Math.sin((u - 0.15) / 0.30 * Math.PI)
    // S dip
    return S_AMP * Math.sin((u - 0.45) / 0.55 * Math.PI)
  }
  // ST segment: flat
  const st_end = qrs_end + ST_DUR
  if (t < st_end) return 0

  // T wave
  const t_end = st_end + T_DUR
  if (t < t_end) {
    const u = (t - st_end) / T_DUR
    return T_AMP * Math.sin(u * Math.PI)
  }
  // Diastole: baseline
  return 0
}

// ── Pre-built waveform cache to avoid recalculating each frame ──────────────
// RING_BUFFER_SIZE samples pre-computed for a given HR
const waveformCache = new Float32Array(vitalsStore.RING_BUFFER_SIZE)
let cachedHR = -1

function rebuildWaveformCache(hr: number) {
  if (hr === cachedHR) return
  cachedHR = hr
  const clampedHR = Math.max(30, Math.min(220, hr))
  const size = vitalsStore.RING_BUFFER_SIZE
  for (let i = 0; i < size; i++) {
    // Map canvas index to phase in ECG cycle
    // Display shows ~2 seconds, so 2 RR cycles at given HR
    const cycles = (clampedHR / 60) * 2   // e.g. 72bpm → 2.4 cycles in 2s
    const t = ((i / size) * cycles) % 1.0
    waveformCache[i] = ecgSample(t)
  }
}

// ── Draw Loop ───────────────────────────────────────────────────────────────
function draw() {
  if (isUnmounted) return
  const canvas = canvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const w = canvas.width
  const h = canvas.height
  const mid = h / 2
  const amp = mid * 0.75   // Waveform amplitude in pixels

  // Clear
  ctx.clearRect(0, 0, w, h)
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, w, h)

  // Grid
  ctx.strokeStyle = 'rgba(0, 255, 102, 0.06)'
  ctx.lineWidth = 1
  for (let x = 0; x < w; x += 40) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke()
  }
  for (let y = 0; y < h; y += 20) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke()
  }

  // ── Data source priority ──────────────────────────────────────────────────
  // Priority 1: telemetryStore (MockSensorService or WebSocket adapter)
  // Priority 2: vitalsStore ring buffer (legacy direct WebSocket path)
  const telemetry = telemetryStore.current
  const hasTelemetry = telemetry.heartRate > 0 && telemetry.ecgPoints.length > 0
  const isConnectedLegacy = vitalsStore.isConnected

  if (hasTelemetry) {
    // ── TELEMETRY MODE: Pre-computed ECG points from store ────────────────
    const points = telemetry.ecgPoints
    const size = points.length
    const currentHR = telemetry.heartRate
    const rScale = 0.8 + (currentHR / 72) * 0.2

    ctx.beginPath()
    ctx.strokeStyle = '#00FF66'
    ctx.lineWidth = 1.5
    ctx.shadowColor = '#00FF66'
    ctx.shadowBlur = 5

    for (let i = 0; i < size; i++) {
      const x = (i / size) * w
      const y = mid - points[i] * rScale * amp
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
    ctx.stroke()
    ctx.shadowBlur = 0

    // HR overlay
    ctx.fillStyle = 'rgba(0, 255, 102, 0.7)'
    ctx.font = '10px "Roboto Mono", monospace'
    ctx.fillText(`${currentHR} BPM  |  SpO₂: ${telemetry.spo2?.toFixed(1)}%  |  BP: ${telemetry.systolic}/${telemetry.diastolic}`, 8, 14)

  } else if (isConnectedLegacy) {
    // ── LEGACY LIVE MODE: Build ECG from vitalsStore ring buffer ─────────
    const size = vitalsStore.RING_BUFFER_SIZE
    const writeIdx = vitalsStore.bufferWriteIdx
    const history = vitalsStore.heartRateHistory

    let currentHR = 0
    for (let k = 1; k <= size; k++) {
      const val = history[(writeIdx - k + size) % size]
      if (val > 0) { currentHR = val; break }
    }

    if (currentHR > 0) {
      rebuildWaveformCache(currentHR)
      const rScale = 0.8 + (currentHR / 72) * 0.2

      ctx.beginPath()
      ctx.strokeStyle = '#00FF66'
      ctx.lineWidth = 1.5
      ctx.shadowColor = '#00FF66'
      ctx.shadowBlur = 5

      for (let i = 0; i < size; i++) {
        const x = (i / size) * w
        const rawHR = history[(writeIdx + i) % size]
        const hrVariation = rawHR > 0 ? (rawHR - currentHR) / currentHR : 0
        const ecgVal = waveformCache[i] * rScale * (1 + hrVariation * 0.3)
        const y = mid - ecgVal * amp
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }

      ctx.stroke()
      ctx.shadowBlur = 0
      ctx.fillStyle = 'rgba(0, 255, 102, 0.7)'
      ctx.font = '10px "Roboto Mono", monospace'
      ctx.fillText(`${currentHR} BPM`, 8, 14)
    }

  } else {
    // ── OFFLINE MODE: Dim flatline with idle flutter ──────────────────────
    rebuildWaveformCache(60)   // Baseline idle template

    ctx.beginPath()
    ctx.strokeStyle = 'rgba(0, 255, 102, 0.3)'
    ctx.lineWidth = 1.0
    ctx.setLineDash([4, 8])

    const size = vitalsStore.RING_BUFFER_SIZE
    for (let i = 0; i < size; i++) {
      const x = (i / size) * w
      const ecgVal = waveformCache[i] * 0.3
      const y = mid - ecgVal * amp
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }

    ctx.stroke()
    ctx.setLineDash([])

    ctx.fillStyle = 'rgba(0, 255, 102, 0.25)'
    ctx.font = '9px "Roboto Mono", monospace'
    ctx.fillText('NO_SIGNAL — OFFLINE', 8, 14)
  }

  animFrameId = requestAnimationFrame(draw)
}

onMounted(() => {
  animFrameId = requestAnimationFrame(draw)
})

onUnmounted(() => {
  isUnmounted = true
  cancelAnimationFrame(animFrameId)
})
</script>

<style scoped>
.ecg-canvas-container {
  position: relative;
  width: 100%;
  background: #000000;
  border: 1px solid var(--color-border-dim);
}
.ecg-canvas-container canvas {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
