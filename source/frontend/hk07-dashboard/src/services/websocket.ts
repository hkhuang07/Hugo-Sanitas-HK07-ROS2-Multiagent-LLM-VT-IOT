import { Client, type IMessage } from '@stomp/stompjs'
import SockJS from 'sockjs-client'
import { useVitalsStore } from '../stores/vitals'
import { useAgentsStore } from '../stores/agents'
import { useSafetyStore } from '../stores/safety'
import { useAuthStore } from '../stores/auth'
import { useKinematicsStore } from '../stores/kinematics'
import { useTelemetryStore } from '../stores/telemetry'
import type { SafetyInhibitAlert } from '../types/safety'

let _client: Client | null = null
let _reconnectAttempts = 0
const MAX_RECONNECT = 10

/**
 * WebSocket Service Singleton — STOMP over SockJS
 *
 * [P2-1] Exponential Backoff: delay = min(1000 * 2^attempts, 30_000ms)
 *         This prevents connection storms after a server restart.
 *
 * [P1-2] Offline Cache Integration:
 *   - onDisconnect: marks isConnected = false (EcgWaveform shows flatline)
 *   - onConnect: calls vitalsStore.flushOfflineQueue() to replay buffered vitals
 */
export function initWebSocket(onReady?: () => void): void {
  if (_client?.active) return

  const authStore = useAuthStore()

  _client = new Client({
    webSocketFactory: () => new SockJS(import.meta.env.VITE_WS_URL || '/ws'),

    // [P2-1] Exponential Backoff: 1s, 2s, 4s, 8s ... capped at 30s
    reconnectDelay: Math.min(1000 * Math.pow(2, _reconnectAttempts), 30_000),

    connectHeaders: {
      Authorization: `Bearer ${authStore.accessToken}`
    },

    beforeConnect: async () => {
      // Refresh JWT before each (re)connect attempt
      if (authStore.isAuthenticated) {
        await authStore.refreshSession()
      }
      if (_client) {
        _client.connectHeaders = {
          Authorization: `Bearer ${authStore.accessToken}`
        }
        // Update reconnect delay for next potential failure
        _client.reconnectDelay = Math.min(1000 * Math.pow(2, _reconnectAttempts), 30_000)
      }
    },

    onConnect: async () => {
      _reconnectAttempts = 0
      console.log('[WS] Connected to HK-07 Core securely')

      const vitalsStore = useVitalsStore()
      const agentsStore = useAgentsStore()
      const safetyStore = useSafetyStore()
      const telemetryStore = useTelemetryStore()

      // Set telemetry mode to live/streaming
      telemetryStore.setLive(true)
      telemetryStore.isMock = false

      // [P1-2] Reconnected: flush offline queue into ring buffer
      await vitalsStore.flushOfflineQueue()

      // ── Subscribe: Vital signs stream
      _client!.subscribe('/topic/vitals', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        
        // Unpack nested VitalSignDto from the VitalSignWithAlertDto wrapper
        const vitalsData = {
          deviceId: data.vitals?.deviceId || data.deviceId || '',
          heartRate: data.vitals?.heartRate ?? data.heartRate ?? 0,
          spo2: data.vitals?.spo2 ?? data.spo2 ?? 99,
          systolic: data.vitals?.systolic ?? data.systolic ?? 120,
          diastolic: data.vitals?.diastolic ?? data.diastolic ?? 80,
          bodyTemperature: data.vitals?.bodyTemperature ?? data.bodyTemperature ?? 36.6,
          alertLevel: data.alertLevel || 'NORMAL',
          userId: data.userId || '',
          epochTimestampMs: data.vitals?.epochTimestampMs || Date.now()
        }
        
        vitalsStore.updateVitals(vitalsData)
        
        // Sync to telemetryStore so Dashboard text values update live
        const telemetryStore = useTelemetryStore()
        telemetryStore.update({
          deviceId: vitalsData.deviceId,
          heartRate: vitalsData.heartRate,
          spo2: vitalsData.spo2,
          systolic: vitalsData.systolic,
          diastolic: vitalsData.diastolic,
          bodyTemperature: vitalsData.bodyTemperature,
          alertLevel: vitalsData.alertLevel,
          epochTimestampMs: vitalsData.epochTimestampMs,
          ecgPoints: []
        })
      })

      // ── Subscribe: Agent event log
      _client!.subscribe('/topic/agent-events', (msg: IMessage) => {
        const ev = JSON.parse(msg.body)
        if (ev.eventType === 'AI_EMERGENCY_WAKEUP' || ev.id === 'AI_EMERGENCY_WAKEUP') {
          document.dispatchEvent(new CustomEvent('hk07:ai-emergency-wakeup', { detail: ev }))
        }
      })

      // ── Subscribe: Agent system logs
      _client!.subscribe('/topic/agent-logs', (msg: IMessage) => {
        const ev = JSON.parse(msg.body)
        agentsStore.addEvent(ev)
      })

      // ── Subscribe: LiDAR scan (MQTT → Core → enriched snapshot)
      _client!.subscribe('/topic/safety-scan', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        safetyStore.applyScan(data)
      })

      // ── Subscribe: IMU / fall-risk telemetry
      _client!.subscribe('/topic/safety-imu', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        safetyStore.applyImu(data)
      })

      // ── Subscribe: Kinematics 3D data (Holographic Twin)
      _client!.subscribe('/topic/hk07/telemetry/imu', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        const kinematicsStore = useKinematicsStore()
        kinematicsStore.updateKinematics(data)
      })

      // ── Subscribe: Pneumatic telemetry
      _client!.subscribe('/topic/hk07/telemetry/pneumatic', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        const kinematicsStore = useKinematicsStore()
        kinematicsStore.updatePneumatic(data)
      })

      // ── Subscribe: Tactile telemetry
      _client!.subscribe('/topic/hk07/telemetry/tactile', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        const kinematicsStore = useKinematicsStore()
        kinematicsStore.updateTactile(data)
      })

      // ── Subscribe: PMU telemetry
      _client!.subscribe('/topic/hk07/telemetry/pmu', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        const kinematicsStore = useKinematicsStore()
        kinematicsStore.updatePmu(data)
      })

      // ── Subscribe: Joint telemetry
      _client!.subscribe('/topic/hk07/telemetry/joints', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        const kinematicsStore = useKinematicsStore()
        kinematicsStore.updateJoints(data)
      })

      // ── Subscribe: LiDAR Point Cloud (Spatial Perception)
      _client!.subscribe('/topic/hk07/telemetry/lidar/points', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        const kinematicsStore = useKinematicsStore()
        kinematicsStore.updateLidarPoints(data)
      })

       // ── Subscribe: Obstacle Avoidance Vector
      _client!.subscribe('/topic/hk07/telemetry/avoidance', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        const kinematicsStore = useKinematicsStore()
        kinematicsStore.updateAvoidanceVector(data)
      })

      // ── Subscribe: Joint States Telemetry
      _client!.subscribe('/topic/hk07/telemetry/joint_states', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        const kinematicsStore = useKinematicsStore()
        kinematicsStore.updateJointStates(data)
      })

      // ── Subscribe: Clinical / Multimodal Vision analysis
      _client!.subscribe('/topic/hk07/perception/clinical', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        safetyStore.applyClinical(data)
      })

      // ── Subscribe: Thermal and rPPG telemetry
      _client!.subscribe('/topic/hk07/sensors/camera/thermal-rppg', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        const kinematicsStore = useKinematicsStore()
        kinematicsStore.updateThermalRppg(data)
      })

      // ── Subscribe: Safety alerts / Subsumption (SafetyAgent inhibit bridge)
      _client!.subscribe('/topic/safety-alerts', (msg: IMessage) => {
        const data = JSON.parse(msg.body) as SafetyInhibitAlert
        const isActive = data.subsumptionActivated === true
        agentsStore.setSubsumptionActive(isActive, data.triggerType)
        safetyStore.applyInhibit(data)
      })

      // ── Subscribe: System state changes
      _client!.subscribe('/topic/system-state', (msg: IMessage) => {
        document.dispatchEvent(new CustomEvent('hk07:system-state', { detail: msg.body }))
      })

      vitalsStore.isConnected = true
      onReady?.()
    },

    onDisconnect: () => {
      _reconnectAttempts = Math.min(_reconnectAttempts + 1, MAX_RECONNECT)
      const delay = Math.min(1000 * Math.pow(2, _reconnectAttempts), 30_000)
      console.warn(`[WS] Disconnected. Reconnect #${_reconnectAttempts} in ${delay}ms (Exponential Backoff)`)
      const vitalsStore = useVitalsStore()
      vitalsStore.isConnected = false
      const telemetryStore = useTelemetryStore()
      telemetryStore.setLive(false)
      const kinematicsStore = useKinematicsStore()
      kinematicsStore.setLive(false)

      document.dispatchEvent(new CustomEvent('hk07:toast', {
        detail: {
          severity: 'warning',
          agent: 'SYSTEM',
          message: 'CORE TELEMETRY CONNECTION LOST. OFFLINE_MODE TRIGGERED.',
          duration: 5000
        }
      }))
    },

    onStompError: (frame) => {
      console.error('[WS] STOMP error:', frame.headers['message'])
      const vitalsStore = useVitalsStore()
      vitalsStore.isConnected = false
    },
  })

  _client.activate()
}

export function sendMessage(destination: string, body: object): void {
  if (!_client?.active) {
    console.warn('[WS] Not connected — message dropped:', destination)
    return
  }
  _client.publish({ destination, body: JSON.stringify(body) })
}

export function disconnectWebSocket(): void {
  _client?.deactivate()
  _client = null
  try {
    const vitalsStore = useVitalsStore()
    vitalsStore.isConnected = false
    const telemetryStore = useTelemetryStore()
    telemetryStore.setLive(false)
    const kinematicsStore = useKinematicsStore()
    kinematicsStore.setLive(false)
  } catch {}
}
