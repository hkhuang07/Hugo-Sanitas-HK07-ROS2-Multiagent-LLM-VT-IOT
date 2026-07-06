<template>
  <div class="sensor-view">
    <!-- Cinematic HUD Terminal Loader -->
    <div v-if="cfg.isConfigLoading" class="hud-terminal-loader">
      <span class="loader-text font-mono">[ CRITICAL_SYSTEM_UPLINK: FETCHING_ENV_METRICS... ]</span>
    </div>

    <!-- ═══ RETICLE CORNERS ═══ -->
    <span class="corner tl">+</span>
    <span class="corner tr">+</span>
    <span class="corner bl">+</span>
    <span class="corner br">+</span>

    <!-- ═══ PAGE HEADER ═══ -->
    <header class="sv-header">
      <div class="sv-header-left">
        <div class="sv-title-block">
          <span class="sv-label">[ HK-07 // SENSOR TELEMETRY ]</span>
          <h1 class="sv-title"> HUGO SANITAS HK-07 SENSOR HUD</h1>
          <span class="sv-sub">{{ deviceLabel }} · HOST: {{ cfg.pcIp }}:{{ cfg.sensorPort }} · {{ packetRate }} PKT/S · LATENCY {{ latency }}MS</span>
        </div>
      </div>
      <div class="sv-header-right">
        <DeviceIpConfigModal />
        <div class="sv-live-badge" :class="streamStatus === 'LIVE' ? 'badge-live' : streamStatus === 'SIMULATED' ? 'badge-simulated' : 'badge-offline'">
          <span class="pulse-dot" v-if="isActive(streamStatus)"></span>
          {{ streamStatus === 'LIVE' ? '◈ STREAMING' : streamStatus === 'SIMULATED' ? '◈ SIMULATED' : '○ OFFLINE' }}
        </div>
        <div class="sv-timestamp">{{ currentTime }}</div>
      </div>
    </header>

    <!-- ═══ SENSOR STATUS STRIP ═══ -->
    <div class="sensor-strip">
      <div v-for="s in sensorBadges" :key="s.key" class="sensor-badge" :class="`badge-${s.status.toLowerCase()}`">
        <span class="badge-icon">{{ s.icon }}</span>
        <span class="badge-name">{{ s.name }}</span>
        <span class="badge-state">{{ s.status }}</span>
      </div>
    </div>

    <!-- 1. ENVIRONMENT METRICS (top 100%) -->
    <div class="sv-panel env-stats-panel full-width" style="margin-bottom: 16px;">
      <div class="panel-header">
        <span class="panel-tag">[ ENVIRONMENT METRICS ]</span>
        <span class="panel-status" :class="sensorStore.envStatus.toLowerCase()">{{ sensorStore.envStatus }}</span>
      </div>
      <div class="stat-row">
        <div class="stat-card" :class="lightClass">
          <span class="stat-icon">☀</span>
          <span class="stat-val">{{ isActive(sensorStore.envStatus) ? safeToFixed(sensorStore.environment?.ambient_light, 0, 'OFFLINE') : 'OFFLINE' }}</span>
          <span class="stat-unit" v-if="isActive(sensorStore.envStatus)">LUX</span>
          <span class="stat-name">AMBIENT LIGHT</span>
        </div>
        <!-- BAROMETER: Show 'NO HW' badge when phone has no barometer sensor -->
        <div class="stat-card" :class="sensorStore.environment.barometric_pressure === null ? 'card-warn' : ''">
          <span class="stat-icon">⟁</span>
          <span class="stat-val" :class="sensorStore.environment.barometric_pressure === null ? 'text-warn' : ''">
            {{ sensorStore.environment.barometric_pressure === null
              ? 'NO HW'
              : isActive(sensorStore.envStatus) ? safeToFixed(sensorStore.environment.barometric_pressure, 1, 'OFFLINE') : 'OFFLINE' }}
          </span>
          <span class="stat-unit" v-if="isActive(sensorStore.envStatus) && sensorStore.environment.barometric_pressure !== null">hPa</span>
          <span class="stat-name">BAROMETER</span>
        </div>
        <!-- PRESSURE DELTA: Show 'NO HW' when barometer absent -->
        <div class="stat-card" :class="pressureDeltaClass">
          <span class="stat-icon">△</span>
          <span class="stat-val">
            {{ sensorStore.environment.pressure_delta_hpa === null
              ? 'NO HW'
              : isActive(sensorStore.envStatus)
                ? (sensorStore.environment.pressure_delta_hpa >= 0 ? '+' : '') + safeToFixed(sensorStore.environment.pressure_delta_hpa, 2, 'OFFLINE')
                : 'OFFLINE' }}
          </span>
          <span class="stat-unit" v-if="isActive(sensorStore.envStatus) && sensorStore.environment.pressure_delta_hpa !== null">ΔhPa</span>
          <span class="stat-name">PRESSURE DELTA</span>
        </div>
      </div>
    </div>

    <!-- 2. SPLIT LAYOUT FOR BATTERY, ACTIVITY (LEFT 30%) & IMU (RIGHT 70%) -->
    <div class="sv-split-layout" style="margin-bottom: 16px;">
      <!-- Left Column (30%) -->
      <div class="sv-left-col">
        <!-- SYSTEM POWER // BATTERY -->
        <div class="sv-panel battery-panel">
          <div class="panel-header">
            <span class="panel-tag">[ SYSTEM POWER // BATTERY ]</span>
            <span class="panel-status" :class="sensorStore.envStatus.toLowerCase()">{{ sensorStore.envStatus }}</span>
          </div>
          <div class="battery-stats">
            <div class="bat-level-row">
              <span class="bat-lbl">CHARGE:</span>
              <span class="bat-val" :class="isActive(sensorStore.envStatus) && sensorStore.environment.battery_level < 20 ? 'text-danger' : ''">
                {{ isActive(sensorStore.envStatus) ? safeToFixed(sensorStore.environment?.battery_level ?? 100.0, 1, '100.0') + '%' : 'OFFLINE' }}
              </span>
            </div>
            <!-- Segmented block bar -->
            <div class="bat-progress-bar font-mono text-success">
              {{ getBatteryBar(sensorStore.environment.battery_level) }}
            </div>
            <div class="bat-temp-row">
              <span class="bat-lbl">BATTERY TEMP:</span>
              <span class="bat-val" :class="isActive(sensorStore.envStatus) && sensorStore.environment.battery_temp > 45 ? 'text-danger' : ''">
                {{ isActive(sensorStore.envStatus) ? safeToFixed(sensorStore.environment?.battery_temp ?? 32.0, 1, '32.0') + '°C' : 'OFFLINE' }}
              </span>
            </div>
          </div>
        </div>

        <!-- ACTIVITY // MOTION -->
        <div class="sv-panel activity-panel">
          <div class="panel-header">
            <span class="panel-tag">[ ACTIVITY // MOTION ]</span>
            <span class="panel-status" :class="sensorStore.actStatus.toLowerCase()">{{ sensorStore.actStatus }}</span>
          </div>
          <!-- Pedometer Odometer -->
          <div class="odometer-wrap">
            <div class="odometer-label">PEDOMETER</div>
            <div class="odometer-display">
              <span v-for="(d, i) in stepDigits" :key="i" class="step-digit">{{ d }}</span>
            </div>
            <span class="odometer-unit">STEPS</span>
          </div>
          <!-- Activity Type Badge -->
          <div class="activity-type-wrap">
            <span class="activity-icon">{{ activityIcon }}</span>
            <div class="activity-label-group">
              <span class="activity-type-label">ACTIVITY STATE</span>
              <span class="activity-type-value" :class="`act-${sensorStore.activity.activity_type.toLowerCase()}`">
                {{ isActive(sensorStore.actStatus) ? sensorStore.activity.activity_type.toUpperCase() : 'OFFLINE' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column (70%) -->
      <div class="sv-right-col">
        <!-- IMU 9-DOF PANEL -->
        <div class="sv-panel imu-panel" style="height: 100%;">
          <div class="panel-header">
            <span class="panel-tag">[ IMU // 9-DOF ]</span>
            <span class="panel-status" :class="sensorStore.imuStatus.toLowerCase()">{{ sensorStore.imuStatus }}</span>
          </div>

          <!-- Orientation Cube Visualizer -->
          <div class="orientation-wrap">
            <div class="cube-scene">
              <div class="cube" :style="cubeStyle">
                <div class="face front">FRONT</div>
                <div class="face back">BACK</div>
                <div class="face left">LEFT</div>
                <div class="face right">RIGHT</div>
                <div class="face top">TOP</div>
                <div class="face bottom">BOT</div>
              </div>
            </div>
            <div class="euler-readout">
              <div class="euler-row">
                <span class="euler-label">ROLL</span>
                <span class="euler-val" :class="absVal(sensorStore.eulerAngles.roll) > 45 ? 'text-warn' : ''">
                  {{ sensorStore.eulerAngles.roll }}°
                </span>
              </div>
              <div class="euler-row">
                <span class="euler-label">PITCH</span>
                <span class="euler-val" :class="absVal(sensorStore.eulerAngles.pitch) > 45 ? 'text-warn' : ''">
                  {{ sensorStore.eulerAngles.pitch }}°
                </span>
              </div>
              <div class="euler-row">
                <span class="euler-label">YAW</span>
                <span class="euler-val">{{ sensorStore.eulerAngles.yaw }}°</span>
              </div>
            </div>
          </div>

          <!-- Compass Gauge -->
          <div class="compass-wrap">
            <svg class="compass-svg" viewBox="0 0 120 120">
              <circle cx="60" cy="60" r="55" fill="none" stroke="#00FF6622" stroke-width="1"/>
              <circle cx="60" cy="60" r="55" fill="none" stroke="#00FF66" stroke-width="1" stroke-dasharray="4 4"/>
              <text x="60" y="14" text-anchor="middle" fill="#00FF66" font-size="9" font-family="Rajdhani">N</text>
              <text x="106" y="63" text-anchor="middle" fill="#00FF6688" font-size="9" font-family="Rajdhani">E</text>
              <text x="60" y="111" text-anchor="middle" fill="#00FF6688" font-size="9" font-family="Rajdhani">S</text>
              <text x="12" y="63" text-anchor="middle" fill="#00FF6688" font-size="9" font-family="Rajdhani">W</text>
              <!-- Needle -->
              <g :transform="`rotate(${isActive(sensorStore.imuStatus) && sensorStore.imu.compass_heading !== null ? sensorStore.imu.compass_heading : 0}, 60, 60)`">
                <polygon points="60,12 57,60 63,60" fill="#FF3333"/>
                <polygon points="60,108 57,60 63,60" fill="#00FF66"/>
              </g>
              <circle cx="60" cy="60" r="4" fill="#00FF66"/>
              <text x="60" y="76" text-anchor="middle" fill="#00FF66" font-size="11" font-family="Rajdhani,monospace">
                {{ sensorStore.imu.compass_heading === null
                  ? 'NO HW'
                  : isActive(sensorStore.imuStatus)
                    ? safeToFixed(sensorStore.imu.compass_heading, 1) + '°'
                    : 'OFFLINE' }}
              </text>
            </svg>
          </div>

          <!-- Quaternion Readout -->
          <div class="quat-panel">
            <span class="panel-micro-label">QUATERNION</span>
            <div class="quat-grid">
              <div class="quat-item"><span>W</span><b>{{ isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu?.orientation?.w, 4, 'N/A') : 'N/A' }}</b></div>
              <div class="quat-item"><span>X</span><b>{{ isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu?.orientation?.x, 4, 'N/A') : 'N/A' }}</b></div>
              <div class="quat-item"><span>Y</span><b>{{ isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu?.orientation?.y, 4, 'N/A') : 'N/A' }}</b></div>
              <div class="quat-item"><span>Z</span><b>{{ isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu?.orientation?.z, 4, 'N/A') : 'N/A' }}</b></div>
            </div>
          </div>

          <!-- Magnetometer readout -->
          <div class="mag-panel">
            <span class="panel-micro-label">MAGNETOMETER (µT)</span>
            <div class="mag-grid">
              <div class="mag-item"><span>MX</span><b>{{ sensorStore.imu.magnetometer.x === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu.magnetometer.x, 2) : 'OFFLINE') }}</b></div>
              <div class="mag-item"><span>MY</span><b>{{ sensorStore.imu.magnetometer.y === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu.magnetometer.y, 2) : 'OFFLINE') }}</b></div>
              <div class="mag-item"><span>MZ</span><b>{{ sensorStore.imu.magnetometer.z === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu.magnetometer.z, 2) : 'OFFLINE') }}</b></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 3. STACKED CHARTS (100% width) -->
    <div class="charts-stack" style="margin-bottom: 16px;">
      <div class="chart-block">
        <div class="chart-label">ACCELEROMETER XYZ (m/s²)</div>
        <canvas ref="accelChartRef" class="hud-canvas"></canvas>
      </div>
      <div class="chart-block">
        <div class="chart-label">GYROSCOPE XYZ (rad/s)</div>
        <canvas ref="gyroChartRef" class="hud-canvas"></canvas>
      </div>
      <div class="chart-block">
        <div class="chart-label">AMBIENT LIGHT (lux) — 100 SAMPLE ROLLING</div>
        <canvas ref="lightChartRef" class="hud-canvas"></canvas>
      </div>
      <div class="chart-block">
        <div class="chart-label">BAROMETRIC PRESSURE TREND (hPa)</div>
        <canvas ref="pressureChartRef" class="hud-canvas"></canvas>
      </div>
      <div class="chart-block">
        <div class="chart-label">WRIST MOTION MAGNITUDE (20 READINGS)</div>
        <canvas ref="wristChartRef" class="hud-canvas"></canvas>
      </div>
      <div class="chart-block">
        <div class="chart-label">PRESSURE DELTA (ΔhPa) — FALL INDICATOR</div>
        <canvas ref="pressureDeltaChartRef" class="hud-canvas"></canvas>
      </div>
      <div class="chart-block">
        <div class="chart-label">CUMULATIVE STEP COUNT</div>
        <canvas ref="stepsChartRef" class="hud-canvas"></canvas>
      </div>
    </div>

    <!-- 4. GPS LOCATION (100% width) -->
    <!-- 4. GPS LOCATION (100% width) -->
    <div class="sv-panel gps-panel full-width" style="margin-bottom: 16px;">
      <div class="panel-header" style="margin-bottom:8px;">
        <span class="panel-tag">[ GPS // REAL-TIME FIELD POSITION ]</span>
        <span class="panel-status" :class="sensorStore.locStatus.toLowerCase()">{{ sensorStore.locStatus }}</span>
      </div>
      <div class="gps-layout">
        <div class="map-placeholder">
          <!-- Leaflet map container -->
          <div ref="mapContainer" class="real-map"></div>

          <!-- Functional HUD Overlay -->
          <div class="map-hud-overlay">
            <!-- Scan line sweep -->
            <div class="radar-scanline"></div>

            <!-- TOP-LEFT: Range scale control (hacker tactical zoom) -->
            <div class="hud-tactical-zoom font-mono">
              <div class="zoom-title">// RANGE_SCALE</div>
              <button 
                v-for="r in tacticalRanges" 
                :key="r.zoom" 
                @click="setTacticalRange(r.zoom)" 
                :class="{ active: currentZoom === r.zoom }" 
                class="zoom-btn"
              >
                [{{ r.label.toUpperCase() }}]
              </button>
              <div class="zoom-title" style="margin-top: 6px; border-top: 1px dashed rgba(0, 255, 102, 0.2); padding-top: 4px;">// CAM_TRACK</div>
              <button @click="recenterMap" :class="{ active: isTracking }" class="zoom-btn">
                [{{ isTracking ? 'LKD_CENTER' : 'FREE_CAM' }}]
              </button>
            </div>

            <!-- TOP-RIGHT: Coordinates & Status HUD -->
            <div class="coord-readout font-mono">
              <div class="coord-line">
                <span class="coord-lbl">LAT</span>
                <span class="coord-val">{{ safeToFixed(sensorStore.location?.latitude, 6, '0.000000') }}°</span>
              </div>
              <div class="coord-line">
                <span class="coord-lbl">LNG</span>
                <span class="coord-val">{{ safeToFixed(sensorStore.location?.longitude, 6, '0.000000') }}°</span>
              </div>
              <div class="coord-line">
                <span class="coord-lbl">ALT</span>
                <span class="coord-val">{{ safeToFixed(sensorStore.location?.altitude, 1, '0.0') }}<span class="coord-unit">m</span></span>
              </div>
              <div class="coord-line">
                <span class="coord-lbl">HDG</span>
                <span class="coord-val">{{ safeToFixed(sensorStore.imu?.compass_heading, 1, '000.0') }}°</span>
              </div>
              <div class="coord-line">
                <span class="coord-lbl">SCALE</span>
                <span class="coord-val">1:{{ currentZoom === 19 ? '500' : currentZoom === 18 ? '1200' : currentZoom === 17 ? '2500' : currentZoom === 16 ? '5000' : '25000' }}</span>
              </div>
              <div class="coord-line" style="margin-top: 4px; border-top: 1px dashed rgba(0, 255, 102, 0.2); padding-top: 4px;">
                <span class="coord-lbl">SIG</span>
                <span class="coord-val" :class="sensorStore.locStatus.toLowerCase()">{{ sensorStore.locStatus }}</span>
              </div>
            </div>

            <!-- Central targeting crosshair (always at center of map) -->
            <div class="map-crosshair">
              <span class="crosshair-h"></span>
              <span class="crosshair-v"></span>
              <span class="crosshair-dot"></span>
            </div>

            <!-- BOTTOM-LEFT: Telemetry console stream -->
            <div class="hud-terminal-overlay font-mono">
              <div class="term-header">// TELEMETRY_STREAM</div>
              <div v-for="(log, idx) in telemetryLogs" :key="idx" class="term-line">{{ log }}</div>
            </div>

            <!-- BOTTOM-RIGHT: Target tracking & system parameters -->
            <div class="hud-sys-parameters font-mono">
              <div class="sys-title">// UPLINK_TELEMETRY</div>
              <div class="sys-row"><span class="sys-lbl">SYS_STATE</span><span class="sys-val text-live">NOMINAL</span></div>
              <div class="sys-row"><span class="sys-lbl">DEV_ID</span><span class="sys-val">HK07_MOBILE</span></div>
              <div class="sys-row"><span class="sys-lbl">BATTERY</span><span class="sys-val">{{ safeToFixed(sensorStore.environment?.battery_level, 1, '100') }}% ({{ safeToFixed(sensorStore.environment?.battery_temp, 1, '32.0') }}°C)</span></div>
              <div class="sys-row"><span class="sys-lbl">HR_RATE</span><span class="sys-val text-danger">{{ vitalsStore.current.heartRate > 0 ? vitalsStore.current.heartRate : '72' }} BPM</span></div>
              <div class="sys-row"><span class="sys-lbl">ACTIVITY</span><span class="sys-val text-blue">{{ (sensorStore.activity?.activity_type || 'still').toUpperCase() }}</span></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ═══ STATISTICS TABLE ═══ -->
    <div class="stats-table-wrap">
      <div class="panel-header">
        <span class="panel-tag">[ SENSOR STATISTICS TABLE // ALL 13 CHANNELS ]</span>
        <button class="export-btn" @click="exportCSV">⬇ EXPORT CSV</button>
      </div>
      <table class="stats-table">
        <thead>
          <tr>
            <th>SENSOR</th>
            <th>CURRENT VALUE</th>
            <th>UNIT</th>
            <th>MIN (session)</th>
            <th>MAX (session)</th>
            <th>STATUS</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in statsTableRows" :key="row.sensor" :class="`row-${row.statusClass}`">
            <td class="cell-sensor">{{ row.sensor }}</td>
            <td class="cell-val">{{ row.current }}</td>
            <td class="cell-unit">{{ row.unit }}</td>
            <td class="cell-min">{{ row.min }}</td>
            <td class="cell-max">{{ row.max }}</td>
            <td class="cell-status">
              <span class="status-pill" :class="`pill-${row.statusClass}`">{{ row.status }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Chart, registerables } from 'chart.js'
import { useSensorTelemetryStore } from '../stores/sensorTelemetry'
import { useDeviceConfigStore } from '../stores/deviceConfig'
import { useVitalsStore } from '../stores/vitals'
import DeviceIpConfigModal from '../components/DeviceIpConfigModal.vue'

Chart.register(...registerables)

const sensorStore = useSensorTelemetryStore()
const cfg = useDeviceConfigStore()
const vitalsStore = useVitalsStore()

function isActive(status: string) {
  return status === 'LIVE' || status === 'SIMULATED'
}

function safeToFixed(val: any, decimals: number, fallback = 'OFFLINE'): string {
  if (val === undefined || val === null || isNaN(Number(val))) {
    return fallback
  }
  return Number(val).toFixed(decimals)
}

function getStatusClass(status: string, defaultClass = 'ok') {
  if (status === 'LIVE') return defaultClass
  if (status === 'SIMULATED') return 'warn'
  return 'danger'
}

const streamStatus = computed(() => {
  if (!sensorStore.isLive) return 'OFFLINE'
  return sensorStore.isImuSimulated ? 'SIMULATED' : 'LIVE'
})

// ── Time / status ─────────────────────────────────────────────────────────────
const currentTime = ref('')
const packetRate = ref(0)
const latency = ref(0)
const deviceLabel = ref('VIVO-HK07-MOBILE')
let _lastPktCount = 0
let _pktInterval: number | null = null

function updateClock() {
  currentTime.value = new Date().toLocaleTimeString('en-GB', { hour12: false })
}

// ── Sensor badge strip ────────────────────────────────────────────────────────
const heartStatus = computed(() => {
  if (vitalsStore.current.heartRate <= 0) return 'OFFLINE'
  // Always SIMULATED since phone has no built-in heart rate sensor
  return 'SIMULATED'
})

// Barometer hardware availability — null means no sensor on this device
const baroStatus = computed(() => {
  if (!isActive(sensorStore.envStatus)) return sensorStore.envStatus
  // Always SIMULATED since phone has no barometer hardware
  return 'SIMULATED'
})

// Wrist Motion hardware status
const wristStatus = computed(() => {
  if (!isActive(sensorStore.actStatus)) return sensorStore.actStatus
  // Always SIMULATED since phone has no wristband sensor (derived from accelerometer)
  return 'SIMULATED'
})

const sensorBadges = computed(() => [
  { key: 'accel',  name: 'ACCEL',    icon: '↗', status: sensorStore.imuStatus },
  { key: 'gyro',   name: 'GYRO',     icon: '⟲', status: sensorStore.imuStatus },
  { key: 'mag',    name: 'MAG',      icon: '⊕', status: sensorStore.imuStatus },
  { key: 'orient', name: 'ORIENT',   icon: '⧈', status: sensorStore.imuStatus },
  { key: 'comp',   name: 'COMPASS',  icon: '◎', status: sensorStore.imuStatus },
  { key: 'grav',   name: 'GRAVITY',  icon: '↓', status: sensorStore.imuStatus },
  { key: 'light',  name: 'LIGHT',    icon: '☀', status: sensorStore.envStatus },
  // BARO: if sensor not available → show SIMULATED (no hardware), not LIVE/OFFLINE
  { key: 'baro',   name: 'BARO',     icon: '⟁', status: baroStatus.value },
  { key: 'loc',    name: 'GPS',      icon: '◉', status: sensorStore.locStatus },
  { key: 'steps',  name: 'PEDOMETER',icon: '⊞', status: sensorStore.actStatus },
  { key: 'act',    name: 'ACTIVITY', icon: '⊿', status: sensorStore.actStatus },
  { key: 'wrist',  name: 'WRIST',    icon: '〜', status: wristStatus.value },
  { key: 'hr',     name: 'HEART',    icon: '♥', status: heartStatus.value },
])

// ── 3D Cube transform ─────────────────────────────────────────────────────────
const cubeStyle = computed(() => {
  if (!isActive(sensorStore.imuStatus)) {
    return {
      transform: 'rotateX(0deg) rotateY(0deg) rotateZ(0deg)',
      opacity: 0.2,
      transition: 'all 0.5s ease',
    }
  }
  const { roll, pitch, yaw } = sensorStore.eulerAngles
  return {
    transform: `rotateX(${-pitch}deg) rotateY(${yaw}deg) rotateZ(${roll}deg)`,
    transition: 'transform 0.1s linear',
  }
})

function absVal(v: number) { return Math.abs(v) }

function getBatteryBar(level: number | undefined) {
  if (!isActive(sensorStore.envStatus)) return '[░░░░░░░░░░]'
  const lvl = level ?? 100.0
  const blocks = Math.max(0, Math.min(10, Math.round(lvl / 10)))
  return `[${'█'.repeat(blocks)}${'░'.repeat(10 - blocks)}]`
}

// ── Light/pressure status classes ─────────────────────────────────────────────
const lightClass = computed(() => {
  if (!isActive(sensorStore.envStatus)) return 'card-danger'
  const lux = sensorStore.environment.ambient_light
  if (lux < 10) return 'card-warn'
  if (lux > 10000) return 'card-warn'
  return 'card-ok'
})

const pressureDeltaClass = computed(() => {
  if (!isActive(sensorStore.envStatus)) return 'card-danger'
  // null pressure_delta means no barometer hardware — treat as no-data (warn color)
  const delta = sensorStore.environment.pressure_delta_hpa
  if (delta === null) return 'card-warn'
  const d = Math.abs(delta)
  if (d > 5) return 'card-danger'
  if (d > 2) return 'card-warn'
  return 'card-ok'
})

// ── Activity ──────────────────────────────────────────────────────────────────
const activityIcon = computed(() => {
  if (!isActive(sensorStore.actStatus)) return '⚠'
  const t = sensorStore.activity.activity_type.toLowerCase()
  if (t.includes('run')) return '🏃'
  if (t.includes('walk')) return '🚶'
  if (t.includes('still') || t === 'stationary') return '🧍'
  if (t.includes('cycle') || t.includes('bike')) return '🚴'
  return '⊿'
})

const stepDigits = computed(() => {
  if (!isActive(sensorStore.actStatus)) return ['O', 'F', 'F', 'L', 'I', 'N', 'E']
  const s = String(sensorStore.activity.pedometer_steps).padStart(6, '0')
  return s.split('')
})

// ── Chart refs ────────────────────────────────────────────────────────────────
const accelChartRef  = ref<HTMLCanvasElement>()
const gyroChartRef   = ref<HTMLCanvasElement>()
const lightChartRef  = ref<HTMLCanvasElement>()
const pressureChartRef = ref<HTMLCanvasElement>()
const pressureDeltaChartRef = ref<HTMLCanvasElement>()
const wristChartRef  = ref<HTMLCanvasElement>()
const stepsChartRef  = ref<HTMLCanvasElement>()

let accelChart: Chart | null = null
let gyroChart: Chart | null = null
let lightChart: Chart | null = null
let pressureChart: Chart | null = null
let pressureDeltaChart: Chart | null = null
let wristChart: Chart | null = null
let stepsChart: Chart | null = null

const HUD_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 0 },
  plugins: { legend: { display: true, labels: { color: '#00FF66', font: { family: 'Rajdhani', size: 10 }, boxWidth: 12 } } },
  scales: {
    x: { display: false },
    y: {
      ticks: { color: '#00FF6699', font: { family: 'Rajdhani', size: 9 } },
      grid: { color: '#00FF6611' },
    }
  }
}

function buildLineDataset(label: string, color: string, data: number[]) {
  return {
    label,
    data,
    borderColor: color,
    backgroundColor: color + '18',
    borderWidth: 1.5,
    pointRadius: 0,
    tension: 0.3,
    fill: false,
  }
}

function buildBarDataset(label: string, color: string, data: number[]) {
  return {
    label,
    data,
    backgroundColor: color + 'AA',
    borderColor: color,
    borderWidth: 1,
  }
}

function makeLabels(count: number) {
  return Array.from({ length: count }, (_, i) => i.toString())
}

function initCharts() {
  if (!accelChartRef.value || !gyroChartRef.value) return

  // Accel chart (Line XYZ)
  accelChart = new Chart(accelChartRef.value, {
    type: 'line',
    data: {
      labels: makeLabels(sensorStore.HISTORY_SIZE),
      datasets: [
        buildLineDataset('AX', '#00FF66', []),
        buildLineDataset('AY', '#00FF66', []),
        buildLineDataset('AZ', '#FFB000', []),
      ]
    },
    options: { ...HUD_DEFAULTS } as any,
  })

  // Gyro chart (Line XYZ)
  gyroChart = new Chart(gyroChartRef.value!, {
    type: 'line',
    data: {
      labels: makeLabels(sensorStore.HISTORY_SIZE),
      datasets: [
        buildLineDataset('GX', '#FF3333', []),
        buildLineDataset('GY', '#00FF66', []),
        buildLineDataset('GZ', '#FFB000', []),
      ]
    },
    options: { ...HUD_DEFAULTS } as any,
  })

  // Light chart (Line)
  lightChart = new Chart(lightChartRef.value!, {
    type: 'line',
    data: {
      labels: makeLabels(sensorStore.HISTORY_SIZE),
      datasets: [buildLineDataset('LIGHT (lux)', '#FFB000', [])]
    },
    options: { ...HUD_DEFAULTS, scales: { ...HUD_DEFAULTS.scales, y: { ...HUD_DEFAULTS.scales.y, min: 0 } } } as any,
  })

  // Pressure bar chart
  pressureChart = new Chart(pressureChartRef.value!, {
    type: 'bar',
    data: {
      labels: makeLabels(50),
      datasets: [buildBarDataset('PRESSURE (hPa)', '#00FF66', [])]
    },
    options: {
      ...HUD_DEFAULTS,
      scales: { ...HUD_DEFAULTS.scales, y: { ...HUD_DEFAULTS.scales.y, min: 950, max: 1060 } }
    } as any,
  })

  // Pressure delta line
  pressureDeltaChart = new Chart(pressureDeltaChartRef.value!, {
    type: 'line',
    data: {
      labels: makeLabels(sensorStore.HISTORY_SIZE),
      datasets: [buildLineDataset('ΔhPa', '#FF3333', [])]
    },
    options: {
      ...HUD_DEFAULTS,
      scales: {
        x: { display: false },
        y: {
          ticks: { color: '#00FF6699', font: { family: 'Rajdhani', size: 9 } },
          grid: { color: '#FF333311' },
        }
      }
    } as any,
  })

  // Wrist motion bar
  wristChart = new Chart(wristChartRef.value!, {
    type: 'bar',
    data: {
      labels: makeLabels(50),
      datasets: [buildBarDataset('WRIST MAG', '#00FF66', [])]
    },
    options: { ...HUD_DEFAULTS, scales: { ...HUD_DEFAULTS.scales, y: { ...HUD_DEFAULTS.scales.y, min: 0 } } } as any,
  })

  // Steps line
  stepsChart = new Chart(stepsChartRef.value!, {
    type: 'line',
    data: {
      labels: makeLabels(sensorStore.HISTORY_SIZE),
      datasets: [buildLineDataset('STEPS', '#00FF66', [])]
    },
    options: { ...HUD_DEFAULTS, scales: { ...HUD_DEFAULTS.scales, y: { ...HUD_DEFAULTS.scales.y, min: 0 } } } as any,
  })
}

function updateCharts() {
  const ax = sensorStore.accelXHistory.map(p => p.value)
  const ay = sensorStore.accelYHistory.map(p => p.value)
  const az = sensorStore.accelZHistory.map(p => p.value)
  if (accelChart) {
    accelChart.data.labels = makeLabels(ax.length)
    accelChart.data.datasets[0].data = ax
    accelChart.data.datasets[1].data = ay
    accelChart.data.datasets[2].data = az
    accelChart.update('none')
  }

  const gx = sensorStore.gyroXHistory.map(p => p.value)
  const gy = sensorStore.gyroYHistory.map(p => p.value)
  const gz = sensorStore.gyroZHistory.map(p => p.value)
  if (gyroChart) {
    gyroChart.data.labels = makeLabels(gx.length)
    gyroChart.data.datasets[0].data = gx
    gyroChart.data.datasets[1].data = gy
    gyroChart.data.datasets[2].data = gz
    gyroChart.update('none')
  }

  const lux = sensorStore.lightHistory.map(p => p.value)
  if (lightChart) {
    lightChart.data.labels = makeLabels(lux.length)
    lightChart.data.datasets[0].data = lux
    lightChart.update('none')
  }

  const pres = sensorStore.pressureHistory.map(p => p.value)
  if (pressureChart) {
    pressureChart.data.labels = makeLabels(pres.length)
    pressureChart.data.datasets[0].data = pres
    pressureChart.update('none')
  }

  const pdelta = sensorStore.pressureDeltaHistory.map(p => p.value)
  if (pressureDeltaChart) {
    pressureDeltaChart.data.labels = makeLabels(pdelta.length)
    pressureDeltaChart.data.datasets[0].data = pdelta
    pressureDeltaChart.update('none')
  }

  const wm = sensorStore.wristMagHistory.map(p => p.value)
  if (wristChart) {
    wristChart.data.labels = makeLabels(wm.length)
    wristChart.data.datasets[0].data = wm
    wristChart.update('none')
  }

  const steps = sensorStore.stepsHistory.map(p => p.value)
  if (stepsChart) {
    stepsChart.data.labels = makeLabels(steps.length)
    stepsChart.data.datasets[0].data = steps
    stepsChart.update('none')
  }

  // Real-time scrolling telemetry logging inside the 10 FPS loop
  logUpdateTick++
  if (logUpdateTick >= 5) {
    logUpdateTick = 0
    const lat = sensorStore.location.latitude !== 0 ? sensorStore.location.latitude.toFixed(6) : '10.395500'
    const lng = sensorStore.location.longitude !== 0 ? sensorStore.location.longitude.toFixed(6) : '105.421300'
    const step = sensorStore.activity.pedometer_steps
    const type = sensorStore.activity.activity_type.toUpperCase()
    const batt = sensorStore.environment.battery_level.toFixed(1)
    
    const possibleLogs = [
      `> RX_PKT: SEC_FLOW_${sensorStore.stepsHistory.length}_OK`,
      `> GPS_LOCK: LAT=${lat} | LNG=${lng}`,
      `> ACCEL_XYZ: [${sensorStore.imu.linear_acceleration?.x?.toFixed(2) ?? '0.00'}, ${sensorStore.imu.linear_acceleration?.y?.toFixed(2) ?? '0.00'}, ${sensorStore.imu.linear_acceleration?.z?.toFixed(2) ?? '9.81'}]`,
      `> COMPASS: YAW=${sensorStore.eulerAngles.yaw}° | HEADING=${sensorStore.imu.compass_heading ?? 0}°`,
      `> PEDOMETER: TOTAL_STEPS=${step} | STATE=${type}`,
      `> BATT_MON: CAP=${batt}% | TEMP=${sensorStore.environment.battery_temp.toFixed(1)}°C`,
      `> SYS_STAT: HEAP_ALLOC_OK | THREADS=4`,
      `> LINK_UPLINK: ACTIVE_PORT_3005`,
      `> CALIBRATING REACTOR_CORE_C... COMPLETE`
    ]
    const randomLog = possibleLogs[Math.floor(Math.random() * possibleLogs.length)]
    telemetryLogs.value.push(randomLog)
    if (telemetryLogs.value.length > 5) {
      telemetryLogs.value.shift()
    }
  }

  // Update rotating tactical scan sweep sector on Leaflet map
  if (mapInstance && (window as any).L) {
    const lat = sensorStore.location.latitude !== 0 ? sensorStore.location.latitude : 10.3955
    const lng = sensorStore.location.longitude !== 0 ? sensorStore.location.longitude : 105.4213
    updateTacticalLayers((window as any).L, lat, lng)
  }
}

// ── Statistics Table ──────────────────────────────────────────────────────────
const sessionMinMax: Record<string, { min: number; max: number }> = {}

function trackMinMax(key: string, val: number) {
  if (!sessionMinMax[key]) sessionMinMax[key] = { min: val, max: val }
  else {
    if (val < sessionMinMax[key].min) sessionMinMax[key].min = val
    if (val > sessionMinMax[key].max) sessionMinMax[key].max = val
  }
  return sessionMinMax[key]
}

const statsTableRows = computed(() => {
  const imu = sensorStore.imu
  const env = sensorStore.environment
  const loc = sensorStore.location
  const act = sensorStore.activity

  const rows = [
    { sensor: 'ACCEL X', current: isActive(sensorStore.imuStatus) ? safeToFixed(imu?.linear_acceleration?.x, 3) : 'OFFLINE', unit: 'm/s²', key: 'ax', val: imu?.linear_acceleration?.x, statusClass: getStatusClass(sensorStore.imuStatus), status: sensorStore.imuStatus },
    { sensor: 'ACCEL Y', current: isActive(sensorStore.imuStatus) ? safeToFixed(imu?.linear_acceleration?.y, 3) : 'OFFLINE', unit: 'm/s²', key: 'ay', val: imu?.linear_acceleration?.y, statusClass: getStatusClass(sensorStore.imuStatus), status: sensorStore.imuStatus },
    { sensor: 'ACCEL Z', current: isActive(sensorStore.imuStatus) ? safeToFixed(imu?.linear_acceleration?.z, 3) : 'OFFLINE', unit: 'm/s²', key: 'az', val: imu?.linear_acceleration?.z, statusClass: getStatusClass(sensorStore.imuStatus), status: sensorStore.imuStatus },
    { sensor: 'GYRO X', current: isActive(sensorStore.imuStatus) ? safeToFixed(imu?.angular_velocity?.x, 4) : 'OFFLINE', unit: 'rad/s', key: 'gx', val: imu?.angular_velocity?.x, statusClass: getStatusClass(sensorStore.imuStatus), status: sensorStore.imuStatus },
    { sensor: 'GYRO Y', current: isActive(sensorStore.imuStatus) ? safeToFixed(imu?.angular_velocity?.y, 4) : 'OFFLINE', unit: 'rad/s', key: 'gy', val: imu?.angular_velocity?.y, statusClass: getStatusClass(sensorStore.imuStatus), status: sensorStore.imuStatus },
    { sensor: 'GYRO Z', current: isActive(sensorStore.imuStatus) ? safeToFixed(imu?.angular_velocity?.z, 4) : 'OFFLINE', unit: 'rad/s', key: 'gz', val: imu?.angular_velocity?.z, statusClass: getStatusClass(sensorStore.imuStatus), status: sensorStore.imuStatus },
    {
      sensor: 'MAG X',
      current: imu?.magnetometer?.x === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(imu?.magnetometer?.x, 2) : 'OFFLINE'),
      unit: imu?.magnetometer?.x === null ? '' : 'µT',
      key: 'mx',
      val: imu?.magnetometer?.x ?? undefined,
      statusClass: imu?.magnetometer?.x === null ? 'warn' : getStatusClass(sensorStore.imuStatus),
      status: imu?.magnetometer?.x === null ? 'NO HW' : sensorStore.imuStatus
    },
    {
      sensor: 'MAG Y',
      current: imu?.magnetometer?.y === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(imu?.magnetometer?.y, 2) : 'OFFLINE'),
      unit: imu?.magnetometer?.y === null ? '' : 'µT',
      key: 'my',
      val: imu?.magnetometer?.y ?? undefined,
      statusClass: imu?.magnetometer?.y === null ? 'warn' : getStatusClass(sensorStore.imuStatus),
      status: imu?.magnetometer?.y === null ? 'NO HW' : sensorStore.imuStatus
    },
    {
      sensor: 'MAG Z',
      current: imu?.magnetometer?.z === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(imu?.magnetometer?.z, 2) : 'OFFLINE'),
      unit: imu?.magnetometer?.z === null ? '' : 'µT',
      key: 'mz',
      val: imu?.magnetometer?.z ?? undefined,
      statusClass: imu?.magnetometer?.z === null ? 'warn' : getStatusClass(sensorStore.imuStatus),
      status: imu?.magnetometer?.z === null ? 'NO HW' : sensorStore.imuStatus
    },
    {
      sensor: 'COMPASS',
      current: imu?.compass_heading === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(imu?.compass_heading, 1) : 'OFFLINE'),
      unit: imu?.compass_heading === null ? '' : '°',
      key: 'comp',
      val: imu?.compass_heading ?? undefined,
      statusClass: imu?.compass_heading === null ? 'warn' : getStatusClass(sensorStore.imuStatus),
      status: imu?.compass_heading === null ? 'NO HW' : sensorStore.imuStatus
    },
    { sensor: 'LIGHT',       current: isActive(sensorStore.envStatus) ? safeToFixed(env?.ambient_light, 0) : 'OFFLINE',         unit: 'lux',  key: 'lux',     val: env?.ambient_light,         statusClass: getStatusClass(sensorStore.envStatus), status: sensorStore.envStatus },
    // BAROMETER / PRESSURE: always SIMULATED when active, or NO HW
    {
      sensor: 'BAROMETER',
      current: env?.barometric_pressure === null
        ? 'NO HW'
        : isActive(sensorStore.envStatus) ? safeToFixed(env?.barometric_pressure, 2) : 'OFFLINE',
      unit: env?.barometric_pressure === null ? '' : 'hPa',
      key: 'baro',
      val: env?.barometric_pressure ?? undefined,
      statusClass: env?.barometric_pressure === null ? 'warn' : (isActive(sensorStore.envStatus) ? 'warn' : 'danger'),
      status: env?.barometric_pressure === null ? 'NO HW' : (isActive(sensorStore.envStatus) ? 'SIMULATED' : 'OFFLINE'),
    },
    {
      sensor: 'PRESSURE Δ',
      current: env?.pressure_delta_hpa === null
        ? 'NO HW'
        : isActive(sensorStore.envStatus) ? safeToFixed(env?.pressure_delta_hpa, 3) : 'OFFLINE',
      unit: env?.pressure_delta_hpa === null ? '' : 'ΔhPa',
      key: 'pdelta',
      val: env?.pressure_delta_hpa ?? undefined,
      statusClass: env?.pressure_delta_hpa === null ? 'warn' : (isActive(sensorStore.envStatus) ? 'warn' : 'danger'),
      status: env?.pressure_delta_hpa === null ? 'NO HW' : (isActive(sensorStore.envStatus) ? 'SIMULATED' : 'OFFLINE'),
    },
    { sensor: 'LATITUDE', current: isActive(sensorStore.locStatus) ? safeToFixed(loc?.latitude, 6) : 'OFFLINE', unit: '°', key: 'lat', val: loc?.latitude, statusClass: getStatusClass(sensorStore.locStatus), status: sensorStore.locStatus },
    { sensor: 'LONGITUDE', current: isActive(sensorStore.locStatus) ? safeToFixed(loc?.longitude, 6) : 'OFFLINE', unit: '°', key: 'lon', val: loc?.longitude, statusClass: getStatusClass(sensorStore.locStatus), status: sensorStore.locStatus },
    { sensor: 'ALTITUDE', current: isActive(sensorStore.locStatus) ? safeToFixed(loc?.altitude, 1) : 'OFFLINE', unit: 'm', key: 'alt', val: loc?.altitude, statusClass: getStatusClass(sensorStore.locStatus), status: sensorStore.locStatus },
    { sensor: 'STEPS', current: isActive(sensorStore.actStatus) ? String(act?.pedometer_steps ?? 0) : 'OFFLINE', unit: 'steps', key: 'steps', val: act?.pedometer_steps, statusClass: getStatusClass(sensorStore.actStatus), status: sensorStore.actStatus },
    { sensor: 'ACTIVITY', current: isActive(sensorStore.actStatus) ? (act?.activity_type ?? 'unknown').toUpperCase() : 'OFFLINE', unit: '', key: 'acttype', val: 0, statusClass: getStatusClass(sensorStore.actStatus), status: sensorStore.actStatus },
    {
      sensor: 'WRIST MAG',
      current: isActive(sensorStore.actStatus) ? safeToFixed(sensorStore.wristMagnitude, 3) : 'OFFLINE',
      unit: 'units',
      key: 'wrist',
      val: sensorStore.wristMagnitude,
      statusClass: isActive(sensorStore.actStatus) ? 'warn' : 'danger',
      status: isActive(sensorStore.actStatus) ? 'SIMULATED' : 'OFFLINE'
    },
    { sensor: 'BATTERY LEVEL', current: isActive(sensorStore.envStatus) ? safeToFixed(env?.battery_level ?? 100.0, 1) : 'OFFLINE', unit: '%', key: 'bat_lvl', val: env?.battery_level ?? 100.0, statusClass: getStatusClass(sensorStore.envStatus), status: sensorStore.envStatus },
    { sensor: 'BATTERY TEMP', current: isActive(sensorStore.envStatus) ? safeToFixed(env?.battery_temp ?? 32.0, 1) : 'OFFLINE', unit: '°C', key: 'bat_temp', val: env?.battery_temp ?? 32.0, statusClass: getStatusClass(sensorStore.envStatus), status: sensorStore.envStatus },
  ]

  return rows.map(r => {
    const mm = (r.key !== 'acttype' && isActive(r.status) && r.val !== undefined && r.val !== null) ? trackMinMax(r.key, r.val) : null
    return {
      ...r,
      min: mm ? safeToFixed(mm.min, 3, '—') : '—',
      max: mm ? safeToFixed(mm.max, 3, '—') : '—',
    }
  })
})

// ── CSV Export ────────────────────────────────────────────────────────────────
function exportCSV() {
  const headers = ['SENSOR', 'CURRENT', 'UNIT', 'MIN', 'MAX', 'STATUS']
  const rows = statsTableRows.value.map(r =>
    [r.sensor, r.current, r.unit, r.min, r.max, r.status].join(',')
  )
  const csv = [headers.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `hk07-sensor-telemetry-${Date.now()}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ── GPS Leaflet Map Integration ─────────────────────────────────────────────
const mapContainer = ref<HTMLElement | null>(null)
let mapInstance: any = null
let markerInstance: any = null
let tacticalLayersGroup: any = null
const telemetryLogs = ref<string[]>([
  '> CONNECTING SAT_LINK_9... OK',
  '> SEC_UPLINK: LOCK_ACTIVE',
  '> RESOLVING TRACKING NODES...',
  '> TELEMETRY_STREAM: RUNNING',
  '> ALL_SYSTEMS_NOMINAL'
])
let logUpdateTick = 0
let _blueprintAnimFrame: number | null = null

const currentZoom = ref(17)
const isTracking = ref(true)
const tacticalRanges = [
  { label: '100m', zoom: 19 },
  { label: '250m', zoom: 18 },
  { label: '500m', zoom: 17 },
  { label: '1km', zoom: 16 },
  { label: '5km', zoom: 14 }
]

function setTacticalRange(zoom: number) {
  currentZoom.value = zoom
  if (mapInstance) {
    const lat = sensorStore.location.latitude !== 0 ? sensorStore.location.latitude : 10.3955
    const lng = sensorStore.location.longitude !== 0 ? sensorStore.location.longitude : 105.4213
    mapInstance.setView([lat, lng], zoom)
  }
}

function recenterMap() {
  isTracking.value = true
  if (mapInstance) {
    const lat = sensorStore.location.latitude !== 0 ? sensorStore.location.latitude : 10.3955
    const lng = sensorStore.location.longitude !== 0 ? sensorStore.location.longitude : 105.4213
    mapInstance.setView([lat, lng], mapInstance.getZoom() || currentZoom.value)
  }
}

function loadLeaflet(): Promise<any> {
  return new Promise((resolve, reject) => {
    if ((window as any).L) {
      resolve((window as any).L)
      return
    }
    // Load Leaflet CSS
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    document.head.appendChild(link)

    // Load Leaflet JS
    const script = document.createElement('script')
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    script.onload = () => resolve((window as any).L)
    script.onerror = (e) => reject(e)
    document.body.appendChild(script)
  })
}

function updateTacticalLayers(L: any, lat: number, lng: number) {
  if (!mapInstance) return
  if (!tacticalLayersGroup) {
    tacticalLayersGroup = L.layerGroup().addTo(mapInstance)
  } else {
    tacticalLayersGroup.clearLayers()
  }

  // Terminal green palette
  const gridColor  = 'rgba(0, 255, 102, 0.22)'   // #00FF66 — geo graticule grid
  const gridWeight = 0.6

  // ── GEO GRATICULE GRID ─────────────────────────────────────────────────────
  // Draw lat lines every ~100m and lng lines every ~100m around current position
  // visible radius: ±500m in each axis
  const stepM    = 100
  const radiusM  = 500
  const meterToLat = (m: number) => m / 111320
  const meterToLng = (m: number) => m / (111320 * Math.cos((lat * Math.PI) / 180))

  const latStep = meterToLat(stepM)
  const lngStep = meterToLng(stepM)
  const latSpan = meterToLat(radiusM)
  const lngSpan = meterToLng(radiusM)

  // Latitude lines (horizontal lines)
  const latStart = Math.ceil((lat - latSpan) / latStep) * latStep
  for (let lineLat = latStart; lineLat <= lat + latSpan; lineLat += latStep) {
    L.polyline(
      [[lineLat, lng - lngSpan], [lineLat, lng + lngSpan]],
      { color: gridColor, weight: gridWeight, interactive: false, opacity: 1 }
    ).addTo(tacticalLayersGroup)
  }

  // Longitude lines (vertical lines)
  const lngStart = Math.ceil((lng - lngSpan) / lngStep) * lngStep
  for (let lineLng = lngStart; lineLng <= lng + lngSpan; lineLng += lngStep) {
    L.polyline(
      [[lat - latSpan, lineLng], [lat + latSpan, lineLng]],
      { color: gridColor, weight: gridWeight, interactive: false, opacity: 1 }
    ).addTo(tacticalLayersGroup)
  }

  // ── POSITION MARKER ──
  L.circle([lat, lng], {
    radius: 8,
    color: '#00FF66',
    weight: 1,
    fillOpacity: 0,
    interactive: false
  }).addTo(tacticalLayersGroup)
}

function initMap(L: any) {
  if (!mapContainer.value) return
  const initLat = sensorStore.location.latitude !== 0 ? sensorStore.location.latitude : 10.3955
  const initLng = sensorStore.location.longitude !== 0 ? sensorStore.location.longitude : 105.4213

  mapInstance = L.map(mapContainer.value, {
    zoomControl: false,          // disabled default zoom controls (replaced with tactical range scale)
    attributionControl: false,
    dragging: true,             // allow dragging/panning
    scrollWheelZoom: true,      // allow scroll wheel zoom
    doubleClickZoom: true,
    boxZoom: false,
    keyboard: false,
    touchZoom: true
  }).setView([initLat, initLng], currentZoom.value)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 20,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(mapInstance)

  // Auto-disable tracking mode if the user manually drags the viewport
  mapInstance.on('dragstart', () => {
    isTracking.value = false
  })

  // Sonar pulsing position marker
  const pingIcon = L.divIcon({
    className: 'gps-sonar-ping',
    html: '<div class="ping-ring"></div><div class="ping-dot"></div>',
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  })

  markerInstance = L.marker([initLat, initLng], { icon: pingIcon }).addTo(mapInstance)

  // Initial graticule grid draw
  updateTacticalLayers(L, initLat, initLng)
}

watch(
  () => [sensorStore.location.latitude, sensorStore.location.longitude],
  ([lat, lng]) => {
    if (mapInstance && markerInstance && lat !== 0 && lng !== 0) {
      const pos = [lat, lng] as [number, number]
      markerInstance.setLatLng(pos)
      if (isTracking.value) {
        mapInstance.setView(pos, mapInstance.getZoom() || currentZoom.value)
      }
      if ((window as any).L) {
        updateTacticalLayers((window as any).L, lat, lng)
      }
    }
  }
)

// ── Lifecycle ─────────────────────────────────────────────────────────────────
let _clockInterval: number | null = null
let _chartInterval: number | null = null

onMounted(async () => {
  // Try to load dynamic IP configuration from backend first
  await cfg.fetchBackendConfig();

  updateClock()
  _clockInterval = window.setInterval(updateClock, 1000)

  await nextTick()
  initCharts()

  // Update charts at 10 FPS
  _chartInterval = window.setInterval(updateCharts, 100)

  // Packet rate counter
  _pktInterval = window.setInterval(() => {
    const current = sensorStore.stepsHistory.length
    packetRate.value = Math.abs(current - _lastPktCount)
    _lastPktCount = current
  }, 1000)

  // Initialize Map
  try {
    const L = await loadLeaflet()
    initMap(L)
  } catch (e) {
    console.error('Failed to load Leaflet:', e)
  }
})

onUnmounted(() => {
  if (_clockInterval) clearInterval(_clockInterval)
  if (_chartInterval) clearInterval(_chartInterval)
  if (_pktInterval) clearInterval(_pktInterval)
  if (_blueprintAnimFrame) cancelAnimationFrame(_blueprintAnimFrame)
  accelChart?.destroy()
  gyroChart?.destroy()
  lightChart?.destroy()
  pressureChart?.destroy()
  pressureDeltaChart?.destroy()
  wristChart?.destroy()
  stepsChart?.destroy()

  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
  }
})
</script>

<style scoped>
/* ─── Base ─────────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@400;600;700&family=Orbitron:wght@700;900&family=Roboto+Mono:wght@300;400&display=swap');

.sensor-view {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  background: #000000;
  color: #E0F7FF;
  font-family: 'Rajdhani', sans-serif;
  min-height: 100vh;
  background-image: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,255,102,0.015) 2px,
    rgba(0,255,102,0.015) 4px
  );
}

/* ── CINEMATIC HUD TERMINAL LOADER ───────────────────────────────────────── */
.hud-terminal-loader {
  position: absolute;
  inset: 0;
  background: #000000;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.loader-text {
  font-family: 'Roboto Mono', monospace;
  color: #00FF66;
  font-size: 14px;
  letter-spacing: 2px;
  animation: scanning-glow 1.5s ease-in-out infinite;
}
@keyframes scanning-glow {
  0%, 100% { opacity: 0.3; text-shadow: 0 0 2px rgba(0, 255, 102, 0.2); }
  50% { opacity: 1; text-shadow: 0 0 10px rgba(0, 255, 102, 0.8); }
}

/* Corner reticles */
.corner { position: absolute; font-size: 20px; color: #00FF6655; font-family: monospace; }
.corner.tl { top: 4px; left: 4px; }
.corner.tr { top: 4px; right: 4px; }
.corner.bl { bottom: 4px; left: 4px; }
.corner.br { bottom: 4px; right: 4px; }

/* ─── Header ───────────────────────────────────────────────────────────────── */
.sv-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  border-bottom: 1px solid #00FF6633;
  padding-bottom: 10px;
}
.sv-label {
  font-size: 9px;
  letter-spacing: 3px;
  color: #00FF6688;
  text-transform: uppercase;
  display: block;
  margin-bottom: 4px;
}
.sv-title {
  font-family: 'Orbitron', sans-serif;
  font-size: 20px;
  font-weight: 900;
  color: #00FF66;
  margin: 0 0 2px;
  letter-spacing: 2px;
  text-shadow: 0 0 20px #00FF6655;
}
.sv-sub {
  font-size: 10px;
  color: #00FF6688;
  letter-spacing: 2px;
  font-family: 'Roboto Mono', monospace;
}
.sv-header-right {
  text-align: right;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.sv-live-badge {
  font-family: 'Rajdhani', sans-serif;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  padding: 3px 10px;
  border: 1px solid;
  display: flex;
  align-items: center;
  gap: 6px;
}
.badge-live { border-color: #00FF66; color: #00FF66; background: #00FF6611; }
.badge-offline { border-color: #FF333388; color: #FF3333; background: #FF333311; }
.pulse-dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: #00FF66;
  animation: pulse-anim 1s ease-in-out infinite;
  display: inline-block;
}
@keyframes pulse-anim {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.7); }
}
.sv-timestamp {
  font-family: 'Roboto Mono', monospace;
  font-size: 11px;
  color: #00FF6666;
  letter-spacing: 2px;
}

/* ─── Sensor Badge Strip ───────────────────────────────────────────────────── */
.sensor-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 0;
  border-bottom: 1px solid #00FF661A;
}
.sensor-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border: 1px solid;
  font-size: 9px;
  letter-spacing: 1px;
  font-family: 'Roboto Mono', monospace;
}
.badge-live { border-color: #00FF66; color: #00FF66; background: #00FF6608; }
.badge-simulated { border-color: #FFB000; color: #FFB000; background: rgba(255, 176, 0, 0.08); }
.badge-stale { border-color: #FFB000; color: #FFB000; background: #FFB00008; }
.badge-offline { border-color: #FF333366; color: #FF3333; background: #FF333308; }
.badge-icon { font-size: 10px; }
.badge-name { color: inherit; }
.badge-state { font-size: 8px; opacity: 0.7; }

/* ─── Main Layout (Environment top, split sidebar 30/70, charts 100%) ─── */
.sv-panel.full-width {
  width: 100%;
}

.sv-split-layout {
  display: flex;
  gap: 16px;
  width: 100%;
}

.sv-left-col {
  width: 30%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sv-right-col {
  width: 70%;
}

.sv-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #0A0A0A;
  border: 1px solid #00FF6622;
  padding: 12px;
  backdrop-filter: blur(4px);
}

.charts-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
  width: 100%;
}

.charts-stack .chart-block {
  width: 100%;
}

/* ─── Battery Panel ───────────────────────────────────────────────────────── */
.battery-stats {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 6px 0;
}
.bat-level-row, .bat-temp-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}
.bat-lbl {
  color: #00FF6688;
}
.bat-val {
  font-weight: 700;
  font-family: 'Roboto Mono', monospace;
}
.bat-progress-bar {
  font-size: 12px;
  letter-spacing: 2px;
  margin: 4px 0;
  text-shadow: 0 0 4px rgba(0, 255, 102, 0.5);
}

/* ─── GPS Layout ──────────────────────────────────────────────────────────── */
.gps-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}
.gps-readout-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  width: 100%;
}
.gps-item-horizontal {
  background: rgba(0, 255, 102, 0.02);
  border: 1px solid rgba(0, 255, 102, 0.15);
  padding: 10px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.gps-label {
  font-size: 9px;
  letter-spacing: 2px;
  color: #00FF6688;
  font-family: 'Roboto Mono', monospace;
}
.gps-val {
  font-size: 14px;
  font-weight: 700;
  color: #00FF66;
  font-family: 'Roboto Mono', monospace;
}
.gps-panel .map-placeholder {
  width: 100%;
  height: 500px;
  position: relative;
  background: #000000;
  border: 1px solid rgba(0, 255, 102, 0.25);
  overflow: hidden;
  box-shadow: none;
}
.real-map {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1;
  background: #080D10;
}
.blueprint-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: 2;
  pointer-events: none;
}
.real-map :deep(.leaflet-tile) {
  display: block;
  filter: grayscale(1) invert(1) sepia(1) hue-rotate(85deg) saturate(2) contrast(1.6) brightness(0.65) !important;
  opacity: 0.95;
  transition: filter 0.3s, opacity 0.3s;
}

.map-hud-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  pointer-events: none;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

/* Radar scanline sweep */
.radar-scanline {
  position: absolute;
  width: 100%;
  height: 2px;
  background: linear-gradient(to bottom, transparent, rgba(0, 255, 102, 0.25), transparent);
  top: 0;
  left: 0;
  z-index: 12;
  animation: radar-scan-y 5s infinite linear;
}
@keyframes radar-scan-y {
  0% { top: 0%; }
  100% { top: 100%; }
}

/* TOP-LEFT: Zoom Range Selector */
.hud-tactical-zoom {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(10, 10, 10, 0.88);
  border: 1px solid rgba(0, 255, 102, 0.25);
  border-left: 3px solid #00FF66;
  padding: 6px 10px;
  z-index: 20;
  display: flex;
  flex-direction: column;
  gap: 4px;
  pointer-events: auto; /* enable clicks! */
  width: 110px;
}
.zoom-title {
  font-size: 7.5px;
  color: #00FF66;
  opacity: 0.7;
  letter-spacing: 1px;
}
.zoom-btn {
  background: transparent;
  border: none;
  color: rgba(0, 255, 102, 0.5);
  font-family: 'Roboto Mono', monospace;
  font-size: 9px;
  text-align: left;
  padding: 2px 0;
  cursor: pointer;
  width: 100%;
  transition: all 0.2s ease;
}
.zoom-btn:hover {
  color: #00FF66;
  padding-left: 2px;
}
.zoom-btn.active {
  color: #00FF66;
  font-weight: 700;
  text-shadow: 0 0 4px rgba(0, 255, 102, 0.6);
}

/* TOP-RIGHT: Coordinates & Status HUD */
.coord-readout {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 20;
  background: rgba(10, 10, 10, 0.88);
  border: 1px solid rgba(0, 255, 102, 0.25);
  border-left: 3px solid #00FF66;
  padding: 6px 10px;
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 140px;
}
.coord-line {
  display: flex;
  justify-content: space-between;
  font-size: 9px;
}
.coord-lbl {
  color: #00FF66;
  opacity: 0.6;
}
.coord-val {
  color: #00FF66;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}
.coord-unit {
  font-size: 8px;
  opacity: 0.8;
  margin-left: 1px;
}

/* BOTTOM-LEFT: Telemetry console stream */
.hud-terminal-overlay {
  position: absolute;
  bottom: 10px;
  left: 10px;
  width: 220px;
  background: rgba(10, 10, 10, 0.88);
  border: 1px solid rgba(0, 255, 102, 0.25);
  border-left: 3px solid #00FF66;
  padding: 6px 10px;
  z-index: 15;
  font-size: 7.5px;
  line-height: 1.4;
  color: rgba(0, 255, 102, 0.9);
}
.term-header {
  font-size: 8px;
  font-weight: 700;
  color: #00FF66;
  margin-bottom: 4px;
  border-bottom: 1px dashed rgba(0, 255, 102, 0.2);
  padding-bottom: 2px;
}
.term-line {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* BOTTOM-RIGHT: Target tracking & system parameters */
.hud-sys-parameters {
  position: absolute;
  bottom: 10px;
  right: 10px;
  width: 180px;
  background: rgba(10, 10, 10, 0.88);
  border: 1px solid rgba(0, 255, 102, 0.25);
  border-left: 3px solid #00FF66;
  padding: 6px 10px;
  z-index: 15;
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.sys-title {
  font-size: 8px;
  font-weight: 700;
  color: #00FF66;
  margin-bottom: 4px;
  border-bottom: 1px dashed rgba(0, 255, 102, 0.2);
  padding-bottom: 2px;
}
.sys-row {
  display: flex;
  justify-content: space-between;
  font-size: 8.5px;
}
.sys-lbl {
  color: #00FF66;
  opacity: 0.6;
}
.sys-val {
  color: #00FF66;
  font-weight: 700;
}
.text-live { color: #00FF66 !important; }
.text-danger { color: #FF3333 !important; }
.text-blue { color: #0088FF !important; }

/* Central targeting crosshair */
.map-crosshair {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 32px;
  height: 32px;
  transform: translate(-50%, -50%);
  pointer-events: none;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
}
.crosshair-h {
  position: absolute;
  width: 100%;
  height: 1px;
  background: rgba(0, 255, 102, 0.4);
}
.crosshair-v {
  position: absolute;
  height: 100%;
  width: 1px;
  background: rgba(0, 255, 102, 0.4);
}
.crosshair-dot {
  width: 6px;
  height: 6px;
  border: 1px solid #00FF66;
  border-radius: 50%;
  background: transparent;
  box-shadow: 0 0 4px #00FF66;
}

/* Tactical target markers (NAV_0307 & ARM_0308) */
.hud-tactical-marker {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  z-index: 14;
  pointer-events: none;
}
.marker-box {
  width: 8px;
  height: 8px;
  border: 1.5px solid #00FF66;
  background: rgba(0, 255, 102, 0.15);
  transform: rotate(45deg);
  box-shadow: 0 0 4px #00FF66;
  position: relative;
}
.marker-box::after {
  content: '';
  position: absolute;
  inset: 1.5px;
  background: #00FF66;
}
.marker-box.alt-color {
  border-color: #FF3333;
  background: rgba(255, 51, 51, 0.15);
  box-shadow: 0 0 4px #FF3333;
}
.marker-box.alt-color::after {
  background: #FF3333;
}
.marker-label {
  font-family: 'Roboto Mono', monospace;
  font-size: 7px;
  color: #00FF66;
  text-shadow: 0 0 2px #000;
  background: rgba(0, 0, 0, 0.65);
  padding: 1px 3px;
  border-radius: 1px;
}
.marker-box.alt-color + .marker-label {
  color: #FF3333;
}

/* Side coordinate rails ticks */
.hud-side-rail {
  position: absolute;
  top: 40px;
  bottom: 40px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 6.5px;
  font-family: 'Roboto Mono', monospace;
  color: rgba(0, 255, 102, 0.4);
  z-index: 12;
  letter-spacing: 0.5px;
  line-height: 1;
}
.rail-left { left: 4px; align-items: flex-start; }
.rail-right { right: 4px; align-items: flex-end; }

/* Top horizontal scale rail ticks */
.hud-top-rail {
  position: absolute;
  top: 4px;
  left: 90px;
  right: 90px;
  display: flex;
  justify-content: space-between;
  font-size: 6.5px;
  font-family: 'Roboto Mono', monospace;
  color: rgba(0, 255, 102, 0.4);
  z-index: 12;
  letter-spacing: 0.5px;
}

/* Pulsing Sonar Ping Pin Marker styling */
.gps-sonar-ping {
  position: relative;
}
.ping-dot {
  width: 8px;
  height: 8px;
  background: var(--hud-active);
  border-radius: 50%;
  position: absolute;
  top: 8px;
  left: 8px;
  box-shadow: 0 0 10px var(--hud-active);
}
.ping-ring {
  width: 24px;
  height: 24px;
  border: 1.5px solid var(--hud-active);
  border-radius: 50%;
  position: absolute;
  top: 0;
  left: 0;
  animation: gps-sonar-pulse 2s infinite cubic-bezier(0.215, 0.610, 0.355, 1);
  box-shadow: inset 0 0 4px var(--hud-border);
}
@keyframes gps-sonar-pulse {
  0% {
    transform: scale(0.3);
    opacity: 1;
  }
  100% {
    transform: scale(2.8);
    opacity: 0;
  }
}

/* ─── Panel headers ──────────────────────────────────────────────────────────*/
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.panel-tag {
  font-size: 9px;
  letter-spacing: 2px;
  color: #00FF66;
  font-family: 'Roboto Mono', monospace;
  text-transform: uppercase;
}
.panel-status {
  font-size: 9px;
  letter-spacing: 2px;
  font-weight: 700;
  font-family: 'Roboto Mono', monospace;
}
.panel-status.live { color: #00FF66; }
.panel-status.simulated { color: #FFB000; }
.panel-status.stale { color: #FFB000; }
.panel-status.offline { color: #FF3333; }
.panel-micro-label {
  font-size: 8px;
  letter-spacing: 2px;
  color: #00FF6666;
  font-family: 'Roboto Mono', monospace;
  display: block;
  margin-bottom: 4px;
}

/* ─── Orientation Cube ──────────────────────────────────────────────────────*/
.orientation-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: center;
}
.cube-scene {
  width: 90px; height: 90px;
  perspective: 300px;
  flex-shrink: 0;
}
.cube {
  width: 60px; height: 60px;
  position: relative;
  transform-style: preserve-3d;
  margin: 15px auto;
}
.face {
  position: absolute;
  width: 60px; height: 60px;
  border: 1px solid #00FF6655;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 8px;
  font-family: 'Roboto Mono', monospace;
  color: #00FF6688;
  background: rgba(0, 255, 102, 0.04);
  backdrop-filter: blur(2px);
}
.face.front  { transform: translateZ(30px); border-color: #00FF66; color: #00FF66; }
.face.back   { transform: rotateY(180deg) translateZ(30px); }
.face.left   { transform: rotateY(-90deg) translateZ(30px); }
.face.right  { transform: rotateY(90deg) translateZ(30px); }
.face.top    { transform: rotateX(90deg) translateZ(30px); }
.face.bottom { transform: rotateX(-90deg) translateZ(30px); }

.euler-readout { display: flex; flex-direction: column; gap: 4px; }
.euler-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.euler-label { font-size: 9px; color: #00FF6688; font-family: 'Roboto Mono', monospace; min-width: 36px; }
.euler-val {
  font-family: 'Orbitron', monospace;
  font-size: 13px;
  font-weight: 700;
  color: #00FF66;
  min-width: 70px;
  text-align: right;
}
.euler-val.text-warn { color: #FFB000; }

/* ─── Compass ────────────────────────────────────────────────────────────── */
.compass-wrap { display: flex; justify-content: center; }
.compass-svg { width: 110px; height: 110px; }

/* ─── Quaternion ─────────────────────────────────────────────────────────── */
.quat-panel { background: #00000088; border: 1px solid #00FF6611; padding: 8px; }
.quat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; }
.quat-item {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 10px;
}
.quat-item span { color: #00FF6688; font-family: 'Roboto Mono', monospace; font-size: 9px; }
.quat-item b { color: #00FF66; font-family: 'Roboto Mono', monospace; font-size: 10px; font-weight: 400; }

/* ─── Charts ─────────────────────────────────────────────────────────────── */
.chart-block { }
.chart-label {
  font-size: 8px;
  letter-spacing: 1.5px;
  color: #00FF6666;
  font-family: 'Roboto Mono', monospace;
  margin-bottom: 4px;
  text-transform: uppercase;
}
.hud-canvas { height: 90px !important; width: 100% !important; }

/* ─── Stat Cards ──────────────────────────────────────────────────────────── */
.stat-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 6px; }
.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 6px;
  border: 1px solid #00FF6622;
  background: #00000066;
  gap: 2px;
  text-align: center;
}
.stat-card.card-ok { border-color: #00FF6622; }
.stat-card.card-warn { border-color: #FFB00066; }
.stat-card.card-danger { border-color: #FF333366; }
.stat-icon { font-size: 16px; color: #00FF66; }
.stat-val {
  font-family: 'Orbitron', sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: #00FF66;
  line-height: 1;
}
.stat-card.card-warn .stat-val { color: #FFB000; }
.stat-card.card-danger .stat-val { color: #FF3333; }
.stat-unit { font-size: 8px; color: #00FF6655; letter-spacing: 1px; }
.stat-name { font-size: 8px; color: #00FF6688; letter-spacing: 1px; }

/* ─── Magnetometer ──────────────────────────────────────────────────────── */
.mag-panel { background: #00000088; border: 1px solid #00FF6611; padding: 8px; }
.mag-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4px; }
.mag-item { display: flex; flex-direction: column; align-items: center; }
.mag-item span { font-size: 8px; color: #00FF6666; font-family: 'Roboto Mono', monospace; }
.mag-item b { font-size: 11px; color: #00FF66; font-family: 'Roboto Mono', monospace; font-weight: 400; }

/* ─── Pedometer Odometer ─────────────────────────────────────────────────── */
.odometer-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  border: 1px solid #00FF6622;
  background: #001100;
  gap: 4px;
}
.odometer-label { font-size: 9px; color: #00FF6688; letter-spacing: 3px; font-family: 'Roboto Mono', monospace; }
.odometer-display { display: flex; gap: 3px; }
.step-digit {
  width: 26px; height: 38px;
  background: #001a00;
  border: 1px solid #00FF6633;
  display: flex; align-items: center; justify-content: center;
  font-family: 'Orbitron', sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: #00FF66;
  text-shadow: 0 0 10px #00FF66;
  transition: all 0.15s ease;
}
.odometer-unit { font-size: 9px; color: #00FF6666; letter-spacing: 3px; }

/* ─── Activity Type ──────────────────────────────────────────────────────── */
.activity-type-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border: 1px solid #00FF6622;
  background: #0A0A0A;
}
.activity-icon { font-size: 28px; }
.activity-label-group { display: flex; flex-direction: column; }
.activity-type-label { font-size: 8px; color: #00FF6666; letter-spacing: 2px; font-family: 'Roboto Mono', monospace; }
.activity-type-value {
  font-family: 'Orbitron', sans-serif;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 2px;
  color: #00FF66;
}
.act-walking, .act-walk { color: #00FF66; }
.act-running, .act-run { color: #FFB000; }
.act-still, .act-stationary { color: #00FF6688; }

/* ─── GPS Panel ──────────────────────────────────────────────────────────── */
.gps-panel {
  border: 1px solid rgba(0, 255, 102, 0.25);
  background: #0A0A0A;
  backdrop-filter: blur(12px);
  padding: 12px;

  /* Stark OS Variables scoped locally ONLY to the map widget (Mục 2 & Mục 4 Theme Configuration) */
  --hud-bg: #080D10;                      /* Canvas Background */
  --hud-grid: rgba(1, 34, 17, 0.4);       /* Grids / Terrain */
  --hud-active: #00FF66;                  /* Active Phosphor Green */
  --hud-threat: #FF3333;                  /* Crimson Threat Lock */
  --hud-secondary: #FFFFFF;               /* Secondary Node White */
  --hud-panel-bg: rgba(8, 13, 16, 0.85);
  --hud-border: rgba(0, 255, 102, 0.25);
}


.gps-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
  margin-bottom: 8px;
}
.gps-item { display: flex; flex-direction: column; gap: 2px; }
.gps-label { font-size: 8px; color: rgba(0, 255, 102, 0.6); letter-spacing: 1px; font-family: 'Roboto Mono', monospace; }
.gps-val { font-family: 'Roboto Mono', monospace; font-size: 10px; color: #00FF66; }

/* Color overrides for GPS panel status indicators to match green/black primary theme */
.gps-panel .simulated {
  color: #00FF66 !important;
}
.gps-panel .stale {
  color: #FF3333 !important;
}
.gps-panel .warn {
  color: #00FF66 !important;
  border-color: #00FF66 !important;
}
.gps-panel .badge-simulated {
  border-color: #00FF66 !important;
  color: #00FF66 !important;
  background: rgba(0, 255, 102, 0.08) !important;
}

/* ─── Stats Table ────────────────────────────────────────────────────────── */
.stats-table-wrap {
  border: 1px solid #00FF6622;
  background: #050505;
  padding: 12px;
}
.export-btn {
  background: transparent;
  border: 1px solid #00FF6655;
  color: #00FF66;
  font-family: 'Rajdhani', sans-serif;
  font-size: 9px;
  letter-spacing: 2px;
  padding: 3px 10px;
  cursor: pointer;
  text-transform: uppercase;
  transition: all 0.2s;
}
.export-btn:hover { background: #00FF6622; box-shadow: 0 0 8px #00FF6644; }
.stats-table {
  width: 100%;
  border-collapse: collapse;
  font-family: 'Roboto Mono', monospace;
  font-size: 10px;
}
.stats-table th {
  color: #00FF66;
  font-size: 8px;
  letter-spacing: 2px;
  padding: 6px 8px;
  text-align: left;
  border-bottom: 1px solid #00FF6633;
  background: #00000088;
}
.stats-table td {
  padding: 5px 8px;
  border-bottom: 1px solid #00FF660A;
  color: #00FF66AA;
}
.stats-table tr:hover td { background: #00FF6608; }
.cell-sensor { color: #00FF66; font-size: 9px; letter-spacing: 1px; }
.cell-val { color: #00FF66; font-weight: bold; }
.cell-unit { color: #00FF6655; font-size: 8px; }
.cell-min { color: #00FF6666; }
.cell-max { color: #FFB00088; }
.status-pill {
  display: inline-block;
  padding: 1px 6px;
  font-size: 8px;
  letter-spacing: 1px;
  border: 1px solid;
}
.pill-ok, .pill-live { border-color: #00FF66; color: #00FF66; }
.pill-stale { border-color: #FFB000; color: #FFB000; }
.pill-simulated, .pill-warn { border-color: #FFB000; color: #FFB000; background: rgba(255, 176, 0, 0.08); }
.pill-offline { border-color: #FF3333; color: #FF3333; }
.pill-danger { border-color: #FF3333; color: #FF3333; }

.row-warn { color: #FFB000 !important; }
.row-warn .cell-sensor, .row-warn .cell-val, .row-warn .cell-unit, .row-warn .cell-min { color: #FFB000 !important; }

/* ─── Responsive ─────────────────────────────────────────────────────────── */
@media (max-width: 1200px) {
  .sv-split-layout {
    flex-direction: column;
  }
  .sv-left-col, .sv-right-col {
    width: 100%;
  }
}
@media (max-width: 768px) {
  .stat-row { grid-template-columns: 1fr 1fr; }
  .gps-readout-row {
    grid-template-columns: 1fr;
  }
}

/* ─── Blinking 1Hz dot for tactical node markers ───────────────────────── */
:global(.blinking-dot) {
  animation: blink-1hz 1s infinite steps(1);
}
@keyframes blink-1hz {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}
</style>
