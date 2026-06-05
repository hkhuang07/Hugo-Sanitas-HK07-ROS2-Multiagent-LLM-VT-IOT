<template>
  <div class="dt-shell" ref="containerRef">

    <!-- ══ 3D Canvas ══════════════════════════════════════════════════════ -->
    <canvas ref="sceneRef" class="dt-canvas" />

    <!-- ══ HUD Overlay ═══════════════════════════════════════════════════ -->
    <div class="hud-overlay">

      <!-- Top-left: system header -->
      <div class="hud-block hud-topleft corner-reticle">
        <div class="hud-title">[ HK-07 // DIGITAL TWIN — HOLOGRAPHIC SIM v2.0 ]</div>
        <div class="hud-sub">
          <span class="status-dot" :style="{ background: twinStore.alertColor }">●</span>
          <span class="mode-tag">{{ twinStore.isSimulationMode ? 'SIM_MODE' : 'LIVE_MODE' }}</span>
          <span class="sep">|</span>
          <span class="fps-val">{{ fps }} FPS</span>
          <span class="sep">|</span>
          <span class="ts-val">{{ timeStr }}</span>
        </div>
      </div>

      <!-- Top-right: alert level -->
      <div class="hud-block hud-topright">
        <div class="alert-chip" :class="alertClass">
          <span class="alert-icon">{{ twinStore.alertLevel === 'CRITICAL' ? '⚠' : twinStore.alertLevel === 'WARNING' ? '△' : '✓' }}</span>
          {{ twinStore.alertLevel }}
        </div>
      </div>

      <!-- Bottom-left: positional telemetry matrix -->
      <div class="hud-block hud-botleft coord-matrix corner-reticle">
        <div class="matrix-header">[ POSITIONAL_TELEMETRY ]</div>
        <div class="matrix-row">
          <span class="axis-x">X</span>
          <span class="axis-bar">━━━━</span>
          <span class="coord-val">{{ twinStore.positionFormatted.x }}</span>
          <span class="unit">m</span>
        </div>
        <div class="matrix-row">
          <span class="axis-y">Y</span>
          <span class="axis-bar">━━━━</span>
          <span class="coord-val">{{ twinStore.positionFormatted.y }}</span>
          <span class="unit">m</span>
        </div>
        <div class="matrix-row">
          <span class="axis-z">Z</span>
          <span class="axis-bar">━━━━</span>
          <span class="coord-val">{{ twinStore.positionFormatted.z }}</span>
          <span class="unit">m</span>
        </div>
        <div class="matrix-divider"></div>
        <div class="matrix-row">
          <span class="axis-label">PITCH</span>
          <span class="axis-bar">━━</span>
          <span class="coord-val">{{ twinStore.rotationFormatted.pitch }}</span>
        </div>
        <div class="matrix-row">
          <span class="axis-label">YAW</span>
          <span class="axis-bar">━━━</span>
          <span class="coord-val">{{ twinStore.rotationFormatted.yaw }}</span>
        </div>
        <div class="matrix-row">
          <span class="axis-label">ROLL</span>
          <span class="axis-bar">━━━</span>
          <span class="coord-val">{{ twinStore.rotationFormatted.roll }}</span>
        </div>
      </div>

      <!-- Bottom-right: velocity + obstacle panel -->
      <div class="hud-block hud-botright">
        <div class="matrix-header">[ KINEMATICS_FEED ]</div>
        <div class="matrix-row">
          <span class="axis-label">VELOCITY</span>
          <span class="coord-val text-orange">{{ twinStore.velocityMs.toFixed(2) }} m/s</span>
        </div>
        <div class="matrix-row">
          <span class="axis-label">OBSTACLE</span>
          <span :class="['coord-val', twinStore.nearestObstacleM < 1.5 ? 'text-red' : 'text-green']">
            {{ twinStore.nearestObstacleM.toFixed(2) }} m
          </span>
        </div>
        <div class="matrix-divider"></div>
        <!-- Control buttons -->
        <div class="ctrl-btns">
          <button id="btn-twin-sim" class="ctrl-btn" :class="{ active: twinStore.isSimRunning }" @click="toggleSim">
            {{ twinStore.isSimRunning ? '[ ■ PAUSE ]' : '[ ► SIM ]' }}
          </button>
          <button id="btn-twin-reset" class="ctrl-btn reset-btn" @click="resetScene">[ ↺ RESET ]</button>
        </div>
        <!-- Bloom strength control -->
        <div class="bloom-ctrl">
          <span class="axis-label">BLOOM</span>
          <input id="bloom-slider" type="range" min="0" max="30" step="1" v-model.number="bloomStrength"
                 class="bloom-slider" @input="updateBloom" />
          <span class="coord-val">{{ (bloomStrength / 10).toFixed(1) }}</span>
        </div>
      </div>

      <!-- Centre: crosshair -->
      <div class="hud-crosshair">
        <div class="ch-h"></div>
        <div class="ch-v"></div>
        <div class="ch-dot"></div>
      </div>

    </div>
    <!-- /hud-overlay -->

  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { useDigitalTwinStore } from '../stores/digitalTwin'

// ─── Store ─────────────────────────────────────────────────────────────────
const twinStore = useDigitalTwinStore()

// ─── Refs ───────────────────────────────────────────────────────────────────
const containerRef = ref<HTMLElement | null>(null)
const sceneRef     = ref<HTMLCanvasElement | null>(null)
const fps          = ref(60)
const bloomStrength = ref(15)   // /10 → 1.5

// ─── Three.js internals ──────────────────────────────────────────────────────
let renderer:   THREE.WebGLRenderer
let scene:      THREE.Scene
let camera:     THREE.PerspectiveCamera
let controls:   OrbitControls
let composer:   EffectComposer
let bloomPass:  UnrealBloomPass
let robotGroup: THREE.Group
let animId:     number
let lastT = 0
let frameCount = 0
let fpsTimer   = 0

// ─── Time HUD ─────────────────────────────────────────────────────────────
const timeStr = computed(() => new Date().toLocaleTimeString('vi-VN', { hour12: false }))

// ─── Alert CSS ─────────────────────────────────────────────────────────────
const alertClass = computed(() => {
  if (twinStore.alertLevel === 'CRITICAL') return 'alert-critical'
  if (twinStore.alertLevel === 'WARNING')  return 'alert-warning'
  return 'alert-normal'
})

// ═══════════════════════════════════════════════════════════════════════════
// SCENE CONSTRUCTION
// ═══════════════════════════════════════════════════════════════════════════

function buildScene() {
  const canvas = sceneRef.value!
  const container = containerRef.value!
  const W = container.clientWidth
  const H = container.clientHeight

  // ── Renderer ────────────────────────────────────────────────────────────
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(W, H)
  renderer.setClearColor(0x000000, 1)
  renderer.toneMapping = THREE.ReinhardToneMapping
  renderer.toneMappingExposure = 1.2

  // ── Scene ───────────────────────────────────────────────────────────────
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x000000)

  // ── Camera ──────────────────────────────────────────────────────────────
  camera = new THREE.PerspectiveCamera(60, W / H, 0.01, 200)
  camera.position.set(5, 4, 7)
  camera.lookAt(0, 1, 0)

  // ── OrbitControls ────────────────────────────────────────────────────────
  controls = new OrbitControls(camera, canvas)
  controls.enableDamping = true
  controls.dampingFactor = 0.06
  controls.minDistance   = 2
  controls.maxDistance   = 40
  controls.target.set(0, 1, 0)

  // ── Grid ─────────────────────────────────────────────────────────────────
  const grid = new THREE.GridHelper(40, 40, 0x00d2ff, 0x002233)
  grid.position.y = 0
  scene.add(grid)

  // Secondary fine grid
  const gridFine = new THREE.GridHelper(20, 80, 0x001122, 0x001122)
  gridFine.position.y = 0.001
  scene.add(gridFine)

  // ── Custom Axes (colored) ────────────────────────────────────────────────
  buildColoredAxes()

  // ── Robot ─────────────────────────────────────────────────────────────────
  robotGroup = buildRobotMockup()
  scene.add(robotGroup)

  // ── Ambient particles (star field) ───────────────────────────────────────
  buildParticles()

  // ── Post-Processing ─────────────────────────────────────────────────────
  composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))

  bloomPass = new UnrealBloomPass(
    new THREE.Vector2(W, H),
    bloomStrength.value / 10,   // strength
    0.4,                         // radius
    0.05                         // threshold
  )
  composer.addPass(bloomPass)
}

// ─── Colored XYZ Axes ──────────────────────────────────────────────────────
function buildColoredAxes() {
  const mat = (color: number) =>
    new THREE.LineBasicMaterial({ color, linewidth: 2 })

  const L = 3
  const axisData = [
    { dir: new THREE.Vector3(L, 0, 0), color: 0x00e5ff },  // X — Cyan
    { dir: new THREE.Vector3(0, L, 0), color: 0x00ff66 },  // Y — Emerald
    { dir: new THREE.Vector3(0, 0, L), color: 0xffb000 },  // Z — Amber
  ]

  for (const { dir, color } of axisData) {
    const geo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(0, 0, 0), dir
    ])
    const line = new THREE.Line(geo, mat(color))
    scene.add(line)
  }

  // Small origin sphere
  const originGeo = new THREE.SphereGeometry(0.06, 8, 8)
  const originMat = new THREE.MeshBasicMaterial({ color: 0xffffff, wireframe: true })
  scene.add(new THREE.Mesh(originGeo, originMat))
}

// ─── HK-07 Robot Mockup (Wireframe Hierarchy) ──────────────────────────────
function buildRobotMockup(): THREE.Group {
  const group = new THREE.Group()
  const cyan = new THREE.MeshBasicMaterial({ color: 0x00e5ff, wireframe: true })
  const dim  = new THREE.MeshBasicMaterial({ color: 0x007aab, wireframe: true })

  // Helper
  const box = (w: number, h: number, d: number, mat = cyan) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat)
    return m
  }
  const cyl = (r: number, h: number, seg = 10, mat = cyan) => {
    const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, h, seg), mat)
    return m
  }
  const sphere = (r: number, mat = cyan) => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(r, 10, 8), mat)
    return m
  }

  // ── Torso ─────────────────────────────────────────────────────────────
  const torso = box(0.7, 0.9, 0.45, cyan)
  torso.position.set(0, 1.2, 0)
  group.add(torso)

  // ── Chest Detail strip ────────────────────────────────────────────────
  const chestStrip = box(0.55, 0.12, 0.1, dim)
  chestStrip.position.set(0, 1.38, 0.23)
  group.add(chestStrip)

  // ── Neck ──────────────────────────────────────────────────────────────
  const neck = cyl(0.1, 0.2, 8, dim)
  neck.position.set(0, 1.75, 0)
  group.add(neck)

  // ── Head (Baymax-round) ───────────────────────────────────────────────
  const head = sphere(0.32, cyan)
  head.position.set(0, 2.12, 0)
  group.add(head)

  // Visor (elongated box on face)
  const visor = box(0.5, 0.1, 0.05)
  visor.position.set(0, 2.12, 0.32)
  group.add(visor)

  // Eye dots
  for (const ex of [-0.13, 0.13]) {
    const eye = sphere(0.04)
    eye.position.set(ex, 2.16, 0.34)
    group.add(eye)
  }

  // ── Pelvis ────────────────────────────────────────────────────────────
  const pelvis = box(0.65, 0.22, 0.4, dim)
  pelvis.position.set(0, 0.74, 0)
  group.add(pelvis)

  // ── Left Arm ─────────────────────────────────────────────────────────
  const lShoulder = sphere(0.18, dim)
  lShoulder.position.set(-0.52, 1.45, 0)
  group.add(lShoulder)

  const lUpperArm = cyl(0.1, 0.45, 8)
  lUpperArm.rotation.z = Math.PI / 2.3
  lUpperArm.position.set(-0.8, 1.18, 0)
  group.add(lUpperArm)

  const lElbow = sphere(0.12, dim)
  lElbow.position.set(-1.05, 0.9, 0)
  group.add(lElbow)

  const lForearm = cyl(0.08, 0.4, 8)
  lForearm.rotation.z = Math.PI / 2.8
  lForearm.position.set(-1.2, 0.65, 0)
  group.add(lForearm)

  const lHand = sphere(0.1)
  lHand.position.set(-1.35, 0.45, 0)
  group.add(lHand)

  // ── Right Arm (mirror) ────────────────────────────────────────────────
  const rShoulder = sphere(0.18, dim)
  rShoulder.position.set(0.52, 1.45, 0)
  group.add(rShoulder)

  const rUpperArm = cyl(0.1, 0.45, 8)
  rUpperArm.rotation.z = -Math.PI / 2.3
  rUpperArm.position.set(0.8, 1.18, 0)
  group.add(rUpperArm)

  const rElbow = sphere(0.12, dim)
  rElbow.position.set(1.05, 0.9, 0)
  group.add(rElbow)

  const rForearm = cyl(0.08, 0.4, 8)
  rForearm.rotation.z = -Math.PI / 2.8
  rForearm.position.set(1.2, 0.65, 0)
  group.add(rForearm)

  const rHand = sphere(0.1)
  rHand.position.set(1.35, 0.45, 0)
  group.add(rHand)

  // ── Left Leg ──────────────────────────────────────────────────────────
  const lHip = sphere(0.16, dim)
  lHip.position.set(-0.22, 0.62, 0)
  group.add(lHip)

  const lThigh = cyl(0.11, 0.5, 8)
  lThigh.position.set(-0.22, 0.35, 0)
  group.add(lThigh)

  const lKnee = sphere(0.13, dim)
  lKnee.position.set(-0.22, 0.08, 0)
  group.add(lKnee)

  const lShin = cyl(0.09, 0.45, 8)
  lShin.position.set(-0.22, -0.18, 0)
  group.add(lShin)

  const lFoot = box(0.22, 0.1, 0.35, dim)
  lFoot.position.set(-0.22, -0.43, 0.06)
  group.add(lFoot)

  // ── Right Leg ─────────────────────────────────────────────────────────
  const rHip = sphere(0.16, dim)
  rHip.position.set(0.22, 0.62, 0)
  group.add(rHip)

  const rThigh = cyl(0.11, 0.5, 8)
  rThigh.position.set(0.22, 0.35, 0)
  group.add(rThigh)

  const rKnee = sphere(0.13, dim)
  rKnee.position.set(0.22, 0.08, 0)
  group.add(rKnee)

  const rShin = cyl(0.09, 0.45, 8)
  rShin.position.set(0.22, -0.18, 0)
  group.add(rShin)

  const rFoot = box(0.22, 0.1, 0.35, dim)
  rFoot.position.set(0.22, -0.43, 0.06)
  group.add(rFoot)

  return group
}

// ─── Particle Star Field ────────────────────────────────────────────────────
function buildParticles() {
  const count = 400
  const positions = new Float32Array(count * 3)
  for (let i = 0; i < count; i++) {
    positions[i * 3]     = (Math.random() - 0.5) * 60
    positions[i * 3 + 1] = Math.random() * 30
    positions[i * 3 + 2] = (Math.random() - 0.5) * 60
  }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  const mat = new THREE.PointsMaterial({ color: 0x002244, size: 0.06 })
  scene.add(new THREE.Points(geo, mat))
}

// ═══════════════════════════════════════════════════════════════════════════
// RENDER LOOP
// ═══════════════════════════════════════════════════════════════════════════

function animate(t: number) {
  animId = requestAnimationFrame(animate)

  // FPS counter
  frameCount++
  fpsTimer += t - lastT
  lastT = t
  if (fpsTimer >= 1000) {
    fps.value = frameCount
    frameCount = 0
    fpsTimer = 0
  }

  controls.update()

  // Sync robot mesh from Pinia store
  if (robotGroup) {
    robotGroup.position.set(
      twinStore.position.x,
      twinStore.position.y,
      twinStore.position.z,
    )
    robotGroup.rotation.set(
      twinStore.rotation.pitch,
      twinStore.rotation.yaw,
      twinStore.rotation.roll,
      'YXZ'
    )
  }

  composer.render()
}

// ─── Resize Handler ──────────────────────────────────────────────────────────
function onResize() {
  if (!containerRef.value) return
  const W = containerRef.value.clientWidth
  const H = containerRef.value.clientHeight
  camera.aspect = W / H
  camera.updateProjectionMatrix()
  renderer.setSize(W, H)
  composer.setSize(W, H)
}

// ─── Bloom control ───────────────────────────────────────────────────────────
function updateBloom() {
  if (bloomPass) bloomPass.strength = bloomStrength.value / 10
}

// ─── Sim / Reset ─────────────────────────────────────────────────────────────
function toggleSim() {
  if (twinStore.isSimRunning) {
    twinStore.stopSimulation()
  } else {
    twinStore.startSimulation()
  }
}

function resetScene() {
  twinStore.resetToOrigin()
  if (camera && controls) {
    camera.position.set(5, 4, 7)
    controls.target.set(0, 1, 0)
    controls.update()
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// LIFECYCLE
// ═══════════════════════════════════════════════════════════════════════════

onMounted(() => {
  buildScene()
  twinStore.startSimulation()
  animId = requestAnimationFrame(animate)
  window.addEventListener('resize', onResize)
})

onUnmounted(() => {
  // Stop sim
  twinStore.stopSimulation()

  // Cancel render loop
  cancelAnimationFrame(animId)

  // Dispose Three.js resources (prevent GPU memory leaks)
  scene.traverse((obj) => {
    if (obj instanceof THREE.Mesh) {
      obj.geometry.dispose()
      if (Array.isArray(obj.material)) {
        obj.material.forEach(m => m.dispose())
      } else {
        obj.material.dispose()
      }
    }
  })

  composer.dispose()
  renderer.dispose()
  controls.dispose()

  window.removeEventListener('resize', onResize)
})
</script>

<style scoped>
/* ── Shell ─────────────────────────────────────────────────────────────── */
.dt-shell {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #000000;
  display: flex;
}

.dt-canvas {
  width: 100% !important;
  height: 100% !important;
  display: block;
}

/* ── HUD Overlay ─────────────────────────────────────────────────────── */
.hud-overlay {
  position: absolute;
  inset: 0;
  pointer-events: none;   /* pass clicks through to canvas by default */
  z-index: 10;
}

/* Hud block common */
.hud-block {
  position: absolute;
  background: rgba(0, 0, 0, 0.72);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(0, 229, 255, 0.18);
  padding: 10px 14px;
  font-family: 'Roboto Mono', 'VT323', monospace;
  font-size: 10px;
  color: #00e5ff;
  letter-spacing: 0.07em;
  pointer-events: auto;
}

/* Corner reticle pseudo-elements */
.corner-reticle::before,
.corner-reticle::after {
  content: '';
  position: absolute;
  width: 6px;
  height: 6px;
  border-color: rgba(0, 229, 255, 0.5);
  border-style: solid;
}
.corner-reticle::before {
  top: -1px;
  left: -1px;
  border-width: 1px 0 0 1px;
}
.corner-reticle::after {
  bottom: -1px;
  right: -1px;
  border-width: 0 1px 1px 0;
}

/* ── Positions ────────────────────────────────────────────────────────── */
.hud-topleft  { top: 12px; left: 12px; min-width: 300px; }
.hud-topright { top: 12px; right: 12px; }
.hud-botleft  { bottom: 12px; left: 12px; min-width: 200px; }
.hud-botright { bottom: 12px; right: 12px; min-width: 180px; }

/* ── Title ────────────────────────────────────────────────────────────── */
.hud-title {
  font-size: 9px;
  font-weight: bold;
  letter-spacing: 0.12em;
  color: #00e5ff;
  text-shadow: 0 0 8px rgba(0, 229, 255, 0.8);
  margin-bottom: 6px;
}

.hud-sub {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 8px;
  color: rgba(0, 229, 255, 0.6);
}

.status-dot { font-size: 8px; animation: dot-blink 1.5s step-end infinite; }
@keyframes dot-blink { 50% { opacity: 0.3; } }

.mode-tag { color: #00ff66; font-weight: bold; }
.sep { color: rgba(0, 229, 255, 0.3); }
.fps-val { color: #ffb000; }
.ts-val  { color: rgba(0, 229, 255, 0.5); }

/* ── Alert chip ──────────────────────────────────────────────────────── */
.alert-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 2px;
  font-size: 10px;
  font-weight: bold;
  letter-spacing: 0.15em;
  border: 1px solid;
}
.alert-normal   { color: #00ff66; border-color: rgba(0, 255, 102, 0.4); background: rgba(0, 255, 102, 0.06); }
.alert-warning  { color: #ffb000; border-color: rgba(255, 176, 0, 0.5); background: rgba(255, 176, 0, 0.08); animation: warn-pulse 1s ease-in-out infinite; }
.alert-critical { color: #ff3333; border-color: rgba(255, 51, 51, 0.6); background: rgba(255, 51, 51, 0.12); animation: crit-pulse 0.5s step-end infinite; }
@keyframes warn-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
@keyframes crit-pulse { 50% { opacity: 0.4; } }

/* ── Coordinate matrix ───────────────────────────────────────────────── */
.matrix-header {
  font-size: 8px;
  color: rgba(0, 229, 255, 0.5);
  letter-spacing: 0.1em;
  margin-bottom: 8px;
  border-bottom: 1px solid rgba(0, 229, 255, 0.1);
  padding-bottom: 4px;
}

.matrix-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.axis-x    { color: #00e5ff; font-weight: bold; min-width: 14px; text-shadow: 0 0 6px rgba(0, 229, 255, 0.9); }
.axis-y    { color: #00ff66; font-weight: bold; min-width: 14px; text-shadow: 0 0 6px rgba(0, 255, 102, 0.9); }
.axis-z    { color: #ffb000; font-weight: bold; min-width: 14px; text-shadow: 0 0 6px rgba(255, 176, 0, 0.9); }
.axis-label { color: rgba(0, 229, 255, 0.55); font-size: 8px; min-width: 44px; }
.axis-bar  { color: rgba(0, 229, 255, 0.2); font-size: 8px; }

.coord-val {
  font-family: 'VT323', 'Roboto Mono', monospace;
  font-size: 13px;
  color: #00e5ff;
  text-shadow: 0 0 10px rgba(0, 229, 255, 0.8);
  min-width: 70px;
  text-align: right;
}

.text-orange { color: #ffb000 !important; text-shadow: 0 0 8px rgba(255, 176, 0, 0.7) !important; }
.text-green  { color: #00ff66 !important; text-shadow: 0 0 8px rgba(0, 255, 102, 0.7) !important; }
.text-red    { color: #ff3333 !important; text-shadow: 0 0 8px rgba(255, 51, 51, 0.8) !important; animation: crit-pulse 0.5s step-end infinite; }

.unit {
  color: rgba(0, 229, 255, 0.4);
  font-size: 8px;
}

.matrix-divider {
  border-top: 1px dashed rgba(0, 229, 255, 0.1);
  margin: 6px 0;
}

/* ── Control buttons ─────────────────────────────────────────────────── */
.ctrl-btns {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}

.ctrl-btn {
  flex: 1;
  padding: 5px 0;
  background: rgba(0, 229, 255, 0.04);
  border: 1px solid rgba(0, 229, 255, 0.25);
  color: #00e5ff;
  font-family: 'Roboto Mono', monospace;
  font-size: 8px;
  letter-spacing: 0.08em;
  cursor: pointer;
  border-radius: 2px;
  transition: all 0.15s ease;
}
.ctrl-btn:hover { background: rgba(0, 229, 255, 0.12); box-shadow: 0 0 6px rgba(0, 229, 255, 0.3); }
.ctrl-btn.active { color: #ffb000; border-color: rgba(255, 176, 0, 0.5); background: rgba(255, 176, 0, 0.05); }

.reset-btn { color: rgba(0, 229, 255, 0.5); }
.reset-btn:hover { color: #00e5ff; }

/* ── Bloom slider ────────────────────────────────────────────────────── */
.bloom-ctrl {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
}

.bloom-slider {
  flex: 1;
  height: 2px;
  accent-color: #00e5ff;
  cursor: pointer;
}

/* ── Crosshair ───────────────────────────────────────────────────────── */
.hud-crosshair {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 24px;
  height: 24px;
  pointer-events: none;
}
.ch-h {
  position: absolute;
  top: 50%; left: 0; right: 0;
  height: 1px;
  background: rgba(0, 229, 255, 0.2);
}
.ch-v {
  position: absolute;
  left: 50%; top: 0; bottom: 0;
  width: 1px;
  background: rgba(0, 229, 255, 0.2);
}
.ch-dot {
  position: absolute;
  top: 50%; left: 50%;
  width: 3px; height: 3px;
  background: rgba(0, 229, 255, 0.5);
  transform: translate(-50%, -50%);
  border-radius: 50%;
}
</style>
