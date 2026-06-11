<template>
  <div class="dt-shell">
    <!-- ══ 3D Holographic Twin Canvas ══════════════════════════════════════ -->
    <HolographicTwin class="dt-canvas" />

    <!-- ══ HUD Overlay ═══════════════════════════════════════════════════ -->
    <div class="hud-overlay">

      <!-- Top-left: system header -->
      <div class="hud-block hud-topleft corner-reticle">
        <div class="hud-title">[ HK-07 // DIGITAL TWIN — HOLOGRAPHIC SCAN v3.0 ]</div>
        <div class="hud-sub">
          <span class="status-dot" :style="{ background: alertColor }">●</span>
          <span class="mode-tag">{{ kinematicsStore.isLive ? 'LIVE_STREAM' : 'OFFLINE_STANDBY' }}</span>
          <span class="sep">|</span>
          <span class="fps-val">{{ kinematicsStore.isLive ? 'SYNCED' : 'NO_LINK' }}</span>
          <span class="sep">|</span>
          <span class="ts-val">{{ timeStr }}</span>
        </div>
      </div>

      <!-- Top-right: alert level -->
      <div class="hud-block hud-topright">
        <div class="alert-chip" :class="alertClass">
          <span class="alert-icon">{{ safetyStore.threatLevel === 'CRITICAL' ? '⚠' : safetyStore.threatLevel === 'WARNING' ? '△' : '✓' }}</span>
          {{ safetyStore.threatLevel }}
        </div>
      </div>

      <!-- Clinical Vision Scan Results Panel (Top-Right under threat chip) -->
      <div class="hud-block hud-clinical corner-reticle" v-if="safetyStore.clinicalAnalysis">
        <div class="matrix-header">[ CLINICAL_VISION_SCAN ]</div>
        <div class="matrix-row">
          <span class="axis-label">INJURIES</span>
          <span :class="['coord-val', safetyStore.clinicalAnalysis.visible_injuries?.detected ? 'text-red' : 'text-green']">
            {{ safetyStore.clinicalAnalysis.visible_injuries?.detected ? 'DETECTED' : 'CLEAR' }}
          </span>
        </div>
        <div class="matrix-desc" v-if="safetyStore.clinicalAnalysis.visible_injuries?.details">
          &gt; {{ safetyStore.clinicalAnalysis.visible_injuries.details }}
        </div>
        <div class="matrix-row">
          <span class="axis-label">DISTRESS</span>
          <span :class="['coord-val', safetyStore.clinicalAnalysis.facial_distress?.detected ? 'text-red' : 'text-green']">
            {{ safetyStore.clinicalAnalysis.facial_distress?.detected ? 'DETECTED' : 'CLEAR' }}
          </span>
        </div>
        <div class="matrix-desc" v-if="safetyStore.clinicalAnalysis.facial_distress?.details">
          &gt; {{ safetyStore.clinicalAnalysis.facial_distress.details }}
        </div>
        <div class="matrix-row">
          <span class="axis-label">HAZARDS</span>
          <span :class="['coord-val', safetyStore.clinicalAnalysis.environmental_hazards?.detected ? 'text-red' : 'text-green']">
            {{ safetyStore.clinicalAnalysis.environmental_hazards?.detected ? 'DETECTED' : 'CLEAR' }}
          </span>
        </div>
        <div class="matrix-desc" v-if="safetyStore.clinicalAnalysis.environmental_hazards?.details">
          &gt; {{ safetyStore.clinicalAnalysis.environmental_hazards.details }}
        </div>
      </div>

      <!-- Bottom-left: positional telemetry matrix -->
      <div class="hud-block hud-botleft coord-matrix corner-reticle">
        <div class="matrix-header">[ POSITIONAL_TELEMETRY ]</div>
        <div class="matrix-row">
          <span class="axis-x">X</span>
          <span class="axis-bar">━━━━</span>
          <span class="coord-val">{{ kinematicsStore.positionFormatted.x }}</span>
          <span class="unit">m</span>
        </div>
        <div class="matrix-row">
          <span class="axis-y">Y</span>
          <span class="axis-bar">━━━━</span>
          <span class="coord-val">{{ kinematicsStore.positionFormatted.y }}</span>
          <span class="unit">m</span>
        </div>
        <div class="matrix-row">
          <span class="axis-z">Z</span>
          <span class="axis-bar">━━━━</span>
          <span class="coord-val">{{ kinematicsStore.positionFormatted.z }}</span>
          <span class="unit">m</span>
        </div>
        <div class="matrix-divider"></div>
        <div class="matrix-row">
          <span class="axis-label">PITCH</span>
          <span class="axis-bar">━━</span>
          <span class="coord-val">{{ kinematicsStore.rotationFormatted.pitch }}</span>
        </div>
        <div class="matrix-row">
          <span class="axis-label">YAW</span>
          <span class="axis-bar">━━━</span>
          <span class="coord-val">{{ kinematicsStore.rotationFormatted.yaw }}</span>
        </div>
        <div class="matrix-row">
          <span class="axis-label">ROLL</span>
          <span class="axis-bar">━━━</span>
          <span class="coord-val">{{ kinematicsStore.rotationFormatted.roll }}</span>
        </div>
      </div>

      <!-- Bottom-right: PMU + controls panel -->
      <div class="hud-block hud-botright">
        <div class="matrix-header">[ POWER_MANAGEMENT_UNIT ]</div>
        <div class="matrix-row">
          <span class="axis-label">VOLTAGE</span>
          <span class="coord-val text-green">{{ kinematicsStore.pmu.voltage.toFixed(2) }} V</span>
        </div>
        <div class="matrix-row">
          <span class="axis-label">CURRENT</span>
          <span class="coord-val text-orange">{{ kinematicsStore.pmu.current.toFixed(2) }} A</span>
        </div>
        <div class="matrix-row">
          <span class="axis-label">BATTERY_SOC</span>
          <span class="coord-val text-green">{{ kinematicsStore.pmu.soc.toFixed(2) }}%</span>
        </div>
        <div class="matrix-row">
          <span class="axis-label">TEMPERATURE</span>
          <span class="coord-val text-orange">{{ kinematicsStore.pmu.temp.toFixed(1) }} °C</span>
        </div>
        <div class="matrix-divider"></div>
        <div class="ctrl-btns">
          <button id="btn-twin-reset" class="ctrl-btn reset-btn" @click="resetScene">[ ↺ RE-CALIBRATE ]</button>
        </div>
      </div>

      <!-- Centre: crosshair -->
      <div class="hud-crosshair">
        <div class="ch-h"></div>
        <div class="ch-v"></div>
        <div class="ch-dot"></div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import HolographicTwin from '../components/HolographicTwin.vue'
import { useKinematicsStore } from '../stores/kinematics'
import { useSafetyStore } from '../stores/safety'

const kinematicsStore = useKinematicsStore()
const safetyStore = useSafetyStore()

const timeStr = computed(() => new Date().toLocaleTimeString('vi-VN', { hour12: false }))

const alertColor = computed(() => {
  if (safetyStore.threatLevel === 'CRITICAL') return '#FF3333'
  if (safetyStore.threatLevel === 'WARNING')  return '#FFB000'
  return '#00FF66'
})

const alertClass = computed(() => {
  if (safetyStore.threatLevel === 'CRITICAL') return 'alert-critical'
  if (safetyStore.threatLevel === 'WARNING')  return 'alert-warning'
  return 'alert-normal'
})

function resetScene() {
  kinematicsStore.reset()
}
</script>

<style scoped>
.dt-shell {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #000000;
  display: flex;
}

.dt-canvas {
  width: 100% !important;
  height: 100% !important;
  display: block;
}

/* ── HUD Overlay ─────────────────────────────────────────────────────── */
.hud-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 10;
}

/* Hud block common */
.hud-block {
  position: absolute;
  background: rgba(0, 0, 0, 0.72);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(0, 255, 102, 0.18);
  padding: 10px 14px;
  font-family: 'Roboto Mono', 'VT323', monospace;
  font-size: 10px;
  color: #00ff66;
  letter-spacing: 0.07em;
  pointer-events: auto;
}

/* Corner reticle pseudo-elements */
.corner-reticle::before,
.corner-reticle::after {
  content: '';
  position: absolute;
  width: 6px;
  height: 6px;
  border-color: rgba(0, 255, 102, 0.5);
  border-style: solid;
}
.corner-reticle::before {
  top: -1px;
  left: -1px;
  border-width: 1px 0 0 1px;
}
.corner-reticle::after {
  bottom: -1px;
  right: -1px;
  border-width: 0 1px 1px 0;
}

/* ── Positions ────────────────────────────────────────────────────────── */
.hud-topleft  { top: 12px; left: 12px; min-width: 300px; }
.hud-topright { top: 12px; right: 12px; }
.hud-botleft  { bottom: 12px; left: 12px; min-width: 200px; }
.hud-botright { bottom: 12px; right: 12px; min-width: 210px; }

.hud-clinical {
  top: 75px;
  right: 12px;
  min-width: 220px;
  border-color: rgba(255, 176, 0, 0.25);
  background: rgba(10, 5, 0, 0.85);
}

.matrix-desc {
  font-size: 8px;
  color: rgba(0, 255, 102, 0.7);
  margin-top: -2px;
  margin-bottom: 6px;
  padding-left: 10px;
  white-space: normal;
  max-width: 200px;
  line-height: 1.2;
}

/* ── Title ────────────────────────────────────────────────────────────── */
.hud-title {
  font-size: 9px;
  font-weight: bold;
  letter-spacing: 0.12em;
  color: #00ff66;
  text-shadow: 0 0 8px rgba(0, 255, 102, 0.8);
  margin-bottom: 6px;
}

.hud-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 8px;
  color: rgba(0, 255, 102, 0.6);
}

.status-dot { font-size: 8px; animation: dot-blink 1.5s step-end infinite; }
@keyframes dot-blink { 50% { opacity: 0.3; } }

.mode-tag { color: #00ff66; font-weight: bold; }
.sep { color: rgba(0, 255, 102, 0.3); }
.fps-val { color: #ffb000; }
.ts-val  { color: rgba(0, 255, 102, 0.5); }

/* ── Alert chip ──────────────────────────────────────────────────────── */
.alert-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 2px;
  font-size: 10px;
  font-weight: bold;
  letter-spacing: 0.15em;
  border: 1px solid;
}
.alert-normal   { color: #00ff66; border-color: rgba(0, 255, 102, 0.4); background: rgba(0, 255, 102, 0.06); }
.alert-warning  { color: #ffb000; border-color: rgba(255, 176, 0, 0.5); background: rgba(255, 176, 0, 0.08); animation: warn-pulse 1s ease-in-out infinite; }
.alert-critical { color: #ff3333; border-color: rgba(255, 51, 51, 0.6); background: rgba(255, 51, 51, 0.12); animation: crit-pulse 0.5s step-end infinite; }
@keyframes warn-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
@keyframes crit-pulse { 50% { opacity: 0.4; } }

/* ── Coordinate matrix ───────────────────────────────────────────────── */
.matrix-header {
  font-size: 8px;
  color: rgba(0, 255, 102, 0.5);
  letter-spacing: 0.1em;
  margin-bottom: 8px;
  border-bottom: 1px solid rgba(0, 255, 102, 0.1);
  padding-bottom: 4px;
}

.matrix-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.axis-x    { color: #00ff66; font-weight: bold; min-width: 14px; text-shadow: 0 0 6px rgba(0, 255, 102, 0.9); }
.axis-y    { color: #00ff66; font-weight: bold; min-width: 14px; text-shadow: 0 0 6px rgba(0, 255, 102, 0.9); }
.axis-z    { color: #ffb000; font-weight: bold; min-width: 14px; text-shadow: 0 0 6px rgba(255, 176, 0, 0.9); }
.axis-label { color: rgba(0, 255, 102, 0.55); font-size: 8px; min-width: 55px; }
.axis-bar  { color: rgba(0, 255, 102, 0.2); font-size: 8px; }

.coord-val {
  font-family: 'VT323', 'Roboto Mono', monospace;
  font-size: 13px;
  color: #00ff66;
  text-shadow: 0 0 10px rgba(0, 255, 102, 0.8);
  min-width: 70px;
  text-align: right;
}

.text-orange { color: #ffb000 !important; text-shadow: 0 0 8px rgba(255, 176, 0, 0.7) !important; }
.text-green  { color: #00ff66 !important; text-shadow: 0 0 8px rgba(0, 255, 102, 0.7) !important; }
.text-red    { color: #ff3333 !important; text-shadow: 0 0 8px rgba(255, 51, 51, 0.8) !important; }

.unit {
  color: rgba(0, 255, 102, 0.4);
  font-size: 8px;
}

.matrix-divider {
  border-top: 1px dashed rgba(0, 255, 102, 0.1);
  margin: 6px 0;
}

/* ── Control buttons ─────────────────────────────────────────────────── */
.ctrl-btns {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.ctrl-btn {
  flex: 1;
  padding: 5px 0;
  background: rgba(0, 255, 102, 0.04);
  border: 1px solid rgba(0, 255, 102, 0.25);
  color: #00ff66;
  font-family: 'Roboto Mono', monospace;
  font-size: 8px;
  letter-spacing: 0.08em;
  cursor: pointer;
  border-radius: 2px;
  transition: all 0.15s ease;
}
.ctrl-btn:hover { background: rgba(0, 255, 102, 0.12); box-shadow: 0 0 6px rgba(0, 255, 102, 0.3); }

.reset-btn { color: rgba(0, 255, 102, 0.5); }
.reset-btn:hover { color: #00ff66; }

/* ── Crosshair ───────────────────────────────────────────────────────── */
.hud-crosshair {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 24px;
  height: 24px;
  pointer-events: none;
}
.ch-h {
  position: absolute;
  top: 50%; left: 0; right: 0;
  height: 1px;
  background: rgba(0, 255, 102, 0.2);
}
.ch-v {
  position: absolute;
  left: 50%; top: 0; bottom: 0;
  width: 1px;
  background: rgba(0, 255, 102, 0.2);
}
.ch-dot {
  position: absolute;
  top: 50%; left: 50%;
  width: 3px; height: 3px;
  background: rgba(0, 255, 102, 0.5);
  transform: translate(-50%, -50%);
  border-radius: 50%;
}
</style>
