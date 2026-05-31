import { defineStore } from 'pinia'
import { ref } from 'vue'

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

const MAX_EVENTS = 100  // Hard cap to prevent memory leak

export const useAgentsStore = defineStore('agents', () => {
  const events = ref<AgentEvent[]>([])
  const agentStatus = ref<Record<AgentType, 'ACTIVE' | 'IDLE' | 'INHIBITED'>>({
    EMPATHETIC: 'IDLE',
    MEDICAL: 'IDLE',
    SAFETY: 'ACTIVE',
  })
  const subsumptionActive = ref(false)
  const currentPriorityAgent = ref<AgentType>('SAFETY')

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

  function clearEvents() { events.value = [] }

  return { events, agentStatus, subsumptionActive, currentPriorityAgent,
           addEvent, setSubsumptionActive, clearEvents }
})
