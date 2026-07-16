import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import api from '../services/api'

// Phase B: SSE base URL — connects directly to FastAPI hk07-agent (port 8889)
const AGENT_ENGINE_URL = (import.meta as any).env?.VITE_AGENT_API_URL || 'http://localhost:8889'

export type AgentType = 'SAFETY' | 'MEDICAL' | 'EMPATHETIC' | 'CARE' | 'PERCEPTION' | 'ACTION' | 'ROUTER'

export interface AgentEvent {
  id: string
  agentType: AgentType
  inputContext: string
  outputDecision: string
  llmProvider: string
  latencyMs: number
  triggeredAt: string
  alertLevel?: string
}

export interface ChatMessage {
  role: 'user' | 'hugo'
  content: string
  timestamp: string
}

const MAX_EVENTS = 200  // Ring Buffer cap as per spec

export const useAgentsStore = defineStore('agents', () => {
  // Load persisted state from localStorage
  const savedEvents = localStorage.getItem('hk07_agent_events')
  const events = ref<AgentEvent[]>(savedEvents ? JSON.parse(savedEvents) : [])

  const stats = ref<Record<AgentType, number>>({
    SAFETY: 0,
    MEDICAL: 0,
    EMPATHETIC: 0,
    CARE: 0,
    PERCEPTION: 0,
    ACTION: 0,
    ROUTER: 0,
  })

  const savedChat = localStorage.getItem('hk07_agent_chat_log')
  const chatLog = ref<ChatMessage[]>(savedChat ? JSON.parse(savedChat) : [
    {
      role: 'hugo',
      content: 'Xin chào. Tôi là Hugo, Trợ lý Y tế Đồng hành và chăm sóc sức khỏe của bạn. Có vẻ bạn đang có vấn đề, bạn có muốn tôi giúp đỡ không ?',
      timestamp: new Date().toTimeString().split(' ')[0]
    }
  ])

  const savedSessionId = localStorage.getItem('hk07_session_id')
  const sessionId = ref<string>(savedSessionId || '')

  const agentStatus = ref<Record<AgentType, 'ACTIVE' | 'IDLE' | 'INHIBITED'>>({
    SAFETY: 'ACTIVE',
    MEDICAL: 'IDLE',
    EMPATHETIC: 'IDLE',
    CARE: 'IDLE',
    PERCEPTION: 'IDLE',
    ACTION: 'IDLE',
    ROUTER: 'ACTIVE',
  })
  const subsumptionActive = ref(false)
  const currentPriorityAgent = ref<AgentType>('SAFETY')

  function initSession(userId?: string) {
    if (!sessionId.value) {
      sessionId.value = 'session_' + (userId || 'anon') + '_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now()
      localStorage.setItem('hk07_session_id', sessionId.value)
    }
  }

  function addEvent(ev: AgentEvent) {
    if (events.value.some(e => e.id === ev.id)) {
      return
    }
    events.value.unshift(ev)
    // Hard cap — drop oldest to prevent unbounded memory growth
    if (events.value.length > MAX_EVENTS) {
      events.value.length = MAX_EVENTS
    }
    agentStatus.value[ev.agentType] = 'ACTIVE'
    if (stats.value[ev.agentType] !== undefined) {
      stats.value[ev.agentType]++
    } else {
      stats.value[ev.agentType] = 1
    }
  }

  async function fetchLogs() {
    try {
      const resp = await api.get('/agents/logs', {
        params: { page: 0, size: MAX_EVENTS }
      })
      if (resp.data && resp.data.success && resp.data.data) {
        const list = resp.data.data.content || []
        const fetchedEvents = list.map((item: any) => ({
          id: item.id,
          agentType: item.agentType as AgentType,
          inputContext: item.inputContext || '',
          outputDecision: item.outputDecision,
          llmProvider: item.llmProvider || 'UNKNOWN',
          latencyMs: item.latencyMs,
          triggeredAt: item.triggeredAt
        }))

        // Merge fetched events with existing local storage events, avoiding duplicates by id
        const merged = [...fetchedEvents]
        const existingIds = new Set(merged.map(e => e.id))
        for (const e of events.value) {
          if (!existingIds.has(e.id)) {
            merged.push(e)
            existingIds.add(e.id)
          }
        }
        // Sort by triggeredAt descending
        merged.sort((a, b) => new Date(b.triggeredAt).getTime() - new Date(a.triggeredAt).getTime())
        // Cap ring buffer size
        if (merged.length > MAX_EVENTS) {
          merged.length = MAX_EVENTS
        }
        events.value = merged
      }
    } catch (err) {
      console.warn('[AGENT_STREAM] Failed to fetch persisted logs from Spring Boot backend. Falling back to FastAPI Agent Engine ring buffer:', err)
      // Fallback to FastAPI in-memory history if Core DB is offline
      await fetchStreamHistory()
    }
  }

  async function fetchStats() {
    try {
      const resp = await api.get('/agents/stats')
      if (resp.data && resp.data.success && resp.data.data) {
        const counts = resp.data.data
        stats.value = {
          SAFETY: Number(counts.SAFETY || 0),
          MEDICAL: Number(counts.MEDICAL || 0),
          EMPATHETIC: Number(counts.EMPATHETIC || 0),
          CARE: Number(counts.CARE || 0),
          PERCEPTION: Number(counts.PERCEPTION || 0),
          ACTION: Number(counts.ACTION || 0),
          ROUTER: Number(counts.ROUTER || 0)
        }
      }
    } catch (err) {
      console.error('Failed to fetch agent stats:', err)
    }
  }

  function setSubsumptionActive(active: boolean, trigger?: string) {
    subsumptionActive.value = active
    if (active) {
      agentStatus.value.SAFETY = 'ACTIVE'
      agentStatus.value.EMPATHETIC = 'INHIBITED'
      agentStatus.value.MEDICAL = 'INHIBITED'
    } else {
      agentStatus.value.EMPATHETIC = 'ACTIVE'
      agentStatus.value.MEDICAL = 'ACTIVE'
    }
  }

  function clearEvents() {
    events.value = []
  }

  // Watchers to update localStorage automatically on changes
  watch(events, (newVal) => {
    localStorage.setItem('hk07_agent_events', JSON.stringify(newVal))
  }, { deep: true })

  watch(chatLog, (newVal) => {
    localStorage.setItem('hk07_agent_chat_log', JSON.stringify(newVal))
  }, { deep: true })

  // ── Phase B: SSE subscription ────────────────────────────────────────────
  let _sseSource: EventSource | null = null
  let _sseReconnectTimer: ReturnType<typeof setTimeout> | null = null
  let _sseFailCount = 0
  const SSE_MAX_FAILS = 5
  const SSE_RECONNECT_BASE_MS = 3000

  function startSSEStream() {
    if (typeof window === 'undefined') return
    if (_sseSource && _sseSource.readyState !== EventSource.CLOSED) return // already open

    const url = `${AGENT_ENGINE_URL}/api/v1/agents/stream?replay=30`
    _sseSource = new EventSource(url)

    _sseSource.onopen = () => {
      _sseFailCount = 0
      console.info('[AGENT_STREAM] SSE connected to', url)
    }

    _sseSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        // Ignore heartbeat/connection meta events
        if (payload.type === 'CONNECTED') return
        const ev: AgentEvent = {
          id: payload.id || `sse_${Date.now()}`,
          agentType: (payload.agentType as AgentType) || 'EMPATHETIC',
          inputContext: payload.inputContext || '',
          outputDecision: payload.outputDecision || '',
          llmProvider: payload.llmProvider || 'UNKNOWN',
          latencyMs: payload.latencyMs || 0,
          triggeredAt: payload.triggeredAt || new Date().toISOString(),
          alertLevel: payload.alertLevel || 'NORMAL',
        }
        addEvent(ev)
        // Update agent status to ACTIVE when event received
        if (agentStatus.value[ev.agentType]) {
          agentStatus.value[ev.agentType] = 'ACTIVE'
          // Auto-reset to IDLE after 5s
          setTimeout(() => {
            if (agentStatus.value[ev.agentType] === 'ACTIVE') {
              agentStatus.value[ev.agentType] = 'IDLE'
            }
          }, 5000)
        }
      } catch (e) {
        console.warn('[AGENT_STREAM] Failed to parse SSE event:', e)
      }
    }

    _sseSource.onerror = () => {
      _sseFailCount++
      console.warn(`[AGENT_STREAM] SSE error. Fail count: ${_sseFailCount}/${SSE_MAX_FAILS}`)
      _sseSource?.close()
      _sseSource = null
      if (_sseFailCount <= SSE_MAX_FAILS) {
        // Exponential backoff reconnect
        const delay = SSE_RECONNECT_BASE_MS * Math.pow(2, Math.min(_sseFailCount - 1, 4))
        _sseReconnectTimer = setTimeout(() => startSSEStream(), delay)
      } else {
        console.error('[AGENT_STREAM] SSE max fails reached. Falling back to HTTP polling.')
        // Fallback: poll /stream/history every 5s
        _sseReconnectTimer = setInterval(() => fetchStreamHistory(), 5000)
      }
    }
  }

  function stopSSEStream() {
    if (_sseReconnectTimer) {
      clearTimeout(_sseReconnectTimer as ReturnType<typeof setTimeout>)
      clearInterval(_sseReconnectTimer as ReturnType<typeof setInterval>)
      _sseReconnectTimer = null
    }
    if (_sseSource) {
      _sseSource.close()
      _sseSource = null
    }
  }

  async function fetchStreamHistory() {
    try {
      const resp = await fetch(`${AGENT_ENGINE_URL}/api/v1/agents/stream/history?limit=50`)
      if (!resp.ok) return
      const data = await resp.json()
      const list: AgentEvent[] = (data.events || []).map((item: any) => ({
        id: item.id,
        agentType: item.agentType as AgentType,
        inputContext: item.inputContext || '',
        outputDecision: item.outputDecision || '',
        llmProvider: item.llmProvider || 'UNKNOWN',
        latencyMs: item.latencyMs || 0,
        triggeredAt: item.triggeredAt || new Date().toISOString(),
        alertLevel: item.alertLevel || 'NORMAL',
      }))
      for (const ev of list) addEvent(ev)
    } catch (e) {
      console.debug('[AGENT_STREAM] fetchStreamHistory failed:', e)
    }
  }
  // ─────────────────────────────────────────────────────────────────────────

  return {
    events,
    stats,
    chatLog,
    sessionId,
    agentStatus,
    subsumptionActive,
    currentPriorityAgent,
    initSession,
    addEvent,
    setSubsumptionActive,
    clearEvents,
    fetchLogs,
    fetchStats,
    // Phase B: SSE stream control
    startSSEStream,
    stopSSEStream,
    fetchStreamHistory,
  }
})

