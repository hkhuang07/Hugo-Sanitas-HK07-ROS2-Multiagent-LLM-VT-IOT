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
  const baymaxHint = ref('Đang chờ dữ liệu thị giác IPWebcam từ robot HK-07...')
  const lastScanMs = ref(0)
  const sectorCount = ref(0)
  const activeTriggers = ref<ActiveSafetyTrigger[]>([])
  const imuFallRisk = ref(false)
  const clinicalAnalysis = ref<any>(null)
  const spatialTargets = ref<any[]>([])
  const cognitiveInsights = ref<Record<string, any>>({})
  const overallRisk = ref<string>('LOW')
  const confidence = ref<number>(0)
  const postureRisk = ref<string>('LOW')

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

  function applyClinical(payload: any) {
    clinicalAnalysis.value = payload
    // Persist structured spatial perception data for HugoVisionView.vue HUD overlay
    if (Array.isArray(payload?.spatial_targets)) spatialTargets.value = payload.spatial_targets
    if (payload?.cognitive_insights) cognitiveInsights.value = payload.cognitive_insights
    if (payload?.overall_risk) overallRisk.value = payload.overall_risk
    if (payload?.confidence !== undefined) confidence.value = payload.confidence
    if (payload?.posture_risk) postureRisk.value = payload.posture_risk
    if (payload?.visible_injuries?.detected) {
      activeTriggers.value = [
        {
          type: 'VISIBLE_INJURIES',
          distanceM: 0,
          message: `Vết thương: ${payload.visible_injuries.details}`,
          severity: 'warning' as const,
          detectedAt: Date.now()
        },
        ...activeTriggers.value.filter(t => t.type !== 'VISIBLE_INJURIES')
      ].slice(0, MAX_TRIGGERS)
    }
    if (payload?.facial_distress?.detected) {
      activeTriggers.value = [
        {
          type: 'FACIAL_DISTRESS',
          distanceM: 0,
          message: `Biểu hiện mặt: ${payload.facial_distress.details}`,
          severity: 'critical' as const,
          detectedAt: Date.now()
        },
        ...activeTriggers.value.filter(t => t.type !== 'FACIAL_DISTRESS')
      ].slice(0, MAX_TRIGGERS)
    }
    if (payload?.environmental_hazards?.detected) {
      activeTriggers.value = [
        {
          type: 'ENVIRONMENT_HAZARDS',
          distanceM: 0,
          message: `Rủi ro MT: ${payload.environmental_hazards.details}`,
          severity: 'warning' as const,
          detectedAt: Date.now()
        },
        ...activeTriggers.value.filter(t => t.type !== 'ENVIRONMENT_HAZARDS')
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
    clinicalAnalysis,
    spatialTargets,
    cognitiveInsights,
    overallRisk,
    confidence,
    postureRisk,
    dataLive,
    dataLinkLabel,
    applyScan,
    applyInhibit,
    applyImu,
    applyClinical,
    pruneStaleTriggers,
    loadSnapshot,
  }
})
