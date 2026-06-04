<template>
  <div class="safety-shell">
    <div class="safety-layout">
      <!-- ── LEFT: Radar Canvas ─────────────────────────────────────────────── -->
      <div class="radar-panel terminal-card corner-reticle" :class="radarPanelClass">
        <div class="terminal-card-header radar-header-row">
          <span>[ LIDAR_360_RADAR // {{ displayHz }}Hz ]</span>
          <span :class="['data-link hud', safetyStore.dataLive ? 'text-green' : 'text-orange']">
            {{ safetyStore.dataLinkLabel }}
          </span>
        </div>
        <div class="radar-meta mono text-dim">
          <span>MIN {{ safetyStore.minDistanceM.toFixed(2) }}m @ {{ safetyStore.closestAngleDeg }}°</span>
          <span :class="threatClass">[ {{ safetyStore.threatLevel }} ]</span>
        </div>
        <div class="radar-container">
          <canvas ref="radarCanvas" :width="RADAR_SIZE" :height="RADAR_SIZE"></canvas>
          <div class="radar-center-label hud text-dim">HK-07</div>
        </div>
        <div class="baymax-hint mono">
          <span class="baymax-tag hud text-cyan">BAYMAX_SCAN</span>
          {{ safetyStore.baymaxHint }}
        </div>
        <div class="radar-legend mono text-dim">
          <span>0.5m ● 1.0m ● 2.0m ● 3.0m</span>
          <span class="legend-bubble">◎ vùng an toàn cá nhân</span>
        </div>
      </div>

      <!-- ── RIGHT: Alert Panel ─────────────────────────────────────────────── -->
      <div class="safety-right">
        <!-- E-STOP Emergency Control -->
        <div class="terminal-card estop-panel">
          <div class="terminal-card-header">[ EMERGENCY_HALT // E-STOP ]</div>
          <div class="estop-container">
            <button
              type="button"
              class="estop-btn"
              :disabled="estopBusy"
              aria-label="Emergency stop — activate SOS protocol"
              @click="triggerEstop"
            >
              <span class="estop-label">[ E-STOP ]</span>
            </button>
            <p v-if="estopStatus" class="estop-status mono" :class="estopStatusOk ? 'text-green' : 'text-red'">
              {{ estopStatus }}
            </p>
          </div>
        </div>

        <!-- Response Time Meter -->
        <div class="terminal-card">
          <div class="terminal-card-header">[ SUBSUMPTION_LATENCY ]</div>
          <div class="latency-display">
            <div :class="['latency-value hud', latencyOk ? 'text-green' : 'text-red']">
              {{ lastResponseMs.toFixed(2) }}<span class="latency-unit">ms</span>
            </div>
            <div class="latency-sla text-dim mono">SLA TARGET: &lt; 5.00ms</div>
            <div :class="['latency-verdict hud', latencyOk ? 'text-green' : 'text-red']">
              {{ latencyOk ? '[ PASS ]' : '[ BREACH ]' }}
            </div>
          </div>
        </div>

        <!-- Active Triggers -->
        <div class="terminal-card">
          <div class="terminal-card-header">[ ACTIVE_TRIGGERS ]</div>
          <div class="triggers-list">
            <div v-for="trigger in safetyStore.activeTriggers" :key="trigger.type + trigger.detectedAt"
                 :class="['trigger-row', trigger.severity]">
              <span class="trigger-type hud">{{ trigger.type }}</span>
              <span class="trigger-dist mono">{{ trigger.distanceM?.toFixed(2) }}m</span>
              <span class="trigger-msg text-dim">{{ trigger.message }}</span>
            </div>
            <div v-if="safetyStore.activeTriggers.length === 0" class="text-dim mono" style="padding:8px;font-size:10px">
              &gt;&gt;&gt; NO ACTIVE THREATS DETECTED
            </div>
          </div>
        </div>

        <!-- Safety Alert History -->
        <div class="terminal-card" style="flex:1">
          <div class="terminal-card-header">[ ALERT_HISTORY ]</div>
          <div class="alert-history">
            <div v-for="(alert, i) in alertHistory" :key="i"
                 :class="['alert-row', alert.severity]">
              <span class="alert-time mono text-dim">{{ alert.time }}</span>
              <span :class="['alert-trigger hud', alert.severity === 'critical' ? 'text-red' : 'text-orange']">
                {{ alert.trigger }}
              </span>
              <span class="alert-latency mono text-dim">{{ alert.responseMs?.toFixed(1) }}ms</span>
              <span class="alert-msg mono">{{ alert.message }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useAgentsStore } from '../stores/agents'
import { useSafetyStore } from '../stores/safety'
import { triggerRobotSosTrigger, fetchLidarSnapshot } from '../services/api'
import { useLidarRadar } from '../composables/useLidarRadar'
import type { LidarScanSnapshot } from '../types/safety'

const agentsStore = useAgentsStore()
const safetyStore = useSafetyStore()

const subsumptionActive = computed(() => agentsStore.subsumptionActive)
const lastResponseMs = ref(0)
const latencyOk = computed(() => lastResponseMs.value < 5.0 || lastResponseMs.value === 0)
const displayHz = computed(() =>
  safetyStore.scanHz > 0 ? safetyStore.scanHz.toFixed(1) : '—'
)

const alertHistory = ref<{ time: string; trigger: string; responseMs: number; message: string; severity: string }[]>([])

const radarCanvas = ref<HTMLCanvasElement | null>(null)
const { RADAR_SIZE } = useLidarRadar(
  radarCanvas,
  computed(() => safetyStore.ranges360),
  computed(() => safetyStore.closestAngleDeg),
  subsumptionActive
)

const threatClass = computed(() => {
  const t = safetyStore.threatLevel
  if (t === 'CRITICAL') return 'text-red'
  if (t === 'WARNING') return 'text-orange'
  if (t === 'CAUTION') return 'text-orange'
  if (t === 'SAFE') return 'text-green'
  return 'text-dim'
})

const radarPanelClass = computed(() => {
  if (agentsStore.subsumptionActive) return 'radar-inhibit'
  if (safetyStore.threatLevel === 'CRITICAL') return 'radar-critical'
  if (safetyStore.threatLevel === 'WARNING') return 'radar-warning'
  return ''
})

const estopBusy = ref(false)
const estopStatus = ref('')
const estopStatusOk = ref(false)

async function triggerEstop() {
  if (estopBusy.value) return
  estopBusy.value = true
  estopStatus.value = '>> DISPATCHING SOS PROTOCOL...'
  estopStatusOk.value = false
  try {
    await triggerRobotSosTrigger()
    estopStatus.value = '>> EMERGENCY PROTOCOL ACTIVATED'
    estopStatusOk.value = true
    document.dispatchEvent(new CustomEvent('hk07:toast', {
      detail: {
        agent: 'SAFETY',
        message: 'EMERGENCY PROTOCOL ACTIVATED',
        severity: 'critical',
        duration: 6000
      }
    }))
    alertHistory.value.unshift({
      time: new Date().toTimeString().slice(0, 8),
      trigger: 'E-STOP',
      responseMs: 0,
      message: 'Manual SOS trigger via E-STOP control',
      severity: 'critical'
    })
    if (alertHistory.value.length > 50) alertHistory.value.pop()
  } catch {
    estopStatus.value = '>> SOS UPLINK FAILED — RETRY OR CALL OPERATOR'
    estopStatusOk.value = false
    document.dispatchEvent(new CustomEvent('hk07:toast', {
      detail: {
        agent: 'SAFETY',
        message: 'E-STOP uplink failed — check network / backend',
        severity: 'warning',
        duration: 5000
      }
    }))
  } finally {
    estopBusy.value = false
  }
}

let pruneInterval: ReturnType<typeof setInterval>

async function loadInitialLidarSnapshot() {
  try {
    const resp = await fetchLidarSnapshot()
    const snap = resp.data?.data as LidarScanSnapshot | undefined
    if (snap?.ranges360?.length) {
      safetyStore.loadSnapshot(snap)
    }
  } catch {
    /* WS stream will populate when broker is live */
  }
}

onMounted(() => {
  loadInitialLidarSnapshot()
  pruneInterval = setInterval(() => safetyStore.pruneStaleTriggers(), 2000)
})

onUnmounted(() => {
  clearInterval(pruneInterval)
})

watch(() => safetyStore.threatLevel, (level, prev) => {
  if (level === 'CRITICAL' && prev !== 'CRITICAL' && safetyStore.dataLive) {
    alertHistory.value.unshift({
      time: new Date().toTimeString().slice(0, 8),
      trigger: 'LIDAR_PROXIMITY',
      responseMs: 0,
      message: `Vật cản ${safetyStore.minDistanceM.toFixed(2)}m — góc ${safetyStore.closestAngleDeg}°`,
      severity: 'critical'
    })
    if (alertHistory.value.length > 50) alertHistory.value.pop()
  }
})

// Watch subsumption events to update trigger log
watch(() => agentsStore.subsumptionActive, (active) => {
  if (active) {
    const latestSafetyEvent = agentsStore.events.find(e => e.agentType === 'SAFETY')
    if (latestSafetyEvent) {
      lastResponseMs.value = latestSafetyEvent.latencyMs
      alertHistory.value.unshift({
        time: new Date().toTimeString().slice(0, 8),
        trigger: 'SUBSUMPTION_ACTIVATED',
        responseMs: latestSafetyEvent.latencyMs,
        message: latestSafetyEvent.outputDecision.slice(0, 60),
        severity: latestSafetyEvent.latencyMs < 5 ? 'warning' : 'critical'
      })
      if (alertHistory.value.length > 50) alertHistory.value.pop()
    }
  }
})
</script>

<style scoped>
.safety-shell { display: flex; flex-direction: column; height: 100vh; }
.safety-status { font-family: var(--font-hud); font-size: 10px; letter-spacing: 0.2em; }
.safety-layout { display: grid; grid-template-columns: 440px 1fr; flex: 1; overflow: hidden; gap: 12px; padding: 12px; }

.radar-panel { display: flex; flex-direction: column; gap: 8px; }
.radar-container { position: relative; display: flex; justify-content: center; align-items: center; }
.radar-container canvas { display: block; }
.radar-center-label {
  position: absolute; font-size: 9px; letter-spacing: 0.2em;
  text-transform: uppercase; pointer-events: none;
}
.radar-header-row { display: flex; justify-content: space-between; align-items: center; }
.radar-meta { display: flex; justify-content: space-between; font-size: 9px; padding: 0 4px 6px; letter-spacing: 0.08em; }
.data-link { font-size: 8px; letter-spacing: 0.2em; }
.baymax-hint {
  font-size: 10px; line-height: 1.5; padding: 8px 10px; margin-top: 6px;
  border-left: 2px solid var(--color-accent-cyan, #00e5ff);
  background: rgba(0, 229, 255, 0.04);
  color: var(--color-text-primary);
}
.baymax-tag { font-size: 8px; display: block; margin-bottom: 4px; letter-spacing: 0.15em; }
.radar-legend { font-size: 9px; text-align: center; margin-top: 4px; display: flex; flex-direction: column; gap: 2px; }
.legend-bubble { font-size: 8px; opacity: 0.75; }
.radar-critical { border-color: rgba(255, 51, 51, 0.6) !important; }
.radar-warning { border-color: rgba(255, 136, 0, 0.5) !important; }
.radar-inhibit { box-shadow: 0 0 24px rgba(255, 51, 51, 0.15); }

.safety-right { display: flex; flex-direction: column; gap: 8px; overflow-y: auto; }

.latency-display { text-align: center; padding: 12px 0; }
.latency-value { font-size: 40px; font-weight: 900; font-family: var(--font-hud); line-height: 1; }
.latency-unit { font-size: 14px; }
.latency-sla { font-size: 9px; letter-spacing: 0.2em; margin: 4px 0; }
.latency-verdict { font-size: 12px; letter-spacing: 0.3em; margin-top: 4px; }

.triggers-list { display: flex; flex-direction: column; gap: 4px; margin-top: 6px; }
.trigger-row { display: flex; gap: 10px; font-size: 10px; padding: 4px 6px; border-left: 2px solid; }
.trigger-row.critical { border-color: var(--color-accent-red); }
.trigger-row.warning { border-color: var(--color-accent-orange); }
.trigger-type { min-width: 80px; font-size: 9px; letter-spacing: 0.15em; }
.trigger-dist { min-width: 40px; }

.alert-history { overflow-y: auto; display: flex; flex-direction: column; gap: 2px; }
.alert-row { display: grid; grid-template-columns: 65px 120px 55px 1fr; gap: 6px; font-size: 10px; padding: 2px 4px; }
.alert-row.critical { background: rgba(255,51,51,0.05); }

.estop-panel { display: flex; flex-direction: column; align-items: center; }
.estop-container { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 12px 0; }
.estop-btn {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  border: 3px solid #FF3333;
  background: radial-gradient(circle at 35% 30%, #ff6666, #FF3333 55%, #990000);
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-hud);
  box-shadow:
    0 0 20px rgba(255, 51, 51, 0.7),
    0 0 40px rgba(255, 51, 51, 0.4),
    inset 0 0 12px rgba(0, 0, 0, 0.35);
  animation: estop-pulse-glow 1.4s ease-in-out infinite;
  transition: transform 0.1s ease;
}
.estop-btn:hover:not(:disabled) { transform: scale(1.05); }
.estop-btn:active:not(:disabled) { transform: scale(0.97); }
.estop-btn:disabled { opacity: 0.6; cursor: not-allowed; animation: none; }
.estop-label {
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-shadow: 0 0 8px rgba(0, 0, 0, 0.8);
}
.estop-status { font-size: 9px; letter-spacing: 0.1em; text-align: center; max-width: 280px; }

@keyframes estop-pulse-glow {
  0%, 100% {
    box-shadow:
      0 0 16px rgba(255, 51, 51, 0.6),
      0 0 32px rgba(255, 51, 51, 0.35),
      inset 0 0 12px rgba(0, 0, 0, 0.35);
  }
  50% {
    box-shadow:
      0 0 28px rgba(255, 51, 51, 1),
      0 0 56px rgba(255, 51, 51, 0.55),
      inset 0 0 12px rgba(0, 0, 0, 0.35);
  }
}
</style>
