<template>
  <div class="companion-canvas">
    <!-- Main asymmetric split layout inside companion view -->
    <div class="companion-layout">
      
      <!-- Left side: The Chat Console (75%) -->
      <section class="chat-console-panel corner-reticle">
        <div class="panel-header">
          <div class="header-title">
            <span class="pulse-dot text-cyan mr-2">●</span>
            <span>AGENT_COMPANION_UPLINK // ID: HUGO-AGENT-007</span>
          </div>
          <div class="connection-status">
            <span class="status-label">UPLINK_STATE:</span>
            <span class="status-value text-green">SECURE_ESTABLISHED</span>
          </div>
        </div>

        <!-- Chat messages view -->
        <div class="chat-history" ref="chatHistoryRef">
          <div v-for="(msg, i) in chatLog" :key="i" :class="['chat-bubble-row', msg.role]">
            <div class="avatar-col">
              <span class="avatar-tag">{{ msg.role === 'user' ? 'USR' : 'HUG' }}</span>
            </div>
            <div class="msg-content-col">
              <div class="msg-header">
                <span class="sender-name">{{ msg.role === 'user' ? 'OPERATOR' : 'AGENT HUGO' }}</span>
                <span class="msg-time">{{ msg.timestamp }}</span>
              </div>
              <div class="msg-body">
                <span class="prefix" v-if="msg.role === 'user'">>>> </span>
                <span class="content-text">{{ msg.content }}</span>
              </div>
            </div>
          </div>

          <div v-if="chatLoading" class="chat-bubble-row hugo">
            <div class="avatar-col">
              <span class="avatar-tag thinking">...</span>
            </div>
            <div class="msg-content-col">
              <div class="msg-header">
                <span class="sender-name">AGENT HUGO</span>
                <span class="msg-time">ANALYZING...</span>
              </div>
              <div class="msg-body thinking-state">
                <div class="pulsing-wave">
                  <span></span><span></span><span></span><span></span>
                </div>
                <span class="content-text text-dim">HUGO IS PROCESSING UPLINK DATA PACKETS...</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Suggesstions & Prompt chips -->
        <div class="prompt-suggestions">
          <button v-for="chip in suggestionChips" :key="chip.label" 
                  class="suggestion-chip" @click="applySuggestion(chip.prompt)">
            <span class="text-dim mr-1">[+]</span> {{ chip.label }}
          </button>
        </div>

        <!-- Chat input bar -->
        <div class="chat-input-bar">
          <input v-model="userInput" 
                 class="tactical-input font-mono w-full" 
                 placeholder="ENTER TACTICAL COMMAND OR INQUIRY TO AGENT HUGO..."
                 @keydown.enter="sendChat" 
                 :disabled="chatLoading" />
          <button class="cmd-btn send-btn" 
                  @click="sendChat" 
                  :disabled="!userInput.trim() || chatLoading">
            TRANSMIT_CMD
          </button>
        </div>
      </section>

      <!-- Right side: Agent Telemetry & Local Monitor (25%) -->
      <aside class="companion-telemetry-panel">
        
        <!-- Animated Voice/Brain Scope -->
        <div class="terminal-card scope-card">
          <div class="terminal-card-header">[ AGENT_COGNITIVE_SCOPE ]</div>
          <div class="scope-container">
            <div :class="['scope-wave', chatLoading ? 'active' : 'idle']">
              <div class="circle outer"></div>
              <div class="circle middle"></div>
              <div class="circle inner"></div>
              <div class="pulse-line"></div>
            </div>
            <div class="scope-status font-mono text-[9px] text-center mt-3">
              COGNITIVE STATE: <span :class="chatLoading ? 'text-orange animate-pulse' : 'text-green'">{{ chatLoading ? 'COMPUTING_RESPONSE' : 'STANDBY_LISTENING' }}</span>
            </div>
          </div>
        </div>

        <!-- Agent Specs -->
        <div class="terminal-card">
          <div class="terminal-card-header">[ AGENT_SPECIFICATIONS ]</div>
          <div class="spec-grid font-mono text-[10px]">
            <div class="spec-row">
              <span class="label">MODEL_CORE:</span>
              <span class="val text-cyan">Llama3-Groq-8B</span>
            </div>
            <div class="spec-row">
              <span class="label">TEMPERATURE:</span>
              <span class="val text-cyan">0.45 (STABLE)</span>
            </div>
            <div class="spec-row">
              <span class="label">SPEED_RATING:</span>
              <span class="val text-green">~78.4 Tok/s</span>
            </div>
            <div class="spec-row">
              <span class="label">CONTEXT_LEN:</span>
              <span class="val text-cyan">8,192 Tok</span>
            </div>
            <div class="spec-row">
              <span class="label">EMPATHY_BIAS:</span>
              <span class="val text-green">94.8% ALPHA</span>
            </div>
          </div>
        </div>

        <!-- Live Vitals Reference Panel -->
        <div class="terminal-card">
          <div class="terminal-card-header">[ LIVE_TELEMETRY_REF ]</div>
          <div class="spec-grid font-mono text-[10px] mb-2" style="padding-bottom: 6px;">
            <div class="spec-row">
              <span class="label">HEART RATE:</span>
              <span :class="['val font-bold', hrClass]">{{ vitalsStore.current.heartRate || '--' }} BPM</span>
            </div>
            <div class="spec-row">
              <span class="label">OXYGEN SAT:</span>
              <span :class="['val font-bold', spo2Class]">{{ vitalsStore.current.spo2?.toFixed(1) || '--' }} %</span>
            </div>
            <div class="spec-row">
              <span class="label">BLOOD PRESS:</span>
              <span class="val text-cyan">{{ vitalsStore.current.systolic || '--' }}/{{ vitalsStore.current.diastolic || '--' }}</span>
            </div>
            <div class="spec-row">
              <span class="label">BODY TEMP:</span>
              <span class="val text-cyan">{{ vitalsStore.current.bodyTemperature?.toFixed(1) || '--' }} °C</span>
            </div>
            <div class="spec-row border-t border-dashed border-[#0052ff]/30 pt-1 mt-1">
              <span class="label">ALERT STATE:</span>
              <span :class="['val font-bold', vitalsStore.isEmergency ? 'text-red animate-pulse' : 'text-green']">
                {{ vitalsStore.isEmergency ? '⚠ EMERGENCY' : '✓ NORMAL' }}
              </span>
            </div>
          </div>
          <EcgWaveform :width="240" :height="50" />
        </div>

      </aside>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useVitalsStore } from '../stores/vitals'
import { useAuthStore } from '../stores/auth'
import api from '../services/api'
import EcgWaveform from '../components/EcgWaveform.vue'

const vitalsStore = useVitalsStore()
const authStore = useAuthStore()

interface ChatMessage {
  role: 'user' | 'hugo'
  content: string
  timestamp: string
}

const userInput = ref('')
const chatLoading = ref(false)
const chatHistoryRef = ref<HTMLElement | null>(null)

const chatLog = ref<ChatMessage[]>([
  {
    role: 'hugo',
    content: 'Chào mừng Operator. Tôi là Hugo, Trợ lý Y tế Đồng hành của bạn. Tôi luôn trực tuyến để phân tích các chỉ số sức khỏe của bạn và đề xuất các hành động an toàn tối ưu.',
    timestamp: getCurrentTimeString()
  }
])

const suggestionChips = [
  { label: 'ANALYZE_VITALS', prompt: 'Hãy phân tích chỉ số sinh tồn (vitals) hiện tại của tôi.' },
  { label: 'HEALTH_ADVICE', prompt: 'Cho tôi lời khuyên bảo vệ sức khỏe tim mạch.' },
  { label: 'EXPLAIN_SUBSUMPTION', prompt: 'Làm thế nào để hệ thống an toàn Lidar và Subsumption ngăn chặn va chạm?' },
  { label: 'SYSTEM_STATUS', prompt: 'Kiểm tra trạng thái liên kết dữ liệu thiết bị đeo tay (Wristband).' }
]

function getCurrentTimeString() {
  const d = new Date()
  return d.toTimeString().split(' ')[0]
}

// Vitals thresholds color mapping
const hrClass = computed(() => {
  const hr = vitalsStore.current.heartRate
  if (!hr) return 'text-dim'
  if (hr < 50 || hr > 120) return 'text-red'
  if (hr < 60 || hr > 100) return 'text-orange'
  return 'text-green'
})

const spo2Class = computed(() => {
  const s = vitalsStore.current.spo2
  if (!s) return 'text-dim'
  if (s < 90) return 'text-red'
  if (s < 94) return 'text-orange'
  return 'text-green'
})

async function sendChat() {
  const msg = userInput.value.trim()
  if (!msg) return
  
  userInput.value = ''
  chatLoading.value = true
  
  chatLog.value.push({
    role: 'user',
    content: msg,
    timestamp: getCurrentTimeString()
  })
  
  await nextTick()
  scrollChatToBottom()

  try {
    const resp = await api.post('/agents/empathetic/interact', { message: msg })
    const reply = resp.data.data?.response || 'Không nhận được câu trả lời hợp lệ từ Agent.'
    chatLog.value.push({
      role: 'hugo',
      content: reply,
      timestamp: getCurrentTimeString()
    })
  } catch (err) {
    console.error("Agent Uplink Connection Failure Details:", err)
    chatLog.value.push({
      role: 'hugo',
      content: '[ERR_CONNECTION_TIMEOUT] Không thể thiết lập kênh giao tiếp với Agent Engine. Vui lòng kiểm tra cổng dịch vụ backend.',
      timestamp: getCurrentTimeString()
    })
  } finally {
    chatLoading.value = false
    await nextTick()
    scrollChatToBottom()
  }
}

function applySuggestion(prompt: string) {
  userInput.value = prompt
  sendChat()
}

function scrollChatToBottom() {
  if (chatHistoryRef.value) {
    chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight
  }
}

onMounted(() => {
  scrollChatToBottom()
})
</script>

<style scoped>
.companion-canvas {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 16px;
  background: var(--color-bg-void);
  overflow: hidden;
}

.companion-layout {
  display: grid;
  grid-template-columns: 7fr 3fr;
  gap: 16px;
  height: 100%;
  overflow: hidden;
}

/* Chat Console Panel */
.chat-console-panel {
  display: flex;
  flex-direction: column;
  background: #000000;
  border: 1px solid var(--color-border-dim);
  height: 100%;
  overflow: hidden;
  border-radius: 4px;
  box-shadow: 0 0 15px rgba(0, 82, 255, 0.05);
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
  background: rgba(0, 82, 255, 0.05);
  border-bottom: 1px solid var(--color-border-dim);
  font-family: var(--font-hud);
  font-size: 10px;
  letter-spacing: 0.1em;
}

.header-title {
  display: flex;
  align-items: center;
  font-weight: bold;
}

.connection-status {
  font-size: 9px;
}

.status-label {
  color: var(--color-text-dim);
  margin-right: 6px;
}

/* Chat History Area */
.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: radial-gradient(circle at center, rgba(0, 6, 36, 0.6) 0%, #000000 100%);
}

.chat-bubble-row {
  display: flex;
  gap: 12px;
}

.chat-bubble-row.user {
  flex-direction: row-reverse;
}

.avatar-col {
  flex-shrink: 0;
}

.avatar-tag {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid var(--color-border-dim);
  background: rgba(0, 82, 255, 0.08);
  font-family: var(--font-hud);
  font-size: 9px;
  font-weight: bold;
  border-radius: 4px;
  color: var(--color-accent-cyan);
}

.chat-bubble-row.user .avatar-tag {
  color: var(--color-accent-green);
  background: rgba(0, 255, 102, 0.08);
}

.avatar-tag.thinking {
  animation: pulse-border 1.2s ease-in-out infinite;
  color: var(--color-accent-orange);
}

@keyframes pulse-border {
  0%, 100% { border-color: var(--color-border-dim); }
  50% { border-color: var(--color-accent-orange); }
}

.msg-content-col {
  max-width: 75%;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.chat-bubble-row.user .msg-content-col {
  align-items: flex-end;
}

.msg-header {
  display: flex;
  gap: 8px;
  font-size: 9px;
  font-family: var(--font-hud);
  letter-spacing: 0.05em;
}

.sender-name {
  font-weight: bold;
  color: var(--color-accent-cyan);
}

.chat-bubble-row.user .sender-name {
  color: var(--color-accent-green);
}

.msg-time {
  color: var(--color-text-dim);
}

.msg-body {
  background: rgba(0, 82, 255, 0.03);
  border: 1px solid rgba(0, 82, 255, 0.15);
  padding: 10px 14px;
  border-radius: 4px;
  font-family: var(--font-data);
  font-size: 11px;
  line-height: 1.6;
  color: var(--color-text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-bubble-row.user .msg-body {
  background: rgba(0, 255, 102, 0.03);
  border: 1px solid rgba(0, 255, 102, 0.15);
  color: #ffffff;
}

/* Thinking Indicator Animation */
.thinking-state {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pulsing-wave {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 14px;
}

.pulsing-wave span {
  width: 2px;
  height: 100%;
  background: var(--color-accent-orange);
  animation: wave-bounce 1s ease-in-out infinite;
}

.pulsing-wave span:nth-child(2) { animation-delay: 0.2s; }
.pulsing-wave span:nth-child(3) { animation-delay: 0.4s; }
.pulsing-wave span:nth-child(4) { animation-delay: 0.6s; }

@keyframes wave-bounce {
  0%, 100% { transform: scaleY(0.3); }
  50% { transform: scaleY(1); }
}

/* Suggestions chips */
.prompt-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 8px 16px;
  background: rgba(0, 0, 0, 0.6);
  border-top: 1px solid rgba(0, 82, 255, 0.1);
  overflow-x: auto;
}

.suggestion-chip {
  background: rgba(0, 82, 255, 0.04);
  border: 1px solid rgba(0, 82, 255, 0.2);
  color: var(--color-accent-cyan);
  font-family: var(--font-hud);
  font-size: 8px;
  letter-spacing: 0.05em;
  padding: 4px 10px;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}

.suggestion-chip:hover {
  background: rgba(0, 82, 255, 0.15);
  border-color: var(--color-accent-cyan);
  box-shadow: 0 0 6px rgba(0, 210, 255, 0.3);
}

/* Input Bar */
.chat-input-bar {
  display: flex;
  gap: 10px;
  padding: 12px 16px;
  background: #000000;
  border-top: 1px solid var(--color-border-dim);
}

.send-btn {
  flex-shrink: 0;
  font-family: var(--font-hud);
  font-size: 10px;
  padding: 0 16px;
}

/* Right side panel */
.companion-telemetry-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
  overflow-y: auto;
}

/* Hologram Scope Card */
.scope-card {
  background: #000000;
  border: 1px solid var(--color-border-dim);
}

.scope-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px 12px;
  background: radial-gradient(circle, rgba(0, 82, 255, 0.05) 0%, rgba(0,0,0,0) 70%);
}

.scope-wave {
  position: relative;
  width: 90px;
  height: 90px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.circle {
  position: absolute;
  border-radius: 50%;
  border: 1px dashed rgba(0, 210, 255, 0.2);
}

.circle.outer {
  width: 90px;
  height: 90px;
  animation: spin-clockwise 15s linear infinite;
}

.circle.middle {
  width: 66px;
  height: 66px;
  border-style: solid;
  border-color: rgba(0, 82, 255, 0.15);
  animation: spin-counter 10s linear infinite;
}

.circle.inner {
  width: 42px;
  height: 42px;
  border-style: dotted;
  border-color: var(--color-accent-cyan);
}

.scope-wave.active .circle.inner {
  animation: pulse-ring 1.5s ease-in-out infinite;
  border-color: var(--color-accent-orange);
}

.pulse-line {
  position: absolute;
  width: 100%;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--color-accent-cyan), transparent);
  animation: scan-line 2.5s ease-in-out infinite;
}

.scope-wave.active .pulse-line {
  background: linear-gradient(90deg, transparent, var(--color-accent-orange), transparent);
  animation: scan-line 1.2s ease-in-out infinite;
}

@keyframes spin-clockwise {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes spin-counter {
  from { transform: rotate(0deg); }
  to { transform: rotate(-360deg); }
}

@keyframes pulse-ring {
  0% { transform: scale(0.95); opacity: 0.5; }
  50% { transform: scale(1.15); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.5; }
}

@keyframes scan-line {
  0%, 100% { transform: translateY(-35px); opacity: 0; }
  50% { opacity: 0.8; }
  99% { transform: translateY(35px); opacity: 0; }
}

/* Specs & live grid */
.spec-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.spec-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.spec-row .label {
  color: var(--color-text-dim);
  font-family: var(--font-hud);
  font-size: 8px;
  letter-spacing: 0.05em;
}
</style>
