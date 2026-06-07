import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

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

  const savedChat = localStorage.getItem('hk07_agent_chat_log')
  const chatLog = ref<ChatMessage[]>(savedChat ? JSON.parse(savedChat) : [
    {
      role: 'hugo',
      content: 'Chào mừng Operator. Tôi là Hugo, Trợ lý Y tế Đồng hành của bạn. Tôi luôn trực tuyến để phân tích các chỉ số sức khỏe của bạn và đề xuất các hành động an toàn tối ưu.',
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
    chatLog,
    sessionId,
    agentStatus, 
    subsumptionActive, 
    currentPriorityAgent,
    initSession,
    addEvent, 
    setSubsumptionActive, 
    clearEvents 
  }
})

