import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import api from '../services/api'

export type AgentType = 'EMPATHETIC' | 'MEDICAL' | 'SAFETY'

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
    EMPATHETIC: 0,
    MEDICAL: 0,
    SAFETY: 0,
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
    EMPATHETIC: 'IDLE',
    MEDICAL: 'IDLE',
    SAFETY: 'ACTIVE',
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
        events.value = list.map((item: any) => ({
          id: item.id,
          agentType: item.agentType,
          inputContext: item.inputContext || '',
          outputDecision: item.outputDecision,
          llmProvider: item.llmProvider || 'UNKNOWN',
          latencyMs: item.latencyMs,
          triggeredAt: item.triggeredAt
        }))
      }
    } catch (err) {
      console.error('Failed to fetch agent logs:', err)
    }
  }

  async function fetchStats() {
    try {
      const resp = await api.get('/agents/stats')
      if (resp.data && resp.data.success && resp.data.data) {
        const counts = resp.data.data
        stats.value = {
          EMPATHETIC: Number(counts.EMPATHETIC || 0),
          MEDICAL: Number(counts.MEDICAL || 0),
          SAFETY: Number(counts.SAFETY || 0)
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
    fetchStats
  }
})

