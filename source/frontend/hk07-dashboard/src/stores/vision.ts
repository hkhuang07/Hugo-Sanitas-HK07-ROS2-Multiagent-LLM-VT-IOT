/**
 * useVisionStore — Pinia Store
 *
 * Single source of truth for IPWebcam vision and PerceptionAgent scan results.
 * Updated by GlobalStreamingService (independent of page navigation).
 *
 * Data pipeline:
 *   [Python headless camera daemon] → /api/v1/sensor-cache/vision
 *   → GlobalStreamingService poll (5s) → useVisionStore
 *   → HugoVisionView.vue, CompanionView.vue (reactive)
 *
 * Camera modes:
 *   MODE_MJPEG    — Live <img :src="mjpegStreamUrl"> (IP Webcam MJPEG)
 *   MODE_SNAPSHOT — base64 frame from Python daemon cache (fallback)
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface PerceptionScanResult {
  agent_type: string
  timestamp: string
  scan_duration_ms: number
  skin_tone_note: string
  facial_distress: number
  visible_injuries: string[]
  posture_risk: string
  heart_rate: number | null
  spo2: number | null
  body_temperature: number | null
  overall_risk: string
  confidence: number
  notes: string
  disclaimer: string
  alertLevel: string
  status: string
}

export const useVisionStore = defineStore('vision', () => {
  // ── Camera state ───────────────────────────────────────────────────────────
  const daemonStatus = ref<string>('UNKNOWN')
  const cameraFresh = ref<boolean>(false)
  const frameAvailable = ref<boolean>(false)
  const frameAgeS = ref<number | null>(null)
  const frameTs = ref<number | null>(null)
  const cameraFrameB64 = ref<string>('')    // base64 snapshot from daemon cache
  const cameraFrameTs = ref<number>(0)       // ms timestamp of last frame fetch

  // ── MJPEG stream state (managed by view, not store) ───────────────────────
  // The view controls <img :src> and fires store.setMjpegOnline() on load/error
  const mjpegOnline = ref<boolean>(false)
  const mjpegLastOnlineMs = ref<number>(0)

  // ── Perception scan ────────────────────────────────────────────────────────
  const latestScan = ref<PerceptionScanResult | null>(null)
  const scanAgeS = ref<number | null>(null)

  // ── Polling metadata ───────────────────────────────────────────────────────
  const lastPollMs = ref<number>(0)
  const phoneIp = ref<string>('')
  const cameraPort = ref<string>('8080')

  // ── Computed ───────────────────────────────────────────────────────────────
  const isVisionOnline = computed(() =>
    daemonStatus.value === 'OK' || cameraFresh.value || mjpegOnline.value
  )

  const cameraMode = computed<'MJPEG' | 'SNAPSHOT' | 'OFFLINE'>(() => {
    if (mjpegOnline.value) return 'MJPEG'
    if (frameAvailable.value && cameraFresh.value) return 'SNAPSHOT'
    return 'OFFLINE'
  })

  const scanRiskLevel = computed(() => latestScan.value?.overall_risk ?? 'UNKNOWN')

  const scanConfidence = computed(() =>
    latestScan.value ? Math.round(latestScan.value.confidence * 100) : 0
  )

  const facialDistressPercent = computed(() =>
    latestScan.value ? Math.round(latestScan.value.facial_distress * 100) : 0
  )

  const isCritical = computed(() =>
    latestScan.value?.overall_risk === 'CRITICAL' ||
    latestScan.value?.alertLevel === 'CRITICAL'
  )

  // ── Actions ────────────────────────────────────────────────────────────────

  function updateVisionStatus(data: any) {
    daemonStatus.value  = data.daemon_status  ?? 'UNKNOWN'
    cameraFresh.value   = data.camera_fresh   ?? false
    frameAvailable.value = data.frame_available ?? false
    frameAgeS.value     = data.frame_age_s    ?? null
    frameTs.value       = data.frame_ts       ?? null
    phoneIp.value       = data.phone_ip       ?? ''
    cameraPort.value    = data.camera_port    ?? '8080'
    lastPollMs.value    = Date.now()

    if (data.latest_scan) {
      latestScan.value = data.latest_scan
      scanAgeS.value   = data.scan_age_s ?? null
    }
  }

  function updateFrameB64(b64: string) {
    cameraFrameB64.value = b64
    cameraFrameTs.value  = Date.now()
  }

  function setMjpegOnline(online: boolean) {
    mjpegOnline.value = online
    if (online) mjpegLastOnlineMs.value = Date.now()
  }

  function updatePerceptionScan(scan: PerceptionScanResult) {
    latestScan.value = scan
    scanAgeS.value   = 0
  }

  function reset() {
    daemonStatus.value   = 'UNKNOWN'
    cameraFresh.value    = false
    frameAvailable.value = false
    frameAgeS.value      = null
    frameTs.value        = null
    cameraFrameB64.value = ''
    mjpegOnline.value    = false
    latestScan.value     = null
    scanAgeS.value       = null
    lastPollMs.value     = 0
  }

  return {
    // State
    daemonStatus, cameraFresh, frameAvailable, frameAgeS, frameTs,
    cameraFrameB64, cameraFrameTs, mjpegOnline, mjpegLastOnlineMs,
    latestScan, scanAgeS, lastPollMs, phoneIp, cameraPort,
    // Computed
    isVisionOnline, cameraMode, scanRiskLevel, scanConfidence,
    facialDistressPercent, isCritical,
    // Actions
    updateVisionStatus, updateFrameB64, setMjpegOnline, updatePerceptionScan, reset,
  }
})
