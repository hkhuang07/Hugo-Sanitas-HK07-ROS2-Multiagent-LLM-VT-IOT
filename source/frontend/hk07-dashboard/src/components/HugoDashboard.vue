<template>
  <div class="hugo-dashboard">
    <!-- SCANLINES OVERLAY (Subtle) -->
    <div class="scanlines-overlay" />

    <!-- MAIN DASHBOARD LAYOUT -->
    <div class="dashboard-container">
      <!-- TOP SECTION: Bio-Telemetry -->
      <div class="dashboard-section">
        <BioTelemetryWidget :telemetry="currentTelemetry" />
      </div>

      <!-- MIDDLE SECTION: Holographic Twin Viewport -->
      <div class="dashboard-section full-width">
        <HolographicTwin :telemetry="currentTelemetry" />
      </div>

      <!-- BOTTOM SECTION: Kinematics & Environment -->
      <div class="dashboard-section">
        <KinematicsWidget :telemetry="currentTelemetry" />
      </div>
    </div>

    <!-- CONNECTION STATUS BAR -->
    <div class="status-bar">
      <div class="status-item">
        <span class="status-indicator" :style="{ backgroundColor: isConnected ? '#00FF66' : '#FF3333' }" />
        <span class="status-text">{{ isConnected ? 'MQTT CONNECTED' : 'MQTT DISCONNECTED' }}</span>
      </div>
      <div class="status-item">
        <span class="timestamp">{{ formattedTimestamp }}</span>
      </div>
      <div class="status-item">
        <span class="latency">LATENCY: {{ latencyMs }}ms</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import BioTelemetryWidget from './telemetry/BioTelemetryWidget.vue';
import KinematicsWidget from './telemetry/KinematicsWidget.vue';
import HolographicTwin from './telemetry/HolographicTwin.vue';
import type { RobotTelemetry } from './telemetry/types';

// Mock telemetry data (replace with WebSocket/HTTP in production)
const currentTelemetry = ref<RobotTelemetry>({
  messageId: 'msg-001',
  sessionId: 'session-hugo-001',
  deviceId: 'wristband-sim-001',
  hr: 72,
  spO2: 98.5,
  light: 450,
  pressure: 1013.25,
  pressureDelta: 0.0,
  yaw: 45.2,
  pitch: 12.5,
  roll: -8.3,
  fallState: false,
  fallConfidence: 0.0,
  gForceMagnitude: 9.81,
  rawAccel: { x: 0.1, y: 0.2, z: 9.81, magnitude: 9.81 },
  sensorStatus: { hrValid: true, spo2Valid: true, lightValid: true, pressureValid: true, yawValid: true, accelValid: true },
  timestamp: Date.now()
});

const isConnected = ref(true);
const latencyMs = ref(24);

const formattedTimestamp = computed(() => {
  const now = new Date(currentTelemetry.value.timestamp);
  return now.toLocaleTimeString();
});

// Simulate telemetry updates
let updateInterval: number | null = null;

function generateMockTelemetry() {
  const time = Date.now() / 1000;
  const accelX = Math.sin(time * 0.5) * 2;
  const accelY = Math.cos(time * 0.3) * 1.5;
  const accelZ = 9.81 + Math.sin(time * 0.7) * 0.5;

  const gMag = Math.sqrt(accelX * accelX + accelY * accelY + accelZ * accelZ);

  // Random fall event (5% chance per update)
  const fallDetected = Math.random() < 0.05;

  currentTelemetry.value = {
    ...currentTelemetry.value,
    hr: 70 + Math.sin(time * 0.3) * 10,
    spO2: 97 + Math.cos(time * 0.2) * 1.5,
    light: 400 + Math.sin(time * 0.1) * 100,
    pressure: 1013.25 + Math.cos(time * 0.05) * 0.5,
    pressureDelta: Math.sin(time * 0.04) * 2,
    yaw: (time * 20) % 360,
    pitch: Math.sin(time * 0.2) * 20,
    roll: Math.cos(time * 0.15) * 15,
    fallState: fallDetected || (gMag > 25),
    fallConfidence: fallDetected ? 0.95 : 0.0,
    gForceMagnitude: gMag,
    rawAccel: { x: accelX, y: accelY, z: accelZ, magnitude: gMag },
    sensorStatus: { hrValid: true, spo2Valid: true, lightValid: true, pressureValid: true, yawValid: true, accelValid: true },
    timestamp: Date.now()
  };

  // Simulate latency
  latencyMs.value = Math.floor(Math.random() * 50) + 10;
}

onMounted(() => {
  // Start periodic telemetry updates (30 FPS equivalent)
  updateInterval = window.setInterval(generateMockTelemetry, 33);
});

onUnmounted(() => {
  if (updateInterval !== null) {
    window.clearInterval(updateInterval);
  }
});
</script>

<style scoped>
.hugo-dashboard {
  position: relative;
  min-height: 100vh;
  background-color: #000000;
  color: #F0F8FF;
  font-family: 'Share Tech Mono', monospace;
  overflow: hidden;
}

.scanlines-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: linear-gradient(
    0deg,
    transparent 24%,
    rgba(0, 255, 204, 0.02) 25%,
    rgba(0, 255, 204, 0.02) 26%,
    transparent 27%,
    transparent 74%,
    rgba(0, 255, 204, 0.02) 75%,
    rgba(0, 255, 204, 0.02) 76%,
    transparent 77%,
    transparent
  );
  background-size: 100% 4px;
  pointer-events: none;
  z-index: 1;
}

.dashboard-container {
  position: relative;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
  max-width: 1600px;
  margin: 0 auto;
}

.dashboard-section {
  animation: fade-in 0.6s ease-out;
}

.dashboard-section.full-width {
  width: 100%;
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.status-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 32px;
  padding: 0 16px;
  background-color: rgba(0, 0, 0, 0.9);
  border-top: 1px solid rgba(0, 255, 204, 0.3);
  font-size: 9px;
  letter-spacing: 0.5px;
  z-index: 100;
}

.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.status-indicator {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  animation: blink-status 1.2s infinite;
}

@keyframes blink-status {
  0%, 49%, 100% {
    opacity: 1;
  }
  50%, 99% {
    opacity: 0.5;
  }
}

.status-text {
  color: #F0F8FF;
  text-transform: uppercase;
}

.timestamp {
  color: #00FFCC;
  font-family: 'VT323', monospace;
  letter-spacing: 1px;
}

.latency {
  color: #F0F8FF;
  font-family: 'VT323', monospace;
  letter-spacing: 1px;
}

/* Responsive adjustments */
@media (max-width: 1200px) {
  .dashboard-container {
    gap: 12px;
    padding: 12px;
  }
}

@media (max-width: 768px) {
  .dashboard-container {
    gap: 8px;
    padding: 8px;
  }

  .status-bar {
    flex-direction: column;
    height: auto;
    gap: 4px;
    padding: 8px;
  }
}
</style>
