/**
 * Digital Twin Store — HK-07 Holographic Simulation
 *
 * Manages real-time robot state for the 3D scene:
 *   - position (x, y, z)  [meters in sim space]
 *   - rotation (pitch, yaw, roll) [radians]
 *   - alert_level, velocity, operational status
 *
 * Simulation mode: sine-wave locomotion until WS bridge connects.
 * WebSocket bridge: call updateFromTelemetry() from websocket.ts.
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface RobotTelemetry {
  x: number
  y: number
  z: number
  pitch: number   // rotation around X-axis (radians)
  yaw: number     // rotation around Y-axis (radians)
  roll: number    // rotation around Z-axis (radians)
  velocityMs: number
  alertLevel: 'NORMAL' | 'WARNING' | 'CRITICAL'
  timestamp: number
}

export const useDigitalTwinStore = defineStore('digitalTwin', () => {
  // ── State ────────────────────────────────────────────────────────────────
  const position = ref({ x: 0, y: 0, z: 0 })
  const rotation = ref({ pitch: 0, yaw: 0, roll: 0 })
  const velocityMs = ref(0)
  const alertLevel = ref<'NORMAL' | 'WARNING' | 'CRITICAL'>('NORMAL')
  const isSimulationMode = ref(true)       // true until WS connects
  const isSimRunning = ref(false)
  const frameCount = ref(0)
  const lastFps = ref(0)
  const nearestObstacleM = ref(999)

  // ── Computed ─────────────────────────────────────────────────────────────
  const positionFormatted = computed(() => ({
    x: position.value.x.toFixed(3),
    y: position.value.y.toFixed(3),
    z: position.value.z.toFixed(3),
  }))

  const rotationFormatted = computed(() => ({
    pitch: (rotation.value.pitch * (180 / Math.PI)).toFixed(1) + '°',
    yaw:   (rotation.value.yaw   * (180 / Math.PI)).toFixed(1) + '°',
    roll:  (rotation.value.roll  * (180 / Math.PI)).toFixed(1) + '°',
  }))

  const alertColor = computed(() => {
    if (alertLevel.value === 'CRITICAL') return '#FF3333'
    if (alertLevel.value === 'WARNING')  return '#FFB000'
    return '#00FF66'
  })

  // ── Simulation Timer ──────────────────────────────────────────────────────
  let simTimer: ReturnType<typeof setInterval> | null = null
  let simT = 0

  function startSimulation() {
    if (isSimRunning.value) return
    isSimRunning.value = true
    isSimulationMode.value = true

    simTimer = setInterval(() => {
      simT += 0.016  // ~60Hz tick

      // Circular patrol path in XZ plane
      const radius = 2.0
      position.value.x = parseFloat((Math.cos(simT * 0.4) * radius).toFixed(4))
      position.value.z = parseFloat((Math.sin(simT * 0.4) * radius).toFixed(4))
      // Slight bob on Y
      position.value.y = parseFloat((Math.abs(Math.sin(simT * 0.8)) * 0.05).toFixed(4))

      // Yaw follows path tangent
      rotation.value.yaw   = parseFloat((-simT * 0.4 + Math.PI / 2).toFixed(4))
      // Gentle roll sway
      rotation.value.roll  = parseFloat((Math.sin(simT * 1.2) * 0.05).toFixed(4))
      // Minimal pitch
      rotation.value.pitch = parseFloat((Math.sin(simT * 0.6) * 0.02).toFixed(4))

      velocityMs.value = parseFloat((0.6 + Math.sin(simT) * 0.2).toFixed(2))
      nearestObstacleM.value = parseFloat((3.5 + Math.sin(simT * 0.3) * 1.5).toFixed(2))

      frameCount.value++
    }, 16)
  }

  function stopSimulation() {
    if (simTimer) {
      clearInterval(simTimer)
      simTimer = null
    }
    isSimRunning.value = false
  }

  // ── WebSocket Bridge ──────────────────────────────────────────────────────
  /**
   * Called from websocket.ts when MQTT/WS delivers real robot telemetry.
   * Switches out of simulation mode automatically.
   */
  function updateFromTelemetry(data: Partial<RobotTelemetry>) {
    isSimulationMode.value = false
    stopSimulation()

    if (data.x !== undefined) position.value.x = data.x
    if (data.y !== undefined) position.value.y = data.y
    if (data.z !== undefined) position.value.z = data.z
    if (data.pitch !== undefined) rotation.value.pitch = data.pitch
    if (data.yaw   !== undefined) rotation.value.yaw   = data.yaw
    if (data.roll  !== undefined) rotation.value.roll  = data.roll
    if (data.velocityMs !== undefined) velocityMs.value = data.velocityMs
    if (data.alertLevel !== undefined) alertLevel.value = data.alertLevel
  }

  function resetToOrigin() {
    position.value = { x: 0, y: 0, z: 0 }
    rotation.value = { pitch: 0, yaw: 0, roll: 0 }
    velocityMs.value = 0
    simT = 0
  }

  return {
    position,
    rotation,
    velocityMs,
    alertLevel,
    isSimulationMode,
    isSimRunning,
    frameCount,
    lastFps,
    nearestObstacleM,
    positionFormatted,
    rotationFormatted,
    alertColor,
    startSimulation,
    stopSimulation,
    updateFromTelemetry,
    resetToOrigin,
  }
})
