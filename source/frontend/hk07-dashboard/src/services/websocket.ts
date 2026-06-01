import { Client, type IMessage } from '@stomp/stompjs'
import SockJS from 'sockjs-client'
import { useVitalsStore } from '../stores/vitals'
import { useAgentsStore } from '../stores/agents'
import { useAuthStore } from '../stores/auth'

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
      if (authStore.refreshToken) {
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

      // [P1-2] Reconnected: flush offline queue into ring buffer
      await vitalsStore.flushOfflineQueue()

      // ── Subscribe: Vital signs stream
      _client!.subscribe('/topic/vitals', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        vitalsStore.updateVitals(data)
      })

      // ── Subscribe: Agent event log
      _client!.subscribe('/topic/agent-events', (msg: IMessage) => {
        const ev = JSON.parse(msg.body)
        agentsStore.addEvent(ev)
      })

      // ── Subscribe: Safety alerts / Subsumption
      _client!.subscribe('/topic/safety-alerts', (msg: IMessage) => {
        const data = JSON.parse(msg.body)
        const isActive = data.subsumptionActivated === true
        agentsStore.setSubsumptionActive(isActive, data.triggerType)
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
  } catch {}
}
