<template>
  <div class="sensor-view">
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
        <div class="sv-live-badge" :class="sensorStore.isLive ? 'badge-live' : 'badge-offline'">
          <span class="pulse-dot" v-if="sensorStore.isLive"></span>
          {{ sensorStore.isLive ? '◈ STREAMING' : '○ OFFLINE' }}
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

    <!-- ═══ MAIN GRID ═══ -->
    <div class="sv-main-grid">

      <!-- ── COL 1: IMU Panel ── -->
      <div class="sv-col imu-col">
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
              <div class="face left">L</div>
              <div class="face right">R</div>
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
            <g :transform="`rotate(${sensorStore.imu.compass_heading}, 60, 60)`">
              <polygon points="60,12 57,60 63,60" fill="#FF3333"/>
              <polygon points="60,108 57,60 63,60" fill="#00FF66"/>
            </g>
            <circle cx="60" cy="60" r="4" fill="#00FF66"/>
            <text x="60" y="76" text-anchor="middle" fill="#00FF66" font-size="11" font-family="Rajdhani,monospace">
              {{ sensorStore.imu.compass_heading.toFixed(1) }}°
            </text>
          </svg>
        </div>

        <!-- Quaternion Readout -->
        <div class="quat-panel">
          <span class="panel-micro-label">QUATERNION</span>
          <div class="quat-grid">
            <div class="quat-item"><span>W</span><b>{{ sensorStore.imu.orientation.w.toFixed(4) }}</b></div>
            <div class="quat-item"><span>X</span><b>{{ sensorStore.imu.orientation.x.toFixed(4) }}</b></div>
            <div class="quat-item"><span>Y</span><b>{{ sensorStore.imu.orientation.y.toFixed(4) }}</b></div>
            <div class="quat-item"><span>Z</span><b>{{ sensorStore.imu.orientation.z.toFixed(4) }}</b></div>
          </div>
        </div>

        <!-- Accel Chart -->
        <div class="chart-block">
          <div class="chart-label">ACCELEROMETER XYZ (m/s²)</div>
          <canvas ref="accelChartRef" class="hud-canvas"></canvas>
        </div>

        <!-- Gyro Chart -->
        <div class="chart-block">
          <div class="chart-label">GYROSCOPE XYZ (rad/s)</div>
          <canvas ref="gyroChartRef" class="hud-canvas"></canvas>
        </div>
      </div>

      <!-- ── COL 2: Environment + Vitals Panel ── -->
      <div class="sv-col env-col">
        <div class="panel-header">
          <span class="panel-tag">[ ENVIRONMENT // BIOMETRICS ]</span>
          <span class="panel-status" :class="sensorStore.envStatus.toLowerCase()">{{ sensorStore.envStatus }}</span>
        </div>

        <!-- Stat cards row -->
        <div class="stat-row">
          <div class="stat-card" :class="lightClass">
            <span class="stat-icon">☀</span>
            <span class="stat-val">{{ sensorStore.environment.ambient_light.toFixed(0) }}</span>
            <span class="stat-unit">LUX</span>
            <span class="stat-name">AMBIENT LIGHT</span>
          </div>
          <div class="stat-card">
            <span class="stat-icon">⟁</span>
            <span class="stat-val">{{ sensorStore.environment.barometric_pressure.toFixed(1) }}</span>
            <span class="stat-unit">hPa</span>
            <span class="stat-name">BAROMETER</span>
          </div>
          <div class="stat-card" :class="pressureDeltaClass">
            <span class="stat-icon">△</span>
            <span class="stat-val">{{ sensorStore.environment.pressure_delta_hpa >= 0 ? '+' : '' }}{{ sensorStore.environment.pressure_delta_hpa.toFixed(2) }}</span>
            <span class="stat-unit">ΔhPa</span>
            <span class="stat-name">PRESSURE DELTA</span>
          </div>
        </div>

        <!-- Light Level Chart (Line) -->
        <div class="chart-block">
          <div class="chart-label">AMBIENT LIGHT (lux) — 100 SAMPLE ROLLING</div>
          <canvas ref="lightChartRef" class="hud-canvas"></canvas>
        </div>

        <!-- Pressure Bar Chart -->
        <div class="chart-block">
          <div class="chart-label">BAROMETRIC PRESSURE TREND (hPa)</div>
          <canvas ref="pressureChartRef" class="hud-canvas"></canvas>
        </div>

        <!-- Pressure Delta Line -->
        <div class="chart-block">
          <div class="chart-label">PRESSURE DELTA (ΔhPa) — FALL INDICATOR</div>
          <canvas ref="pressureDeltaChartRef" class="hud-canvas"></canvas>
        </div>

        <!-- Magnetometer readout -->
        <div class="mag-panel">
          <span class="panel-micro-label">MAGNETOMETER (µT)</span>
          <div class="mag-grid">
            <div class="mag-item"><span>MX</span><b>{{ sensorStore.imu.magnetometer.x.toFixed(2) }}</b></div>
            <div class="mag-item"><span>MY</span><b>{{ sensorStore.imu.magnetometer.y.toFixed(2) }}</b></div>
            <div class="mag-item"><span>MZ</span><b>{{ sensorStore.imu.magnetometer.z.toFixed(2) }}</b></div>
          </div>
        </div>
      </div>

      <!-- ── COL 3: Activity + GPS Panel ── -->
      <div class="sv-col act-col">
        <div class="panel-header">
          <span class="panel-tag">[ ACTIVITY // LOCATION ]</span>
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
              {{ sensorStore.activity.activity_type.toUpperCase() }}
            </span>
          </div>
        </div>

        <!-- Wrist Motion Chart -->
        <div class="chart-block">
          <div class="chart-label">WRIST MOTION MAGNITUDE (20 READINGS)</div>
          <canvas ref="wristChartRef" class="hud-canvas"></canvas>
        </div>

        <!-- Steps Rate Chart -->
        <div class="chart-block">
          <div class="chart-label">CUMULATIVE STEP COUNT</div>
          <canvas ref="stepsChartRef" class="hud-canvas"></canvas>
        </div>

        <!-- GPS Location Card -->
        <div class="gps-panel">
          <div class="panel-header" style="margin-bottom:8px;">
            <span class="panel-tag">[ GPS LOCATION ]</span>
            <span class="panel-status" :class="sensorStore.locStatus.toLowerCase()">{{ sensorStore.locStatus }}</span>
          </div>
          <div class="gps-grid">
            <div class="gps-item">
              <span class="gps-label">LATITUDE</span>
              <span class="gps-val">{{ sensorStore.location.latitude.toFixed(6) }}°</span>
            </div>
            <div class="gps-item">
              <span class="gps-label">LONGITUDE</span>
              <span class="gps-val">{{ sensorStore.location.longitude.toFixed(6) }}°</span>
            </div>
            <div class="gps-item">
              <span class="gps-label">ALTITUDE</span>
              <span class="gps-val">{{ sensorStore.location.altitude.toFixed(1) }} m</span>
            </div>
          </div>
          <!-- Map placeholder -->
          <div class="map-placeholder">
            <span class="map-reticle">+</span>
            <span class="map-label">
              {{ sensorStore.location.latitude === 0 && sensorStore.location.longitude === 0
                ? '[ AWAITING GPS SIGNAL ]'
                : `${sensorStore.location.latitude.toFixed(4)}, ${sensorStore.location.longitude.toFixed(4)}` }}
            </span>
            <div class="map-grid-lines"></div>
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
import DeviceIpConfigModal from '../components/DeviceIpConfigModal.vue'

Chart.register(...registerables)

const sensorStore = useSensorTelemetryStore()
const cfg = useDeviceConfigStore()

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
const sensorBadges = computed(() => [
  { key: 'accel',  name: 'ACCEL',   icon: '↗', status: sensorStore.imuStatus },
  { key: 'gyro',   name: 'GYRO',    icon: '⟲', status: sensorStore.imuStatus },
  { key: 'mag',    name: 'MAG',     icon: '⊕', status: sensorStore.imuStatus },
  { key: 'orient', name: 'ORIENT',  icon: '⧈', status: sensorStore.imuStatus },
  { key: 'comp',   name: 'COMPASS', icon: '◎', status: sensorStore.imuStatus },
  { key: 'grav',   name: 'GRAVITY', icon: '↓', status: sensorStore.imuStatus },
  { key: 'light',  name: 'LIGHT',   icon: '☀', status: sensorStore.envStatus },
  { key: 'baro',   name: 'BARO',    icon: '⟁', status: sensorStore.envStatus },
  { key: 'loc',    name: 'GPS',     icon: '◉', status: sensorStore.locStatus },
  { key: 'steps',  name: 'PEDOMETER', icon: '⊞', status: sensorStore.actStatus },
  { key: 'act',    name: 'ACTIVITY',  icon: '⊿', status: sensorStore.actStatus },
  { key: 'wrist',  name: 'WRIST',     icon: '〜', status: sensorStore.actStatus },
  { key: 'hr',     name: 'HEART',     icon: '♥', status: 'LIVE' as const }, // from vitals store
])

// ── 3D Cube transform ─────────────────────────────────────────────────────────
const cubeStyle = computed(() => {
  const { roll, pitch, yaw } = sensorStore.eulerAngles
  return {
    transform: `rotateX(${-pitch}deg) rotateY(${yaw}deg) rotateZ(${roll}deg)`,
    transition: 'transform 0.1s linear',
  }
})

function absVal(v: number) { return Math.abs(v) }

// ── Light/pressure status classes ─────────────────────────────────────────────
const lightClass = computed(() => {
  const lux = sensorStore.environment.ambient_light
  if (lux < 10) return 'card-warn'
  if (lux > 10000) return 'card-warn'
  return 'card-ok'
})

const pressureDeltaClass = computed(() => {
  const d = Math.abs(sensorStore.environment.pressure_delta_hpa)
  if (d > 5) return 'card-danger'
  if (d > 2) return 'card-warn'
  return 'card-ok'
})

// ── Activity ──────────────────────────────────────────────────────────────────
const activityIcon = computed(() => {
  const t = sensorStore.activity.activity_type.toLowerCase()
  if (t.includes('run')) return '🏃'
  if (t.includes('walk')) return '🚶'
  if (t.includes('still') || t === 'stationary') return '🧍'
  if (t.includes('cycle') || t.includes('bike')) return '🚴'
  return '⊿'
})

const stepDigits = computed(() => {
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
    { sensor: 'ACCEL X', current: imu.linear_acceleration.x.toFixed(3), unit: 'm/s²', key: 'ax', val: imu.linear_acceleration.x, statusClass: 'ok', status: sensorStore.imuStatus },
    { sensor: 'ACCEL Y', current: imu.linear_acceleration.y.toFixed(3), unit: 'm/s²', key: 'ay', val: imu.linear_acceleration.y, statusClass: 'ok', status: sensorStore.imuStatus },
    { sensor: 'ACCEL Z', current: imu.linear_acceleration.z.toFixed(3), unit: 'm/s²', key: 'az', val: imu.linear_acceleration.z, statusClass: 'ok', status: sensorStore.imuStatus },
    { sensor: 'GYRO X', current: imu.angular_velocity.x.toFixed(4), unit: 'rad/s', key: 'gx', val: imu.angular_velocity.x, statusClass: 'ok', status: sensorStore.imuStatus },
    { sensor: 'GYRO Y', current: imu.angular_velocity.y.toFixed(4), unit: 'rad/s', key: 'gy', val: imu.angular_velocity.y, statusClass: 'ok', status: sensorStore.imuStatus },
    { sensor: 'GYRO Z', current: imu.angular_velocity.z.toFixed(4), unit: 'rad/s', key: 'gz', val: imu.angular_velocity.z, statusClass: 'ok', status: sensorStore.imuStatus },
    { sensor: 'MAG X', current: imu.magnetometer.x.toFixed(2), unit: 'µT', key: 'mx', val: imu.magnetometer.x, statusClass: 'ok', status: sensorStore.imuStatus },
    { sensor: 'MAG Y', current: imu.magnetometer.y.toFixed(2), unit: 'µT', key: 'my', val: imu.magnetometer.y, statusClass: 'ok', status: sensorStore.imuStatus },
    { sensor: 'MAG Z', current: imu.magnetometer.z.toFixed(2), unit: 'µT', key: 'mz', val: imu.magnetometer.z, statusClass: 'ok', status: sensorStore.imuStatus },
    { sensor: 'COMPASS', current: imu.compass_heading.toFixed(1), unit: '°', key: 'comp', val: imu.compass_heading, statusClass: 'ok', status: sensorStore.imuStatus },
    { sensor: 'LIGHT', current: env.ambient_light.toFixed(0), unit: 'lux', key: 'lux', val: env.ambient_light, statusClass: 'ok', status: sensorStore.envStatus },
    { sensor: 'BAROMETER', current: env.barometric_pressure.toFixed(2), unit: 'hPa', key: 'baro', val: env.barometric_pressure, statusClass: 'ok', status: sensorStore.envStatus },
    { sensor: 'PRESSURE Δ', current: env.pressure_delta_hpa.toFixed(3), unit: 'ΔhPa', key: 'pdelta', val: env.pressure_delta_hpa, statusClass: Math.abs(env.pressure_delta_hpa) > 5 ? 'danger' : 'ok', status: sensorStore.envStatus },
    { sensor: 'LATITUDE', current: loc.latitude.toFixed(6), unit: '°', key: 'lat', val: loc.latitude, statusClass: 'ok', status: sensorStore.locStatus },
    { sensor: 'LONGITUDE', current: loc.longitude.toFixed(6), unit: '°', key: 'lon', val: loc.longitude, statusClass: 'ok', status: sensorStore.locStatus },
    { sensor: 'ALTITUDE', current: loc.altitude.toFixed(1), unit: 'm', key: 'alt', val: loc.altitude, statusClass: 'ok', status: sensorStore.locStatus },
    { sensor: 'STEPS', current: String(act.pedometer_steps), unit: 'steps', key: 'steps', val: act.pedometer_steps, statusClass: 'ok', status: sensorStore.actStatus },
    { sensor: 'ACTIVITY', current: act.activity_type.toUpperCase(), unit: '', key: 'acttype', val: 0, statusClass: 'ok', status: sensorStore.actStatus },
    { sensor: 'WRIST MAG', current: sensorStore.wristMagnitude.toFixed(3), unit: 'units', key: 'wrist', val: sensorStore.wristMagnitude, statusClass: 'ok', status: sensorStore.actStatus },
  ]

  return rows.map(r => {
    const mm = r.key !== 'acttype' ? trackMinMax(r.key, r.val) : { min: 0, max: 0 }
    return {
      ...r,
      min: r.key !== 'acttype' ? mm.min.toFixed(3) : '—',
      max: r.key !== 'acttype' ? mm.max.toFixed(3) : '—',
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

// ── Lifecycle ─────────────────────────────────────────────────────────────────
let _clockInterval: number | null = null
let _chartInterval: number | null = null

onMounted(async () => {
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
})

onUnmounted(() => {
  if (_clockInterval) clearInterval(_clockInterval)
  if (_chartInterval) clearInterval(_chartInterval)
  if (_pktInterval) clearInterval(_pktInterval)
  accelChart?.destroy()
  gyroChart?.destroy()
  lightChart?.destroy()
  pressureChart?.destroy()
  pressureDeltaChart?.destroy()
  wristChart?.destroy()
  stepsChart?.destroy()
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
.badge-stale { border-color: #FFB000; color: #FFB000; background: #FFB00008; }
.badge-offline { border-color: #FF333366; color: #FF3333; background: #FF333308; }
.badge-icon { font-size: 10px; }
.badge-name { color: inherit; }
.badge-state { font-size: 8px; opacity: 0.7; }

/* ─── Main Grid ────────────────────────────────────────────────────────────── */
.sv-main-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
  flex: 1;
}

.sv-col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  background: #0A0A0A;
  border: 1px solid #00FF6622;
  padding: 12px;
  backdrop-filter: blur(4px);
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
  border: 1px solid #00FF6622;
  background: #0A0A0A;
  padding: 10px;
}
.gps-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
  margin-bottom: 8px;
}
.gps-item { display: flex; flex-direction: column; gap: 2px; }
.gps-label { font-size: 8px; color: #00FF6666; letter-spacing: 1px; font-family: 'Roboto Mono', monospace; }
.gps-val { font-family: 'Roboto Mono', monospace; font-size: 10px; color: #00FF66; }
.map-placeholder {
  position: relative;
  height: 80px;
  background: #001010;
  border: 1px solid #00FF6622;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.map-reticle {
  position: absolute;
  top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  font-size: 20px;
  color: #00FF6688;
}
.map-label {
  font-family: 'Roboto Mono', monospace;
  font-size: 9px;
  color: #00FF6666;
  letter-spacing: 1px;
  z-index: 1;
}
.map-grid-lines {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(0,255,102,0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,255,102,0.05) 1px, transparent 1px);
  background-size: 20px 20px;
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
.pill-offline { border-color: #FF3333; color: #FF3333; }
.pill-danger { border-color: #FF3333; color: #FF3333; }

/* ─── Responsive ─────────────────────────────────────────────────────────── */
@media (max-width: 1200px) {
  .sv-main-grid { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 768px) {
  .sv-main-grid { grid-template-columns: 1fr; }
  .stat-row { grid-template-columns: 1fr 1fr; }
}
</style>
