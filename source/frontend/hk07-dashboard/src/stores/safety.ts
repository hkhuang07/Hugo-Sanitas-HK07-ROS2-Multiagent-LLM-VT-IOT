import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ActiveSafetyTrigger, LidarScanSnapshot, SafetyInhibitAlert } from '../types/safety'
import { analyzeRawScan, STALE_MS } from '../utils/lidarScan'

const MAX_TRIGGERS = 12
const TRIGGER_TTL_MS = 30_000

export const useSafetyStore = defineStore('safety', () => {
  const ranges360 = ref<number[]>(new Array(360).fill(0))
  const minDistanceM = ref(0)
  const closestAngleDeg = ref(0)
  const scanHz = ref(0)
  const threatLevel = ref<LidarScanSnapshot['threatLevel']>('UNKNOWN')
  const baymaxHint = ref('Đang chờ luồng LiDAR từ robot HK-07...')
  const lastScanMs = ref(0)
  const sectorCount = ref(0)
  const activeTriggers = ref<ActiveSafetyTrigger[]>([])
  const imuFallRisk = ref(false)

  const dataLive = computed(() => {
    if (lastScanMs.value <= 0) return false
    return Date.now() - lastScanMs.value <= STALE_MS
  })

  const dataLinkLabel = computed(() => {
    if (lastScanMs.value <= 0) return 'OFFLINE'
    return dataLive.value ? 'LIVE' : 'STALE'
  })

  let previousTs = 0

  function applyScan(payload: Record<string, unknown>) {
    const snap = analyzeRawScan(payload)
    ranges360.value = snap.ranges360
    minDistanceM.value = snap.minDistanceM
    closestAngleDeg.value = snap.closestAngleDeg
    threatLevel.value = snap.threatLevel
    baymaxHint.value = snap.baymaxHint
    sectorCount.value = snap.sectorCount ?? 0
    lastScanMs.value = snap.timestampMs || Date.now()

    if (snap.scanHz > 0) {
      scanHz.value = snap.scanHz
    } else if (previousTs > 0 && snap.timestampMs > previousTs) {
      scanHz.value = Math.round((1000 / (snap.timestampMs - previousTs)) * 10) / 10
    }
    previousTs = snap.timestampMs
  }

  function applyInhibit(alert: SafetyInhibitAlert) {
    if (!alert.subsumptionActivated) {
      activeTriggers.value = activeTriggers.value.filter(
        t => !t.type.startsWith('INHIBIT_')
      )
      return
    }

    const type = alert.triggerType || 'UNKNOWN'
    const dist = alert.distanceM ?? minDistanceM.value
    const severity = type === 'OBSTACLE' || type === 'FALL_RISK' || type === 'OWNER_EMERGENCY'
      ? 'critical' as const
      : 'warning' as const

    const row: ActiveSafetyTrigger = {
      type,
      distanceM: dist,
      message: alert.message || `Subsumption: ${type}`,
      severity,
      detectedAt: Date.now(),
    }

    activeTriggers.value = [
      row,
      ...activeTriggers.value.filter(t => t.type !== type),
    ].slice(0, MAX_TRIGGERS)

    document.dispatchEvent(new CustomEvent('hk07:subsumption-alert', {
      detail: { trigger: type, message: row.message },
    }))
  }

  function applyImu(payload: Record<string, unknown>) {
    const ax = Number(payload.accel_x ?? 0)
    const ay = Number(payload.accel_y ?? 0)
    const az = Number(payload.accel_z ?? 9.81)
    const g = Math.sqrt(ax * ax + ay * ay + az * az) / 9.81
    imuFallRisk.value = g > 2.5
    if (imuFallRisk.value) {
      const fallRow: ActiveSafetyTrigger = {
        type: 'FALL_RISK',
        distanceM: 0,
        message: `Gia tốc bất thường: ${g.toFixed(2)}g`,
        severity: 'critical',
        detectedAt: Date.now(),
      }
      activeTriggers.value = [
        fallRow,
        ...activeTriggers.value.filter(t => t.type !== 'FALL_RISK'),
      ].slice(0, MAX_TRIGGERS)
    }
  }

  function pruneStaleTriggers() {
    const now = Date.now()
    activeTriggers.value = activeTriggers.value.filter(
      t => now - t.detectedAt < TRIGGER_TTL_MS
    )
  }

  function loadSnapshot(snap: LidarScanSnapshot) {
    applyScan(snap as unknown as Record<string, unknown>)
    if (snap.scanHz) scanHz.value = snap.scanHz
    lastScanMs.value = snap.timestampMs || Date.now()
  }

  return {
    ranges360,
    minDistanceM,
    closestAngleDeg,
    scanHz,
    threatLevel,
    baymaxHint,
    lastScanMs,
    sectorCount,
    activeTriggers,
    imuFallRisk,
    dataLive,
    dataLinkLabel,
    applyScan,
    applyInhibit,
    applyImu,
    pruneStaleTriggers,
    loadSnapshot,
  }
})
