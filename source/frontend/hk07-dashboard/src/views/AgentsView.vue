<template>
  <div class="agents-shell">
    <div class="agents-layout">
      <!-- ── LEFT: 3 Agent Status Panels ─────────────────────────────────── -->
      <aside class="agent-sidebar">
        <div
          v-for="agent in agentPanels"
          :key="agent.type"
          :class="['agent-panel terminal-card', `agent-${agent.type.toLowerCase()}`,
                   { inhibited: agentsStore.agentStatus[agent.type] === 'INHIBITED' }]"
        >
          <div class="agent-panel-header">
            <span :class="['agent-tier-badge', agent.tierClass]">TIER {{ agent.tier }}</span>
            <span class="agent-name hud">{{ agent.type }}</span>
            <span :class="['agent-dot', agentsStore.agentStatus[agent.type].toLowerCase()]">●</span>
          </div>
          <div class="agent-desc text-dim mono">{{ agent.description }}</div>
          <div class="agent-metrics">
            <div class="metric">
              <span class="metric-label">LLM</span>
              <span class="metric-val text-cyan">{{ agent.llm }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">STATUS</span>
              <span :class="['metric-val', statusClass(agent.type)]">
                {{ agentsStore.agentStatus[agent.type] }}
              </span>
            </div>
            <div class="metric">
              <span class="metric-label">TOTAL DECISIONS</span>
              <span class="metric-val text-green mono">{{ agentsStore.stats[agent.type] || 0 }}</span>
            </div>
            <div class="metric" v-if="latestEvent(agent.type)">
              <span class="metric-label">LATENCY</span>
              <span class="metric-val text-green">{{ latestEvent(agent.type)?.latencyMs }}ms</span>
            </div>
          </div>
        </div>

        <!-- Subsumption Override Status -->
        <div :class="['terminal-card', agentsStore.subsumptionActive ? 'subsumption-alert' : '']">
          <div class="terminal-card-header">[ SUBSUMPTION_OVERRIDE ]</div>
          <div :class="['sub-status-display', agentsStore.subsumptionActive ? 'text-red' : 'text-green']">
            {{ agentsStore.subsumptionActive ? '⚠ INHIBIT ACTIVE' : '✓ MOTION ENABLED' }}
          </div>
          <div class="sub-priority-chain mono text-dim">
            SAFETY(0) &gt; MEDICAL(1) &gt; EMPATHY(2)
          </div>
        </div>
      </aside>

      <!-- ── RIGHT: Live Event Stream ──────────────────────────────────────── -->
      <main class="event-stream-panel">
        <div class="stream-header terminal-card-header">
          [ AGENT_EVENT_STREAM ] &nbsp;
          <span class="text-dim">{{ agentsStore.events.length }} events captured</span>
          <button class="cmd-btn" style="margin-left:auto;font-size:9px" @click="agentsStore.clearEvents()">
            CLEAR_LOG
          </button>
        </div>

        <!-- Virtual list: only render visible events (performance) -->
        <div class="event-list" ref="eventListRef">
          <div
            v-for="ev in agentsStore.events"
            :key="ev.id"
            :class="['event-row', `ev-${ev.agentType.toLowerCase()}`,
                     ev.alertLevel === 'CRITICAL' || ev.alertLevel === 'STROKE' ? 'ev-critical' : '']"
          >
            <span class="ev-time mono text-dim">{{ formatTime(ev.triggeredAt) }}</span>
            <span :class="['ev-agent hud', agentColorClass(ev.agentType)]">
              [{{ ev.agentType.padEnd(10) }}]
            </span>
            <span class="ev-provider text-dim mono">({{ ev.llmProvider }}/{{ ev.latencyMs }}ms)</span>
            <span class="ev-decision mono">{{ truncate(ev.outputDecision, 120) }}</span>
          </div>

          <!-- Empty state -->
          <div v-if="agentsStore.events.length === 0" class="empty-stream text-dim mono">
            &gt;&gt;&gt; AWAITING AGENT EVENTS... CONNECT MQTT BROKER TO BEGIN
          </div>
        </div>

        <!-- Live thought ticker (last event animated) -->
        <div class="thought-ticker" v-if="agentsStore.events.length > 0">
          <span class="text-dim mono">&gt;&gt;&gt; LAST_DECISION: </span>
          <span class="ticker-text text-green mono">{{ agentsStore.events[0]?.outputDecision }}</span>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useAgentsStore, type AgentType } from '../stores/agents'

const agentsStore = useAgentsStore()
const eventListRef = ref<HTMLElement | null>(null)

onMounted(() => {
  agentsStore.fetchLogs()
  agentsStore.fetchStats()
})

const agentPanels = [
  {
    type: 'SAFETY' as AgentType, tier: 0, tierClass: 'tier-0',
    description: 'LiDAR/IMU deterministic. No LLM. < 5ms response. Highest Subsumption priority.',
    llm: 'THRESHOLD'
  },
  {
    type: 'MEDICAL' as AgentType, tier: 1, tierClass: 'tier-1',
    description: 'Vital sign analysis, stroke prediction. Groq Llama 70B for clinical reasoning.',
    llm: 'GROQ-70B'
  },
  {
    type: 'EMPATHETIC' as AgentType, tier: 2, tierClass: 'tier-2',
    description: 'Emotional conversation. Groq Llama 8B. Volatile context (RAM-only).',
    llm: 'GROQ-8B'
  },
]

function latestEvent(type: AgentType) {
  return agentsStore.events.find(e => e.agentType === type)
}

function statusClass(type: AgentType) {
  const s = agentsStore.agentStatus[type]
  return s === 'ACTIVE' ? 'text-green' : s === 'INHIBITED' ? 'text-red' : 'text-dim'
}

function agentColorClass(type: string) {
  const map: Record<string, string> = {
    SAFETY: 'text-green', MEDICAL: 'text-cyan', EMPATHETIC: 'text-cyan'
  }
  return map[type] || 'text-dim'
}

function formatTime(iso: string) {
  try { return new Date(iso).toTimeString().slice(0, 8) } catch { return '--:--:--' }
}
function truncate(s: string, max: number) {
  return s?.length > max ? s.slice(0, max) + '...' : s
}
</script>

<style scoped>
.agents-shell { display: flex; flex-direction: column; height: 100vh; }
.agents-layout { display: grid; grid-template-columns: 280px 1fr; flex: 1; overflow: hidden; }

.agent-sidebar {
  display: flex; flex-direction: column; gap: 8px; padding: 12px;
  border-right: 1px solid var(--color-border-dim); overflow-y: auto;
}

.agent-panel { padding: 10px 12px; transition: border-color 200ms; }
.agent-panel.inhibited { border-color: var(--color-accent-red) !important; opacity: 0.7; }
.agent-panel-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.agent-tier-badge {
  font-family: var(--font-hud); font-size: 8px; letter-spacing: 0.1em;
  padding: 2px 6px; border: 1px solid;
}
.tier-0 { border-color: var(--color-accent-green); color: var(--color-accent-green); }
.tier-1 { border-color: var(--color-accent-cyan); color: var(--color-accent-cyan); }
.tier-2 { border-color: var(--color-text-dim); color: var(--color-text-dim); }
.agent-name { font-size: 11px; letter-spacing: 0.2em; flex: 1; }
.agent-dot { font-size: 10px; }
.agent-dot.active { color: var(--color-accent-green); animation: pulse-dot 1.5s ease-in-out infinite; }
.agent-dot.inhibited { color: var(--color-accent-red); }
.agent-dot.idle { color: var(--color-text-dim); }
@keyframes pulse-dot { 0%,100%{opacity:1} 50%{opacity:0.2} }

.agent-desc { font-size: 10px; line-height: 1.5; margin-bottom: 8px; }
.agent-metrics { display: flex; flex-direction: column; gap: 3px; }
.metric { display: flex; justify-content: space-between; font-size: 10px; }
.metric-label { font-family: var(--font-hud); font-size: 8px; letter-spacing: 0.15em; color: var(--color-text-dim); }

.subsumption-alert { border-color: var(--color-accent-red) !important; }
.sub-status-display { font-family: var(--font-hud); font-size: 14px; font-weight: 700;
  letter-spacing: 0.2em; text-align: center; padding: 8px 0; margin-top: 6px; }
.sub-priority-chain { font-size: 9px; text-align: center; margin-top: 4px; }

.event-stream-panel { display: flex; flex-direction: column; padding: 12px; overflow: hidden; }
.stream-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
  font-family: var(--font-hud); font-size: 9px; letter-spacing: 0.2em;
  color: var(--color-accent-green); text-transform: uppercase;
}

.event-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.event-row {
  display: grid;
  grid-template-columns:
    minmax(58px, 65px)
    minmax(90px, 120px)
    minmax(70px, 110px)
    minmax(0, 1fr);
  gap: 6px;
  font-size: 10px;
  line-height: 1.6;
  padding: 2px 4px;
  border-left: 2px solid transparent;
  transition: border-color 100ms;
  align-items: start;
}
.event-row:hover { border-left-color: var(--color-accent-green); background: rgba(0,255,102,0.03); }
.ev-critical { border-left-color: var(--color-accent-red) !important; background: rgba(255,51,51,0.05); }
.ev-decision {
  color: var(--color-text-primary);
  word-break: break-word;
  white-space: normal;
  overflow-wrap: anywhere;
}
.ev-time, .ev-agent, .ev-provider {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.empty-stream { padding: 20px; text-align: center; font-size: 11px; animation: blink-cursor 1s step-end infinite; }
@keyframes blink-cursor { 50%{opacity:0} }

.thought-ticker {
  border-top: 1px solid var(--color-border-dim); padding: 6px 4px; font-size: 10px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex-shrink: 0;
}
.ticker-text { animation: slide-in 0.3s ease; }
@keyframes slide-in { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
</style>
