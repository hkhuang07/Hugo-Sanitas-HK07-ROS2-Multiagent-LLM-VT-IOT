import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface VitalSign {
  deviceId: string
  heartRate: number
  systolic: number
  diastolic: number
  bodyTemperature: number
  spo2: number
  epochTimestampMs: number
  alertLevel?: 'NORMAL' | 'WARNING' | 'CRITICAL' | 'STROKE'
  userId?: string
}

const RING_BUFFER_SIZE = 120  // 2 seconds @ 60Hz — Lag Compensation buffer

/**
 * Vitals Pinia Store — Real-time vital signs state
 *
 * Implements a fixed-size ring buffer for the ECG canvas.
 * Ring buffer uses pre-allocated Float32Array to avoid GC pressure at 60Hz.
 * No new Array() creation per frame — only splice on oldest element.
 */
export const useVitalsStore = defineStore('vitals', () => {
  // Current snapshot (WebSocket updates these)
  const current = ref<VitalSign>({
    deviceId: '',
    heartRate: 0,
    systolic: 0,
    diastolic: 0,
    bodyTemperature: 0,
    spo2: 0,
    epochTimestampMs: 0,
    alertLevel: 'NORMAL',
  })

  // Ring buffer for ECG waveform — pre-allocated array of fixed size
  // heartRateHistory[i] = HR value at that frame
  const heartRateHistory = ref<number[]>(Array(RING_BUFFER_SIZE).fill(0))
  const spo2History = ref<number[]>(Array(RING_BUFFER_SIZE).fill(99))
  const bufferWriteIdx = ref(0)

  // Computed
  const alertLevel = computed(() => current.value.alertLevel ?? 'NORMAL')
  const alertClass = computed(() => {
    const map: Record<string, string> = {
      NORMAL: 'state-normal', WARNING: 'state-warning',
      CRITICAL: 'state-critical', STROKE: 'state-stroke',
    }
    return map[alertLevel.value] || 'state-normal'
  })
  const isEmergency = computed(() =>
    alertLevel.value === 'CRITICAL' || alertLevel.value === 'STROKE'
  )

  const isConnected = ref(false)

  // Actions
  function updateVitals(data: VitalSign) {
    current.value = data

    // Ring buffer write (no splice — just overwrite at write index, increment modulo)
    const idx = bufferWriteIdx.value % RING_BUFFER_SIZE
    heartRateHistory.value[idx] = data.heartRate
    spo2History.value[idx] = data.spo2
    bufferWriteIdx.value++
  }

  function reset() {
    heartRateHistory.value.fill(0)
    spo2History.value.fill(99)
    bufferWriteIdx.value = 0
    isConnected.value = false
  }

  return {
    current,
    alertLevel,
    alertClass,
    isEmergency,
    updateVitals,
    reset,
    heartRateHistory,
    bufferWriteIdx,
    RING_BUFFER_SIZE,
    isConnected
  }
})
