<template>
  <div class="safety-shell">
    <div class="safety-layout">
      <!-- ── LEFT: Radar Canvas ─────────────────────────────────────────────── -->
      <div class="radar-panel terminal-card corner-reticle">
        <div class="terminal-card-header">[ LIDAR_360_RADAR // {{ scanHz }}Hz ]</div>
        <div class="radar-container">
          <canvas ref="radarCanvas" :width="RADAR_SIZE" :height="RADAR_SIZE"></canvas>
          <!-- Center label -->
          <div class="radar-center-label hud text-dim">HK-07</div>
        </div>
        <!-- Distance rings legend -->
        <div class="radar-legend mono text-dim">
          <span>0.5m ● 1.0m ● 2.0m ● 3.0m</span>
        </div>
      </div>

      <!-- ── RIGHT: Alert Panel ─────────────────────────────────────────────── -->
      <div class="safety-right">
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
            <div v-for="trigger in activeTriggers" :key="trigger.type"
                 :class="['trigger-row', trigger.severity]">
              <span class="trigger-type hud">{{ trigger.type }}</span>
              <span class="trigger-dist mono">{{ trigger.distanceM?.toFixed(2) }}m</span>
              <span class="trigger-msg text-dim">{{ trigger.message }}</span>
            </div>
            <div v-if="activeTriggers.length === 0" class="text-dim mono" style="padding:8px;font-size:10px">
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

const agentsStore = useAgentsStore()

// ─── State ────────────────────────────────────────────────────────────────────
const RADAR_SIZE = 400
const subsumptionActive = computed(() => agentsStore.subsumptionActive)
const lastResponseMs = ref(0)
const latencyOk = computed(() => lastResponseMs.value < 5.0 || lastResponseMs.value === 0)
const scanHz = ref(10)

const activeTriggers = ref<{ type: string; distanceM: number; message: string; severity: string }[]>([])
const alertHistory = ref<{ time: string; trigger: string; responseMs: number; message: string; severity: string }[]>([])

// ─── Radar Canvas ─────────────────────────────────────────────────────────────
const radarCanvas = ref<HTMLCanvasElement | null>(null)
let animFrame: number
let isUnmountedFlag = false

// Mock LiDAR data (replaced by WebSocket data in real mode)
let lidarRanges: number[] = Array.from({ length: 360 }, () => 3.0 + Math.random() * 0.2)

function drawRadar() {
  if (isUnmountedFlag) return
  const canvas = radarCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')!
  const cx = RADAR_SIZE / 2, cy = RADAR_SIZE / 2
  const maxRange = 3.5   // meters — displayed range

  ctx.clearRect(0, 0, RADAR_SIZE, RADAR_SIZE)
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, RADAR_SIZE, RADAR_SIZE)

  // ── Grid rings ─────────────────────────────────────────────────────────────
  const ringDistances = [0.5, 1.0, 2.0, 3.0]
  ctx.strokeStyle = 'rgba(0, 255, 102, 0.1)'
  ctx.lineWidth = 1
  ringDistances.forEach(d => {
    const r = (d / maxRange) * (RADAR_SIZE / 2)
    ctx.beginPath()
    ctx.arc(cx, cy, r, 0, Math.PI * 2)
    ctx.stroke()
  })

  // ── Crosshair lines ─────────────────────────────────────────────────────────
  ctx.strokeStyle = 'rgba(0, 255, 102, 0.08)'
  ;[0, 45, 90, 135].forEach(angleDeg => {
    const rad = (angleDeg * Math.PI) / 180
    ctx.beginPath()
    ctx.moveTo(cx + Math.cos(rad) * RADAR_SIZE / 2, cy + Math.sin(rad) * RADAR_SIZE / 2)
    ctx.lineTo(cx - Math.cos(rad) * RADAR_SIZE / 2, cy - Math.sin(rad) * RADAR_SIZE / 2)
    ctx.stroke()
  })

  // ── Sweep line (rotating) ───────────────────────────────────────────────────
  const sweepAngle = (Date.now() / 50) % 360
  const sweepRad = (sweepAngle * Math.PI) / 180
  const grad = ctx.createLinearGradient(cx, cy,
    cx + Math.cos(sweepRad) * RADAR_SIZE / 2,
    cy + Math.sin(sweepRad) * RADAR_SIZE / 2)
  grad.addColorStop(0, 'rgba(0, 255, 102, 0.4)')
  grad.addColorStop(1, 'rgba(0, 255, 102, 0)')
  ctx.strokeStyle = grad
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(cx, cy)
  ctx.lineTo(
    cx + Math.cos(sweepRad) * RADAR_SIZE / 2,
    cy + Math.sin(sweepRad) * RADAR_SIZE / 2
  )
  ctx.stroke()

  // ── LiDAR points ───────────────────────────────────────────────────────────
  ctx.fillStyle = '#00FF66'
  ctx.shadowColor = '#00FF66'
  ctx.shadowBlur = 6
  lidarRanges.forEach((dist, angleDeg) => {
    if (dist <= 0 || dist > maxRange) return
    const rad = (angleDeg * Math.PI) / 180
    const pixelDist = (dist / maxRange) * (RADAR_SIZE / 2)
    const px = cx + Math.cos(rad) * pixelDist
    const py = cy + Math.sin(rad) * pixelDist
    ctx.beginPath()
    ctx.arc(px, py, dist < 0.5 ? 4 : 2, 0, Math.PI * 2)
    ctx.fill()
  })
  ctx.shadowBlur = 0

  // ── Center dot (robot) ─────────────────────────────────────────────────────
  ctx.fillStyle = '#00FF66'
  ctx.shadowColor = '#00FF66'
  ctx.shadowBlur = 10
  ctx.beginPath()
  ctx.arc(cx, cy, 6, 0, Math.PI * 2)
  ctx.fill()
  ctx.shadowBlur = 0

  animFrame = requestAnimationFrame(drawRadar)
}

// Simulate LiDAR scan updates (replaced by WebSocket in real mode)
function updateLidarSimulation() {
  lidarRanges = lidarRanges.map((v, i) => {
    // Occasional close-range obstacle for demo
    if (i > 25 && i < 35 && Math.random() < 0.1) return 0.3 + Math.random() * 0.4
    return 3.0 + Math.random() * 0.3 - 0.1
  })
}

onMounted(() => {
  animFrame = requestAnimationFrame(drawRadar)
  const scanInterval = setInterval(updateLidarSimulation, 100)
  onUnmounted(() => clearInterval(scanInterval))
})

onUnmounted(() => {
  isUnmountedFlag = true
  cancelAnimationFrame(animFrame)
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
.radar-legend { font-size: 9px; text-align: center; margin-top: 4px; }

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
</style>
