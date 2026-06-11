<template>
  <div class="kinematics-widget">
    <!-- WIDGET CONTAINER -->
    <div class="widget-frame">
      <!-- HEADER -->
      <div class="widget-header">
        <span class="label-upper">KINEMATICS & ENVIRONMENT</span>
      </div>

      <!-- ENVIRONMENT SECTION -->
      <div class="section-container">
        <div class="section-title">ENVIRONMENTAL</div>
        <div class="env-grid">
          <!-- LIGHT INTENSITY -->
          <div class="env-metric">
            <div class="env-label">AMBIENT LIGHT</div>
            <div class="env-value">
              <span>{{ formatNumber(telemetry.light) }}</span>
              <span class="env-unit">lx</span>
            </div>
            <div class="env-bar">
              <div
                class="bar-fill"
                :style="{ width: `${Math.min((telemetry.light / 5000) * 100, 100)}%` }"
              />
            </div>
          </div>

          <!-- ATMOSPHERIC PRESSURE -->
          <div class="env-metric">
            <div class="env-label">PRESSURE</div>
            <div class="env-value">
              <span>{{ formatNumber(telemetry.pressure, 1) }}</span>
              <span class="env-unit">hPa</span>
            </div>
            <div class="env-bar">
              <div
                class="bar-fill"
                :style="{ width: `${Math.max(Math.min(((telemetry.pressure - 950) / 75) * 100, 100), 0)}%` }"
              />
            </div>
          </div>

          <!-- PRESSURE DELTA (if available) -->
          <div v-if="telemetry.pressureDelta !== undefined" class="env-metric">
            <div class="env-label">PRESSURE DELTA</div>
            <div class="env-value">
              <span :style="{ color: telemetry.pressureDelta < 0 ? '#FF3333' : '#00FF66' }">
                {{ formatNumber(telemetry.pressureDelta, 2) }}
              </span>
              <span class="env-unit">hPa</span>
            </div>
          </div>
        </div>
      </div>

      <!-- IMU SECTION -->
      <div class="section-container">
        <div class="section-title">ORIENTATION (9-DOF)</div>
        <div class="imu-grid">
          <!-- YAW ANGLE -->
          <div class="imu-metric">
            <div class="imu-label">HEADING</div>
            <div class="imu-value">{{ formatNumber(telemetry.yaw, 1) }}°</div>
            <div class="compass-dial">
              <div
                class="compass-needle"
                :style="{ transform: `rotate(${telemetry.yaw}deg)` }"
              />
              <div class="compass-center" />
            </div>
          </div>

          <!-- PITCH -->
          <div v-if="telemetry.pitch !== undefined" class="imu-metric">
            <div class="imu-label">PITCH</div>
            <div class="imu-value">{{ formatNumber(telemetry.pitch, 1) }}°</div>
          </div>

          <!-- ROLL -->
          <div v-if="telemetry.roll !== undefined" class="imu-metric">
            <div class="imu-label">ROLL</div>
            <div class="imu-value">{{ formatNumber(telemetry.roll, 1) }}°</div>
          </div>
        </div>
      </div>

      <!-- ACCELEROMETER RAW DATA SECTION -->
      <div class="section-container">
        <div class="section-title">ACCELEROMETER (RAW)</div>
        <div class="accel-container">
          <div class="accel-vector">
            <div class="axis-display">
              <span class="axis-label">X:</span>
              <span class="axis-value" :style="{ color: getAxisColor(telemetry.rawAccel.x, 'x') }">
                {{ formatNumber(telemetry.rawAccel.x, 2) }}
              </span>
              <span class="axis-unit">m/s²</span>
            </div>
            <div class="axis-display">
              <span class="axis-label">Y:</span>
              <span class="axis-value" :style="{ color: getAxisColor(telemetry.rawAccel.y, 'y') }">
                {{ formatNumber(telemetry.rawAccel.y, 2) }}
              </span>
              <span class="axis-unit">m/s²</span>
            </div>
            <div class="axis-display">
              <span class="axis-label">Z:</span>
              <span class="axis-value" :style="{ color: getAxisColor(telemetry.rawAccel.z, 'z') }">
                {{ formatNumber(telemetry.rawAccel.z, 2) }}
              </span>
              <span class="axis-unit">m/s²</span>
            </div>
          </div>

          <!-- G-FORCE MAGNITUDE -->
          <div class="gmag-display">
            <div class="gmag-label">G-MAGNITUDE</div>
            <div class="gmag-value">{{ formatNumber(calculateGMagnitude(), 2) }}</div>
            <div class="gmag-bar">
              <div
                class="bar-fill"
                :style="{ 
                  width: `${Math.min((calculateGMagnitude() / 30) * 100, 100)}%`,
                  backgroundColor: getGMagnitudeColor()
                }"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- CANVAS WAVEFORM (60 FPS ticker) -->
      <div class="canvas-container">
        <canvas
          ref="waveformCanvas"
          class="waveform-canvas"
          width="100%"
          height="100"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import type { RobotTelemetry, WidgetTheme } from './types';
import { BAYMAX_THEME } from './types';

interface Props {
  telemetry: RobotTelemetry;
  theme?: WidgetTheme;
}

const props = withDefaults(defineProps<Props>(), {
  theme: () => BAYMAX_THEME
});

const waveformCanvas = ref<HTMLCanvasElement | null>(null);
const waveformHistory = ref<number[]>([]);
let animationFrameId: number | null = null;

const themeConfig = computed(() => props.theme);

// Format number utility
function formatNumber(value: number, decimals: number = 0): string {
  if (decimals === 0) {
    return Math.round(value).toString().padStart(3, ' ');
  }
  return value.toFixed(decimals).padStart(6, ' ');
}

function calculateGMagnitude(): number {
  const { x, y, z } = props.telemetry.rawAccel;
  return Math.sqrt(x * x + y * y + z * z);
}

function getAxisColor(value: number, axis: string): string {
  const absVal = Math.abs(value);
  if (absVal > 20) return themeConfig.value.dangerRed;
  if (absVal > 10) return themeConfig.value.warningOrange;
  return '#00FF66';
}

function getGMagnitudeColor(): string {
  const mag = calculateGMagnitude();
  if (mag > 25) return themeConfig.value.dangerRed;
  if (mag > 15) return themeConfig.value.warningOrange;
  return '#00FF66';
}

function drawWaveform() {
  const canvas = waveformCanvas.value;
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  // Update history
  waveformHistory.value.push(calculateGMagnitude());
  if (waveformHistory.value.length > 120) {
    waveformHistory.value.shift();
  }

  // Clear canvas
  ctx.fillStyle = '#000000';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  // Draw grid
  ctx.strokeStyle = 'rgba(0, 255, 102, 0.1)';
  ctx.lineWidth = 0.5;
  for (let i = 0; i <= 10; i++) {
    const y = (canvas.height / 10) * i;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(canvas.width, y);
    ctx.stroke();
  }

  // Draw waveform
  ctx.strokeStyle = '#00FF66';
  ctx.lineWidth = 1.5;
  ctx.beginPath();

  waveformHistory.value.forEach((value, idx) => {
    const x = (idx / 120) * canvas.width;
    const y = canvas.height - ((value / 30) * canvas.height);
    if (idx === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });

  ctx.stroke();

  // Draw reference line (9.81 m/s² - gravity)
  ctx.strokeStyle = 'rgba(0, 255, 102, 0.4)';
  ctx.lineWidth = 0.5;
  const gravityY = canvas.height - ((9.81 / 30) * canvas.height);
  ctx.beginPath();
  ctx.moveTo(0, gravityY);
  ctx.lineTo(canvas.width, gravityY);
  ctx.stroke();

  animationFrameId = requestAnimationFrame(drawWaveform);
}

onMounted(() => {
  if (waveformCanvas.value) {
    waveformCanvas.value.width = waveformCanvas.value.offsetWidth;
    drawWaveform();
  }
});

onUnmounted(() => {
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId);
  }
});
</script>

<style scoped>
.kinematics-widget {
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
}

.widget-header {
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

.section-container {
  margin-bottom: 16px;
}

.section-title {
  font-size: 8px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: #00FF66;
  font-weight: 600;
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(0, 255, 102, 0.2);
}

.env-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.env-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.env-label {
  font-size: 7px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #00FF66;
}

.env-value {
  display: flex;
  align-items: baseline;
  gap: 2px;
  font-size: 12px;
  font-family: 'VT323', monospace;
  color: #F0F8FF;
}

.env-unit {
  font-size: 7px;
  color: #00FF66;
}

.env-bar {
  height: 4px;
  background-color: rgba(0, 255, 102, 0.15);
  border: 0.5px solid rgba(0, 255, 102, 0.2);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background-color: #00FF66;
  transition: width 0.3s ease;
}

.imu-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.imu-metric {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.imu-label {
  font-size: 7px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #00FF66;
}

.imu-value {
  font-size: 14px;
  font-family: 'VT323', monospace;
  color: #F0F8FF;
  letter-spacing: 1px;
}

.compass-dial {
  position: relative;
  width: 40px;
  height: 40px;
  border: 1px solid #00FF66;
  border-radius: 50%;
  background-color: rgba(0, 255, 102, 0.05);
  margin-top: 4px;
}

.compass-needle {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 2px;
  height: 12px;
  background-color: #FF6600;
  transform-origin: 50% 0;
  margin-left: -1px;
  margin-top: -6px;
  transition: transform 0.2s ease;
}

.compass-center {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 4px;
  height: 4px;
  background-color: #00FF66;
  border-radius: 50%;
  margin-left: -2px;
  margin-top: -2px;
}

.accel-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.accel-vector {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.axis-display {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.axis-label {
  width: 16px;
  color: #00FF66;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.axis-value {
  font-family: 'VT323', monospace;
  flex: 0 0 60px;
}

.axis-unit {
  font-size: 7px;
  color: #00FF66;
}

.gmag-display {
  border-top: 1px solid rgba(0, 255, 102, 0.2);
  padding-top: 8px;
}

.gmag-label {
  font-size: 7px;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #00FF66;
  margin-bottom: 4px;
}

.gmag-value {
  font-size: 16px;
  font-family: 'VT323', monospace;
  color: #F0F8FF;
  margin-bottom: 4px;
}

.gmag-bar {
  height: 6px;
  background-color: rgba(0, 255, 102, 0.15);
  border: 0.5px solid rgba(0, 255, 102, 0.2);
  overflow: hidden;
}

.canvas-container {
  margin-top: 12px;
  border-top: 1px solid rgba(0, 255, 102, 0.2);
  padding-top: 8px;
}

.waveform-canvas {
  width: 100%;
  height: 100px;
  border: 1px solid rgba(0, 255, 102, 0.2);
  background-color: #000000;
  display: block;
}
</style>
