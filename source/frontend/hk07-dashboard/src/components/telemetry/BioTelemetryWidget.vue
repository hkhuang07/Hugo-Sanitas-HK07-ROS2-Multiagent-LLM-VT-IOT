<template>
  <div class="bio-telemetry-widget">
    <!-- WIDGET CONTAINER -->
    <div
      class="widget-frame"
      :style="{ borderColor: sensorAlertActive ? themeConfig.warningOrange : '#00FF66' }"
    >
      <!-- HEADER LABEL -->
      <div class="widget-header">
        <span class="label-upper">BIO-TELEMETRY STREAM</span>
        <span
          v-if="sensorAlertActive && telemetry.sensorStatus.hrValid"
          class="alert-badge"
          :style="{ backgroundColor: themeConfig.warningOrange, color: '#000000' }"
        >
          [WARNING: SENSOR_NULL - SAFE_DEFAULT_ENGAGED]
        </span>
      </div>

      <!-- IF DISCONNECTED / OFFLINE -->
      <div v-if="!telemetry.sensorStatus.hrValid" class="no-signal-container">
        <div class="glow-alert blink-fast">[ NO TELEMETRY SIGNAL ]</div>
        <div class="no-signal-sub">AWAITING WRISTBAND PAIRING</div>
        <div class="sensor-matrix-dots">
          <span class="dot-active"></span>
          <span class="dot-active"></span>
          <span class="dot-active"></span>
        </div>
      </div>

      <!-- METRICS GRID -->
      <div v-else class="metrics-container">
        <!-- HEART RATE METRIC -->
        <div class="metric-block">
          <div class="metric-label">HEART RATE</div>
          <div class="metric-display">
            <span class="metric-value">{{ formatNumber(telemetry.hr) }}</span>
            <span class="metric-unit">BPM</span>
          </div>
          <div class="progress-bar-segmented">
            <div
              v-for="(segment, idx) in generateSegments(telemetry.hr, 200)"
              :key="`hr-seg-${idx}`"
              class="segment"
              :style="{ backgroundColor: getSegmentColor(telemetry.hr, 200) }"
            />
          </div>
          <div class="metric-sub">{{ hrStatus }}</div>
        </div>

        <!-- SPO2 METRIC -->
        <div class="metric-block">
          <div class="metric-label">OXYGEN SAT.</div>
          <div class="metric-display">
            <span class="metric-value">{{ formatNumber(telemetry.spO2) }}</span>
            <span class="metric-unit">%</span>
          </div>
          <div class="progress-bar-segmented">
            <div
              v-for="(segment, idx) in generateSegments(telemetry.spO2, 100)"
              :key="`spo2-seg-${idx}`"
              class="segment"
              :style="{ backgroundColor: getSegmentColor(telemetry.spO2, 100) }"
            />
          </div>
          <div class="metric-sub">{{ spo2Status }}</div>
        </div>
      </div>

      <!-- SENSOR STATUS INDICATOR -->
      <div class="sensor-status-row">
        <div
          class="status-indicator"
          :style="{ backgroundColor: telemetry.sensorStatus.hrValid ? '#00FF66' : '#FF3333' }"
        />
        <span class="status-text">{{ telemetry.sensorStatus.hrValid ? 'HR SENSOR ACTIVE' : 'HR SENSOR OFFLINE' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { RobotTelemetry, WidgetTheme } from './types';
import { BAYMAX_THEME } from './types';

interface Props {
  telemetry: RobotTelemetry;
  theme?: WidgetTheme;
}

const props = withDefaults(defineProps<Props>(), {
  theme: () => BAYMAX_THEME
});

const themeConfig = computed(() => props.theme);

// Alert state when HR sensor is invalid
const sensorAlertActive = computed(() => !props.telemetry.sensorStatus.hrValid);

// Status text
const hrStatus = computed(() => {
  if (props.telemetry.hr < 60) return 'BRADYCARDIA';
  if (props.telemetry.hr > 100) return 'TACHYCARDIA';
  return 'NOMINAL';
});

const spo2Status = computed(() => {
  if (props.telemetry.spO2 < 95) return 'LOW_O2';
  if (props.telemetry.spO2 > 99) return 'OPTIMAL';
  return 'NORMAL';
});

// Formatting utility
function formatNumber(value: number): string {
  return Math.round(value).toString().padStart(3, ' ');
}

// Generate segments for vertical progress bar
function generateSegments(value: number, max: number): number[] {
  const segmentCount = 16;
  const filledSegments = Math.ceil((value / max) * segmentCount);
  return Array.from({ length: segmentCount }, (_, i) => i < filledSegments ? 1 : 0);
}

// Color based on threshold
function getSegmentColor(value: number, max: number): string {
  const ratio = value / max;
  if (ratio < 0.5) return themeConfig.value.dangerRed;
  if (ratio < 0.75) return themeConfig.value.warningOrange;
  return '#00FF66';
}
</script>

<style scoped>
.bio-telemetry-widget {
  font-family: 'Share Tech Mono', monospace;
  background-color: #000000;
  color: #F0F8FF;
}

.widget-frame {
  border: 1px solid #00FF66;
  border-radius: 0;
  padding: 12px;
  background-color: #000000;
  box-shadow: inset 0 0 8px rgba(0, 255, 102, 0.1), 0 0 12px rgba(0, 255, 102, 0.15);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.widget-frame:has(.alert-badge) {
  border-color: #FF6600;
  box-shadow: inset 0 0 8px rgba(255, 102, 0, 0.2), 0 0 12px rgba(255, 102, 0, 0.25);
}

.widget-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(0, 255, 102, 0.3);
}

.label-upper {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: #F0F8FF;
}

.alert-badge {
  font-size: 9px;
  padding: 4px 8px;
  border-radius: 2px;
  letter-spacing: 1px;
  animation: pulse-alert 0.6s infinite;
}

@keyframes pulse-alert {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.no-signal-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 90px;
  border: 1px dashed rgba(0, 255, 102, 0.25);
  margin-bottom: 16px;
  background: rgba(0, 255, 102, 0.03);
}

.glow-alert {
  font-size: 11px;
  font-weight: bold;
  letter-spacing: 1.5px;
  color: #FF3333;
  text-shadow: 0 0 8px rgba(255, 51, 51, 0.6);
}

.blink-fast {
  animation: blink-fast-anim 1s step-end infinite;
}

@keyframes blink-fast-anim {
  50% { opacity: 0.2; }
}

.no-signal-sub {
  font-size: 8px;
  color: #888888;
  letter-spacing: 1px;
  margin-top: 4px;
}

.sensor-matrix-dots {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.sensor-matrix-dots span {
  width: 4px;
  height: 4px;
  background-color: rgba(0, 255, 102, 0.15);
  border-radius: 50%;
}

.sensor-matrix-dots span.dot-active {
  animation: pulse-dot 1.5s infinite;
}

.sensor-matrix-dots span:nth-child(2) {
  animation-delay: 0.5s;
}

.sensor-matrix-dots span:nth-child(3) {
  animation-delay: 1s;
}

@keyframes pulse-dot {
  0%, 100% { background-color: rgba(0, 255, 102, 0.15); }
  50% { background-color: #00FF66; box-shadow: 0 0 6px #00FF66; }
}

.metrics-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

.metric-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.metric-label {
  font-size: 8px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: #00FF66;
  font-weight: 600;
}

.metric-display {
  display: flex;
  align-items: baseline;
  gap: 4px;
}

.metric-value {
  font-size: 20px;
  font-family: 'VT323', monospace;
  font-weight: 700;
  color: #F0F8FF;
  letter-spacing: 2px;
}

.metric-unit {
  font-size: 9px;
  color: #00FF66;
  letter-spacing: 0.5px;
}

.progress-bar-segmented {
  display: flex;
  flex-direction: column;
  gap: 2px;
  height: 48px;
}

.segment {
  flex: 1;
  width: 100%;
  border: 0.5px solid rgba(0, 255, 102, 0.2);
  border-radius: 1px;
  background-color: rgba(0, 255, 102, 0.15);
  transition: background-color 0.2s ease;
}

.metric-sub {
  font-size: 8px;
  color: #00FF66;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.sensor-status-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 255, 102, 0.2);
}

.status-indicator {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  animation: blink-status 1.2s infinite;
}

@keyframes blink-status {
  0%, 49%, 100% {
    opacity: 1;
  }
  50%, 99% {
    opacity: 0.4;
  }
}

.status-text {
  font-size: 8px;
  letter-spacing: 1px;
  text-transform: uppercase;
}
</style>
