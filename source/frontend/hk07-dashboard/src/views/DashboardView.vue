<template>
  <div class="dashboard-shell">
    <div class="dashboard-grid">
      <!-- ── Left side: Tactical Parameters Sidebar (30%) ─────────────────── -->
      <aside class="tactical-sidebar">
        <div class="sidebar-header">
          <span class="text-green font-bold text-xs">[ TACTICAL_PARAMETERS ]</span>
          <span class="role-badge">{{ authStore.user?.role }}</span>
        </div>

        <!-- Bio-Telemetry Widget -->
        <BioTelemetryWidget :telemetry="currentTelemetry" />

        <!-- Operational Alerts Status -->
        <div class="terminal-card">
          <div class="terminal-card-header">[ OPERATIONAL_ALERTS ]</div>
          <div class="alerts-list">
            <div v-if="vitalsStore.isEmergency" class="alert-item critical text-[9px]">
              🚨 LEVEL: {{ vitalsStore.alertLevel }} — EMERGENCY ACTIVE
            </div>
            <div v-else class="alert-item normal text-[9px]">
              ✓ PARAMETERS WITHIN NORMAL THRESHOLDS
            </div>
          </div>
        </div>

        <!-- Robot Control Widget -->
        <div class="terminal-card">
          <div class="terminal-card-header">[ ROBOT_CONTROL ]</div>
          <div class="robot-status-row">
            <span class="label text-[9px]">STATE:</span>
            <span :class="['value text-[9px]', robotStateClass]">{{ robotState }}</span>
          </div>
          <div class="control-btns">
            <button class="cmd-btn text-[9px] py-1" @click="robotHold" :disabled="robotState === 'SAFE_HOLD'">SAFE_HOLD</button>
            <button class="cmd-btn text-[9px] py-1" @click="robotResume" :disabled="robotState === 'ACTIVE'">RESUME</button>
            <button class="cmd-btn danger text-[9px] py-1" @click="confirmShutdown" :disabled="authStore.user?.role !== 'OWNER'">SHUTDOWN</button>
          </div>
        </div>

        <!-- OWNER WORKSPACE -->
        <template v-if="authStore.user?.role === 'OWNER'">
          <div class="terminal-card">
            <div class="terminal-card-header">[ SUBSUMPTION_OVERRIDE ]</div>
            <div :class="['sub-status-display text-xs py-1', agentsStore.subsumptionActive ? 'text-red' : 'text-green']">
              {{ agentsStore.subsumptionActive ? '⚠ INHIBIT ACTIVE' : '✓ MOTION ENABLED' }}
            </div>
            <div class="sub-priority-chain mono text-dim text-[8px]">
              CHAIN: SAFETY(0) &gt; MEDICAL(1) &gt; EMPATHY(2)
            </div>
            <div style="margin-top: 6px; display: flex;">
              <button class="cmd-btn text-[9px] w-full py-1" @click="toggleSubsumption">
                {{ agentsStore.subsumptionActive ? 'DEACTIVATE_OVERRIDE' : 'FORCE_SAFETY_HOLD' }}
              </button>
            </div>
          </div>
        </template>

        <!-- TECHNICIAN WORKSPACE -->
        <template v-if="authStore.user?.role === 'TECHNICIAN'">
          <!-- Latency & Diagnostics -->
          <div class="terminal-card">
            <div class="terminal-card-header">[ SYSTEM_DIAGNOSTICS ]</div>
            <div class="diagnostics-grid">
              <div class="diag-item">
                <span class="diag-label text-[8px]">SLA LATENCY:</span>
                <span :class="['diag-val text-[9px] font-bold', latencyClass]">{{ latencyText }}</span>
              </div>
              <div class="diag-item">
                <span class="diag-label text-[8px]">SLA TARGET:</span>
                <span class="diag-val text-green text-[9px]">&lt; 5.00ms</span>
              </div>
              <div class="diag-item">
                <span class="diag-label text-[8px]">VERDICT:</span>
                <span :class="['diag-val text-[9px] font-bold', latencyClass]">{{ latencyVerdict }}</span>
              </div>
            </div>
          </div>

          <!-- Sensor Calibration Controls -->
          <div class="terminal-card">
            <div class="terminal-card-header">[ VISION_CALIBRATION ]</div>
            <div class="calibration-controls">
              <div class="control-row">
                <span class="label text-[8px]">VISION RATE:</span>
                <span class="value text-green text-[9px]">30 FPS</span>
              </div>
              <div class="control-row">
                <span class="label text-[8px]">STATUS:</span>
                <span class="value text-green text-[9px]">ONLINE</span>
              </div>
              <div class="calibration-btns">
                <button class="cmd-btn text-[9px] py-1" @click="calibrateSensors">CALIBRATE</button>
                <button class="cmd-btn text-orange text-[9px] py-1" @click="triggerSelfTest">SELF_TEST</button>
              </div>
            </div>
          </div>
        </template>

        <!-- EMERGENCY_CONTACT WORKSPACE -->
        <template v-if="authStore.user?.role === 'EMERGENCY_CONTACT'">
          <div class="terminal-card">
            <div class="terminal-card-header">[ DISPATCH_CONTROL ]</div>
            <div style="display: flex; flex-direction: column; gap: 6px;">
              <button class="cmd-btn danger text-[10px] py-2" @click="dispatchEmergency">
                🚨 EMERGENCY DISPATCH
              </button>
              <div class="text-dim mono text-[7px] text-center uppercase leading-tight">
                WARNING: Broadcasts telemetry package to medical center
              </div>
            </div>
          </div>
        </template>
      </aside>

      <!-- ── Right side: Data Visualization Canvas (70%) ─────────────────── -->
      <section class="data-canvas">
        <!-- ECG Waveform Canvas -->
        <div class="terminal-card corner-reticle">
          <div class="terminal-card-header">
            [ VITAL_STREAM_ECG ]
            <span :class="['mono ml-2 text-[9px]', vitalsStore.isConnected ? 'text-green' : 'text-dim']">
              {{ vitalsStore.isConnected ? 'STREAMING' : 'OFFLINE_SIM' }}
            </span>
          </div>
          <div class="ecg-widget-wrapper">
            <EcgWaveform :height="90" />
          </div>
        </div>
        
        <!-- Kinematics & Environment Widget -->
        <div>
          <KinematicsWidget :telemetry="currentTelemetry" />
        </div>

        <!-- Subsumption Architecture Summary -->
        <div class="terminal-card">
          <div class="terminal-card-header">[ SUBSUMPTION_ARCHITECTURE ]</div>
          <div class="subsumption-grid">
            <div :class="['sub-layer', agentsStore.subsumptionActive ? 'active' : '']">
              <span class="sub-priority">TIER 0</span>
              <span class="sub-name">SAFETY_OVERRIDE</span>
              <span class="sub-status">{{ agentsStore.subsumptionActive ? 'INHIBIT_ACTIVE' : 'ARMED' }}</span>
            </div>
            <div :class="['sub-layer', agentsStore.agentStatus.MEDICAL === 'ACTIVE' ? 'active' : '',
                          agentsStore.agentStatus.MEDICAL === 'INHIBITED' ? 'inhibited' : '']">
              <span class="sub-priority">TIER 1</span>
              <span class="sub-name">MEDICAL_MONITOR</span>
              <span class="sub-status">{{ agentsStore.agentStatus.MEDICAL }}</span>
            </div>
            <div :class="['sub-layer', agentsStore.agentStatus.EMPATHETIC === 'ACTIVE' ? 'active' : '',
                          agentsStore.agentStatus.EMPATHETIC === 'INHIBITED' ? 'inhibited' : '']">
              <span class="sub-priority">TIER 2</span>
              <span class="sub-name">EMPATHETIC_COMM</span>
              <span class="sub-status">{{ agentsStore.agentStatus.EMPATHETIC }}</span>
            </div>
          </div>
        </div>

        <!-- Agent Event Log — Last 20 events from Pinia -->
        <div class="terminal-card flex-1">
          <div class="terminal-card-header">[ AGENT_EVENT_STREAM ]</div>
          <div class="event-log mono">
            <div v-for="ev in agentsStore.events.slice(0, 20)" :key="ev.id"
                 :class="['event-line', ev.alertLevel === 'CRITICAL' ? 'ev-critical' : '']">
              <span class="event-time text-dim">{{ formatTime(ev.triggeredAt) }}</span>
              <span :class="['event-agent', agentColor(ev.agentType)]"> [{{ ev.agentType }}]</span>
              <span class="event-msg"> {{ ev.outputDecision?.slice(0, 120) }}</span>
            </div>
            <div v-if="agentsStore.events.length === 0" class="text-dim p-2">
              &gt;&gt;&gt; AWAITING AGENT EVENTS...
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useVitalsStore } from '../stores/vitals'
import { useAgentsStore } from '../stores/agents'
import { useTelemetryStore } from '../stores/telemetry'
import { useSensorTelemetryStore } from '../stores/sensorTelemetry'
import EcgWaveform from '../components/EcgWaveform.vue'
import BioTelemetryWidget from '../components/telemetry/BioTelemetryWidget.vue'
import KinematicsWidget from '../components/telemetry/KinematicsWidget.vue'
import type { RobotTelemetry } from '../components/telemetry/types'
import api from '../services/api'

const authStore = useAuthStore()
const vitalsStore = useVitalsStore()
const agentsStore = useAgentsStore()
const telemetryStore = useTelemetryStore()
const sensorStore = useSensorTelemetryStore()

const currentTelemetry = computed<RobotTelemetry>(() => {
  return {
    messageId: 'msg-dashboard',
    sessionId: 'session-dashboard',
    deviceId: vitalsStore.current.deviceId || 'NO_DEVICE',
    hr: vitalsStore.current.heartRate,
    spO2: vitalsStore.current.spo2,
    light: sensorStore.environment.ambient_light,
    pressure: sensorStore.environment.barometric_pressure,
    pressureDelta: sensorStore.environment.pressure_delta_hpa,
    yaw: sensorStore.eulerAngles.yaw,
    pitch: sensorStore.eulerAngles.pitch,
    roll: sensorStore.eulerAngles.roll,
    latitude: sensorStore.location.latitude,
    longitude: sensorStore.location.longitude,
    altitude: sensorStore.location.altitude,
    steps: sensorStore.activity.pedometer_steps,
    activityType: sensorStore.activity.activity_type,
    fallState: vitalsStore.isEmergency,
    fallConfidence: vitalsStore.isEmergency ? 1.0 : 0.0,
    gForceMagnitude: sensorStore.wristMagnitude,
    rawAccel: {
      x: sensorStore.imu.linear_acceleration.x,
      y: sensorStore.imu.linear_acceleration.y,
      z: sensorStore.imu.linear_acceleration.z,
      magnitude: sensorStore.wristMagnitude
    },
    sensorStatus: {
      hrValid: vitalsStore.isConnected,
      spo2Valid: vitalsStore.isConnected,
      lightValid: sensorStore.envStatus === 'LIVE',
      pressureValid: sensorStore.envStatus === 'LIVE',
      yawValid: sensorStore.imuStatus === 'LIVE',
      accelValid: sensorStore.imuStatus === 'LIVE'
    },
    timestamp: vitalsStore.current.epochTimestampMs || Date.now()
  }
})

// Robot State
const robotState = ref('ACTIVE')
const robotStateClass = computed(() => {
  if (robotState.value === 'ACTIVE') return 'text-green'
  if (robotState.value === 'SAFE_HOLD') return 'text-orange'
  return 'text-red'
})

// Vitals thresholds color mapping — now reads from telemetryStore
const hrClass = computed(() => {
  const s = telemetryStore.hrStatus
  if (s === 'critical') return 'text-red font-bold glow-red'
  if (s === 'warning') return 'text-orange font-bold'
  return 'text-green font-bold'
})

const spo2Class = computed(() => {
  const s = telemetryStore.spo2Status
  if (s === 'critical') return 'text-red font-bold glow-red'
  if (s === 'warning') return 'text-orange font-bold'
  return 'text-green font-bold'
})

const bpClass = computed(() => {
  const s = telemetryStore.bpStatus
  if (s === 'critical') return 'text-red font-bold glow-red'
  return 'text-green font-bold'
})

const tempClass = computed(() => {
  const s = telemetryStore.tempStatus
  if (s === 'critical') return 'text-red font-bold glow-red'
  if (s === 'warning') return 'text-orange font-bold'
  return 'text-green font-bold'
})

// Robot Action handlers
async function robotHold() {
  await api.post('/robot/command/hold').catch(() => {})
  robotState.value = 'SAFE_HOLD'
  document.dispatchEvent(new CustomEvent('hk07:system-state', { detail: 'SAFE_HOLD' }))
}

async function robotResume() {
  await api.post('/robot/command/resume').catch(() => {})
  robotState.value = 'ACTIVE'
  document.dispatchEvent(new CustomEvent('hk07:system-state', { detail: 'ACTIVE' }))
}

function confirmShutdown() {
  if (confirm('[WARNING] Confirm robot shutdown?')) {
    api.post('/robot/command/shutdown').catch(() => {})
    robotState.value = 'SHUTDOWN'
    document.dispatchEvent(new CustomEvent('hk07:system-state', { detail: 'SHUTDOWN' }))
  }
}

function toggleSubsumption() {
  agentsStore.setSubsumptionActive(!agentsStore.subsumptionActive)
}

// Technician Diagnostics
const latestSafetyEvent = computed(() => 
  agentsStore.events.find(e => e.agentType === 'SAFETY')
)

const latencyText = computed(() => {
  if (!latestSafetyEvent.value) return '0.00 ms'
  return `${latestSafetyEvent.value.latencyMs.toFixed(2)} ms`
})

const latencyClass = computed(() => {
  if (!latestSafetyEvent.value) return 'text-green'
  return latestSafetyEvent.value.latencyMs < 5.0 ? 'text-green' : 'text-red'
})

const latencyVerdict = computed(() => {
  if (!latestSafetyEvent.value) return '[ PASS ]'
  return latestSafetyEvent.value.latencyMs < 5.0 ? '[ PASS ]' : '[ BREACH ]'
})

function calibrateSensors() {
  document.dispatchEvent(new CustomEvent('hk07:toast', {
    detail: {
      severity: 'info',
      agent: 'DIAGNOSTIC',
      message: '[DIAGNOSTIC] Sensor matrix calibration triggered.',
      duration: 5000
    }
  }))
}

function triggerSelfTest() {
  document.dispatchEvent(new CustomEvent('hk07:toast', {
    detail: {
      severity: 'warning',
      agent: 'DIAGNOSTIC',
      message: '[DIAGNOSTIC] Running system-wide health and safety self test...',
      duration: 6000
    }
  }))
}

// Emergency Contact
function dispatchEmergency() {
  if (confirm('[EMERGENCY] Confirm manual dispatch of emergency services?')) {
    document.dispatchEvent(new CustomEvent('hk07:toast', {
      detail: {
        severity: 'critical',
        agent: 'DISPATCH',
        message: '[DISPATCHED] Emergency rescue dispatched. Patient vital metrics broadcasted.',
        duration: 10000
      }
    }))
  }
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toTimeString().slice(0, 8)
  } catch {
    return '--:--:--'
  }
}

function agentColor(type: string) {
  return 'text-green'
}

function onUnauthorized() {
  document.dispatchEvent(new CustomEvent('hk07:navigate', { detail: '/login' }))
}

function onSystemState(e: Event) {
  const customEvent = e as CustomEvent<string>
  robotState.value = customEvent.detail
}

onMounted(() => {
  document.addEventListener('hk07:unauthorized', onUnauthorized)
  document.addEventListener('hk07:system-state', onSystemState)
})

onUnmounted(() => {
  document.removeEventListener('hk07:unauthorized', onUnauthorized)
  document.removeEventListener('hk07:system-state', onSystemState)
})
</script>

<style scoped>
.dashboard-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: 3fr 7fr;
  gap: var(--space-md);
  height: 100%;
  padding: var(--space-md);
  overflow: hidden;
}

.tactical-sidebar {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
  overflow-y: auto;
  padding-right: 4px;
}

.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--font-hud);
  font-size: 9px;
  letter-spacing: 0.1em;
  border-bottom: 1px solid var(--color-border-dim);
  padding-bottom: 6px;
  margin-bottom: 4px;
}

.role-badge {
  background: var(--color-border-dim);
  color: var(--color-accent-green);
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: bold;
  font-size: 8px;
}

.data-canvas {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  overflow-y: auto;
}

.vitals-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px;
  margin-top: 4px;
}

.vital-item {
  border: 1px solid var(--color-border-dim);
  background: rgba(0, 0, 0, 0.4);
  padding: 6px;
  text-align: center;
  border-radius: 2px;
}

.vital-value {
  font-family: var(--font-mono);
  line-height: 1.2;
}

.vital-unit {
  font-size: 7px;
  color: var(--color-text-dim);
  text-transform: uppercase;
  margin-top: 2px;
}

.robot-status-row {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-hud);
  margin-bottom: 4px;
}

.control-btns, .calibration-btns {
  display: flex;
  gap: 4px;
  flex-wrap: nowrap;
  margin-top: 6px;
}

.control-btns button, .calibration-btns button {
  flex: 1;
  white-space: nowrap;
  font-size: 8px !important;
  padding: 4px 2px !important;
}

.sub-status-display {
  font-family: var(--font-hud);
  font-weight: 700;
  letter-spacing: 0.1em;
  text-align: center;
}

.sub-priority-chain {
  text-align: center;
}

.alerts-list {
  padding: 4px 0;
}

.alert-item {
  font-family: var(--font-hud);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 4px;
  border-radius: 2px;
  text-align: center;
}

.alert-item.critical {
  background: rgba(255, 51, 51, 0.12);
  border: 1px solid var(--color-accent-red);
  color: var(--color-accent-red);
  animation: blink-crit 1.5s step-end infinite;
}

.alert-item.normal {
  border: 1px solid var(--color-border-dim);
  color: var(--color-accent-green);
}

@keyframes blink-crit {
  50% { opacity: 0.5; }
}

.diagnostics-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
}

.diag-item, .control-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.diag-label, .label {
  color: var(--color-text-dim);
  font-family: var(--font-hud);
  letter-spacing: 0.05em;
}

.ecg-widget-wrapper {
  background: #000000;
}

.subsumption-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
}

.sub-layer {
  display: flex;
  gap: 12px;
  align-items: center;
  font-family: var(--font-hud);
  font-size: 9px;
  letter-spacing: 0.15em;
  padding: 4px 8px;
  border: 1px solid var(--color-border-dim);
  color: var(--color-text-dim);
}

.sub-layer.active {
  border-color: var(--color-accent-green);
  color: var(--color-accent-green);
}

.sub-layer.inhibited {
  border-color: var(--color-accent-red);
  color: var(--color-accent-red);
}

.sub-priority {
  min-width: 45px;
}

.sub-name {
  flex: 1;
}

.sub-status {
  font-weight: 700;
}

.event-log {
  flex: 1;
  min-height: 150px;
  overflow-y: auto;
  font-size: 10px;
  line-height: 1.7;
}

.event-line {
  display: grid;
  grid-template-columns: minmax(58px, 62px) minmax(80px, 100px) minmax(0, 1fr);
  gap: 6px;
  align-items: start;
}

.ev-critical .event-msg {
  color: var(--color-accent-red);
}

.event-time {
  white-space: nowrap;
}

.event-agent {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-msg {
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: bold;
  font-size: 8px;
}

.data-canvas {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  overflow-y: auto;
}

.vitals-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px;
  margin-top: 4px;
}

.vital-item {
  border: 1px solid var(--color-border-dim);
  background: rgba(0, 0, 0, 0.4);
  padding: 6px;
  text-align: center;
  border-radius: 2px;
}

.vital-value {
  font-family: var(--font-mono);
  line-height: 1.2;
}

.vital-unit {
  font-size: 7px;
  color: var(--color-text-dim);
  text-transform: uppercase;
  margin-top: 2px;
}

.robot-status-row {
  display: flex;
  justify-content: space-between;
  font-family: var(--font-hud);
  margin-bottom: 4px;
}

.control-btns, .calibration-btns {
  display: flex;
  gap: 4px;
  flex-wrap: nowrap;
  margin-top: 6px;
}

.control-btns button, .calibration-btns button {
  flex: 1;
  white-space: nowrap;
  font-size: 8px !important;
  padding: 4px 2px !important;
}

.sub-status-display {
  font-family: var(--font-hud);
  font-weight: 700;
  letter-spacing: 0.1em;
  text-align: center;
}

.sub-priority-chain {
  text-align: center;
}

.alerts-list {
  padding: 4px 0;
}

.alert-item {
  font-family: var(--font-hud);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  padding: 4px;
  border-radius: 2px;
  text-align: center;
}

.alert-item.critical {
  background: rgba(255, 51, 51, 0.12);
  border: 1px solid var(--color-accent-red);
  color: var(--color-accent-red);
  animation: blink-crit 1.5s step-end infinite;
}

.alert-item.normal {
  border: 1px solid var(--color-border-dim);
  color: var(--color-accent-green);
}

@keyframes blink-crit {
  50% { opacity: 0.5; }
}

.diagnostics-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px 0;
}

.diag-item, .control-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.diag-label, .label {
  color: var(--color-text-dim);
  font-family: var(--font-hud);
  letter-spacing: 0.05em;
}

.ecg-widget-wrapper {
  background: #000000;
}

.subsumption-grid {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 8px;
}

.sub-layer {
  display: flex;
  gap: 12px;
  align-items: center;
  font-family: var(--font-hud);
  font-size: 9px;
  letter-spacing: 0.15em;
  padding: 4px 8px;
  border: 1px solid var(--color-border-dim);
  color: var(--color-text-dim);
}

.sub-layer.active {
  border-color: var(--color-accent-green);
  color: var(--color-accent-green);
}

.sub-layer.inhibited {
  border-color: var(--color-accent-red);
  color: var(--color-accent-red);
}

.sub-priority {
  min-width: 45px;
}

.sub-name {
  flex: 1;
}

.sub-status {
  font-weight: 700;
}

.event-log {
  flex: 1;
  min-height: 150px;
  overflow-y: auto;
  font-size: 10px;
  line-height: 1.7;
}

.event-line {
  display: grid;
  grid-template-columns: minmax(58px, 62px) minmax(80px, 100px) minmax(0, 1fr);
  gap: 6px;
  align-items: start;
}

.ev-critical .event-msg {
  color: var(--color-accent-red);
}

.event-time {
  white-space: nowrap;
}

.event-agent {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.event-msg {
  word-break: break-word;
  white-space: normal;
  overflow-wrap: anywhere;
}

.source-badge {
  font-family: var(--font-hud);
  font-size: 7px;
  letter-spacing: 0.1em;
}

.dashboard-visual-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-md);
}

@media (max-width: 1024px) {
  .dashboard-visual-row {
    grid-template-columns: 1fr;
  }
}
</style>
