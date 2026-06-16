<template>
  <div class="history-shell">

    <!-- ── Control Bar ──────────────────────────────────────────────────── -->
    <div class="history-controls-bar terminal-card">
      <div class="controls-left">
        <span class="hud text-dim">[ HISTORY_QUERY_PARAMETERS ]</span>
      </div>

      <div class="controls-right">
        <!-- Combobox dropdown select (Cyber-Cinematic style) -->
        <div class="cyber-combobox-wrapper">
          <select 
            v-model="selectedRange" 
            class="cyber-select mono" 
            @change="handleRangeChange"
          >
            <option value="6">6H</option>
            <option value="12">12H</option>
            <option value="24">24H</option>
            <option value="48">48H</option>
            <option value="72">72H</option>
            <option value="custom">[ CUSTOM ]</option>
          </select>
          <div class="select-arrow">//</div>
        </div>
      </div>
    </div>

    <!-- Custom date range picker panel (shows below the combobox) -->
    <transition name="slide-down">
      <div v-if="selectedRange === 'custom'" class="custom-datepicker-panel terminal-card mono">
        <div class="picker-fields">
          <div class="picker-group">
            <span class="text-dim text-prefix">&gt;&gt; FROM:</span>
            <input
              type="datetime-local"
              v-model="customFrom"
              class="tactical-input datetime-input"
              :max="customTo || undefined"
            />
          </div>
          <div class="picker-group">
            <span class="text-dim text-prefix">&gt;&gt; TO:</span>
            <input
              type="datetime-local"
              v-model="customTo"
              class="tactical-input datetime-input"
              :min="customFrom || undefined"
            />
          </div>
          <span v-if="customRangeLabel" class="text-cyan range-label-text">{{ customRangeLabel }}</span>
        </div>
        <button
          class="cmd-btn execute-btn"
          :disabled="!customFrom || !customTo || loading"
          @click="fetchCustomRange"
        >
          &gt;&gt; EXECUTE_QUERY
        </button>
      </div>
    </transition>

    <!-- ── Loading ──────────────────────────────────────────────────────── -->
    <div v-if="loading" class="loading-state terminal-card">
      <div class="seg-progress-wrapper">
        <div class="seg-progress-label mono">STATUS: FETCHING HEALTH ARCHIVE...</div>
        <div class="seg-progress-track">
          <div v-for="i in 20" :key="i"
               :class="['seg-progress-block', i <= loadingProgress ? 'active' : '']" />
        </div>
      </div>
    </div>

    <!-- ── API Error (real, not suppressed) ────────────────────────────── -->
    <div v-else-if="apiError" class="error-state terminal-card">
      <span class="text-red mono">&gt;&gt;&gt; [DATA_FETCH_ERROR] {{ apiError }}</span>
      <button class="cmd-btn mt-2" @click="retryFetch" style="font-size:9px;">
        &gt;&gt; RETRY
      </button>
    </div>

    <!-- ── Charts Grid ──────────────────────────────────────────────────── -->
    <div v-else class="charts-grid">

      <!-- Heart Rate Timeline -->
      <div class="terminal-card chart-card corner-reticle">
        <div class="terminal-card-header">
          [ HEART_RATE_TIMELINE ]
          <span class="chart-stat" :class="stats.avgHr !== '--' ? 'text-green glow-green' : 'text-dim'">
            AVG: {{ stats.avgHr !== '--' ? stats.avgHr + ' bpm' : '--bpm' }}
            | MAX: {{ stats.maxHr !== '--' ? stats.maxHr + ' bpm' : '--bpm' }}
            | MIN: {{ stats.minHr !== '--' ? stats.minHr + ' bpm' : '--bpm' }}
          </span>
        </div>
        <div v-if="!hourlyBuckets.length" class="no-data-overlay mono text-dim">
          NO_RECORDS — SENSOR NOT YET ACTIVE OR NO DATA IN RANGE
        </div>
        <div class="chart-container">
          <canvas ref="hrChartCanvas"></canvas>
        </div>
      </div>

      <!-- SpO2 + Blood Pressure -->
      <div class="terminal-card chart-card corner-reticle">
        <div class="terminal-card-header">
          [ SPO2_&amp;_BLOOD_PRESSURE ]
          <span class="chart-stat text-cyan">
            AVG SpO₂: {{ stats.avgSpo2 !== '--' ? stats.avgSpo2 + '%' : '--' }}
            | AVG SYS: {{ stats.avgSystolic !== '--' ? stats.avgSystolic + ' mmHg' : '--' }}
          </span>
        </div>
        <div v-if="!hourlyBuckets.length" class="no-data-overlay mono text-dim">
          NO_RECORDS — SENSOR NOT YET ACTIVE OR NO DATA IN RANGE
        </div>
        <div class="chart-container">
          <canvas ref="spo2ChartCanvas"></canvas>
        </div>
      </div>

      <!-- Alert Level Distribution -->
      <div class="terminal-card chart-card corner-reticle" style="grid-column: 1 / -1;">
        <div class="terminal-card-header">
          [ ALERT_LEVEL_DISTRIBUTION // {{ rangeLabel }} ]
          <span class="chart-stat text-dim" style="font-size:8px;">
            {{ hourlyBuckets.length }} BUCKETS | {{ totalSamples }} SAMPLES
          </span>
        </div>

        <div v-if="!hourlyBuckets.length" class="no-data-overlay mono text-dim">
          NO_RECORDS_IN_RANGE — START WEARING WRISTBAND TO SEE VITALS HISTORY
        </div>

        <div class="alert-dist-grid">
          <div
            v-for="bucket in hourlyBuckets"
            :key="bucket.bucket_hour"
            class="hour-bucket"
            :title="`${formatHour(bucket.bucket_hour)}\nHR: ${bucket.avg_hr ?? '--'}bpm\nSpO₂: ${bucket.avg_spo2?.toFixed(1) ?? '--'}%\nSamples: ${bucket.sample_count ?? 0}`"
          >
            <div
              class="bucket-bar"
              :class="alertClass(bucket.worst_alert)"
              :style="{ height: hrToPercent(bucket.avg_hr) + '%' }"
            ></div>
            <div class="bucket-label mono text-dim">{{ formatHour(bucket.bucket_hour) }}</div>
          </div>
        </div>

        <div class="dist-legend">
          <span class="legend-item"><span class="dot normal"></span>NORMAL</span>
          <span class="legend-item"><span class="dot warning"></span>WARNING</span>
          <span class="legend-item"><span class="dot critical"></span>CRITICAL</span>
          <span class="legend-item"><span class="dot stroke"></span>STROKE</span>
          <span class="legend-item text-dim" style="margin-left:auto;">
            SRC: {{ dataSource }}
          </span>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Chart, registerables } from 'chart.js'
import api from '../services/api'
import { useVitalsStore } from '../stores/vitals'

Chart.register(...registerables)

// ─── Types ─────────────────────────────────────────────────────────────────
interface HourlyBucket {
  bucket_hour: string
  avg_hr: number | null
  max_hr: number | null
  min_hr: number | null
  avg_systolic: number | null
  avg_spo2: number | null
  avg_temp: number | null
  sample_count: number | null
  worst_alert: string | null
}

// ─── State ──────────────────────────────────────────────────────────────────
const loading        = ref(false)
const loadingProgress = ref(0)
const apiError       = ref('')       // Real errors — NOT suppressed
const dataSource     = ref('--')     // 'LIVE_DB' | 'OFFLINE_MOCK'

const activeMode     = ref<'preset' | 'custom'>('preset')
const activeHours    = ref(24)
const showCustomPicker = ref(false)
const customFrom     = ref('')       // datetime-local string
const customTo       = ref('')
const customRangeLabel = ref('')
const selectedRange  = ref<string>('24')

const vitalsStore = useVitalsStore()
const hourlyBuckets = computed({
  get: () => vitalsStore.hourlyBuckets,
  set: (val) => { vitalsStore.hourlyBuckets = val }
})

const hrChartCanvas  = ref<HTMLCanvasElement | null>(null)
const spo2ChartCanvas = ref<HTMLCanvasElement | null>(null)
let hrChart: Chart | null = null
let spo2Chart: Chart | null = null
let progressTimer: number | null = null

// ─── Computed Stats ─────────────────────────────────────────────────────────
const stats = computed(() => {
  const buckets = hourlyBuckets.value
  if (!buckets.length) {
    return { avgHr: '--', maxHr: '--', minHr: '--', avgSpo2: '--', avgSystolic: '--' }
  }
  const hrs      = buckets.map(b => b.avg_hr).filter((v): v is number => v != null && v > 0)
  const spo2s    = buckets.map(b => b.avg_spo2).filter((v): v is number => v != null && v > 0)
  const systolics = buckets.map(b => b.avg_systolic).filter((v): v is number => v != null && v > 0)
  const maxHrs   = buckets.map(b => b.max_hr).filter((v): v is number => v != null && v > 0)
  const minHrs   = buckets.map(b => b.min_hr).filter((v): v is number => v != null && v > 0)

  return {
    avgHr:      hrs.length      ? Math.round(hrs.reduce((a, b) => a + b, 0) / hrs.length) : '--',
    maxHr:      maxHrs.length   ? Math.max(...maxHrs)                                        : '--',
    minHr:      minHrs.length   ? Math.min(...minHrs)                                        : '--',
    avgSpo2:    spo2s.length    ? (spo2s.reduce((a, b) => a + b, 0) / spo2s.length).toFixed(1) : '--',
    avgSystolic: systolics.length ? Math.round(systolics.reduce((a, b) => a + b, 0) / systolics.length) : '--',
  }
})

const totalSamples = computed(() =>
  hourlyBuckets.value.reduce((sum, b) => sum + (b.sample_count ?? 0), 0)
)

const rangeLabel = computed(() => {
  if (activeMode.value === 'custom' && customRangeLabel.value) return customRangeLabel.value
  return `${activeHours.value}H`
})

// ─── Fetch: Preset range ────────────────────────────────────────────────────
async function fetchHistory() {
  loading.value     = true
  apiError.value    = ''
  loadingProgress.value = 0
  startProgressSim()

  try {
    const resp = await api.get('/health/history/hourly', {
      params: { hours: activeHours.value }
    })
    const rawData = resp.data?.data ?? []
    const data: HourlyBucket[] = rawData.map((b: any) => ({
      bucket_hour: b.bucketHour ?? b.bucket_hour,
      avg_hr: b.avgHr ?? b.avg_hr,
      max_hr: b.maxHr ?? b.max_hr,
      min_hr: b.minHr ?? b.min_hr,
      avg_systolic: b.avgSystolic ?? b.avg_systolic,
      avg_spo2: b.avgSpo2 ?? b.avg_spo2,
      avg_temp: b.avgTemp ?? b.avg_temp,
      sample_count: b.sampleCount ?? b.sample_count,
      worst_alert: b.worstAlert ?? b.worst_alert
    }))
    hourlyBuckets.value = data
    dataSource.value = data.length > 0 ? 'LIVE_DB' : 'LIVE_DB (EMPTY)'
    loadingProgress.value = 20
  } catch (e: any) {
    const status = e.response?.status
    apiError.value = status
      ? `HTTP ${status}: ${e.response?.data?.message ?? e.message}`
      : `CONNECTION_FAILED: ${e.message}`
    dataSource.value = 'ERROR'
  } finally {
    stopProgressSim()
    loading.value = false
    await renderCharts()
  }
}

// ─── Fetch: Custom date range ────────────────────────────────────────────────
async function fetchCustomRange() {
  if (!customFrom.value || !customTo.value) return

  loading.value     = true
  apiError.value    = ''
  loadingProgress.value = 0
  activeMode.value  = 'custom'
  startProgressSim()

  const from = new Date(customFrom.value)
  const to   = new Date(customTo.value)

  // Format for display
  const fmtDate = (d: Date) => d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  customRangeLabel.value = `${fmtDate(from)} → ${fmtDate(to)}`

  try {
    const resp = await api.get('/health/history/range', {
      params: {
        fromDate: from.toISOString().slice(0, 19),  // ISO8601 without Z
        toDate:   to.toISOString().slice(0, 19),
      }
    })
    const rawData = resp.data?.data ?? []
    const data: HourlyBucket[] = rawData.map((b: any) => ({
      bucket_hour: b.bucketHour ?? b.bucket_hour,
      avg_hr: b.avgHr ?? b.avg_hr,
      max_hr: b.maxHr ?? b.max_hr,
      min_hr: b.minHr ?? b.min_hr,
      avg_systolic: b.avgSystolic ?? b.avg_systolic,
      avg_spo2: b.avgSpo2 ?? b.avg_spo2,
      avg_temp: b.avgTemp ?? b.avg_temp,
      sample_count: b.sampleCount ?? b.sample_count,
      worst_alert: b.worstAlert ?? b.worst_alert
    }))
    hourlyBuckets.value = data
    dataSource.value = data.length > 0 ? 'LIVE_DB' : 'LIVE_DB (EMPTY)'
    loadingProgress.value = 20
  } catch (e: any) {
    const status = e.response?.status
    apiError.value = status
      ? `HTTP ${status}: ${e.response?.data?.message ?? e.message}`
      : `CONNECTION_FAILED: ${e.message}`
  } finally {
    stopProgressSim()
    loading.value = false
    await renderCharts()
  }
}

function retryFetch() {
  if (activeMode.value === 'custom') {
    fetchCustomRange()
  } else {
    fetchHistory()
  }
}

// ─── UI Controls ────────────────────────────────────────────────────────────
function handleRangeChange() {
  if (selectedRange.value === 'custom') {
    activeMode.value = 'custom'
    showCustomPicker.value = true
    if (!customTo.value) {
      // Pre-fill: last 24h
      const now = new Date()
      const yesterday = new Date(now.getTime() - 24 * 3600_000)
      customTo.value   = toLocalDateTimeInput(now)
      customFrom.value = toLocalDateTimeInput(yesterday)
    }
  } else {
    activeMode.value = 'preset'
    showCustomPicker.value = false
    activeHours.value = parseInt(selectedRange.value, 10)
    fetchHistory()
  }
}

function toLocalDateTimeInput(d: Date): string {
  // datetime-local requires YYYY-MM-DDTHH:mm format in local time
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ─── Progress Simulation ─────────────────────────────────────────────────────
function startProgressSim() {
  stopProgressSim()
  progressTimer = window.setInterval(() => {
    if (loadingProgress.value < 18) loadingProgress.value++
  }, 80)
}
function stopProgressSim() {
  if (progressTimer != null) { clearInterval(progressTimer); progressTimer = null }
}

// ─── Chart.js Rendering ──────────────────────────────────────────────────────
const COLORS = {
  green:  '#00FF66',
  cyan:   '#00E5FF',
  orange: '#FFB000',
  red:    '#FF3333',
  dimGreen: 'rgba(0,255,102,0.12)',
  dimCyan:  'rgba(0,229,255,0.10)',
  grid:   'rgba(0,255,102,0.06)',
}

const FONT = { data: 'Roboto Mono', hud: 'Orbitron' }

const BASE_OPTS = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 350 },
  plugins: {
    legend: {
      labels: { color: COLORS.green, font: { family: FONT.data, size: 10 } }
    },
    tooltip: {
      backgroundColor: '#0d0d0d',
      borderColor: COLORS.green,
      borderWidth: 1,
      titleColor: COLORS.green,
      bodyColor: '#E0FFE8',
      titleFont: { family: FONT.hud, size: 9 },
      bodyFont:  { family: FONT.data, size: 10 },
    },
  },
  scales: {
    x: {
      grid:  { color: COLORS.grid },
      ticks: { color: '#5a5a5a', font: { family: FONT.data, size: 9 }, maxTicksLimit: 10 },
    },
    y: {
      grid:  { color: COLORS.grid },
      ticks: { color: COLORS.green, font: { family: FONT.data, size: 9 } },
    },
  },
}

async function renderCharts() {
  // Guard: DOM elements must exist (v-else ensures this)
  await new Promise(r => setTimeout(r, 20))  // Tick for v-else to settle
  if (!hrChartCanvas.value || !spo2ChartCanvas.value) return

  const labels      = hourlyBuckets.value.map(b => formatHour(b.bucket_hour))
  const hrData      = hourlyBuckets.value.map(b => b.avg_hr)
  const maxHrData   = hourlyBuckets.value.map(b => b.max_hr)
  const minHrData   = hourlyBuckets.value.map(b => b.min_hr)
  const spo2Data    = hourlyBuckets.value.map(b => b.avg_spo2)
  const systolicData = hourlyBuckets.value.map(b => b.avg_systolic)

  hrChart?.destroy()
  spo2Chart?.destroy()

  hrChart = new Chart(hrChartCanvas.value, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'AVG HR (bpm)',
          data: hrData,
          borderColor: COLORS.green,
          backgroundColor: COLORS.dimGreen,
          borderWidth: 1.5,
          pointRadius: 2,
          fill: true,
          tension: 0.2,
        },
        {
          label: 'MAX HR',
          data: maxHrData,
          borderColor: 'rgba(0,255,102,0.35)',
          borderWidth: 1,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
          tension: 0.2,
        },
        {
          label: 'MIN HR',
          data: minHrData,
          borderColor: 'rgba(0,229,255,0.35)',
          borderWidth: 1,
          borderDash: [2, 6],
          pointRadius: 0,
          fill: false,
          tension: 0.2,
        },
      ]
    },
    options: {
      ...BASE_OPTS,
      scales: {
        ...BASE_OPTS.scales,
        y: {
          ...BASE_OPTS.scales.y,
          min: 40, max: 180,
          title: { display: true, text: 'BPM', color: '#5a5a5a', font: { size: 9 } }
        }
      }
    } as any
  })

  spo2Chart = new Chart(spo2ChartCanvas.value, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'SpO₂ (%)',
          data: spo2Data,
          borderColor: COLORS.cyan,
          backgroundColor: COLORS.dimCyan,
          borderWidth: 1.5,
          pointRadius: 2,
          fill: true,
          tension: 0.2,
          yAxisID: 'ySpo2',
        },
        {
          label: 'SYSTOLIC (mmHg)',
          data: systolicData,
          borderColor: COLORS.orange,
          backgroundColor: 'rgba(255,176,0,0.07)',
          borderWidth: 1,
          pointRadius: 2,
          tension: 0.2,
          yAxisID: 'ySys',
        }
      ]
    },
    options: {
      ...BASE_OPTS,
      scales: {
        x: BASE_OPTS.scales.x,
        ySpo2: {
          ...BASE_OPTS.scales.y,
          min: 80, max: 100,
          position: 'left' as const,
          title: { display: true, text: 'SpO₂ %', color: '#5a5a5a', font: { size: 9 } }
        },
        ySys: {
          ...BASE_OPTS.scales.y,
          min: 80, max: 200,
          position: 'right' as const,
          title: { display: true, text: 'mmHg', color: '#5a5a5a', font: { size: 9 } },
          grid: { color: 'transparent' }
        },
      }
    } as any
  })
}

// generateMockData deleted completely as per specs

// ─── Helpers ─────────────────────────────────────────────────────────────────
function formatHour(iso: string): string {
  try {
    const d = new Date(iso)
    return `${d.getMonth()+1}/${d.getDate()} ${d.getHours().toString().padStart(2,'0')}:00`
  } catch { return '--:--' }
}

function hrToPercent(hr: number | null): number {
  if (!hr) return 10
  return Math.min(95, Math.max(10, ((hr - 40) / 140) * 100))
}

function alertClass(level: string | null): string {
  const map: Record<string, string> = {
    NORMAL: 'normal', WARNING: 'warning', CRITICAL: 'critical', STROKE: 'stroke'
  }
  return map[level ?? ''] ?? 'normal'
}

// ─── Lifecycle ────────────────────────────────────────────────────────────────
onMounted(fetchHistory)
onUnmounted(() => {
  hrChart?.destroy()
  spo2Chart?.destroy()
  stopProgressSim()
})

watch(() => vitalsStore.hourlyBuckets, async () => {
  await renderCharts()
}, { deep: true })
</script>

<style scoped>
.history-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg-void);
  gap: 0;
}

/* ── Control bar ──────────────────────────────────────────────────── */
.history-controls-bar {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 8px 8px 0;
  padding: 6px 16px;
}

.controls-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.controls-right {
  display: flex;
  align-items: center;
}

/* ── Cyber-Cinematic Select/Combobox ────────────────────────────────── */
.cyber-combobox-wrapper {
  position: relative;
  display: inline-block;
}

.cyber-select {
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  background: #000000;
  border: 1px solid var(--color-accent-cyan, #00e5ff);
  color: var(--color-accent-cyan, #00e5ff);
  font-family: var(--font-data, 'Roboto Mono');
  font-size: 10px;
  padding: 4px 28px 4px 10px;
  outline: none;
  cursor: pointer;
  border-radius: 0;
  min-width: 120px;
  transition: all 0.2s ease;
}

.cyber-select:focus, .cyber-select:hover {
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.4);
  border-color: var(--color-accent-cyan, #00e5ff);
}

.select-arrow {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-accent-cyan, #00e5ff);
  font-size: 8px;
  pointer-events: none;
  font-family: var(--font-data, 'Roboto Mono');
  letter-spacing: -1px;
}

/* ── Custom date picker panel ─────────────────────────────────────── */
.custom-datepicker-panel {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin: 4px 8px 0;
  padding: 6px 16px;
  background: rgba(10, 10, 10, 0.85);
  border: 1px solid var(--color-accent-cyan, #00e5ff);
  backdrop-filter: blur(12px);
}

.picker-fields {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 12px;
  flex: 1;
  flex-wrap: wrap;
}

.picker-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.text-prefix {
  font-size: 10px;
  color: var(--color-accent-cyan, #00e5ff);
  letter-spacing: 0.1em;
}

.execute-btn {
  font-size: 9px;
  padding: 4px 16px;
  background: #000;
  border: 1px solid var(--color-accent-cyan, #00e5ff);
  color: var(--color-accent-cyan, #00e5ff);
  cursor: pointer;
  white-space: nowrap;
}

.execute-btn:hover {
  background: var(--color-accent-cyan, #00e5ff);
  color: #000;
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.5);
}

.execute-btn:disabled {
  border-color: var(--color-border-dim);
  color: var(--color-text-dim);
  cursor: not-allowed;
  box-shadow: none;
}

.range-label-text {
  font-size: 9px;
  color: var(--color-accent-cyan, #00e5ff);
}

.datetime-input {
  background: #000;
  border: 1px solid var(--color-border-dim);
  color: var(--color-accent-cyan);
  font-family: var(--font-data);
  font-size: 10px;
  padding: 3px 6px;
  outline: none;
  color-scheme: dark;
}
.datetime-input:focus {
  border-color: var(--color-accent-cyan);
  box-shadow: 0 0 6px rgba(0, 229, 255, 0.3);
}

/* Slide down transition */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.25s ease-out;
}
.slide-down-enter-from,
.slide-down-leave-to {
  transform: translateY(-10px);
  opacity: 0;
}

/* ── States ──────────────────────────────────────────────────────── */
.loading-state, .error-state {
  margin: 8px;
  padding: 24px;
}

.no-data-overlay {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--color-text-dim);
  padding: 16px;
  text-align: center;
}

/* ── Charts grid ─────────────────────────────────────────────────── */
.charts-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr auto;
  gap: 8px;
  padding: 8px;
  overflow: hidden;
  min-height: 0;
}

.chart-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.terminal-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.chart-stat {
  font-size: 8px;
  letter-spacing: 0.08em;
  margin-left: auto;
  text-align: right;
}

.chart-container {
  flex: 1;
  min-height: 0;
  position: relative;
}
.chart-container canvas {
  width: 100% !important;
  height: 100% !important;
}

/* ── Alert distribution ──────────────────────────────────────────── */
.alert-dist-grid {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  height: 80px;
  padding: 4px;
  margin-top: 8px;
  overflow-x: auto;
  overflow-y: hidden;
}

.hour-bucket {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  flex: 1;
  min-width: 0;
  height: 100%;
  cursor: default;
  transition: opacity 0.15s;
}
.hour-bucket:hover { opacity: 0.8; }

.bucket-bar {
  width: 100%;
  min-height: 2px;
  transition: height 300ms ease;
  border-radius: 1px 1px 0 0;
}
.bucket-bar.normal   { background: var(--color-accent-green); }
.bucket-bar.warning  { background: var(--color-accent-orange); }
.bucket-bar.critical { background: var(--color-accent-red); }
.bucket-bar.stroke   { background: #FF0000; animation: blink-danger 0.5s step-end infinite; }

@keyframes blink-danger { 50% { opacity: 0.2; } }

.bucket-label {
  font-size: 7px;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.dist-legend {
  display: flex;
  gap: 16px;
  padding: 6px 4px;
  border-top: 1px solid var(--color-border-dim);
  flex-wrap: wrap;
  align-items: center;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 9px;
  color: var(--color-text-dim);
  font-family: var(--font-hud);
  letter-spacing: 0.1em;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 1px;
  flex-shrink: 0;
}
.dot.normal   { background: var(--color-accent-green); }
.dot.warning  { background: var(--color-accent-orange); }
.dot.critical { background: var(--color-accent-red); }
.dot.stroke   { background: #FF0000; }
</style>
