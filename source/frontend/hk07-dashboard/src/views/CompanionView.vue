<template>
  <div class="companion-canvas">
    <!-- Safety-Critical Action Confirmation Modal Overlay -->
    <div v-if="pendingPlan" class="tactical-modal-overlay">
      <div class="tactical-modal-card corner-reticle border-danger">
        <div class="modal-hdr text-red">[ ACTION_REQUIRED // CONFIRMATION_DEMANDED ]</div>
        <div class="modal-body font-mono text-[11px] text-white">
          <div class="alert-banner">
            <span class="blink-fast">⚠️</span> WARNING: SAFETY CRITICAL ACTION ATTEMPTED
          </div>
          <div class="plan-details mt-4">
            <div class="detail-row">
              <span class="label text-dim">PLAN_ID:</span>
              <span class="val text-cyan">{{ pendingPlan.plan_id }}</span>
            </div>
            <div class="detail-row">
              <span class="label text-dim">CURRENT_STEP:</span>
              <span class="val text-orange font-bold">
                {{ pendingPlan.steps[pendingPlan.current_step_index]?.type }}
              </span>
            </div>
            <div class="detail-row">
              <span class="label text-dim">MQTT_TOPIC:</span>
              <span class="val text-[#00E5FF]">
                {{ pendingPlan.steps[pendingPlan.current_step_index]?.mqtt_topic }}
              </span>
            </div>
          </div>
          <p class="warning-text mt-4">
            Hành động này có tính chất nhạy cảm hoặc ảnh hưởng trực tiếp đến trạng thái an toàn của robot/người dùng. Bạn có chắc chắn muốn cho phép thực thi?
          </p>
        </div>
        <div class="modal-footer">
          <button class="cmd-btn cancel-btn" @click="confirmAction(false)">
            [ ESC_CANCEL ]
          </button>
          <button class="cmd-btn confirm-btn btn-danger-glow" @click="confirmAction(true)">
            [ EXECUTE_CONFIRM ]
          </button>
        </div>
      </div>
    </div>

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
            <span :class="['status-value', vitalsStore.isConnected ? 'text-green' : 'text-danger']">
              {{ vitalsStore.isConnected ? 'SECURE_ESTABLISHED' : 'DISCONNECTED' }}
            </span>
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
          <button 
            type="button" 
            class="cmd-btn mute-btn"
            :class="{ active: isMuted }"
            @click="toggleMute"
            :title="isMuted ? 'Unmute voice response' : 'Mute voice response'"
          >
            {{ isMuted ? '🔇 MUTED' : '🔊 AGENT VOICE' }}
          </button>
          <input v-model="userInput" 
                 class="tactical-input font-mono w-full" 
                 placeholder="ENTER TACTICAL COMMAND OR INQUIRY TO AGENT HUGO..."
                 @keydown.enter="sendChat" />
          <button class="cmd-btn send-btn" 
                  @click="sendChat" 
                  :disabled="!userInput.trim()">
            SEND
          </button>
        </div>
      </section>

      <!-- Right side: Agent Telemetry & Local Monitor (25%) -->
      <aside class="companion-telemetry-panel">
        
        <!-- Animated Voice/Brain Scope -->
        <div class="terminal-card scope-card">
          <div class="terminal-card-header">[ AGENT_COGNITIVE_SCOPE ]</div>
          <div class="scope-container">
            <div :class="['scope-wave', chatLoading || isSpeaking ? 'active' : 'idle']">
              <div class="circle outer"></div>
              <div class="circle middle"></div>
              <div class="circle inner"></div>
              <div class="pulse-line"></div>
            </div>
            <div class="scope-status font-mono text-[9px] text-center mt-3">
              COGNITIVE STATE: 
              <span v-if="chatLoading" class="text-orange animate-pulse">COMPUTING_RESPONSE</span>
              <span v-else-if="isSpeaking" class="text-green animate-pulse">SPEAKING_TO_USER</span>
              <span v-else class="text-green">STANDBY_LISTENING</span>
            </div>
          </div>
        </div>

        <!-- Agent Specs -->
        <div class="terminal-card">
          <div class="terminal-card-header">[ AGENT_SPECIFICATIONS ]</div>
          <div class="spec-grid font-mono text-[10px]">
            <div class="spec-row">
              <span class="label">MODEL_CORE:</span>
              <span class="val" :class="vitalsStore.isConnected ? 'text-cyan' : 'text-dim'">
                {{ vitalsStore.isConnected ? (llmStats?.model || 'LOADING...') : 'OFFLINE' }}
              </span>
            </div>
            <div class="spec-row">
              <span class="label">PROVIDER:</span>
              <span class="val" :class="vitalsStore.isConnected ? 'text-cyan' : 'text-dim'">
                {{ vitalsStore.isConnected ? (llmStats?.provider || 'LOADING...') : 'OFFLINE' }}
              </span>
            </div>
            <div class="spec-row">
              <span class="label">INFERENCE:</span>
              <span class="val" :class="vitalsStore.isConnected ? 'text-green' : 'text-dim'">
                {{ vitalsStore.isConnected ? `ONLINE (${llmStats?.temperature || 0.45})` : 'OFFLINE' }}
              </span>
            </div>
          </div>
        </div>

        <!-- SENSORS FUSION MATRIX (Merged Vitals + rPPG) -->
        <div class="terminal-card">
          <div class="terminal-card-header">[ SENSORS_FUSION_MATRIX ]</div>
          <div class="spec-grid font-mono text-[10px] mb-2" style="padding-bottom: 6px;">
            <div class="spec-row">
              <span class="label">WRISTBAND HR:</span>
              <span :class="['val font-bold', vitalsStore.isSimulated ? 'text-orange' : (vitalsStore.current.heartRate ? hrClass : 'text-dim')]">
                {{ vitalsStore.current.heartRate ? vitalsStore.current.heartRate + ' BPM' : 'OFFLINE' }}
                <span v-if="vitalsStore.isSimulated && vitalsStore.current.heartRate" class="text-[8px]">(SIM)</span>
              </span>
            </div>
            <div class="spec-row">
              <span class="label">CAMERA rPPG HR:</span>
              <span :class="['val font-bold', kinematicsStore.isLive ? (kinematicsStore.rppgHeartRate ? rppgHrClass : 'text-cyan') : 'text-dim']">
                {{ kinematicsStore.isLive ? (kinematicsStore.rppgHeartRate ? Number(kinematicsStore.rppgHeartRate).toFixed(1) + ' BPM' : 'ANALYZING...') : 'OFFLINE' }}
              </span>
            </div>
            <div class="spec-row border-t border-dashed border-[#0052ff]/30 pt-1 mt-1">
              <span class="label">OXYGEN SAT (WRIST):</span>
              <span :class="['val font-bold', vitalsStore.isSimulated ? 'text-orange' : (vitalsStore.current.spo2 ? spo2Class : 'text-dim')]">
                {{ vitalsStore.current.spo2 ? Number(vitalsStore.current.spo2).toFixed(1) + ' %' : 'OFFLINE' }}
                <span v-if="vitalsStore.isSimulated && vitalsStore.current.spo2" class="text-[8px]">(SIM)</span>
              </span>
            </div>
            <div class="spec-row">
              <span class="label">BLOOD PRESS (WRIST):</span>
              <span :class="['val', vitalsStore.isSimulated ? 'text-orange' : (vitalsStore.current.systolic ? 'text-cyan' : 'text-dim')]">
                {{ vitalsStore.current.systolic ? vitalsStore.current.systolic + '/' + vitalsStore.current.diastolic : 'OFFLINE' }}
              </span>
            </div>
            <div class="spec-row border-t border-dashed border-[#0052ff]/30 pt-1 mt-1">
              <span class="label">THERMAL VISION:</span>
              <span :class="['val font-bold', kinematicsStore.isLive ? (kinematicsStore.thermalTemperature ? thermalTempClass : 'text-cyan') : 'text-dim']">
                {{ kinematicsStore.isLive ? (kinematicsStore.thermalTemperature ? Number(kinematicsStore.thermalTemperature).toFixed(2) + ' °C' : 'MEASURING...') : 'OFFLINE' }}
              </span>
            </div>
            <div class="spec-row border-t border-dashed border-[#0052ff]/30 pt-1 mt-1">
              <span class="label">AMB AUDIO:</span>
              <span :class="['val font-mono text-[9px]', sensorStore.isHearingSimulated ? 'text-orange' : (sensorStore.hearing.intensity_label ? 'text-[#00E5FF]' : 'text-dim')]">
                {{ sensorStore.hearing.intensity_label ? `${sensorStore.hearing.frequency}, ${sensorStore.hearing.intensity_label}` : 'OFFLINE' }}
              </span>
            </div>
            <div class="spec-row pt-1 mt-1">
              <span class="label">ALERT STATE:</span>
              <span :class="['val font-bold', vitalsStore.isEmergency || (kinematicsStore.isLive && kinematicsStore.feverAlert) ? 'text-red animate-pulse' : 'text-green']">
                {{ vitalsStore.isEmergency || (kinematicsStore.isLive && kinematicsStore.feverAlert) ? '⚠ EMERGENCY' : '✓ NORMAL' }}
              </span>
            </div>
          </div>
          <EcgWaveform :width="240" :height="40" />
        </div>

        <!-- Phase 2: Perception Scan Panel -->
        <div class="terminal-card perception-card">
          <div class="terminal-card-header">[ PERCEPTION_SCAN_MODULE ]</div>
          <div class="perception-body">

            <!-- Scan State -->
            <div class="scan-status-row">
              <span class="label">SCAN_STATUS:</span>
              <span :class="['val', scanLoading ? 'text-orange animate-pulse' : (scanResult ? 'text-green' : 'text-dim')]">
                {{ scanLoading ? 'SCANNING...' : (scanResult ? 'SCAN_COMPLETE' : 'READY') }}
              </span>
            </div>

            <!-- Scan Button -->
            <button
              id="btn-full-body-scan"
              class="scan-btn"
              :class="{ scanning: scanLoading }"
              :disabled="scanLoading"
              @click="executeScan"
            >
              <span class="scan-icon">◎</span>
              {{ scanLoading ? 'SCANNING...' : '[ FULL_BODY_SCAN ]' }}
            </button>

            <!-- Scan Results -->
            <div v-if="scanResult" class="scan-result-grid font-mono text-[9px]">
              <div class="scan-result-row">
                <span class="label">OVERALL_RISK:</span>
                <span :class="['val font-bold', riskClass(scanResult.overall_risk)]">
                  {{ scanResult.overall_risk }}
                </span>
              </div>
              <div class="scan-result-row">
                <span class="label">POSTURE:</span>
                <span :class="['val', riskClass(scanResult.posture_risk)]">{{ scanResult.posture_risk }}</span>
              </div>
              <div class="scan-result-row">
                <span class="label">DISTRESS:</span>
                <span class="val text-cyan">{{ (scanResult.facial_distress * 100).toFixed(0) }}%</span>
              </div>
              <div class="scan-result-row">
                <span class="label">CONFIDENCE:</span>
                <span class="val text-green">{{ (scanResult.confidence * 100).toFixed(0) }}%</span>
              </div>
              <div v-if="scanResult.skin_tone_note" class="scan-result-row">
                <span class="label">SKIN_TONE:</span>
                <span class="val text-cyan">{{ scanResult.skin_tone_note }}</span>
              </div>
              <div v-if="scanResult.visible_injuries?.length" class="scan-result-row">
                <span class="label">INJURIES:</span>
                <span class="val text-orange">{{ scanResult.visible_injuries.join(', ') }}</span>
              </div>
              <div v-if="scanResult.threat_level !== 'CLEAR'" class="scan-result-row">
                <span class="label">ENV_THREAT:</span>
                <span :class="['val', riskClass(scanResult.threat_level)]">{{ scanResult.threat_level }}</span>
              </div>
              <div v-if="scanResult.notes" class="scan-notes">
                <span class="text-dim">{{ scanResult.notes }}</span>
              </div>
              <div class="scan-disclaimer">{{ scanResult.disclaimer }}</div>
            </div>

          </div>
        </div>

      </aside>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useVitalsStore } from '../stores/vitals'
import { useAuthStore } from '../stores/auth'
import { useKinematicsStore } from '../stores/kinematics'
import { useAgentsStore } from '../stores/agents'
import { useSensorTelemetryStore } from '../stores/sensorTelemetry'
import api from '../services/api'
import EcgWaveform from '../components/EcgWaveform.vue'

const isMuted = ref(false)
const isSpeaking = ref(false)
const llmStats = ref<any>(null)

async function fetchLlmStats() {
  if (!vitalsStore.isConnected) return
  try {
    const res = await api.get('/health/llm-stats')
    llmStats.value = res.data
  } catch (err) {
    console.warn('[LLM_STATS] Failed to fetch LLM stats', err)
  }
}
let llmStatsInterval: any = null

function toggleMute() {
  isMuted.value = !isMuted.value
  if (isMuted.value) {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel()
    }
    isSpeaking.value = false
  }
}

const vitalsStore = useVitalsStore()
const authStore = useAuthStore()
const kinematicsStore = useKinematicsStore()
const sensorStore = useSensorTelemetryStore()

interface ChatMessage {
  role: 'user' | 'hugo'
  content: string
  timestamp: string
}

interface PerceptionScan {
  overall_risk: string
  posture_risk: string
  facial_distress: number
  confidence: number
  skin_tone_note: string
  visible_injuries: string[]
  threat_level: string
  nearest_obstacle_m: number
  notes: string
  disclaimer: string
  scan_duration_ms: number
}

const scanLoading = ref(false)
const scanResult = ref<PerceptionScan | null>(null)

function riskClass(risk: string) {
  if (!risk) return 'text-dim'
  const r = risk.toUpperCase()
  if (r === 'CRITICAL') return 'text-red animate-pulse'
  if (r === 'HIGH' || r === 'WARNING') return 'text-orange'
  if (r === 'MED' || r === 'MEDIUM') return 'text-orange'
  if (r === 'LOW' || r === 'CLEAR') return 'text-green'
  return 'text-cyan'
}

async function executeScan() {
  if (scanLoading.value) return
  
  const token = authStore.accessToken
  if (!token || token === 'undefined' || token === 'null') {
    console.error("CRITICAL: Access Token is missing from authStore. Attempting silent session refresh...");
    const restored = await authStore.refreshSession()
    if (!restored) {
      agentsStore.chatLog.push({
        role: 'hugo',
        content: '[ERR_AUTH_REQUIRED] Yêu cầu đăng nhập để thực hiện quét sinh thể.',
        timestamp: getCurrentTimeString()
      })
      return
    }
  }

  scanLoading.value = true
  scanResult.value = null
  try {
    const resp = await api.post('/agents/perception/scan', {}, { timeout: 30000 })
    const data = resp.data?.data
    if (data?.scan) {
      scanResult.value = data.scan as PerceptionScan
      // Push scan context to chat log
      const risk = data.scan.overall_risk
      const notes = data.scan.notes || ''
      agentsStore.chatLog.push({
        role: 'hugo',
        content: `[PERCEPTION_SCAN_COMPLETE] Đã quét toàn thân. Risk: ${risk}${notes ? ' — ' + notes : ''}. Kết quả chi tiết hiển thị trên bảng bên phải.`,
        timestamp: getCurrentTimeString()
      })
      await nextTick()
      scrollChatToBottom()
    }
  } catch (err) {
    console.error('[SCAN_ERROR]', err)
    agentsStore.chatLog.push({
      role: 'hugo',
      content: '[SCAN_ERR] Không thể kết nối Perception Module. Kiểm tra kết nối agent engine.',
      timestamp: getCurrentTimeString()
    })
  } finally {
    scanLoading.value = false
  }
}

const userInput = ref('')
const chatLoading = ref(false)
const chatHistoryRef = ref<HTMLElement | null>(null)

const agentsStore = useAgentsStore()
const { chatLog } = storeToRefs(agentsStore)

const suggestionChips = [
  { label: 'ANALYZE_VITALS', prompt: 'Hãy phân tích chỉ số sinh tồn (vitals) hiện tại của tôi.' },
  { label: 'HEALTH_ADVICE', prompt: 'Cho tôi lời khuyên bảo vệ sức khỏe tim mạch.' },
  { label: 'EXPLAIN_SUBSUMPTION', prompt: 'Làm thế nào để hệ thống an toàn thị giác IPWebcam và Subsumption ngăn chặn va chạm?' },
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

const rppgHrClass = computed(() => {
  if (!kinematicsStore.isLive) return 'text-dim'
  const hr = kinematicsStore.rppgHeartRate
  if (!hr) return 'text-dim'
  if (hr < 50 || hr > 120) return 'text-red'
  if (hr < 60 || hr > 100) return 'text-orange'
  return 'text-green'
})

const thermalTempClass = computed(() => {
  if (!kinematicsStore.isLive) return 'text-dim'
  const t = kinematicsStore.thermalTemperature
  if (!t) return 'text-dim'
  if (t >= 38.0) return 'text-red'
  if (t > 37.3) return 'text-orange'
  return 'text-green'
})

async function sendChat() {
  const msg = userInput.value.trim()
  if (!msg) return
  
  // Pre-flight: ensure we have a valid token before sending
  if (!authStore.accessToken || authStore.accessToken === 'undefined' || authStore.accessToken === 'null') {
    console.error("CRITICAL: Access Token is missing from authStore. Attempting silent session refresh...");
    const restored = await authStore.refreshSession()
    if (!restored) {
      agentsStore.chatLog.push({
        role: 'hugo',
        content: '[ERR_AUTH_REQUIRED] Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.',
        timestamp: getCurrentTimeString()
      })
      return
    }
  }

  try {
    chatLoading.value = true
    
    // Clear input immediately so user knows it has been sent
    userInput.value = ''
    
    agentsStore.chatLog.push({
      role: 'user',
      content: msg,
      timestamp: getCurrentTimeString()
    })
    
    await nextTick()
    scrollChatToBottom()

    const resp = await api.post('/agents/empathetic/interact', { message: msg }, { timeout: 30000 })
    const reply = resp.data.data?.response || 'Không nhận được câu trả lời hợp lệ từ Agent.'
    agentsStore.chatLog.push({
      role: 'hugo',
      content: reply,
      timestamp: getCurrentTimeString()
    })
    await nextTick()
    scrollChatToBottom()
    setTimeout(() => {
      speakResponse(reply)
    }, 150)
  } catch (err) {
    console.error("Agent Uplink Connection Failure Details:", err)
    const errText = '[ERR_CONNECTION_TIMEOUT] Không thể thiết lập kênh giao tiếp với Agent Engine. Vui lòng kiểm tra cổng dịch vụ backend.'
    agentsStore.chatLog.push({
      role: 'hugo',
      content: errText,
      timestamp: getCurrentTimeString()
    })
    await nextTick()
    scrollChatToBottom()
    setTimeout(() => {
      speakResponse(errText)
    }, 150)
  } finally {
    chatLoading.value = false
    await nextTick()
    scrollChatToBottom()
  }
}

onMounted(() => {
  fetchLlmStats()
  llmStatsInterval = setInterval(fetchLlmStats, 5000)
  nextTick(() => {
    scrollChatToBottom()
  })
})

onUnmounted(() => {
  if (llmStatsInterval) clearInterval(llmStatsInterval)
})

// ── Web Speech API Integration & Language Detection ──

function detectLanguage(text: string): 'en' | 'vi' {
  const viAccents = /[àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệđìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]/i
  if (viAccents.test(text)) {
    return 'vi'
  }
  
  // Common Vietnamese words without accents
  const commonViWords = /\b(chao sếp|chao sep|chào sếp|chào bạn|chao ban|toi|co|khong|di|dao|nhip|tim|suc|khoe|o|day|giup|chi|so|met|moi|dau|nguc|binh|thuong|thoi|tiet|hom|nay|the|nao|cho|loi|khuyen|bao|ve|cuu|voi|nga|roi|phat|tin|hieu|khan|cap|oi|sep|cam|thay|nho|lon|vua|tram|cao|nhanh|cham|trai|phai)\b/i
  
  const words = text.toLowerCase().split(/\s+/)
  let viCount = 0
  let enCount = 0
  
  const commonEnWords = new Set([
    "hello", "hi", "hey", "you", "there", "is", "are", "am", "how", "what", "weather", "today", "go", "walk", 
    "robot", "check", "sensor", "status", "connection", "heart", "rate", "health", "vitals", "feel", "tired", 
    "dizzy", "pain", "chest", "severe", "help", "me", "fall", "emergency", "signal", "please", "advice", 
    "protect", "who", "where", "why", "can", "do", "should", "thank", "thanks"
  ])
  
  for (const w of words) {
    if (viAccents.test(w) || commonViWords.test(w)) {
      viCount++
    } else if (commonEnWords.has(w)) {
      enCount++
    }
  }
  
  if (enCount > viCount) {
    return 'en'
  }
  return 'vi'
}

let availableVoices: SpeechSynthesisVoice[] = []
function initVoices() {
  if ('speechSynthesis' in window) {
    availableVoices = window.speechSynthesis.getVoices()
  }
}
if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
  initVoices()
  window.speechSynthesis.onvoiceschanged = initVoices
}

function speakResponse(text: string) {
  if (isMuted.value) return
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel()
    
    // Ensure voices are loaded
    if (availableVoices.length === 0) {
      availableVoices = window.speechSynthesis.getVoices()
    }
    
    const getBestVoice = (langCode: 'vi-VN' | 'en-US') => {
      let voice = availableVoices.find(v => {
        const l = v.lang.toLowerCase().replace('_', '-')
        return l === langCode.toLowerCase()
      })
      if (!voice) {
        const prefix = langCode.split('-')[0].toLowerCase()
        voice = availableVoices.find(v => {
          const l = v.lang.toLowerCase().replace('_', '-')
          return l === prefix || l.startsWith(prefix + '-')
        })
      }
      return voice
    }
    
    const viVoice = getBestVoice('vi-VN')
    const enVoice = getBestVoice('en-US')
    
    // Check if the text matches something like [TAG] Rest
    const bracketMatch = text.match(/^\[(.*?)\](.*)$/s)
    if (bracketMatch) {
      const tagText = bracketMatch[1].replace(/_/g, ' ') // e.g. "ERR_CONNECTION_TIMEOUT" -> "ERR CONNECTION TIMEOUT"
      const bodyText = bracketMatch[2].trim()
      
      const utteranceTag = new SpeechSynthesisUtterance(tagText)
      utteranceTag.lang = 'en-US'
      if (enVoice) utteranceTag.voice = enVoice
      utteranceTag.rate = 1.0
      utteranceTag.pitch = 1.0
      
      const utteranceBody = new SpeechSynthesisUtterance(bodyText)
      const bodyLang = detectLanguage(bodyText)
      if (bodyLang === 'en') {
        utteranceBody.lang = 'en-US'
        if (enVoice) utteranceBody.voice = enVoice
      } else {
        utteranceBody.lang = 'vi-VN'
        if (viVoice) utteranceBody.voice = viVoice
      }
      utteranceBody.rate = 1.0
      utteranceBody.pitch = 1.0
      
      utteranceTag.onstart = () => {
        isSpeaking.value = true
      }
      utteranceBody.onend = () => {
        isSpeaking.value = false
      }
      utteranceTag.onerror = () => {
        isSpeaking.value = false
      }
      utteranceBody.onerror = () => {
        isSpeaking.value = false
      }
      
      window.speechSynthesis.speak(utteranceTag)
      window.speechSynthesis.speak(utteranceBody)
    } else {
      const cleanText = text.trim()
      const utterance = new SpeechSynthesisUtterance(cleanText)
      
      const lang = detectLanguage(cleanText)
      if (lang === 'en') {
        utterance.lang = 'en-US'
        if (enVoice) utterance.voice = enVoice
      } else {
        utterance.lang = 'vi-VN'
        if (viVoice) utterance.voice = viVoice
      }
      utterance.rate = 1.0
      utterance.pitch = 1.0
      
      utterance.onstart = () => {
        isSpeaking.value = true
      }
      utterance.onend = () => {
        isSpeaking.value = false
      }
      utterance.onerror = () => {
        isSpeaking.value = false
      }
      
      window.speechSynthesis.speak(utterance)
    }
  }
}

// Continuous voice stream is handled by the backend's semantic audio analyzer via SensorLogs payload.

function applySuggestion(prompt: string) {
  userInput.value = prompt
  sendChat()
}

function scrollChatToBottom() {
  if (chatHistoryRef.value) {
    chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight
  }
}

// ── Action Plan Confirmation System (Phase 5) ──
const pendingPlan = ref<any>(null)
let checkInterval: any = null

async function checkPendingActions() {
  const currentToken = authStore.accessToken;
  if (!currentToken || currentToken === 'undefined' || currentToken === 'null') {
      return; // Absolute freeze. Zero network usage if the token is literal junk.
  }
  try {
    const response = await api.get('/agents/action/plan/latest')
    const plan = response.data?.data?.plan
    if (plan && plan.status === 'AWAITING_CONFIRM') {
      pendingPlan.value = plan
    } else {
      pendingPlan.value = null
    }
  } catch (err) {
    console.error('[ACTION_CHECK_ERR]', err)
  }
}

async function confirmAction(confirm: boolean) {
  if (!pendingPlan.value) return
  const planId = pendingPlan.value.plan_id
  pendingPlan.value = null
  const token = authStore.accessToken
  if (!token || token === 'undefined' || token === 'null') {
    console.error("CRITICAL: Access Token is missing from authStore. Attempting silent session refresh...");
    const success = await authStore.refreshSession()
    if (!success) {
      return
    }
  }
  try {
    const resp = await api.post('/agents/action/confirm', { plan_id: planId, confirm }, { timeout: 30000 })
    agentsStore.chatLog.push({
      role: 'hugo',
      content: `[ACTION_PLAN_CONFIRMATION] ${confirm ? 'Đã xác nhận thực thi hành động.' : 'Đã hủy thực thi hành động.'} Kết quả: ${resp.data?.data?.result || ''}`,
      timestamp: getCurrentTimeString()
    })
    await nextTick()
    scrollChatToBottom()
  } catch (err) {
    console.error('[ACTION_CONFIRM_ERR]', err)
    agentsStore.chatLog.push({
      role: 'hugo',
      content: `[ACTION_CONFIRM_ERR] Lỗi xác nhận hành động.`,
      timestamp: getCurrentTimeString()
    })
  }
}

function handleUnauthorized() {
  if (checkInterval) {
    clearInterval(checkInterval)
    checkInterval = null
  }
}

let lastProcessedHearingTs = 0
watch(
  () => sensorStore.lastHearingMs,
  async (newVal) => {
    if (newVal === 0) return
    const hearing = sensorStore.hearing
    if (hearing.timestamp_ms > lastProcessedHearingTs && hearing.transcript && hearing.transcript.trim() !== '') {
      lastProcessedHearingTs = hearing.timestamp_ms
      
      // 1. Push user message to chat log (acting as if operator spoke via phone mic)
      agentsStore.chatLog.push({
        role: 'user',
        content: hearing.transcript,
        timestamp: getCurrentTimeString()
      })
      
      await nextTick()
      scrollChatToBottom()
      
      // 2. Set loading state to show Hugo is computing
      chatLoading.value = true
      
      try {
        // Ensure valid session token
        if (!authStore.accessToken || authStore.accessToken === 'undefined' || authStore.accessToken === 'null') {
          await authStore.refreshSession()
        }
        
        // 3. Interact with AI agent core to generate response
        const resp = await api.post('/agents/empathetic/interact', { message: hearing.transcript }, { timeout: 30000 })
        const reply = resp.data.data?.response || 'Không nhận được phản hồi hợp lệ.'
        
        // 4. Push agent's reply to chat log
        agentsStore.chatLog.push({
          role: 'hugo',
          content: reply,
          timestamp: getCurrentTimeString()
        })
        await nextTick()
        scrollChatToBottom()
        
        // 5. Output voice speech response
        setTimeout(() => {
          speakResponse(reply)
        }, 150)
      } catch (err) {
        console.error("Empathetic agent voice interaction failed:", err)
        const errText = '[HEARING_RESP_ERR] Có lỗi xảy ra khi robot phản hồi âm thanh.'
        agentsStore.chatLog.push({
          role: 'hugo',
          content: errText,
          timestamp: getCurrentTimeString()
        })
        await nextTick()
        scrollChatToBottom()
        setTimeout(() => {
          speakResponse(errText)
        }, 150)
      } finally {
        chatLoading.value = false
        await nextTick()
        scrollChatToBottom()
      }
    }
  }
)

// Auto scroll chat to bottom when chatLog is updated from anywhere (e.g. GlobalVoiceWidget)
watch(
  chatLog,
  async () => {
    await nextTick()
    scrollChatToBottom()
  },
  { deep: true }
)

onMounted(() => {
  agentsStore.initSession(authStore.user?.id)
  scrollChatToBottom()
  checkInterval = setInterval(checkPendingActions, 2000)
  document.addEventListener('hk07:unauthorized', handleUnauthorized)
})

onUnmounted(() => {
  if (checkInterval) {
    clearInterval(checkInterval)
    checkInterval = null
  }
  document.removeEventListener('hk07:unauthorized', handleUnauthorized)
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
  background: rgba(0, 229, 255, 0.05);
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
  /*background: radial-gradient(circle at center, rgba(10, 10, 10, 0.96) 0%, #000000 100%);*/
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
  background: rgba(0, 229, 255, 0.03);
  border: 1px solid rgba(0, 229, 255, 0.15);
  padding: 12px 16px;
  border-radius: 4px;
  font-family: var(--font-data);
  font-size: 11px;
  line-height: 1.8;
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
  border-top: 1px solid rgba(0, 229, 255, 0.1);
  overflow-x: auto;
}

.suggestion-chip {
  background: rgba(0, 229, 255, 0.04);
  border: 1px solid rgba(0, 229, 255, 0.2);
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
  background: rgba(0, 229, 255, 0.15);
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

.mic-btn {
  flex-shrink: 0;
  font-family: var(--font-hud);
  font-size: 10px;
  padding: 0 12px;
  background: rgba(0, 229, 255, 0.05);
  border-color: var(--color-border-dim);
  transition: all 0.2s;
  user-select: none;
}
.mic-btn.active {
  background: rgba(255, 51, 51, 0.2);
  border-color: var(--color-accent-red);
  color: var(--color-accent-red);
  box-shadow: 0 0 10px rgba(255, 51, 51, 0.4);
  animation: pulse-mic 1s infinite alternate;
}
.mute-btn {
  flex-shrink: 0;
  font-family: var(--font-hud);
  font-size: 10px;
  padding: 0 12px;
  background: rgba(0, 229, 255, 0.05);
  border-color: var(--color-border-dim);
  transition: all 0.2s;
  user-select: none;
}
.mute-btn.active {
  background: rgba(255, 176, 0, 0.15);
  border-color: var(--color-accent-orange);
  color: var(--color-accent-orange);
  box-shadow: 0 0 10px rgba(255, 176, 0, 0.2);
}
@keyframes pulse-mic {
  0% { box-shadow: 0 0 2px rgba(255, 51, 51, 0.2); }
  100% { box-shadow: 0 0 8px rgba(255, 51, 51, 0.6); }
}

.scope-wave.recording .circle.inner {
  animation: pulse-ring 0.8s ease-in-out infinite;
  border-color: var(--color-accent-cyan);
}
.scope-wave.recording .pulse-line {
  background: linear-gradient(90deg, transparent, var(--color-accent-cyan), transparent);
  animation: scan-line 0.8s ease-in-out infinite;
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
  background: radial-gradient(circle, rgba(0, 229, 255, 0.05) 0%, rgba(0,0,0,0) 70%);
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
  border-color: rgba(0, 229, 255, 0.15);
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

/* ── Perception Scan Card ──────────────────────────────────────────────── */
.perception-card {
  border-color: rgba(0, 229, 255, 0.2);
}

.perception-body {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.scan-status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--font-hud);
  font-size: 8px;
  letter-spacing: 0.05em;
}

.scan-status-row .label {
  color: var(--color-text-dim);
}

.scan-btn {
  width: 100%;
  padding: 8px 0;
  background: rgba(0, 82, 255, 0.04);
  border: 1px solid rgba(0, 229, 255, 0.3);
  color: var(--color-accent-cyan);
  font-family: var(--font-hud);
  font-size: 10px;
  letter-spacing: 0.12em;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.scan-btn:hover:not(:disabled) {
  background: rgba(0, 82, 255, 0.12);
  border-color: var(--color-accent-cyan);
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.25), inset 0 0 10px rgba(0, 229, 255, 0.05);
}

.scan-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.scan-btn.scanning {
  animation: scan-pulse 1.2s ease-in-out infinite;
  border-color: var(--color-accent-orange);
  color: var(--color-accent-orange);
}

@keyframes scan-pulse {
  0%, 100% { box-shadow: 0 0 4px rgba(255, 176, 0, 0.2); }
  50% { box-shadow: 0 0 12px rgba(255, 176, 0, 0.6); }
}

.scan-icon {
  font-size: 14px;
  animation: scan-rotate 3s linear infinite;
}

.scan-btn.scanning .scan-icon {
  animation-duration: 0.8s;
}

@keyframes scan-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.scan-result-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-top: 1px dashed rgba(0, 229, 255, 0.15);
  padding-top: 8px;
}

.scan-result-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 9px;
}

.scan-result-row .label {
  color: var(--color-text-dim);
  font-size: 8px;
  letter-spacing: 0.04em;
}

.scan-result-row .val {
  font-family: var(--font-hud);
  font-size: 9px;
}

.scan-notes {
  font-size: 8px;
  color: var(--color-text-dim);
  line-height: 1.4;
  border-left: 2px solid rgba(0, 229, 255, 0.2);
  padding-left: 6px;
}

.scan-disclaimer {
  font-size: 7px;
  color: rgba(255,255,255,0.2);
  line-height: 1.3;
  font-style: italic;
  border-top: 1px dashed rgba(255,255,255,0.06);
  padding-top: 4px;
}

/* Tactical Confirmation Modal Styles */
.tactical-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(8px);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.tactical-modal-card {
  width: 420px;
  background: #0A0A0A;
  border: 1px solid rgba(255, 51, 51, 0.4);
  border-radius: 4px;
  padding: 24px;
  box-shadow: 0 0 30px rgba(255, 51, 51, 0.15);
  font-family: var(--font-hud);
}

.tactical-modal-card.border-danger {
  border-color: var(--color-accent-red);
}

.modal-hdr {
  font-size: 12px;
  font-weight: bold;
  letter-spacing: 0.1em;
  margin-bottom: 16px;
  border-bottom: 1px solid rgba(255, 51, 51, 0.2);
  padding-bottom: 8px;
}

.alert-banner {
  background: rgba(255, 51, 51, 0.1);
  border: 1px solid rgba(255, 51, 51, 0.3);
  padding: 10px;
  text-align: center;
  color: var(--color-accent-red);
  font-weight: bold;
  font-size: 11px;
  letter-spacing: 0.05em;
}

.plan-details {
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid var(--color-border-dim);
  padding: 12px;
  border-radius: 4px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.detail-row:last-child {
  margin-bottom: 0;
}

.warning-text {
  color: var(--color-text-dim);
  font-size: 10px;
  line-height: 1.5;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
  border-top: 1px solid var(--color-border-dim);
  padding-top: 16px;
}

.confirm-btn {
  background: rgba(255, 51, 51, 0.1);
  border: 1px solid var(--color-accent-red);
  color: var(--color-accent-red);
}
.confirm-btn:hover {
  background: rgba(255, 51, 51, 0.25);
  box-shadow: 0 0 10px rgba(255, 51, 51, 0.5);
}

.cancel-btn {
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--color-border-dim);
  color: #ffffff;
}
.cancel-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.blink-fast {
  animation: fast-blink 0.6s infinite alternate;
}
@keyframes fast-blink {
  0% { opacity: 0.2; }
  100% { opacity: 1; }
}
</style>
