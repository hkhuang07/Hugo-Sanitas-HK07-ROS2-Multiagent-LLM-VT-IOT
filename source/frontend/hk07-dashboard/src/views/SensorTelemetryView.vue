<template>
  <div class="sensor-view">
    <!-- Cinematic HUD Terminal Loader -->
    <div v-if="cfg.isConfigLoading" class="hud-terminal-loader">
      <span class="loader-text font-mono">[ CRITICAL_SYSTEM_UPLINK: FETCHING_ENV_METRICS... ]</span>
    </div>

    <!-- ═══ RETICLE CORNERS ═══ -->
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
        <div class="sv-header-actions-row">
          <button class="hud-btn-toggle-log header-action-item font-mono" @click="showLogsSidebar = !showLogsSidebar" :class="{ active: showLogsSidebar }">
            {{ showLogsSidebar ? '[ HIDE_LIVE_LOG ]' : '[ SHOW_LIVE_LOG ]' }}
          </button>
          <div class="header-action-item">
            <DeviceIpConfigModal />
          </div>
          <div class="sv-live-badge header-action-item" :class="streamStatus === 'LIVE' ? 'badge-live' : streamStatus === 'SIMULATED' ? 'badge-simulated' : 'badge-offline'">
            <span class="pulse-dot" v-if="isActive(streamStatus)"></span>
            {{ streamStatus === 'LIVE' ? '◈ STREAMING' : streamStatus === 'SIMULATED' ? '◈ SIMULATED' : '○ OFFLINE' }}
          </div>
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

    <!-- ═══ MAIN GRID CONTAINER (Zero Scroll HUD Target) ═══ -->
    <div class="hud-grid-container">

      <!-- ─── UPPER ROW (30% / 70%) ─── -->
      <div class="hud-row-upper">
        <!-- ─── COLUMN 1: LEFT PANEL (30%, vertically scrollable) ─── -->
        <div class="hud-column col-left">
          <!-- System Power Card -->
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
              <div class="bat-progress-bar font-mono text-success">
                {{ getBatteryBar(sensorStore.environment.battery_level) }}
              </div>
              <div class="bat-temp-row">
                <span class="bat-lbl">TEMP:</span>
                <span class="bat-val" :class="isActive(sensorStore.envStatus) && sensorStore.environment.battery_temp > 45 ? 'text-danger' : ''">
                  {{ isActive(sensorStore.envStatus) ? safeToFixed(sensorStore.environment?.battery_temp ?? 32.0, 1, '32.0') + '°C' : 'OFFLINE' }}
                </span>
              </div>
            </div>
          </div>

          <!-- Environment Panel -->
          <div class="sv-panel env-stats-panel">
            <div class="panel-header">
              <span class="panel-tag">[ ENVIRONMENT METRICS ]</span>
              <span class="panel-status" :class="sensorStore.envStatus.toLowerCase()">{{ sensorStore.envStatus }}</span>
            </div>
            <div class="stat-vertical-list">
              <div class="stat-card" :class="lightClass">
                <span class="stat-name">AMBIENT LIGHT</span>
                <div class="stat-val-row">
                  <span class="stat-icon">☀</span>
                  <span class="stat-val">{{ isActive(sensorStore.envStatus) ? safeToFixed(sensorStore.environment?.ambient_light, 0, 'OFFLINE') : 'OFFLINE' }}</span>
                  <span class="stat-unit" v-if="isActive(sensorStore.envStatus)">LUX</span>
                </div>
              </div>
              <div class="stat-card" :class="sensorStore.environment.barometric_pressure === null ? 'card-danger' : ''">
                <span class="stat-name">BAROMETER</span>
                <div class="stat-val-row">
                  <span class="stat-icon">⟁</span>
                  <span class="stat-val" :class="sensorStore.environment.barometric_pressure === null ? 'text-danger' : ''">
                    {{ sensorStore.environment.barometric_pressure === null ? 'NO HW' : (isActive(sensorStore.envStatus) ? safeToFixed(sensorStore.environment.barometric_pressure, 1, 'OFFLINE') : 'OFFLINE') }}
                  </span>
                  <span class="stat-unit" v-if="isActive(sensorStore.envStatus) && sensorStore.environment.barometric_pressure !== null">hPa</span>
                </div>
              </div>
              <div class="stat-card" :class="pressureDeltaClass">
                <span class="stat-name">PRESSURE DELTA</span>
                <div class="stat-val-row">
                  <span class="stat-icon">△</span>
                  <span class="stat-val">
                    {{ sensorStore.environment.pressure_delta_hpa === null ? 'NO HW' : (isActive(sensorStore.envStatus) ? (sensorStore.environment.pressure_delta_hpa >= 0 ? '+' : '') + safeToFixed(sensorStore.environment.pressure_delta_hpa, 2, 'OFFLINE') : 'OFFLINE') }}
                  </span>
                  <span class="stat-unit" v-if="isActive(sensorStore.envStatus) && sensorStore.environment.pressure_delta_hpa !== null">ΔhPa</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Activity Panel -->
          <div class="sv-panel activity-panel">
            <div class="panel-header">
              <span class="panel-tag">[ ACTIVITY // MOTION ]</span>
              <span class="panel-status" :class="sensorStore.actStatus.toLowerCase()">{{ sensorStore.actStatus }}</span>
            </div>
            <div class="odometer-wrap">
              <div class="odometer-label">PEDOMETER</div>
              <div class="odometer-display">
                <span v-for="(d, i) in stepDigits" :key="i" class="step-digit">{{ d }}</span>
              </div>
              <span class="odometer-unit">STEPS</span>
            </div>
            <div class="activity-type-wrap" style="margin-top: 6px;">
              <span class="activity-icon">{{ activityIcon }}</span>
              <div class="activity-label-group">
                <span class="activity-type-label">STATE</span>
                <span class="activity-type-value" :class="`act-${sensorStore.activity.activity_type.toLowerCase()}`">
                  {{ isActive(sensorStore.actStatus) ? sensorStore.activity.activity_type.toUpperCase() : 'OFFLINE' }}
                </span>
              </div>
            </div>
          </div>

          <!-- Hearing Panel -->
          <div class="sv-panel hearing-panel">
            <div class="panel-header">
              <span class="panel-tag">[ HEARING // AUDIO ]</span>
              <span class="panel-status" :class="sensorStore.hearingStatus.toLowerCase()">{{ sensorStore.hearingStatus }}</span>
            </div>
            <div class="hearing-body font-mono text-[9px]" style="padding: 6px; display: flex; flex-direction: column; gap: 4px; border: 1px solid rgba(0, 255, 102, 0.15); background: rgba(0, 0, 0, 0.4);">
              <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px dashed rgba(0,255,102,0.2); padding-bottom: 3px;">
                <span class="text-dim">MIC INTENSITY:</span>
                <span :class="['font-bold', sensorStore.hearing.intensity > -25 ? 'text-warn' : 'text-live']">
                  {{ isActive(sensorStore.hearingStatus) ? safeToFixed(sensorStore.hearing.intensity, 1, 'OFFLINE') + ' dBFS' : 'OFFLINE' }}
                </span>
              </div>
              <div style="color: #00FF66; letter-spacing: 1px; font-size: 10px; text-align: center;">
                {{ getMicBar(sensorStore.hearing.intensity) }}
              </div>

              <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 2px;">
                <div style="border: 1px solid rgba(0,255,102,0.1); padding: 3px; background: rgba(0,0,0,0.6);">
                  <span class="text-dim" style="font-size: 7px; display: block;">PITCH</span>
                  <span class="text-live font-bold" style="font-size: 9px;">{{ isActive(sensorStore.hearingStatus) ? sensorStore.hearing.frequency.toUpperCase() : 'OFFLINE' }}</span>
                </div>
                <div style="border: 1px solid rgba(0,255,102,0.1); padding: 3px; background: rgba(0,0,0,0.6);">
                  <span class="text-dim" style="font-size: 7px; display: block;">VOLUME</span>
                  <span class="text-live font-bold" style="font-size: 9px;">{{ isActive(sensorStore.hearingStatus) ? sensorStore.hearing.intensity_label.toUpperCase() : 'OFFLINE' }}</span>
                </div>
              </div>
              <div style="border-top: 1px dashed rgba(0,255,102,0.2); padding-top: 4px; margin-top: 2px;">
                <span class="text-dim" style="font-size: 7px; display: block;">SPEECH TRANSCRIPT:</span>
                <div style="background: rgba(0,229,255,0.05); border: 1px solid rgba(0,229,255,0.25); color: #00E5FF; padding: 4px; font-family: 'Roboto Mono', monospace; font-size: 9px; min-height: 20px;">
                  {{ isActive(sensorStore.hearingStatus) ? (sensorStore.hearing.transcript || '>> STANDBY...') : 'OFFLINE' }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- ─── COLUMN 2: RIGHT PANEL (70%, vertically scrollable) ─── -->
        <div class="hud-column col-right">
          <!-- IMU 9-DOF Widget -->
          <div class="sv-panel imu-panel">
            <div class="panel-header">
              <span class="panel-tag">[ IMU // 9-DOF ]</span>
              <span class="panel-status" :class="sensorStore.imuStatus.toLowerCase()">{{ sensorStore.imuStatus }}</span>
            </div>
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
              <!-- Compass mini gauge -->
              <div class="compass-wrap">
                <svg class="compass-svg" viewBox="0 0 120 120">
                  <circle cx="60" cy="60" r="55" fill="none" stroke="#00FF6622" stroke-width="1"/>
                  <circle cx="60" cy="60" r="55" fill="none" stroke="#00FF66" stroke-width="1" stroke-dasharray="4 4"/>
                  <text x="60" y="14" text-anchor="middle" fill="#00FF66" font-size="9" font-family="Rajdhani">N</text>
                  <g :transform="`rotate(${isActive(sensorStore.imuStatus) && sensorStore.imu.compass_heading !== null ? sensorStore.imu.compass_heading : 0}, 60, 60)`">
                    <polygon points="60,12 57,60 63,60" fill="#FF3333"/>
                    <polygon points="60,108 57,60 63,60" fill="#00FF66"/>
                  </g>
                  <circle cx="60" cy="60" r="4" fill="#00FF66"/>
                  <text x="60" y="74" text-anchor="middle" fill="#00FF66" font-size="10" font-family="Rajdhani,monospace">
                    {{ sensorStore.imu.compass_heading === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu.compass_heading, 1) + '°' : 'OFFLINE') }}
                  </text>
                </svg>
              </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px; margin-top: 6px;">
              <div class="quat-panel">
                <span class="panel-micro-label">QUATERNION</span>
                <div class="quat-grid">
                  <div class="quat-item"><span>W</span><b>{{ isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu?.orientation?.w, 3, 'N/A') : 'N/A' }}</b></div>
                  <div class="quat-item"><span>X</span><b>{{ isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu?.orientation?.x, 3, 'N/A') : 'N/A' }}</b></div>
                  <div class="quat-item"><span>Y</span><b>{{ isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu?.orientation?.y, 3, 'N/A') : 'N/A' }}</b></div>
                  <div class="quat-item"><span>Z</span><b>{{ isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu?.orientation?.z, 3, 'N/A') : 'N/A' }}</b></div>
                </div>
              </div>
              <div class="mag-panel">
                <span class="panel-micro-label">MAGNETOMETER</span>
                <div class="mag-grid">
                  <div class="mag-item"><span>MX</span><b :class="sensorStore.imu.magnetometer.x === null ? 'text-danger' : ''">{{ sensorStore.imu.magnetometer.x === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu.magnetometer.x, 1) : 'OFFLINE') }}</b></div>
                  <div class="mag-item"><span>MY</span><b :class="sensorStore.imu.magnetometer.y === null ? 'text-danger' : ''">{{ sensorStore.imu.magnetometer.y === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu.magnetometer.y, 1) : 'OFFLINE') }}</b></div>
                  <div class="mag-item"><span>MZ</span><b :class="sensorStore.imu.magnetometer.z === null ? 'text-danger' : ''">{{ sensorStore.imu.magnetometer.z === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(sensorStore.imu.magnetometer.z, 1) : 'OFFLINE') }}</b></div>
                </div>
              </div>
            </div>
          </div>

          <!-- Dynamic Chart Console (all charts stacked, no tabs) -->
          <div class="sv-panel charts-console-panel">
            <div class="panel-header">
              <span class="panel-tag">[ GRAPH TRENDS CONSOLE ]</span>
            </div>

            <div class="charts-console-content">
              <div class="chart-block-mini">
                <div class="chart-label">WRIST MAGNITUDE</div>
                <canvas ref="wristChartRef" class="hud-canvas-mini"></canvas>
              </div>
              <div class="chart-block-mini">
                <div class="chart-label">ACCELEROMETER XYZ (m/s²)</div>
                <canvas ref="accelChartRef" class="hud-canvas-mini"></canvas>
              </div>
              <div class="chart-block-mini">
                <div class="chart-label">GYROSCOPE XYZ (rad/s)</div>
                <canvas ref="gyroChartRef" class="hud-canvas-mini"></canvas>
              </div>
              <div class="chart-block-mini">
                <div class="chart-label">LIGHT SENSOR (lux)</div>
                <canvas ref="lightChartRef" class="hud-canvas-mini"></canvas>
              </div>
              <div class="chart-block-mini">
                <div class="chart-label">PRESSURE DELTA (ΔhPa)</div>
                <canvas ref="pressureDeltaChartRef" class="hud-canvas-mini"></canvas>
              </div>
              <div class="chart-block-mini">
                <div class="chart-label">STEP COUNT</div>
                <canvas ref="stepsChartRef" class="hud-canvas-mini"></canvas>
              </div>
              <div class="chart-block-mini">
                <div class="chart-label">BAROMETRIC PRESSURE (hPa)</div>
                <canvas ref="pressureChartRef" class="hud-canvas-mini"></canvas>
              </div>
            </div>
          </div>
        </div> <!-- closes col-right -->
      </div> <!-- closes hud-row-upper -->

      <!-- Tactical GIS Map Card (100% width) -->
      <div class="sv-panel gps-panel flex-grow-map" style="margin-top: 8px; flex-shrink: 0; min-height: 350px;">
        <div class="panel-header">
          <span class="panel-tag">[ GPS // FIELD ROAD MAP ]</span>
          <span class="panel-status" :class="sensorStore.locStatus.toLowerCase()">{{ sensorStore.locStatus }}</span>
        </div>
        <div class="gps-layout">
          <div class="map-placeholder">
            <div ref="mapContainer" class="real-map"></div>

            <!-- HUD overlays on Map -->
            <div class="map-hud-overlay">
              <div class="radar-scanline"></div>
              <div class="hud-tactical-zoom font-mono">
                <div class="zoom-title">// RANGE</div>
                <button v-for="r in tacticalRanges" :key="r.zoom" @click="setTacticalRange(r.zoom)" :class="{ active: currentZoom === r.zoom }" class="zoom-btn">
                  [{{ r.label.toUpperCase() }}]
                </button>
                <div class="zoom-title" style="margin-top: 4px; border-top: 1px dashed rgba(0, 255, 102, 0.2); padding-top: 2px;">// CAM</div>
                <button @click="recenterMap" :class="{ active: isTracking }" class="zoom-btn">
                  [{{ isTracking ? 'LKD' : 'FREE' }}]
                </button>
              </div>

              <div class="coord-readout font-mono">
                <div class="coord-line"><span class="coord-lbl">LAT</span><span class="coord-val">{{ safeToFixed(sensorStore.location?.latitude, 6, '0.000000') }}°</span></div>
                <div class="coord-line"><span class="coord-lbl">LNG</span><span class="coord-val">{{ safeToFixed(sensorStore.location?.longitude, 6, '0.000000') }}°</span></div>
                <div class="coord-line"><span class="coord-lbl">HDG</span><span class="coord-val">{{ safeToFixed(sensorStore.imu?.compass_heading, 1, '000.0') }}°</span></div>
              </div>

              <div class="hud-terminal-overlay font-mono">
                <div v-for="(log, idx) in telemetryLogs" :key="idx" class="term-line">
                  <span class="log-ts">[{{ log.timestamp }}]</span>
                  <span :class="['log-level', log.type]">[{{ log.level }}]</span>
                  <span class="log-content">— {{ log.content }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 13 Channels Stats Table (100% width) -->
      <div class="stats-table-wrap compact-table-wrap" style="margin-top: 8px; flex-shrink: 0; max-height: 300px;">
        <div class="panel-header">
          <span class="panel-tag">[ ALL 13 TELEMETRY CHANNELS ]</span>
          <button class="export-btn-mini" @click="exportCSV">CSV</button>
        </div>
        <div class="table-scroll-container">
          <table class="stats-table compact">
            <thead>
              <tr>
                <th>SENSOR</th>
                <th>VALUE</th>
                <th>UNIT</th>
                <th>MIN</th>
                <th>MAX</th>
                <th>STAT</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in statsTableRows" :key="row.sensor" :class="`row-${row.statusClass}`">
                <td class="cell-sensor">{{ row.sensor }}</td>
                <td class="cell-val" :class="row.current === 'NO HW' ? 'text-danger' : ''">{{ row.current }}</td>
                <td class="cell-unit">{{ row.unit }}</td>
                <td class="cell-min">{{ row.min }}</td>
                <td class="cell-max">{{ row.max }}</td>
                <td class="cell-status">
                  <span class="status-pill-mini" :class="`pill-${row.statusClass}`">{{ row.status }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div> <!-- closes hud-grid-container -->

    <!-- ═══ RIGHT-DOCKED SIDEBAR TERMINAL LOG ═══ -->
    <div class="sensor-streaming-log-sidebar" :class="{ active: showLogsSidebar }">
      <div class="panel-header" style="margin-bottom: 8px;">
        <span class="panel-tag">[ SENSOR_LOG // LIVE_STREAM ]</span>
        <div style="display: flex; gap: 6px; align-items: center;">
          <button class="btn-copy-tactical" @click="copyAllLogs">COPY</button>
          <button class="btn-clear-tactical" @click="clearLogs">CLR</button>
          <button class="btn-clear-tactical" @click="showLogsSidebar = false" style="border-color: #555; color: #888;">X</button>
        </div>
      </div>
      <div class="console-logs-window" ref="sensorLogsContainerRef">
        <div v-for="(log, idx) in sensorStreamingLogs" :key="idx" class="term-line">
          <span class="log-ts">[{{ log.timestamp }}]</span>
          <span :class="['log-source', log.type]">{{ log.source.split('.').pop() }}</span>
          <span class="log-content">— {{ log.content }}</span>
        </div>
        <div v-if="sensorStreamingLogs.length === 0" class="text-dim italic" style="padding: 10px; text-align: center; color: rgba(0, 255, 102, 0.4);">
          &gt;&gt; UPLINK ACTIVE: STANDBY FOR TELEMETRY PACKETS...
        </div>
      </div>
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

const showLogsSidebar = ref(false)

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
  // No barometer hardware on phone and cannot be inferred -> OFFLINE
  return 'OFFLINE'
})

// Wrist Motion hardware status
const wristStatus = computed(() => {
  if (!isActive(sensorStore.actStatus)) return sensorStore.actStatus
  // Always SIMULATED since phone has no wristband sensor (derived from accelerometer)
  return 'SIMULATED'
})

const sysState = computed(() => {
  if (!sensorStore.isLive) return 'OFFLINE'
  if (sensorStore.imuStatus === 'OFFLINE' && sensorStore.locStatus === 'OFFLINE' && sensorStore.envStatus === 'OFFLINE' && sensorStore.actStatus === 'OFFLINE') {
    return 'OFFLINE'
  }
  if (sensorStore.imuStatus === 'STALE' || sensorStore.locStatus === 'STALE' || sensorStore.envStatus === 'STALE' || sensorStore.actStatus === 'STALE') {
    return 'STALE'
  }
  return 'NOMINAL'
})

const sysStateClass = computed(() => {
  if (sysState.value === 'NOMINAL') return 'text-live'
  if (sysState.value === 'STALE') return 'text-warn'
  return 'text-danger'
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
  { key: 'hearing', name: 'HEARING', icon: '👂', status: sensorStore.hearingStatus },
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

function getMicBar(dbfs: number | undefined) {
  if (!isActive(sensorStore.hearingStatus)) return '[░░░░░░░░░░]'
  const val = dbfs ?? -120.0
  const normalized = Math.max(0, Math.min(10, Math.round((val + 80) / 8)))
  return `[${'█'.repeat(normalized)}${'░'.repeat(10 - normalized)}]`
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
      statusClass: imu?.magnetometer?.x === null ? 'danger' : getStatusClass(sensorStore.imuStatus),
      status: imu?.magnetometer?.x === null ? 'NO HW' : sensorStore.imuStatus
    },
    {
      sensor: 'MAG Y',
      current: imu?.magnetometer?.y === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(imu?.magnetometer?.y, 2) : 'OFFLINE'),
      unit: imu?.magnetometer?.y === null ? '' : 'µT',
      key: 'my',
      val: imu?.magnetometer?.y ?? undefined,
      statusClass: imu?.magnetometer?.y === null ? 'danger' : getStatusClass(sensorStore.imuStatus),
      status: imu?.magnetometer?.y === null ? 'NO HW' : sensorStore.imuStatus
    },
    {
      sensor: 'MAG Z',
      current: imu?.magnetometer?.z === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(imu?.magnetometer?.z, 2) : 'OFFLINE'),
      unit: imu?.magnetometer?.z === null ? '' : 'µT',
      key: 'mz',
      val: imu?.magnetometer?.z ?? undefined,
      statusClass: imu?.magnetometer?.z === null ? 'danger' : getStatusClass(sensorStore.imuStatus),
      status: imu?.magnetometer?.z === null ? 'NO HW' : sensorStore.imuStatus
    },
    {
      sensor: 'COMPASS',
      current: imu?.compass_heading === null ? 'NO HW' : (isActive(sensorStore.imuStatus) ? safeToFixed(imu?.compass_heading, 1) : 'OFFLINE'),
      unit: imu?.compass_heading === null ? '' : '°',
      key: 'comp',
      val: imu?.compass_heading ?? undefined,
      statusClass: imu?.compass_heading === null ? 'danger' : getStatusClass(sensorStore.imuStatus),
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
      statusClass: env?.barometric_pressure === null ? 'danger' : (isActive(sensorStore.envStatus) ? 'warn' : 'danger'),
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
      statusClass: env?.pressure_delta_hpa === null ? 'danger' : (isActive(sensorStore.envStatus) ? 'warn' : 'danger'),
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
    { sensor: 'MIC INTENSITY', current: isActive(sensorStore.hearingStatus) ? safeToFixed(sensorStore.hearing?.intensity, 1) : 'OFFLINE', unit: 'dBFS', key: 'mic_int', val: sensorStore.hearing?.intensity, statusClass: getStatusClass(sensorStore.hearingStatus), status: sensorStore.hearingStatus },
    { sensor: 'HEARING TRANSCRIPT', current: isActive(sensorStore.hearingStatus) ? (sensorStore.hearing?.transcript || 'STANDBY...') : 'OFFLINE', unit: '', key: 'mic_tx', val: 0, statusClass: getStatusClass(sensorStore.hearingStatus), status: sensorStore.hearingStatus },
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

interface TelemetryLogEntry {
  timestamp: string
  level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG'
  type: 'info' | 'warn' | 'error' | 'debug'
  source: string
  content: string
}

function getFormattedTime(): string {
  const d = new Date()
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${d.getMilliseconds().toString().padStart(3, '0')}`
}

const telemetryLogs = ref<TelemetryLogEntry[]>([
  { timestamp: getFormattedTime(), level: 'INFO', type: 'info', source: 'hk07.main', content: 'Connecting SAT_LINK_9... OK' },
  { timestamp: getFormattedTime(), level: 'INFO', type: 'info', source: 'hk07.main', content: 'SEC_UPLINK: LOCK_ACTIVE' },
  { timestamp: getFormattedTime(), level: 'INFO', type: 'info', source: 'hk07.main', content: 'Resolving tracking nodes...' },
  { timestamp: getFormattedTime(), level: 'INFO', type: 'info', source: 'hk07.main', content: 'TELEMETRY_STREAM: RUNNING' },
  { timestamp: getFormattedTime(), level: 'INFO', type: 'info', source: 'hk07.main', content: 'ALL_SYSTEMS_NOMINAL' }
])

const sensorStreamingLogs = ref<TelemetryLogEntry[]>([
  { timestamp: getFormattedTime(), level: 'INFO', type: 'info', source: 'hk07.main', content: 'Connecting SAT_LINK_9... OK' },
  { timestamp: getFormattedTime(), level: 'INFO', type: 'info', source: 'hk07.main', content: 'SEC_UPLINK: LOCK_ACTIVE' },
  { timestamp: getFormattedTime(), level: 'INFO', type: 'info', source: 'hk07.main', content: 'Resolving tracking nodes...' },
  { timestamp: getFormattedTime(), level: 'INFO', type: 'info', source: 'hk07.main', content: 'TELEMETRY_STREAM: RUNNING' },
  { timestamp: getFormattedTime(), level: 'INFO', type: 'info', source: 'hk07.main', content: 'ALL_SYSTEMS_NOMINAL' }
])

const sensorLogsContainerRef = ref<HTMLDivElement | null>(null)

function addTelemetryLog(level: 'INFO' | 'WARN' | 'ERROR' | 'DEBUG', source: string, content: string) {
  const typeMap = { INFO: 'info', WARN: 'warn', ERROR: 'error', DEBUG: 'debug' } as const
  const entry = {
    timestamp: getFormattedTime(),
    level,
    type: typeMap[level],
    source,
    content
  }

  telemetryLogs.value.push(entry)
  if (telemetryLogs.value.length > 5) {
    telemetryLogs.value.shift()
  }

  sensorStreamingLogs.value.push(entry)
  if (sensorStreamingLogs.value.length > 100) {
    sensorStreamingLogs.value.shift()
  }

  nextTick(() => {
    if (sensorLogsContainerRef.value) {
      sensorLogsContainerRef.value.scrollTop = sensorLogsContainerRef.value.scrollHeight
    }
  })
}

function copyAllLogs() {
  const text = sensorStreamingLogs.value.map(log => `[${log.timestamp}] [${log.level}] ${log.source} — ${log.content}`).join('\n')
  navigator.clipboard.writeText(text).then(() => {
    alert('Real-time log buffer copied to clipboard.')
  }).catch(err => {
    console.error('Failed to copy logs:', err)
  })
}

function clearLogs() {
  sensorStreamingLogs.value = []
}

let lastImuLogTime = 0
watch(
  () => sensorStore.lastImuMs,
  (newVal) => {
    if (newVal === 0) return
    const now = Date.now()
    if (now - lastImuLogTime >= 3000) {
      lastImuLogTime = now
      const la = sensorStore.imu.linear_acceleration
      const yaw = sensorStore.eulerAngles.yaw
      const heading = sensorStore.imu.compass_heading ?? 0
      addTelemetryLog('INFO', 'hk07.sensors.imu', `ACCEL=[${la.x.toFixed(2)}, ${la.y.toFixed(2)}, ${la.z.toFixed(2)}] | YAW=${yaw}° | HEADING=${heading}°`)
    }
  }
)

let lastLocLogTime = 0
watch(
  () => sensorStore.lastLocMs,
  (newVal) => {
    if (newVal === 0) return
    const now = Date.now()
    if (now - lastLocLogTime >= 3000) {
      lastLocLogTime = now
      const lat = sensorStore.location.latitude
      const lng = sensorStore.location.longitude
      addTelemetryLog('INFO', 'hk07.sensors.location', `GPS_LOCK: LAT=${lat.toFixed(6)} | LNG=${lng.toFixed(6)}`)
    }
  }
)

let lastEnvLogTime = 0
watch(
  () => sensorStore.lastEnvMs,
  (newVal) => {
    if (newVal === 0) return
    const now = Date.now()
    if (now - lastEnvLogTime >= 3000) {
      lastEnvLogTime = now
      const batt = sensorStore.environment.battery_level
      const temp = sensorStore.environment.battery_temp
      addTelemetryLog('INFO', 'hk07.sensors.environment', `BATT: CAP=${batt.toFixed(1)}% | TEMP=${temp.toFixed(1)}°C`)
    }
  }
)

let lastActLogTime = 0
 watch(
   () => sensorStore.lastActMs,
   (newVal) => {
     if (newVal === 0) return
     const now = Date.now()
     if (now - lastActLogTime >= 3000) {
       lastActLogTime = now
       const steps = sensorStore.activity.pedometer_steps
       const type = sensorStore.activity.activity_type.toUpperCase()
       addTelemetryLog('INFO', 'hk07.sensors.activity', `PEDOMETER: STEPS=${steps} | STATE=${type}`)
     }
   }
 )

 let lastHearingLogTime = 0
 watch(
   () => sensorStore.lastHearingMs,
   (newVal) => {
     if (newVal === 0) return
     const now = Date.now()
     if (now - lastHearingLogTime >= 1000) {
       lastHearingLogTime = now
       const hearing = sensorStore.hearing
       addTelemetryLog('INFO', 'hk07.sensors.hearing', `MICROPHONE: DBFS=${hearing.intensity.toFixed(1)} | PITCH=${hearing.frequency} | RHYTHM=${hearing.rhythm} | DIR=${hearing.direction} | TXT="${hearing.transcript}"`)
     }
   }
 )

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
.sv-header-actions-row {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
}
/* All 3 header controls (log toggle, IP config, live badge) share the
   same width and sit in a single aligned row */
.header-action-item {
  width: 190px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
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
  justify-content: center;
  gap: 6px;
  box-sizing: border-box;
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

/* Header Log Toggle Button */
.hud-btn-toggle-log {
  background: transparent;
  border: 1px solid rgba(0, 255, 102, 0.4);
  color: #00FF66;
  font-size: 9px;
  padding: 3px 8px;
  cursor: pointer;
  letter-spacing: 1px;
  transition: all 0.2s ease;
  width: 100%;
  box-sizing: border-box;
  text-align: center;
}
.hud-btn-toggle-log:hover, .hud-btn-toggle-log.active {
  background: rgba(0, 255, 102, 0.15);
  box-shadow: 0 0 6px rgba(0, 255, 102, 0.4);
}

/* Sensor Streaming Log Sidebar */
.sensor-streaming-log-sidebar {
  position: fixed;
  top: 48px;
  right: 0;
  width: 760px;
  height: calc(100vh - 48px);
  z-index: 9999;
  background: rgba(5, 5, 5, 0.96);
  border-left: 1px solid rgba(0, 255, 102, 0.3);
  box-shadow: -5px 0 25px rgba(0, 0, 0, 0.8);
  transform: translateX(100%);
  transition: transform 0.3s cubic-bezier(0.1, 0.9, 0.2, 1);
  display: flex;
  flex-direction: column;
  padding: 10px;
  box-sizing: border-box;
}
.sensor-streaming-log-sidebar.active {
  transform: translateX(0);
}
.sensor-streaming-log-sidebar .console-logs-window {
  flex: 1;
  background: rgba(0, 0, 0, 0.98);
  border: 1px solid rgba(0, 255, 102, 0.15);
  padding: 8px;
  overflow-y: auto;
  font-size: 11px;
  line-height: 1.4;
  font-family: 'Roboto Mono', monospace;
  user-select: text !important;
  -webkit-user-select: text !important;
}
.sensor-streaming-log-sidebar .console-logs-window::-webkit-scrollbar {
  width: 3px;
}
.sensor-streaming-log-sidebar .console-logs-window::-webkit-scrollbar-track {
  background: rgba(0,0,0,0.9);
}
.sensor-streaming-log-sidebar .console-logs-window::-webkit-scrollbar-thumb {
  background: rgba(0, 255, 102, 0.3);
  border-radius: 2px;
}

/* Tactical Copy / Clear Buttons styling */
.btn-copy-tactical {
  background: rgba(0, 0, 0, 0.9);
  border: 1px solid #00FF66;
  color: #00FF66;
  font-family: 'Roboto Mono', monospace;
  font-size: 8px;
  font-weight: bold;
  padding: 2px 6px;
  cursor: pointer;
  letter-spacing: 0.5px;
  transition: all 0.2s ease;
}
.btn-copy-tactical:hover {
  background: #00FF66;
  color: #000000;
  box-shadow: 0 0 6px #00FF66bb;
}

.btn-clear-tactical {
  background: rgba(0, 0, 0, 0.9);
  border: 1px solid #FF3333;
  color: #FF3333;
  font-family: 'Roboto Mono', monospace;
  font-size: 8px;
  font-weight: bold;
  padding: 2px 6px;
  cursor: pointer;
  letter-spacing: 0.5px;
  transition: all 0.2s ease;
}
.btn-clear-tactical:hover {
  background: #FF3333;
  color: #000000;
  box-shadow: 0 0 6px #FF3333bb;
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

.text-live { color: #00FF66 !important; }
.text-danger { color: #FF3333 !important; }
.text-blue { color: #0088FF !important; }

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

/* ─── Zero Scroll Layout Grid ─────────────────────────────────────────── */
.sensor-view {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 8px;
  overflow: hidden;
  box-sizing: border-box;
  background-color: #000000;
}
.sv-header {
  flex-shrink: 0;
  margin-bottom: 6px;
}
.sensor-strip {
  flex-shrink: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}
.hud-grid-container {
  display: flex;
  flex-direction: column;
  gap: 10px;
  flex-grow: 1;
  overflow-y: auto;
  box-sizing: border-box;
}

/* ── UPPER ROW: 30% (left, scrollable) / 70% (right, scrollable) ── */
/* Both columns are stretched to the same height (row height = tallest
   column's content), so their bottom edges are always aligned. */
.hud-row-upper {
  display: grid;
  grid-template-columns: 30% 70%;
  gap: 10px;
  flex-shrink: 0;
  align-items: stretch;
}
.hud-column {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  overflow-x: hidden;
  box-sizing: border-box;
}
.hud-column.col-left {
  overflow-y: auto;
}
.hud-column.col-right {
  overflow-y: auto;
}

/* Scrollbar customizations */
.hud-column::-webkit-scrollbar,
.table-scroll-container::-webkit-scrollbar {
  width: 3px;
  height: 3px;
}
.hud-column::-webkit-scrollbar-track,
.table-scroll-container::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.9);
}
.hud-column::-webkit-scrollbar-thumb,
.table-scroll-container::-webkit-scrollbar-thumb {
  background: #00FF6644;
  border-radius: 2px;
}
.hud-column::-webkit-scrollbar-thumb:hover,
.table-scroll-container::-webkit-scrollbar-thumb:hover {
  background: #00FF66aa;
}

/* Panel structures */
.sv-panel {
  border: 1px solid rgba(0, 255, 102, 0.22);
  background: rgba(10, 10, 10, 0.8);
  padding: 8px;
  box-sizing: border-box;
  backdrop-filter: blur(12px);
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  border-bottom: 1px solid rgba(0, 255, 102, 0.1);
  padding-bottom: 3px;
}
.panel-tag {
  font-size: 8px;
  letter-spacing: 1.5px;
  color: #00FF66;
  font-family: 'Roboto Mono', monospace;
}
.panel-status {
  font-size: 8px;
  font-weight: 700;
  font-family: 'Roboto Mono', monospace;
}
.panel-status.live { color: #00FF66; }
.panel-status.simulated { color: #FFB000; }
.panel-status.stale { color: #FFB000; }
.panel-status.offline { color: #FF3333; }
.panel-micro-label {
  font-size: 7px;
  color: #00FF6666;
  font-family: 'Roboto Mono', monospace;
  display: block;
  margin-bottom: 2px;
}

/* Environment Metrics List style */
.stat-vertical-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.stat-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 6px;
  border: 1px solid rgba(0, 255, 102, 0.1);
  background: rgba(0, 0, 0, 0.5);
  box-sizing: border-box;
}
.stat-card.card-ok { border-color: rgba(0, 255, 102, 0.2); }
.stat-card.card-warn { border-color: rgba(255, 176, 0, 0.3); }
.stat-card.card-danger { border-color: rgba(255, 51, 51, 0.4); }
.stat-val-row {
  display: flex;
  align-items: center;
  gap: 4px;
}
.stat-icon { font-size: 11px; color: #00FF66; }
.stat-val {
  font-family: 'Orbitron', sans-serif;
  font-size: 11px;
  font-weight: 700;
  color: #00FF66;
}
.stat-card.card-warn .stat-val { color: #FFB000; }
.stat-card.card-danger .stat-val { color: #FF3333; }
.stat-unit { font-size: 7px; color: #00FF6655; }
.stat-name { font-size: 8px; color: #00FF6688; font-family: 'Roboto Mono', monospace; }

/* ─── Orientation Cube ──────────────────────────────────────────────────────*/
.orientation-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: space-between;
  padding: 4px;
}
.cube-scene {
  width: 70px; height: 70px;
  perspective: 250px;
  flex-shrink: 0;
}
.cube {
  width: 46px; height: 46px;
  position: relative;
  transform-style: preserve-3d;
  margin: 12px auto;
}
.face {
  position: absolute;
  width: 46px; height: 46px;
  border: 1px solid #00FF6644;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 7px;
  font-family: 'Roboto Mono', monospace;
  color: #00FF6688;
  background: rgba(0, 255, 102, 0.04);
}
.face.front  { transform: translateZ(23px); border-color: #00FF66; color: #00FF66; }
.face.back   { transform: rotateY(180deg) translateZ(23px); }
.face.left   { transform: rotateY(-90deg) translateZ(23px); }
.face.right  { transform: rotateY(90deg) translateZ(23px); }
.face.top    { transform: rotateX(90deg) translateZ(23px); }
.face.bottom { transform: rotateX(-90deg) translateZ(23px); }

.euler-readout { display: flex; flex-direction: column; gap: 2px; }
.euler-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}
.euler-label { font-size: 8px; color: #00FF6688; font-family: 'Roboto Mono', monospace; }
.euler-val {
  font-family: 'Orbitron', monospace;
  font-size: 11px;
  font-weight: 700;
  color: #00FF66;
  min-width: 50px;
  text-align: right;
}
.euler-val.text-warn { color: #FFB000; }

/* ─── Compass ────────────────────────────────────────────────────────────── */
.compass-wrap { display: flex; justify-content: center; flex-shrink: 0; }
.compass-svg { width: 75px; height: 75px; }

/* ─── Quaternion & Mag Panels ─────────────────────────────────────────────── */
.quat-panel, .mag-panel { background: #00000088; border: 1px solid #00FF6611; padding: 4px; }
.quat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 2px; }
.quat-item {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 8px;
}
.quat-item span { color: #00FF6666; font-family: 'Roboto Mono', monospace; font-size: 8px; }
.quat-item b { color: #00FF66; font-family: 'Roboto Mono', monospace; font-size: 8px; font-weight: 400; }

.mag-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 2px; }
.mag-item { display: flex; flex-direction: column; align-items: center; }
.mag-item span { font-size: 7px; color: #00FF6666; font-family: 'Roboto Mono', monospace; }
.mag-item b { font-size: 8px; color: #00FF66; font-family: 'Roboto Mono', monospace; font-weight: 400; }

/* ─── Odometer Activity ──────────────────────────────────────────────────── */
.odometer-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 6px;
  border: 1px solid #00FF6622;
  background: #000b00;
  gap: 2px;
}
.odometer-label { font-size: 8px; color: #00FF6688; letter-spacing: 2px; font-family: 'Roboto Mono', monospace; }
.odometer-display { display: flex; gap: 2px; }
.step-digit {
  width: 18px; height: 26px;
  background: #001200;
  border: 1px solid #00FF6633;
  display: flex; align-items: center; justify-content: center;
  font-family: 'Orbitron', sans-serif;
  font-size: 15px;
  font-weight: 700;
  color: #00FF66;
  text-shadow: 0 0 4px #00FF66;
}
.odometer-unit { font-size: 8px; color: #00FF6666; letter-spacing: 2px; }

.activity-type-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border: 1px solid #00FF6622;
  background: #0A0A0A;
}
.activity-icon { font-size: 18px; }
.activity-label-group { display: flex; flex-direction: column; }
.activity-type-label { font-size: 7px; color: #00FF6666; font-family: 'Roboto Mono', monospace; }
.activity-type-value {
  font-family: 'Orbitron', sans-serif;
  font-size: 11px;
  font-weight: 700;
  color: #00FF66;
}
.act-walking, .act-walk { color: #00FF66; }
.act-running, .act-run { color: #FFB000; }
.act-still, .act-stationary { color: #00FF6688; }

/* ─── Map Flexible Frame ─────────────────────────────────────────────────── */
.flex-grow-map {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 6px;
  min-height: 220px;
}
.gps-layout {
  flex-grow: 1;
  position: relative;
  width: 100%;
  height: 100%;
}
.map-placeholder {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
}
.real-map {
  width: 100%;
  height: 100%;
  background: #080D10;
  border: 1px solid rgba(0, 255, 102, 0.2);
}

/* Custom overlay metrics on Map */
.map-hud-overlay {
  pointer-events: none;
}
.map-hud-overlay button {
  pointer-events: auto;
}
.hud-tactical-zoom {
  position: absolute;
  top: 6px; left: 6px;
  z-index: 1000;
  background: rgba(8, 13, 16, 0.85);
  border: 1px solid rgba(0,255,102,0.3);
  padding: 4px;
  font-size: 7px;
}
.zoom-title {
  color: #00FF6688;
  margin-bottom: 2px;
}
.zoom-btn {
  background: transparent;
  border: none;
  color: #00FF66aa;
  font-family: 'Roboto Mono', monospace;
  font-size: 7px;
  padding: 1px 3px;
  cursor: pointer;
  display: block;
  text-align: left;
  width: 100%;
}
.zoom-btn.active, .zoom-btn:hover {
  color: #00FF66;
  font-weight: bold;
}
.coord-readout {
  position: absolute;
  top: 6px; right: 6px;
  z-index: 1000;
  background: rgba(8, 13, 16, 0.85);
  border: 1px solid rgba(0,255,102,0.3);
  padding: 4px;
  font-size: 8px;
}
.coord-line {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}
.coord-lbl { color: #00FF6688; }
.coord-val { color: #00FF66; font-weight: bold; }

.hud-terminal-overlay {
  position: absolute;
  bottom: 6px; left: 6px; right: 6px;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.75);
  border: 1px solid rgba(0, 255, 102, 0.15);
  padding: 4px;
  font-size: 8px;
  max-height: 50px;
  overflow: hidden;
}
.term-line {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: flex;
  align-items: center;
  gap: 4px;
}
.term-line .log-ts {
  color: rgba(255, 255, 255, 0.4);
}
.term-line .log-level {
  font-weight: bold;
}
.term-line .log-level.info {
  color: #00FF66;
}
.term-line .log-level.warn {
  color: #FFB000;
}
.term-line .log-level.error {
  color: #FF3333;
}
.term-line .log-level.debug {
  color: #00E5FF;
}
.term-line .log-source {
  color: #ffffff;
  font-weight: 600;
}
.term-line .log-content {
  color: #00FF66;
  opacity: 0.95;
}

/* ─── Compact Table (100% width, bottom) ─────────────────────────────────── */
.compact-table-wrap {
  border: 1px solid #00FF6622;
  background: #050505;
  padding: 6px;
  max-height: 190px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}
.table-scroll-container {
  flex-grow: 1;
  overflow-y: auto;
}
.export-btn-mini {
  background: transparent;
  border: 1px solid #00FF6644;
  color: #00FF66;
  font-family: 'Rajdhani', sans-serif;
  font-size: 8px;
  padding: 0 4px;
  cursor: pointer;
}
.export-btn-mini:hover { background: #00FF6622; }

.stats-table.compact {
  width: 100%;
  border-collapse: collapse;
  font-family: 'Roboto Mono', monospace;
  font-size: 8.5px;
}
.stats-table.compact th {
  color: #00FF66;
  font-size: 7px;
  padding: 3px;
  border-bottom: 1px solid rgba(0,255,102,0.2);
  background: #000;
  text-align: left;
}
.stats-table.compact td {
  padding: 2px 3px;
  border-bottom: 1px solid rgba(0,255,102,0.05);
  color: #00FF66aa;
}
.status-pill-mini {
  display: inline-block;
  padding: 0 4px;
  font-size: 7px;
  border: 1px solid;
}
.pill-ok, .pill-live { border-color: #00FF66; color: #00FF66; }
.pill-stale { border-color: #FFB000; color: #FFB000; }
.pill-simulated, .pill-warn { border-color: #FFB000; color: #FFB000; background: rgba(255, 176, 0, 0.08); }
.pill-danger, .pill-offline { border-color: #FF3333; color: #FF3333; background: rgba(255, 51, 51, 0.08); }

/* ─── Charts Console (stacked, no tabs) ──────────────────────────────────── */
.charts-console-panel {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  padding: 6px;
}
.charts-console-content {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}
.chart-block-mini {
  border: 1px solid rgba(0, 255, 102, 0.1);
  padding: 3px;
  background: rgba(0, 0, 0, 0.2);
}
.chart-label {
  font-size: 7px;
  color: rgba(0, 255, 102, 0.5);
  font-family: 'Roboto Mono', monospace;
  margin-bottom: 2px;
}
.hud-canvas-mini {
  height: 70px !important;
  width: 100% !important;
}

/* Responsive adjustments */
@media (max-width: 1024px) {
  .hud-row-upper {
    grid-template-columns: 1fr;
    height: auto;
  }
  .hud-column {
    height: auto;
    overflow: visible;
  }
  .sensor-view {
    height: auto;
    overflow: visible;
  }
}

/* Blinking 1Hz dot */
:global(.blinking-dot) {
  animation: blink-1hz 1s infinite steps(1);
}
@keyframes blink-1hz {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* Audio wave oscillator */
.bar-osc {
  width: 3px;
  height: 100%;
  background: #00FF66;
  animation: osc-anim 0.8s ease-in-out infinite alternate;
}
@keyframes osc-anim {
  from { height: 15%; }
  to { height: 100%; }
}
</style>
