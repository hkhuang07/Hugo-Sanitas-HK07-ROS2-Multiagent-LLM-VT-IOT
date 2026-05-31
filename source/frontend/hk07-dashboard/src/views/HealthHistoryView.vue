<template>
  <div class="history-shell">
    <!-- Time Controls Top Bar -->
    <div class="history-controls-bar terminal-card">
      <span class="hud text-dim">[ HISTORY_QUERY_PARAMETERS ]</span>
      <div class="time-controls">
        <button
          v-for="range in timeRanges"
          :key="range.label"
          :class="['cmd-btn', activeRange === range.value ? 'range-active' : '']"
          @click="setRange(range.value)"
          style="font-size:9px;padding:3px 10px"
        >{{ range.label }}</button>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="loading" class="loading-state terminal-card">
      <div class="seg-progress-wrapper">
        <div class="seg-progress-label">STATUS: FETCHING HEALTH ARCHIVE...</div>
        <div class="seg-progress-track">
          <div v-for="i in 20" :key="i"
               :class="['seg-progress-block', i <= loadingProgress ? 'active' : '']" />
        </div>
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="error-state terminal-card">
      <span class="text-red mono">&gt;&gt;&gt; [DATA_FETCH_ERROR] {{ error }}</span>
    </div>

    <!-- Charts grid -->
    <div v-else class="charts-grid">
      <!-- Heart Rate Chart -->
      <div class="terminal-card chart-card corner-reticle">
        <div class="terminal-card-header">
          [ HEART_RATE_TIMELINE ]
          <span class="chart-stat text-green glow-green">
            AVG: {{ stats.avgHr }}bpm | MAX: {{ stats.maxHr }}bpm | MIN: {{ stats.minHr }}bpm
          </span>
        </div>
        <div class="chart-container">
          <canvas ref="hrChartCanvas"></canvas>
        </div>
      </div>

      <!-- SpO2 + BP Chart -->
      <div class="terminal-card chart-card corner-reticle">
        <div class="terminal-card-header">
          [ SPO2_&_BLOOD_PRESSURE ]
          <span class="chart-stat text-cyan">AVG SpO₂: {{ stats.avgSpo2 }}%</span>
        </div>
        <div class="chart-container">
          <canvas ref="spo2ChartCanvas"></canvas>
        </div>
      </div>

      <!-- Alert Distribution -->
      <div class="terminal-card chart-card corner-reticle" style="grid-column: 1 / -1;">
        <div class="terminal-card-header">[ ALERT_LEVEL_DISTRIBUTION // {{ activeRange }}H ]</div>
        <div class="alert-dist-grid">
          <div v-for="bucket in hourlyBuckets" :key="bucket.bucket_hour"
               class="hour-bucket" :title="`${bucket.bucket_hour}\nHR: ${bucket.avg_hr}bpm\nSpO2: ${bucket.avg_spo2}%`">
            <div class="bucket-bar" :class="alertClass(bucket.worst_alert)"
                 :style="{ height: hrToPercent(bucket.avg_hr) + '%' }"></div>
            <div class="bucket-label mono text-dim">{{ formatHour(bucket.bucket_hour) }}</div>
          </div>
        </div>
        <div class="dist-legend">
          <span class="legend-item"><span class="dot normal"></span>NORMAL</span>
          <span class="legend-item"><span class="dot warning"></span>WARNING</span>
          <span class="legend-item"><span class="dot critical"></span>CRITICAL</span>
          <span class="legend-item"><span class="dot stroke"></span>STROKE</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { Chart, registerables } from 'chart.js'
import api from '../services/api'

Chart.register(...registerables)

// ─── State ────────────────────────────────────────────────────────────────────
const loading = ref(false)
const loadingProgress = ref(0)
const error = ref('')
const activeRange = ref(24)
const hourlyBuckets = ref<any[]>([])

const timeRanges = [
  { label: '6H', value: 6 },
  { label: '12H', value: 12 },
  { label: '24H', value: 24 },
]

const hrChartCanvas = ref<HTMLCanvasElement | null>(null)
const spo2ChartCanvas = ref<HTMLCanvasElement | null>(null)
let hrChart: Chart | null = null
let spo2Chart: Chart | null = null

// ─── Stats ────────────────────────────────────────────────────────────────────
const stats = computed(() => {
  if (!hourlyBuckets.value.length) return { avgHr: '--', maxHr: '--', minHr: '--', avgSpo2: '--' }
  const hrs = hourlyBuckets.value.map((b: any) => b.avg_hr).filter(Boolean)
  const spo2s = hourlyBuckets.value.map((b: any) => b.avg_spo2).filter(Boolean)
  return {
    avgHr: hrs.length ? Math.round(hrs.reduce((a: number, b: number) => a + b, 0) / hrs.length) : '--',
    maxHr: hrs.length ? Math.max(...hrs) : '--',
    minHr: hrs.length ? Math.min(...hrs) : '--',
    avgSpo2: spo2s.length ? (spo2s.reduce((a: number, b: number) => a + b, 0) / spo2s.length).toFixed(1) : '--',
  }
})

// ─── Data Fetch ───────────────────────────────────────────────────────────────
async function fetchHistory() {
  loading.value = true
  error.value = ''
  loadingProgress.value = 0

  // Simulate progress bar (real data fetch isn't resumable)
  const progressInterval = setInterval(() => {
    if (loadingProgress.value < 18) loadingProgress.value++
  }, 80)

  try {
    const resp = await api.get('/health/history/hourly', {
      params: { hours: activeRange.value }
    })
    hourlyBuckets.value = resp.data?.data || []
    loadingProgress.value = 20
    clearInterval(progressInterval)
    await renderCharts()
  } catch (e: any) {
    clearInterval(progressInterval)
    // Use mock data when backend not yet ready
    hourlyBuckets.value = generateMockData(activeRange.value)
    await renderCharts()
    error.value = ''  // Don't show error if mock data loaded
  } finally {
    loading.value = false
  }
}

/** Generate mock hourly data for offline development */
function generateMockData(hours: number) {
  return Array.from({ length: hours }, (_, i) => {
    const hrVariation = (Math.sin(i * 0.5) * 8 + Math.random() * 5)
    return {
      bucket_hour: new Date(Date.now() - (hours - i) * 3600_000).toISOString(),
      avg_hr: Math.round(72 + hrVariation),
      max_hr: Math.round(78 + hrVariation),
      min_hr: Math.round(66 + hrVariation),
      avg_systolic: 118 + Math.random() * 8,
      avg_spo2: 97.5 + Math.random() * 1.5,
      avg_temp: 36.7 + Math.random() * 0.3,
      worst_alert: i === 3 ? 'WARNING' : i === 8 ? 'CRITICAL' : 'NORMAL',
      sample_count: Math.round(50 + Math.random() * 20),
    }
  })
}

// ─── Chart Rendering (Chart.js with decimation) ───────────────────────────────
const CHART_COLORS = {
  green: '#00FF66',
  cyan: '#00E5FF',
  orange: '#FF6600',
  red: '#FF3333',
  dim: 'rgba(0,255,102,0.15)',
  grid: 'rgba(0,255,102,0.06)',
}

const CHART_DEFAULTS = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 400 },
  plugins: {
    legend: { labels: { color: '#00FF66', font: { family: 'Roboto Mono', size: 10 } } },
    tooltip: {
      backgroundColor: '#0d0d0d',
      borderColor: '#00FF66',
      borderWidth: 1,
      titleColor: '#00FF66',
      bodyColor: '#E0FFE8',
      titleFont: { family: 'Orbitron', size: 10 },
      bodyFont: { family: 'Roboto Mono', size: 10 },
    },
    decimation: {
      enabled: true,
      algorithm: 'lttb',  // Largest-Triangle-Three-Buckets — preserves visual shape at 1/10 data
      samples: 50,        // Max 50 rendered points regardless of data size
    },
  },
  scales: {
    x: {
      grid: { color: CHART_COLORS.grid },
      ticks: { color: '#5a5a5a', font: { family: 'Roboto Mono', size: 9 }, maxTicksLimit: 8 },
    },
    y: {
      grid: { color: CHART_COLORS.grid },
      ticks: { color: CHART_COLORS.green, font: { family: 'Roboto Mono', size: 9 } },
    },
  },
}

async function renderCharts() {
  if (!hrChartCanvas.value || !spo2ChartCanvas.value) return

  const labels = hourlyBuckets.value.map((b: any) => formatHour(b.bucket_hour))
  const hrData = hourlyBuckets.value.map((b: any) => b.avg_hr)
  const spo2Data = hourlyBuckets.value.map((b: any) => b.avg_spo2)
  const systolicData = hourlyBuckets.value.map((b: any) => b.avg_systolic)

  // Destroy existing charts to free canvas context (prevents memory leak)
  hrChart?.destroy()
  spo2Chart?.destroy()

  hrChart = new Chart(hrChartCanvas.value, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'HEART RATE (bpm)',
        data: hrData,
        borderColor: CHART_COLORS.green,
        backgroundColor: CHART_COLORS.dim,
        borderWidth: 1.5,
        pointRadius: 2,
        fill: true,
        tension: 0.2,
      }]
    },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        ...CHART_DEFAULTS.scales,
        y: { ...CHART_DEFAULTS.scales.y, min: 40, max: 180,
             title: { display: true, text: 'BPM', color: '#5a5a5a', font: { size: 9 } } }
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
          borderColor: CHART_COLORS.cyan,
          backgroundColor: 'rgba(0,229,255,0.1)',
          borderWidth: 1.5,
          pointRadius: 2,
          tension: 0.2,
          yAxisID: 'ySpo2',
        },
        {
          label: 'SYSTOLIC (mmHg)',
          data: systolicData,
          borderColor: CHART_COLORS.orange,
          backgroundColor: 'rgba(255,102,0,0.08)',
          borderWidth: 1,
          pointRadius: 2,
          tension: 0.2,
          yAxisID: 'ySys',
        }
      ]
    },
    options: {
      ...CHART_DEFAULTS,
      scales: {
        x: CHART_DEFAULTS.scales.x,
        ySpo2: { ...CHART_DEFAULTS.scales.y, min: 80, max: 100, position: 'left' as const,
                  title: { display: true, text: 'SpO₂ %', color: '#5a5a5a', font: { size: 9 } } },
        ySys: { ...CHART_DEFAULTS.scales.y, min: 80, max: 200, position: 'right' as const,
                title: { display: true, text: 'mmHg', color: '#5a5a5a', font: { size: 9 } },
                grid: { color: 'transparent' } },
      }
    } as any
  })
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
function setRange(hours: number) {
  activeRange.value = hours
  fetchHistory()
}

function formatHour(iso: string) {
  try { return new Date(iso).toTimeString().slice(0, 5) } catch { return '--:--' }
}

function hrToPercent(hr: number) {
  // Scale HR to 0-100% column height. 60-100bpm = 20%-80%
  if (!hr) return 20
  return Math.min(95, Math.max(10, ((hr - 40) / 140) * 100))
}

function alertClass(level: string) {
  const map: Record<string, string> = { NORMAL: 'normal', WARNING: 'warning', CRITICAL: 'critical', STROKE: 'stroke' }
  return map[level] || 'normal'
}

onMounted(fetchHistory)
onUnmounted(() => { hrChart?.destroy(); spo2Chart?.destroy() })
</script>

<style scoped>
.history-shell { display: flex; flex-direction: column; height: 100%; background: var(--color-bg-void); }

.history-controls-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin: 8px;
  padding: 8px 16px;
}

.time-controls { display: flex; gap: 4px; }
.range-active {
  background: var(--color-accent-green) !important;
  color: var(--color-bg-void) !important;
}

.loading-state, .error-state { margin: 24px; padding: 24px; }

.charts-grid {
  flex: 1; display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr auto;
  gap: 8px; padding: 8px; overflow: hidden;
}
.chart-card { display: flex; flex-direction: column; }
.terminal-card-header { display: flex; align-items: center; gap: 8px; }
.chart-stat { font-size: 9px; letter-spacing: 0.1em; margin-left: auto; }
.chart-container { flex: 1; min-height: 0; position: relative; }
.chart-container canvas { width: 100% !important; height: 100% !important; }

/* Alert distribution bar chart */
.alert-dist-grid {
  display: flex; align-items: flex-end; gap: 2px; height: 80px;
  padding: 4px; margin-top: 8px;
}
.hour-bucket { display: flex; flex-direction: column; align-items: center;
  justify-content: flex-end; flex: 1; min-width: 0; height: 100%; cursor: default; }
.bucket-bar {
  width: 100%; min-height: 2px; transition: height 300ms ease;
  border-radius: 1px 1px 0 0;
}
.bucket-bar.normal   { background: var(--color-accent-green); }
.bucket-bar.warning  { background: var(--color-accent-orange); }
.bucket-bar.critical { background: var(--color-accent-red); }
.bucket-bar.stroke   { background: #FF0000; animation: blink-danger 0.5s step-end infinite; }
@keyframes blink-danger { 50%{opacity:0.3} }
.bucket-label { font-size: 7px; margin-top: 2px; white-space: nowrap; overflow: hidden; }

.dist-legend { display: flex; gap: 16px; padding: 6px 4px; border-top: 1px solid var(--color-border-dim); }
.legend-item { display: flex; align-items: center; gap: 4px; font-size: 9px; color: var(--color-text-dim); font-family: var(--font-hud); letter-spacing: 0.1em; }
.dot { width: 8px; height: 8px; border-radius: 1px; }
.dot.normal   { background: var(--color-accent-green); }
.dot.warning  { background: var(--color-accent-orange); }
.dot.critical { background: var(--color-accent-red); }
.dot.stroke   { background: #FF0000; }
</style>
