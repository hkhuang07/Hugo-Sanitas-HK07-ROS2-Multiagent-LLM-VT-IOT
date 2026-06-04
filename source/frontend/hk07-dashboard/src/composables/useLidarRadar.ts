import { ref, type Ref, onMounted, onUnmounted, watch } from 'vue'
import { OBSTACLE_STOP_M, pointColor } from '../utils/lidarScan'

const RADAR_SIZE = 400
const MAX_RANGE_M = 3.5

export function useLidarRadar(
  canvasRef: Ref<HTMLCanvasElement | null>,
  ranges360: Ref<number[]>,
  closestAngleDeg: Ref<number>,
  subsumptionActive: Ref<boolean>
) {
  let animFrame = 0
  let isUnmounted = false

  function draw() {
    if (isUnmounted) return
    const canvas = canvasRef.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const cx = RADAR_SIZE / 2
    const cy = RADAR_SIZE / 2
    const ranges = ranges360.value

    ctx.clearRect(0, 0, RADAR_SIZE, RADAR_SIZE)
    ctx.fillStyle = '#000000'
    ctx.fillRect(0, 0, RADAR_SIZE, RADAR_SIZE)

    const ringDistances = [0.5, 1.0, 2.0, 3.0]
    ctx.strokeStyle = 'rgba(0, 255, 102, 0.12)'
    ctx.lineWidth = 1
    ringDistances.forEach((d) => {
      const r = (d / MAX_RANGE_M) * (RADAR_SIZE / 2)
      ctx.beginPath()
      ctx.arc(cx, cy, r, 0, Math.PI * 2)
      ctx.stroke()
    })

    // Baymax personal-space bubble (0.5m — SafetyAgent stop threshold)
    const bubbleR = (OBSTACLE_STOP_M / MAX_RANGE_M) * (RADAR_SIZE / 2)
    ctx.strokeStyle = subsumptionActive.value
      ? 'rgba(255, 51, 51, 0.85)'
      : 'rgba(0, 229, 255, 0.45)'
    ctx.lineWidth = 2
    ctx.setLineDash([6, 4])
    ctx.beginPath()
    ctx.arc(cx, cy, bubbleR, 0, Math.PI * 2)
    ctx.stroke()
    ctx.setLineDash([])

    ctx.strokeStyle = 'rgba(0, 255, 102, 0.08)'
    ;[0, 45, 90, 135].forEach((angleDeg) => {
      const rad = (angleDeg * Math.PI) / 180
      ctx.beginPath()
      ctx.moveTo(cx + Math.cos(rad) * RADAR_SIZE / 2, cy + Math.sin(rad) * RADAR_SIZE / 2)
      ctx.lineTo(cx - Math.cos(rad) * RADAR_SIZE / 2, cy - Math.sin(rad) * RADAR_SIZE / 2)
      ctx.stroke()
    })

    const sweepAngle = (Date.now() / 50) % 360
    const sweepRad = (sweepAngle * Math.PI) / 180
    const grad = ctx.createLinearGradient(
      cx, cy,
      cx + Math.cos(sweepRad) * RADAR_SIZE / 2,
      cy + Math.sin(sweepRad) * RADAR_SIZE / 2
    )
    grad.addColorStop(0, 'rgba(0, 255, 102, 0.35)')
    grad.addColorStop(1, 'rgba(0, 255, 102, 0)')
    ctx.strokeStyle = grad
    ctx.lineWidth = 2
    ctx.beginPath()
    ctx.moveTo(cx, cy)
    ctx.lineTo(
      cx + Math.cos(sweepRad) * RADAR_SIZE / 2,
      cy + Math.sin(sweepRad) * RADAR_SIZE / 2
    )
    ctx.stroke()

    ranges.forEach((dist, angleDeg) => {
      if (dist <= 0.01 || dist > MAX_RANGE_M) return
      const rad = (angleDeg * Math.PI) / 180
      const pixelDist = (dist / MAX_RANGE_M) * (RADAR_SIZE / 2)
      const px = cx + Math.cos(rad) * pixelDist
      const py = cy + Math.sin(rad) * pixelDist
      ctx.fillStyle = pointColor(dist)
      ctx.shadowColor = pointColor(dist)
      ctx.shadowBlur = dist < OBSTACLE_STOP_M ? 10 : 4
      ctx.beginPath()
      ctx.arc(px, py, dist < OBSTACLE_STOP_M ? 5 : dist < 1 ? 3 : 2, 0, Math.PI * 2)
      ctx.fill()
    })
    ctx.shadowBlur = 0

    // Closest threat bearing
    if (ranges[closestAngleDeg.value] > 0.01) {
      const ca = (closestAngleDeg.value * Math.PI) / 180
      const cd = ranges[closestAngleDeg.value]
      const pr = (cd / MAX_RANGE_M) * (RADAR_SIZE / 2)
      ctx.strokeStyle = '#FF3333'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(cx, cy)
      ctx.lineTo(cx + Math.cos(ca) * pr, cy + Math.sin(ca) * pr)
      ctx.stroke()
    }

    ctx.fillStyle = '#00FF66'
    ctx.shadowColor = '#00FF66'
    ctx.shadowBlur = 10
    ctx.beginPath()
    ctx.arc(cx, cy, 6, 0, Math.PI * 2)
    ctx.fill()
    ctx.shadowBlur = 0

    animFrame = requestAnimationFrame(draw)
  }

  watch([ranges360, closestAngleDeg, subsumptionActive], () => {
    /* redraw driven by rAF loop reading refs */
  }, { deep: true })

  onMounted(() => {
    animFrame = requestAnimationFrame(draw)
  })

  onUnmounted(() => {
    isUnmounted = true
    cancelAnimationFrame(animFrame)
  })

  return { RADAR_SIZE, MAX_RANGE_M }
}
