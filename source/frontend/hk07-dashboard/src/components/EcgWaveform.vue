<template>
  <div class="ecg-canvas-container" :style="{ height: height + 'px' }">
    <canvas ref="canvasRef" :width="width" :height="height"></canvas>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useVitalsStore } from '../stores/vitals'

const props = withDefaults(defineProps<{
  width?: number
  height?: number
}>(), {
  width: 760,
  height: 90
})

const vitalsStore = useVitalsStore()
const canvasRef = ref<HTMLCanvasElement | null>(null)
let animFrameId: number
let simPhase = 0
let isUnmounted = false

function draw() {
  if (isUnmounted) return
  const canvas = canvasRef.value
  if (!canvas) return
  
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const w = canvas.width
  const h = canvas.height

  // Clear background
  ctx.clearRect(0, 0, w, h)
  ctx.fillStyle = '#000000'
  ctx.fillRect(0, 0, w, h)

  // Draw technical grid lines
  ctx.strokeStyle = 'rgba(0, 255, 102, 0.05)'
  ctx.lineWidth = 1
  for (let x = 0; x < w; x += 40) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, h)
    ctx.stroke()
  }
  for (let y = 0; y < h; y += 20) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(w, y)
    ctx.stroke()
  }

  // Draw waveform with zero memory allocations inside loop
  const isConnected = vitalsStore.isConnected
  const size = vitalsStore.RING_BUFFER_SIZE
  const writeIdx = vitalsStore.bufferWriteIdx
  const history = vitalsStore.heartRateHistory

  const hasData = isConnected && history.some(v => v > 0)

  ctx.beginPath()
  ctx.strokeStyle = '#00FF66'
  ctx.lineWidth = 1.5
  ctx.shadowColor = '#00FF66'
  ctx.shadowBlur = 4

  if (hasData) {
    const lastHR = history[(writeIdx - 1 + size) % size] || 72
    simPhase += (lastHR / 60) * (1 / 60)
    for (let i = 0; i < size; i++) {
      const hr = history[(writeIdx + i) % size]
      const t = (i / size) + simPhase
      const base = Math.sin(t * Math.PI * 2) * 3
      const qrs = Math.sin(t * Math.PI * 160) > 0.97 ? 35 * (hr / 72) : 0
      const val = base + qrs

      const x = (i / size) * w
      const y = h / 2 - val
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
  } else {
    // Zero allocation offline simulator
    simPhase += 0.016
    for (let i = 0; i < size; i++) {
      const t = i / size + simPhase
      const val = Math.sin(t * Math.PI * 2) * 4
                + (Math.sin(t * Math.PI * 160) > 0.97 ? 32 : 0)
                + (Math.sin(t * Math.PI * 80) * 1.2)
      
      const x = (i / size) * w
      const y = h / 2 - val
      if (i === 0) ctx.moveTo(x, y)
      else ctx.lineTo(x, y)
    }
  }

  ctx.stroke()
  ctx.shadowBlur = 0

  animFrameId = requestAnimationFrame(draw)
}

onMounted(() => {
  animFrameId = requestAnimationFrame(draw)
})

onUnmounted(() => {
  isUnmounted = true
  cancelAnimationFrame(animFrameId)
})
</script>

<style scoped>
.ecg-canvas-container {
  position: relative;
  width: 100%;
  background: #000000;
  border: 1px solid var(--color-border-dim);
}
.ecg-canvas-container canvas {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
