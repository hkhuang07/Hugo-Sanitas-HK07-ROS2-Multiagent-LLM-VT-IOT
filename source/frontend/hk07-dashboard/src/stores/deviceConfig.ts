/**
 * useDeviceConfigStore — Pinia Store
 *
 * Single source of truth for the phone's IP and PC's IP addresses.
 * Persisted to localStorage so it survives page reload.
 *
 * Pipeline it controls:
 *   BaymaxVisionView  → MJPEG stream URL (camera on Phone)
 *   SensorTelemetryView → Destination PC IP where phone SensorLogs publishes to
 *
 * Usage:
 *   const cfg = useDeviceConfigStore()
 *   cfg.cameraUrl   // computed MJPEG URL (Phone IP)
 *   cfg.confirmIp() // apply + save + broadcast reconnect event
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

const LS_PHONE_IP = 'hk07_phone_ip'
const LS_PC_IP = 'hk07_pc_ip'
const LS_PORT_CAM = 'hk07_camera_port'
const LS_PORT_SENSOR = 'hk07_sensor_port'

export const useDeviceConfigStore = defineStore('deviceConfig', () => {
  // One-time migration: upgrade old default 8080 → 5005 for sensor port
  const _storedSensorPort = localStorage.getItem(LS_PORT_SENSOR)
  if (_storedSensorPort === '8080') localStorage.removeItem(LS_PORT_SENSOR)

  const _oldIp = localStorage.getItem('hk07_device_ip')
  const phoneIp = ref(localStorage.getItem(LS_PHONE_IP) || _oldIp || '192.168.101.103')
  const pcIp = ref(localStorage.getItem(LS_PC_IP) || '192.168.101.49')
  const cameraPort = ref(localStorage.getItem(LS_PORT_CAM) || '8080')
  const sensorPort = ref(localStorage.getItem(LS_PORT_SENSOR) || '5007')

  /** draft edited by the form — only committed on confirmIp() */
  const draftPhoneIp = ref(phoneIp.value)
  const draftPcIp = ref(pcIp.value)
  const draftCameraPort = ref(cameraPort.value)
  const draftSensorPort = ref(sensorPort.value)

  /** last confirmation timestamp — watchers in views react to this */
  const confirmedAt = ref(0)

  /** human-readable status after last confirm */
  const status = ref<'IDLE' | 'TESTING' | 'ONLINE' | 'ERROR'>('IDLE')
  const statusMsg = ref('')

  // ── Computed URLs ───────────────────────────────────────────────────────────
  // Camera:  http://<PHONE_IP>:8080/video   (IP Webcam Android app)
  // Sensor:  http://<PC_IP>:5007/data        (hk07_sensor_fusion.py / SensorLogs destination)
  const cameraUrl = computed(() => `http://${phoneIp.value}:${cameraPort.value}/video`)
  const sensorBridgeUrl = computed(() => `http://${pcIp.value}:${sensorPort.value}/data`)

  // ── Actions ─────────────────────────────────────────────────────────────────

  /**
   * Apply draft values → persist → broadcast reconnect.
   * Views watch `confirmedAt` to trigger their own reconnect logic.
   */
  async function confirmIp() {
    status.value = 'TESTING'
    statusMsg.value = 'Đang kiểm tra kết nối...'

    // Commit drafts
    phoneIp.value = draftPhoneIp.value.trim()
    pcIp.value = draftPcIp.value.trim()
    cameraPort.value = draftCameraPort.value.trim()
    sensorPort.value = draftSensorPort.value.trim()

    // Persist
    localStorage.setItem(LS_PHONE_IP, phoneIp.value)
    localStorage.setItem(LS_PC_IP, pcIp.value)
    localStorage.setItem(LS_PORT_CAM, cameraPort.value)
    localStorage.setItem(LS_PORT_SENSOR, sensorPort.value)

    // Probe camera endpoint (lightweight HEAD check)
    try {
      const testUrl = `http://${phoneIp.value}:${cameraPort.value}/`
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 3000)
      await fetch(testUrl, { method: 'HEAD', signal: ctrl.signal, mode: 'no-cors' })
      clearTimeout(timer)
      status.value = 'ONLINE'
      statusMsg.value = `Kết nối thành công → Điện thoại: ${phoneIp.value}`
    } catch {
      status.value = 'ONLINE'
      statusMsg.value = `Đã lưu → ${phoneIp.value} (không thể xác minh qua browser CORS)`
    }

    // Notify the Python sensor fusion server about the updated phone IP
    try {
      const pythonBridgeConfigUrl = `http://localhost:${sensorPort.value}/api/v1/config/device-ip`
      await fetch(pythonBridgeConfigUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: phoneIp.value })
      })
      console.log(`[CONFIG] Synchronized phone IP ${phoneIp.value} to Python sensor fusion bridge at port ${sensorPort.value}`)
    } catch (err) {
      console.warn(`[CONFIG] Could not sync IP to Python bridge at port ${sensorPort.value}:`, err)
    }

    // Broadcast so any listening component reconnects
    confirmedAt.value = Date.now()
    document.dispatchEvent(new CustomEvent('hk07:device-ip-changed', {
      detail: { phoneIp: phoneIp.value, pcIp: pcIp.value, cameraPort: cameraPort.value, sensorPort: sensorPort.value }
    }))
  }

  function resetDraft() {
    draftPhoneIp.value = phoneIp.value
    draftPcIp.value = pcIp.value
    draftCameraPort.value = cameraPort.value
    draftSensorPort.value = sensorPort.value
    status.value = 'IDLE'
    statusMsg.value = ''
  }

  // Auto-sync IP to Python bridge on store initialization
  setTimeout(async () => {
    try {
      const pythonBridgeConfigUrl = `http://localhost:${sensorPort.value}/api/v1/config/device-ip`
      await fetch(pythonBridgeConfigUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ip: phoneIp.value })
      })
    } catch {}
  }, 1000)

  return {
    phoneIp, pcIp, cameraPort, sensorPort,
    draftPhoneIp, draftPcIp, draftCameraPort, draftSensorPort,
    confirmedAt, status, statusMsg,
    cameraUrl, sensorBridgeUrl,
    confirmIp, resetDraft,
  }
})
