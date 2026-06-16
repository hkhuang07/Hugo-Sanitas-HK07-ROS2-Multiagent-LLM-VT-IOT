import { ref, type Ref, onMounted, onUnmounted, watch } from 'vue'
import { useKinematicsStore } from '../stores/kinematics'
import { useSafetyStore } from '../stores/safety'

const RADAR_SIZE = 400

export function useLidarRadar(
  canvasRef: Ref<HTMLCanvasElement | null>,
  ranges360: Ref<number[]>,
  closestAngleDeg: Ref<number>,
  subsumptionActive: Ref<boolean>
) {
  const kinematicsStore = useKinematicsStore()
  const safetyStore = useSafetyStore()
  let animFrame = 0
  let isUnmounted = false
  let scanLineY = 50
  let scanDir = 1

  function draw() {
    if (isUnmounted) return
    const canvas = canvasRef.value
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Clear and draw True Black background
    ctx.clearRect(0, 0, RADAR_SIZE, RADAR_SIZE)
    ctx.fillStyle = '#000000'
    ctx.fillRect(0, 0, RADAR_SIZE, RADAR_SIZE)

    // Draw grid lines (1px neon border style)
    ctx.strokeStyle = 'rgba(0, 255, 102, 0.08)'
    ctx.lineWidth = 1
    const gridSize = 40
    for (let x = 0; x < RADAR_SIZE; x += gridSize) {
      ctx.beginPath()
      ctx.moveTo(x, 0)
      ctx.lineTo(x, RADAR_SIZE)
      ctx.stroke()
    }
    for (let y = 0; y < RADAR_SIZE; y += gridSize) {
      ctx.beginPath()
      ctx.moveTo(0, y)
      ctx.lineTo(RADAR_SIZE, y)
      ctx.stroke()
    }

    // Draw camera crop frame
    ctx.strokeStyle = 'rgba(0, 255, 102, 0.3)'
    ctx.lineWidth = 2
    ctx.strokeRect(30, 30, RADAR_SIZE - 60, RADAR_SIZE - 60)

    // Corner reticles inside the frame
    ctx.fillStyle = '#00FF66'
    const corners = [
      { x: 30, y: 30, dx: 1, dy: 1 },
      { x: RADAR_SIZE - 30, y: 30, dx: -1, dy: 1 },
      { x: 30, y: RADAR_SIZE - 30, dx: 1, dy: -1 },
      { x: RADAR_SIZE - 30, y: RADAR_SIZE - 30, dx: -1, dy: -1 }
    ]
    corners.forEach(c => {
      ctx.beginPath()
      ctx.moveTo(c.x, c.y)
      ctx.lineTo(c.x + c.dx * 15, c.y)
      ctx.moveTo(c.x, c.y)
      ctx.lineTo(c.x, c.y + c.dy * 15)
      ctx.stroke()
    })

    // Horizontal scanning line
    scanLineY += scanDir * 1.5
    if (scanLineY > RADAR_SIZE - 40 || scanLineY < 40) {
      scanDir *= -1
    }
    const scanGrad = ctx.createLinearGradient(0, scanLineY - 10 * scanDir, 0, scanLineY)
    scanGrad.addColorStop(0, 'rgba(0, 255, 102, 0)')
    scanGrad.addColorStop(1, 'rgba(0, 255, 102, 0.25)')
    ctx.fillStyle = scanGrad
    ctx.fillRect(32, Math.min(scanLineY, scanLineY - 15 * scanDir), RADAR_SIZE - 64, 15)

    ctx.strokeStyle = '#00FF66'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.moveTo(32, scanLineY)
    ctx.lineTo(RADAR_SIZE - 32, scanLineY)
    ctx.stroke()

    // Draw central target crosshair
    ctx.strokeStyle = 'rgba(0, 229, 255, 0.4)'
    ctx.lineWidth = 1
    ctx.beginPath()
    ctx.arc(RADAR_SIZE / 2, RADAR_SIZE / 2, 25, 0, Math.PI * 2)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(RADAR_SIZE / 2 - 35, RADAR_SIZE / 2)
    ctx.lineTo(RADAR_SIZE / 2 + 35, RADAR_SIZE / 2)
    ctx.moveTo(RADAR_SIZE / 2, RADAR_SIZE / 2 - 35)
    ctx.lineTo(RADAR_SIZE / 2, RADAR_SIZE / 2 + 35)
    ctx.stroke()

    // Draw simulated vision tracking box
    const hasDistress = safetyStore.activeTriggers.some(t => t.type === 'FACIAL_DISTRESS' || t.type === 'FALL_RISK')
    const boxColor = hasDistress ? 'rgba(255, 51, 51, 0.6)' : 'rgba(0, 229, 255, 0.5)'
    const boxBorder = hasDistress ? '#FF3333' : '#00E5FF'

    ctx.fillStyle = boxColor
    ctx.strokeStyle = boxBorder
    ctx.lineWidth = 1.5
    const trackingBoxX = 120
    const trackingBoxY = 100
    const trackingBoxW = 160
    const trackingBoxH = 180

    ctx.strokeRect(trackingBoxX, trackingBoxY, trackingBoxW, trackingBoxH)
    ctx.fillRect(trackingBoxX, trackingBoxY, trackingBoxW, trackingBoxH)

    // Bounding Box tracking tag
    ctx.fillStyle = boxBorder
    ctx.font = '9px monospace'
    ctx.fillText('[ TARGET: OWNER_HUMAN ]', trackingBoxX + 5, trackingBoxY - 5)

    // Render diagnostic overlays
    ctx.fillStyle = 'rgba(0, 255, 102, 0.7)'
    ctx.font = '10px monospace'
    ctx.fillText('STREAM: IPWEBCAM_LIVE', 42, 52)
    ctx.fillText('RESOLUTION: 1920x1080', 42, 65)
    ctx.fillText('AI_ENGINE: MEDIAPIPE_VISION_PRO', 42, 78)

    // Display threat status overlay
    if (hasDistress) {
      ctx.fillStyle = 'rgba(255, 51, 51, 0.85)'
      ctx.font = 'bold 12px monospace'
      ctx.fillText('[ WARNING: CRITICAL STATE ]', 42, RADAR_SIZE - 50)
    } else {
      ctx.fillStyle = 'rgba(0, 255, 102, 0.85)'
      ctx.font = 'bold 12px monospace'
      ctx.fillText('[ VISION STATUS: NOMINAL ]', 42, RADAR_SIZE - 50)
    }

    // Draw rPPG Heart Wave
    ctx.strokeStyle = '#00FF66'
    ctx.lineWidth = 1.5
    ctx.beginPath()
    const waveY = RADAR_SIZE - 80
    ctx.moveTo(42, waveY)
    for (let x = 42; x < RADAR_SIZE - 42; x++) {
      const angle = (x / 20.0) + (Date.now() / 150.0)
      const y = waveY + Math.sin(angle) * (hasDistress ? 18.0 : 8.0)
      ctx.lineTo(x, y)
    }
    ctx.stroke()

    animFrame = requestAnimationFrame(draw)
  }

  onMounted(() => {
    animFrame = requestAnimationFrame(draw)
  })

  onUnmounted(() => {
    isUnmounted = true
    cancelAnimationFrame(animFrame)
  })

  return { RADAR_SIZE }
}
