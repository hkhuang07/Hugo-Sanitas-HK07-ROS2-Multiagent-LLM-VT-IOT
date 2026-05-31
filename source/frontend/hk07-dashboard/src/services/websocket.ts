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
 * Securely connects using JWT Authorization header and automatically
 * refreshes session tokens before connection/reconnection.
 */
export function initWebSocket(onReady?: () => void): void {
  if (_client?.active) return

  const authStore = useAuthStore()

  _client = new Client({
    webSocketFactory: () => new SockJS('/ws'),
    reconnectDelay: Math.min(1000 * Math.pow(2, _reconnectAttempts), 30_000),
    connectHeaders: {
      Authorization: `Bearer ${authStore.accessToken}`
    },
    beforeConnect: async () => {
      if (authStore.refreshToken) {
        console.log('[WS] Validating and refreshing session token...')
        await authStore.refreshSession()
      }
      if (_client) {
        _client.connectHeaders = {
          Authorization: `Bearer ${authStore.accessToken}`
        }
      }
    },

    onConnect: () => {
      _reconnectAttempts = 0
      console.log('[WS] Connected to HK-07 Core securely')

      const vitalsStore = useVitalsStore()
      const agentsStore = useAgentsStore()

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
      _reconnectAttempts++
      console.warn(`[WS] Disconnected. Reconnect attempt #${_reconnectAttempts}`)
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
