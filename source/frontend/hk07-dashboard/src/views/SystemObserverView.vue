<template>
  <div class="observer-shell cyber-scanlines">
    <!-- HUD status band -->
    <div class="hud-header">
      <div class="hud-title-wrapper">
        <span class="hud-marker">// SYSTEM_STATUS_MATRIX</span>
        <h1 class="hud-title font-orbitron">COCKPIT STATUS COMMAND MATRIX</h1>
      </div>
      <div class="hud-meta font-mono">
        <div class="meta-item">
          <span class="text-dim">OPERATOR:</span>
          <span class="text-green">HK07_CONSOLE_ROOT</span>
        </div>
        <div class="meta-item">
          <span class="text-dim">STATUS:</span>
          <span class="text-green blink">[ ARMED_ACTIVE ]</span>
        </div>
        <div class="meta-item">
          <span class="text-dim">REFRESH_RATE:</span>
          <span class="text-amber">2.0Hz</span>
        </div>
      </div>
    </div>

    <!-- Main Grid containing Blocks A, B, C, D -->
    <div class="matrix-grid">
      <!-- BLOCK A: CORE SUBSYSTEM MAPPING & PORT MATRIX -->
      <div class="matrix-card block-a">
        <div class="card-corner-reticles">
          <div class="reticle tl">+</div>
          <div class="reticle tr">+</div>
          <div class="reticle bl">+</div>
          <div class="reticle br">+</div>
        </div>
        <div class="card-header border-green">
          <span class="header-tag text-green">[ BLOCK_A ]</span>
          <h2 class="card-title font-orbitron">CORE SUBSYSTEM MAPPING & PORT MATRIX</h2>
        </div>
        <div class="card-body font-mono text-xs">
          <table class="hud-table">
            <thead>
              <tr>
                <th>SUBSYSTEM</th>
                <th>PORT</th>
                <th>PROTOCOL</th>
                <th>STATE</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="text-white font-bold">ROS2 Server Bridge</td>
                <td class="text-green">9090</td>
                <td>WebSocket</td>
                <td>
                  <span :class="isRosOnline ? 'state-badge green' : 'state-badge red'">
                    {{ isRosOnline ? '[ONLINE]' : '[OFFLINE]' }}
                  </span>
                </td>
              </tr>
              <tr>
                <td class="text-white font-bold">hk07-core Backend</td>
                <td class="text-green">8888</td>
                <td>HTTP/REST</td>
                <td>
                  <span :class="isCoreOnline ? 'state-badge green' : 'state-badge red'">
                    {{ isCoreOnline ? '[ONLINE]' : '[OFFLINE]' }}
                  </span>
                </td>
              </tr>
              <tr>
                <td class="text-white font-bold">hk07-agent MAS Core</td>
                <td class="text-green">8000</td>
                <td>HTTP/REST</td>
                <td>
                  <span :class="isAgentOnline ? 'state-badge green' : 'state-badge red'">
                    {{ isAgentOnline ? '[ONLINE]' : '[OFFLINE]' }}
                  </span>
                </td>
              </tr>
              <tr>
                <td class="text-white font-bold">Dashboard Client</td>
                <td class="text-green">3000</td>
                <td>HTTP</td>
                <td>
                  <span class="state-badge green">[ONLINE]</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="card-footer-metrics mt-4 pt-2 border-t border-[rgba(0,255,102,0.1)]">
            <div class="flex justify-between">
              <span>SCANNER_LINK_STATE:</span>
              <span class="text-green font-bold">CONNECTED_STABLE</span>
            </div>
          </div>
        </div>
      </div>

      <!-- BLOCK B: ROS2 WEBSOCKET LIVE SUBSCRIBER TELEMETRY -->
      <div class="matrix-card block-b">
        <div class="card-corner-reticles">
          <div class="reticle tl">+</div>
          <div class="reticle tr">+</div>
          <div class="reticle bl">+</div>
          <div class="reticle br">+</div>
        </div>
        <div class="card-header border-green">
          <span class="header-tag text-green">[ BLOCK_B ]</span>
          <h2 class="card-title font-orbitron">ROS2 WEBSOCKET LIVE SUBSCRIBER TELEMETRY</h2>
        </div>
        <div class="card-body font-mono text-xs">
          <div class="summary-metric mb-3">
            <span class="text-dim">ACTIVE CONNECTED CLIENTS:</span>
            <span class="text-green font-bold ml-2 text-sm">2 clients total</span>
          </div>
          <div class="topic-grid">
            <div class="topic-header text-dim">
              <span>TOPIC UPLINK CHANNEL</span>
              <span class="text-right">INGESTION STATE</span>
            </div>
            <div class="topic-row">
              <span class="text-white">/telemetry/sensors/vitals</span>
              <span class="text-green font-bold">[ACTIVE] (Streaming)</span>
            </div>
            <div class="topic-row">
              <span class="text-white">/sensors/camera/thermal_rppg</span>
              <span class="text-green font-bold">[ACTIVE] (MediaPipe Flow)</span>
            </div>
            <div class="topic-row">
              <span class="text-white">/vitals/wristband</span>
              <span class="text-green font-bold">[ACTIVE] (Wristband Sim 001)</span>
            </div>
            <div class="topic-row">
              <span class="text-white">/telemetry/imu</span>
              <span class="text-green font-bold">[ACTIVE] (9-DOF Stream)</span>
            </div>
            <div class="topic-row">
              <span class="text-white">/hk07/perception/clinical</span>
              <span class="text-green font-bold">[ACTIVE] (LLM Vision Analysis)</span>
            </div>
          </div>
        </div>
      </div>

      <!-- BLOCK C: AI COGNITIVE CORES & MEMORY MATRIX -->
      <div class="matrix-card block-c">
        <div class="card-corner-reticles">
          <div class="reticle tl">+</div>
          <div class="reticle tr">+</div>
          <div class="reticle bl">+</div>
          <div class="reticle br">+</div>
        </div>
        <div class="card-header border-amber">
          <span class="header-tag text-amber">[ BLOCK_C ]</span>
          <h2 class="card-title font-orbitron">AI COGNITIVE CORES & MEMORY MATRIX</h2>
        </div>
        <div class="card-body font-mono text-xs">
          <div class="info-row text-xs flex justify-between">
            <span class="text-dim">ORCHESTRATOR:</span>
            <span class="text-green font-bold">USE_ORCHESTRATOR_V2 = true</span>
          </div>
          <div class="info-row text-[10px] text-green pl-2 mb-2">
            <span>(Active Cognitive Tool-Calling Router)</span>
          </div>
          
          <div class="section-title text-green border-b border-[rgba(0,255,102,0.1)] pb-1 mb-2">// LANCE_VECTOR_DB_CACHE</div>
          <div class="info-row">
            <span>owner_memory:</span>
            <span class="text-green font-bold">[LOADED] (0 records)</span>
          </div>
          <div class="info-row">
            <span>medical_guidelines:</span>
            <span class="text-green font-bold">[LOADED] (0 records)</span>
          </div>
          <div class="info-row">
            <span>agent_chat_memory:</span>
            <span class="text-green font-bold">[LOADED] (96 records compacted)</span>
          </div>

          <div class="section-title mt-3 text-amber border-b border-[rgba(255,176,0,0.1)] pb-1 mb-2">// SUBSUMPTION ACTIVE LAYERS</div>
          <div class="info-row">
            <span>Tầng 0 (Safety Agent):</span>
            <span class="text-green font-bold">[ARMED & ACTIVE]</span>
          </div>
          <div class="info-row">
            <span>Tầng 1 (Medical Agent):</span>
            <span class="text-green font-bold">[ACTIVE]</span>
          </div>
          <div class="info-row">
            <span>Tầng 2 (Empathy Agent):</span>
            <span class="text-green font-bold">[ACTIVE]</span>
          </div>

          <div class="info-row mt-3 pt-2 border-t border-[rgba(255,176,0,0.1)]">
            <span class="text-dim">EDGE EXECUTION:</span>
            <span class="text-red font-bold">[OFFLINE] (Fallback: Local Rule-Based Active)</span>
          </div>
        </div>
      </div>

      <!-- BLOCK D: DATA LEDGER & BROKER UPLINK DETAILS -->
      <div class="matrix-card block-d">
        <div class="card-corner-reticles">
          <div class="reticle tl">+</div>
          <div class="reticle tr">+</div>
          <div class="reticle bl">+</div>
          <div class="reticle br">+</div>
        </div>
        <div class="card-header border-green">
          <span class="header-tag text-green">[ BLOCK_D ]</span>
          <h2 class="card-title font-orbitron">DATA LEDGER & BROKER UPLINK DETAILS</h2>
        </div>
        <div class="card-body font-mono text-xs">
          <div class="ledger-grid">
            <div class="ledger-row">
              <span class="label">DATABASE_TYPE:</span>
              <span class="val text-white">MySQL/MariaDB (Version: 8.4.9)</span>
            </div>
            <div class="ledger-row flex-col items-start gap-1">
              <span class="label">DATABASE_URL:</span>
              <span class="val text-green font-mono break-all text-[10px]" style="line-height:1.2;">jdbc:mysql://localhost:3306/hk07db?useSSL=false&serverTimezone=UTC</span>
            </div>
            <div class="ledger-row">
              <span class="label">DATABASE_USER:</span>
              <span class="val text-green">hk07user@172.21.0.1</span>
            </div>
            <div class="ledger-row">
              <span class="label">DATABASE_DRIVER:</span>
              <span class="val text-white">MySQL Connector/J</span>
            </div>
            <div class="ledger-row">
              <span class="label">REDIS_CACHE_HOST:</span>
              <span class="val text-green">::1 | Port: 6379 (Active Buffer State)</span>
            </div>
            <div class="ledger-row">
              <span class="label">MQTT_MESSAGE_BROKER:</span>
              <span class="val text-green">tcp://[::1]:1883 (Active Broker Uplink)</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom console logs panel -->
    <div class="terminal-console-panel matrix-card">
      <div class="card-corner-reticles">
        <div class="reticle tl">+</div>
        <div class="reticle tr">+</div>
        <div class="reticle bl">+</div>
        <div class="reticle br">+</div>
      </div>
      <div class="console-header border-green">
        <div class="flex items-center gap-2">
          <span class="console-dot animate-pulse"></span>
          <span class="font-orbitron text-xs font-bold text-green">LIVE TELEMETRY LOGS STREAM PANEL</span>
        </div>
        <span class="font-mono text-[9px] text-dim">[ BUFFER_CAP: 100_LINES ]</span>
      </div>
      <div class="console-logs-window font-mono text-[11px]" ref="consoleLogsRef">
        <div v-for="(log, idx) in logs" :key="idx" :class="['log-line', log.type]">
          <span class="log-ts text-dim">[{{ log.timestamp }}]</span>
          <span class="log-level" :class="log.type">[{{ log.level }}]</span>
          <span class="log-content text-white">{{ log.content }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useVitalsStore } from '../stores/vitals'

const vitalsStore = useVitalsStore()

const isRosOnline = computed(() => vitalsStore.isConnected)
const isCoreOnline = ref(false)
const isAgentOnline = ref(false)

interface LogEntry {
  timestamp: string
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG'
  type: 'info' | 'warn' | 'error' | 'debug'
  content: string
}

const logs = ref<LogEntry[]>([])
const consoleLogsRef = ref<HTMLDivElement | null>(null)

function getFormattedTime(): string {
  const d = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${d.getMilliseconds().toString().padStart(3, '0')}`
}

function addLog(level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG', content: string) {
  const typeMap = {
    INFO: 'info',
    WARN: 'warn',
    ERROR: 'error',
    DEBUG: 'debug'
  } as const

  logs.value.push({
    timestamp: getFormattedTime(),
    level,
    type: typeMap[level],
    content
  })

  // Cap at 100 lines
  if (logs.value.length > 100) {
    logs.value.shift()
  }

  // Auto scroll to bottom
  nextTick(() => {
    if (consoleLogsRef.value) {
      consoleLogsRef.value.scrollTop = consoleLogsRef.value.scrollHeight
    }
  })
}

// Generate mock telemetry ticks
const mockLogTemplates = [
  { level: 'INFO' as const, content: 'hk07.main — [ISOLATED_HEARTBEAT] Connected to Rosbridge. Starting pulse check transmission...' },
  { level: 'INFO' as const, content: 'hk07.core — [MQTT Call] Inbound processor status: SUBSUMPTION_INHIBIT active=true trigger=FALL_RISK' },
  { level: 'INFO' as const, content: 'hk07.agent — [LANCEDB] Compacted 96 chat memory logs successfully' },
  { level: 'INFO' as const, content: 'hk07.core — [SECURITY] Unauthenticated request allowed for path: /actuator/health' },
  { level: 'INFO' as const, content: 'hk07.agent — [CORS] Dynamic origin check succeeded for http://localhost:3000' },
  { level: 'DEBUG' as const, content: 'hk07.core — [API_KEY_BYPASS] Service-to-service auth successful for path=/api/v1/agents/status' },
  { level: 'INFO' as const, content: 'hk07.core — [AUDIT] INHIBIT | actor=0 status=SUCCESS' },
  { level: 'WARN' as const, content: 'hk07.agent — [SAFETY_WORKER] Critical facial distress detected via IPWebcam; empathy dialogue inhibited.' },
  { level: 'INFO' as const, content: 'hk07.main — [HEARTBEAT] Send frame payload seq=4028' },
  { level: 'DEBUG' as const, content: 'hk07.core — [REDIS] Cache hit for vital telemetry key "hk07:vitals:latest"' },
  { level: 'INFO' as const, content: 'hk07.agent — [FHIR] Rendered 1 clinical observation bundle for patient a0000000' }
]

function triggerMockLog() {
  const template = mockLogTemplates[Math.floor(Math.random() * mockLogTemplates.length)]
  addLog(template.level, template.content)
}

async function runHealthChecks() {
  try {
    const resp = await fetch('http://localhost:8888/actuator/health', { method: 'GET', mode: 'cors' })
    isCoreOnline.value = resp.ok || resp.status === 200 || resp.status === 401
  } catch {
    isCoreOnline.value = false
  }

  try {
    const resp = await fetch('http://localhost:8000/health', { method: 'GET', mode: 'cors' })
    isAgentOnline.value = resp.ok || resp.status === 200
  } catch {
    isAgentOnline.value = false
  }
}

let logIntervalId: number | null = null
let healthIntervalId: number | null = null

onMounted(() => {
  // Add initial startup logs
  addLog('INFO', 'hk07.main — Initializing System Observability HUD Cockpit...')
  addLog('INFO', 'hk07.main — Establishing connection checks to core subsystems...')
  addLog('INFO', 'hk07.main — Connected to store memory states.')
  
  runHealthChecks()
  
  // Set intervals
  logIntervalId = window.setInterval(triggerMockLog, 2000)
  healthIntervalId = window.setInterval(runHealthChecks, 3000)
})

onUnmounted(() => {
  if (logIntervalId != null) clearInterval(logIntervalId)
  if (healthIntervalId != null) clearInterval(healthIntervalId)
})
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@500;700&family=Roboto+Mono:wght@400;700&family=VT323&display=swap');

.font-orbitron {
  font-family: 'Orbitron', 'Rajdhani', sans-serif;
  letter-spacing: 0.08em;
}

.font-mono {
  font-family: 'VT323', 'Roboto Mono', monospace;
}

.cyber-scanlines {
  position: relative;
  overflow: hidden;
}

.cyber-scanlines::before {
  content: " ";
  display: block;
  position: absolute;
  top: 0; left: 0; bottom: 0; right: 0;
  background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
  z-index: 10;
  background-size: 100% 4px, 6px 100%;
  pointer-events: none;
}

.observer-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
  background-color: #000000;
  color: #00FF66;
  padding: 16px;
  gap: 16px;
  box-sizing: border-box;
}

.hud-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  background: rgba(10, 10, 10, 0.85);
  border: 1px solid rgba(0, 255, 102, 0.2);
  backdrop-filter: blur(12px);
  position: relative;
}

.hud-title-wrapper {
  display: flex;
  flex-direction: column;
}

.hud-marker {
  font-size: 10px;
  color: #00FF66;
  letter-spacing: 0.15em;
}

.hud-title {
  margin: 0;
  font-size: 18px;
  color: #00FF66;
  font-weight: 700;
  text-shadow: 0 0 10px rgba(0, 255, 102, 0.4);
}

.hud-meta {
  display: flex;
  gap: 24px;
  font-size: 13px;
}

.meta-item {
  display: flex;
  gap: 8px;
}

.text-dim {
  color: rgba(0, 255, 102, 0.5);
}

.text-green {
  color: #00FF66;
  text-shadow: 0 0 8px rgba(0, 255, 102, 0.3);
}

.text-amber {
  color: #FFB000;
  text-shadow: 0 0 8px rgba(255, 176, 0, 0.3);
}

.text-red {
  color: #FF3333;
  text-shadow: 0 0 8px rgba(255, 51, 51, 0.3);
}

.blink {
  animation: hud-blink 1.5s infinite;
}

@keyframes hud-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.matrix-grid {
  display: grid;
  grid-template-columns: 3fr 7fr;
  gap: 16px;
  align-items: start;
}

.matrix-card {
  position: relative;
  background: rgba(10, 10, 10, 0.9);
  border: 1px solid rgba(0, 255, 102, 0.15);
  backdrop-filter: blur(12px);
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  flex-direction: column;
  margin-bottom: 12px;
  border-bottom: 1px solid;
  padding-bottom: 6px;
}

.card-header.border-green { border-bottom-color: rgba(0, 255, 102, 0.3); }
.card-header.border-amber { border-bottom-color: rgba(255, 176, 0, 0.3); }

.header-tag {
  font-size: 10px;
  font-weight: bold;
  letter-spacing: 0.1em;
}

.card-title {
  margin: 2px 0 0 0;
  font-size: 13px;
  font-weight: bold;
  color: #ffffff;
}

.card-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Reticles styling */
.card-corner-reticles {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  pointer-events: none;
}

.reticle {
  position: absolute;
  color: rgba(0, 255, 102, 0.7);
  font-family: monospace;
  font-size: 14px;
  line-height: 1;
}

.reticle.tl { top: -2px; left: 2px; }
.reticle.tr { top: -2px; right: 2px; }
.reticle.bl { bottom: -2px; left: 2px; }
.reticle.br { bottom: -2px; right: 2px; }

/* Table styling for block A */
.hud-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 4px;
}

.hud-table th, .hud-table td {
  padding: 6px 8px;
  text-align: left;
  border-bottom: 1px solid rgba(0, 255, 102, 0.05);
}

.hud-table th {
  color: rgba(0, 255, 102, 0.5);
  font-weight: normal;
  font-size: 11px;
}

.hud-table td {
  color: rgba(255, 255, 255, 0.85);
  font-size: 12px;
}

.state-badge {
  font-weight: bold;
  font-size: 11px;
  padding: 1px 4px;
  border-radius: 2px;
}

.state-badge.green {
  color: #00FF66;
  background: rgba(0, 255, 102, 0.1);
  border: 1px solid rgba(0, 255, 102, 0.3);
}

.state-badge.red {
  color: #FF3333;
  background: rgba(255, 51, 51, 0.1);
  border: 1px solid rgba(255, 51, 51, 0.3);
}

/* Topic list for block B */
.topic-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.topic-header {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(0, 255, 102, 0.1);
}

.topic-row {
  display: flex;
  justify-content: space-between;
  padding: 4px 6px;
  background: rgba(0, 255, 102, 0.02);
  border-left: 2px solid rgba(0, 255, 102, 0.3);
}

.topic-row:hover {
  background: rgba(0, 255, 102, 0.05);
}

/* Info rows for block C and general */
.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 2px 0;
  font-size: 12px;
}

.section-title {
  font-size: 10px;
  font-weight: bold;
  letter-spacing: 0.1em;
  margin-top: 10px;
}

/* Ledger styling for block D */
.ledger-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ledger-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  padding-bottom: 4px;
  border-bottom: 1px dashed rgba(0, 255, 102, 0.1);
}

.ledger-row .label {
  color: rgba(0, 255, 102, 0.5);
}

/* Terminal Console Panel styling */
.terminal-console-panel {
  flex: 0 0 180px;
  display: flex;
  flex-direction: column;
  padding: 12px;
  border-color: rgba(0, 255, 102, 0.25);
  background: rgba(5, 5, 5, 0.95);
}

.console-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 6px;
  margin-bottom: 6px;
  border-bottom: 1px solid rgba(0, 255, 102, 0.3);
}

.console-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #FF3333;
  box-shadow: 0 0 6px #FF3333;
}

.console-logs-window {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 6px;
  background: #000000;
  border: 1px solid rgba(0, 255, 102, 0.1);
}

.log-line {
  display: flex;
  gap: 8px;
  line-height: 1.4;
  white-space: pre-wrap;
}

.log-line.info .log-level { color: #00FF66; }
.log-line.warn .log-level { color: #FFB000; }
.log-line.error .log-level { color: #FF3333; }
.log-line.debug .log-level { color: #00FF66; }

.log-ts {
  flex-shrink: 0;
}

.log-level {
  font-weight: bold;
  flex-shrink: 0;
}

.log-content {
  word-break: break-all;
}

/* Custom scrollbars */
.console-logs-window::-webkit-scrollbar,
.observer-shell::-webkit-scrollbar {
  width: 4px;
}

.console-logs-window::-webkit-scrollbar-track,
.observer-shell::-webkit-scrollbar-track {
  background: #000000;
}

.console-logs-window::-webkit-scrollbar-thumb,
.observer-shell::-webkit-scrollbar-thumb {
  background: rgba(0, 255, 102, 0.3);
}
</style>
