<template>
  <div class="twin-container" ref="containerRef">
    <!-- ══ Subtle CRT Horizontal Scanlines Overlay ════════════════════════ -->
    <div class="crt-overlay"></div>
    <div class="glow-vignette"></div>

    <!-- ══ 3D Canvas ══════════════════════════════════════════════════════ -->
    <canvas ref="canvasRef" class="twin-canvas" />

    <!-- ══ Offline/Standby Watermark Overlay ═════════════════════════════ -->
    <div v-if="!kinematicsStore.isLive" class="offline-watermark mono">
      <div class="watermark-box">
        <div class="watermark-title animate-pulse">[ WARNING: STANDBY PREVIEW SWEEP — NO ACTIVE FEED ]</div>
      </div>
    </div>

    <!-- ══ Calibration/Status indicators inside canvas ═══════════════════ -->
    <div class="twin-hud mono text-[8px]">
      <div class="hud-item"><span class="label">HUD_MODEL:</span> <span class="val text-cyan">HK07_HUMANOID_V2.0</span></div>
      <div class="hud-item">
        <span class="label">TELEMETRY_LINK:</span>
        <span :class="['val', kinematicsStore.isLive ? 'text-green' : 'text-orange']">
          {{ kinematicsStore.isLive ? 'STREAMING_DDS' : 'OFFLINE_SIM' }}
        </span>
      </div>
      <div class="hud-item"><span class="label">GRID_RESOLUTION:</span> <span class="val text-cyan">0.5m</span></div>
      <div class="hud-item">
        <span class="label">PNEUMATIC_FORCE:</span>
        <span :class="['val', forceColorClass]">{{ kinematicsStore.hugForce.toFixed(1) }} N</span>
      </div>
      <div class="hud-item">
        <span class="label">PRESSURE_L:</span>
        <span class="val text-cyan">{{ kinematicsStore.pressureL.toFixed(2) }} PSI</span>
      </div>
      <div class="hud-item">
        <span class="label">PRESSURE_R:</span>
        <span class="val text-cyan">{{ kinematicsStore.pressureR.toFixed(2) }} PSI</span>
      </div>
      <div class="hud-item">
        <span class="label">ORIENTATION (Q):</span>
        <span class="val text-cyan">[{{ kinematicsStore.rotation.qw.toFixed(2) }}, {{ kinematicsStore.rotation.qx.toFixed(2) }}, {{ kinematicsStore.rotation.qy.toFixed(2) }}, {{ kinematicsStore.rotation.qz.toFixed(2) }}]</span>
      </div>
      <div class="hud-item">
        <span class="label">ORIENTATION (E):</span>
        <span class="val text-cyan">P:{{ kinematicsStore.rotationFormatted.pitch }} Y:{{ kinematicsStore.rotationFormatted.yaw }} R:{{ kinematicsStore.rotationFormatted.roll }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { useKinematicsStore } from '../stores/kinematics'

const kinematicsStore = useKinematicsStore()

const containerRef = ref<HTMLDivElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)

let renderer: THREE.WebGLRenderer
let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let controls: OrbitControls
let composer: EffectComposer
let bloomPass: UnrealBloomPass
let animId: number

// Humanoid elements
let humanoidGroup: THREE.Group
let pelvisMesh: THREE.Mesh
let torsoMesh: THREE.Mesh
let headMesh: THREE.Mesh

// Materials mapping pressure colors
let neonCyanMat: THREE.MeshBasicMaterial
let dynamicTorsoMat: THREE.MeshBasicMaterial
let dynamicLimbsMat: THREE.MeshBasicMaterial

// Spatial perception elements
let lidarPointsMesh: THREE.Points
let arrowHelper: THREE.ArrowHelper

// SLAM Costmap elements
let costmapMesh: THREE.Mesh
let costmapCanvas: HTMLCanvasElement
let costmapTexture: THREE.CanvasTexture

// Skeletal bone elements
let skeleton: THREE.Skeleton | null = null
let shoulderBone: THREE.Bone | null = null
let elbowBone: THREE.Bone | null = null
let handBone: THREE.Bone | null = null
let spineBone: THREE.Bone | null = null

// Color metrics based on hugForce
const forceColorClass = computed(() => {
  const f = kinematicsStore.hugForce
  if (f > 15) return 'text-red'
  if (f > 5) return 'text-orange'
  return 'text-green'
})

function buildScene() {
  const canvas = canvasRef.value!
  const container = containerRef.value!
  const W = container.clientWidth
  const H = container.clientHeight

  // ── Renderer ────────────────────────────────────────────────────────────
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false })
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.setSize(W, H)
  renderer.setClearColor(0x000000, 1)
  renderer.toneMapping = THREE.ReinhardToneMapping
  renderer.toneMappingExposure = 1.3

  // ── Scene ───────────────────────────────────────────────────────────────
  scene = new THREE.Scene()
  scene.background = new THREE.Color(0x000000)

  // ── Camera ──────────────────────────────────────────────────────────────
  camera = new THREE.PerspectiveCamera(50, W / H, 0.01, 100)
  camera.position.set(0, 2, 5.5)

  // ── OrbitControls ────────────────────────────────────────────────────────
  controls = new OrbitControls(camera, canvas)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.minDistance = 1.5
  controls.maxDistance = 20
  controls.target.set(0, 1.1, 0)

  // ── Grid ─────────────────────────────────────────────────────────────────
  // Electric Cyan Glowing Grid
  const gridHelper = new THREE.GridHelper(30, 60, 0x00ff66, 0x0a2233)
  gridHelper.position.y = 0
  scene.add(gridHelper)

  // Sub-axes (colored lines at origin)
  buildXYZOriginAxes()

  // ── Holographic Materials ───────────────────────────────────────────────
  neonCyanMat = new THREE.MeshBasicMaterial({ color: 0x00ff66, wireframe: true })
  dynamicTorsoMat = new THREE.MeshBasicMaterial({ color: 0x00ff66, wireframe: true })
  dynamicLimbsMat = new THREE.MeshBasicMaterial({ color: 0x00ff66, wireframe: true })

  // ── Articulated Humanoid construction ────────────────────────────────────
  humanoidGroup = new THREE.Group()
  scene.add(humanoidGroup)

  buildHumanoidBody()

  // ── Load Rigged GLTF Model ──────────────────────────────────────────────
  const loader = new GLTFLoader()
  loader.load(
    '/assets/models/hk07_mock.glb',
    (gltf) => {
      console.log('[GLTF] Successfully loaded /assets/models/hk07_mock.glb')
      const model = gltf.scene
      humanoidGroup.add(model)
    },
    undefined,
    (err: any) => {
      console.warn('[GLTF] Could not load GLTF model. Falling back to wireframe skeleton.', err?.message || err)
      buildRightArmSkeleton()
    }
  )

  // ── 2D SLAM Costmap (Occupancy Grid) ────────────────────────────────────
  costmapCanvas = document.createElement('canvas')
  costmapCanvas.width = 256
  costmapCanvas.height = 256
  costmapTexture = new THREE.CanvasTexture(costmapCanvas)
  
  const costmapGeo = new THREE.PlaneGeometry(12, 12)
  const costmapMat = new THREE.MeshBasicMaterial({
    map: costmapTexture,
    transparent: true,
    opacity: 0.75,
    side: THREE.DoubleSide
  })
  
  costmapMesh = new THREE.Mesh(costmapGeo, costmapMat)
  costmapMesh.rotation.x = -Math.PI / 2
  costmapMesh.position.y = 0.005 // raised slightly above grid to prevent flickering/z-fighting
  scene.add(costmapMesh)
  
  updateCostmap()

  // ── Post Processing (Neon Bloom) ────────────────────────────────────────
  composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))

  bloomPass = new UnrealBloomPass(
    new THREE.Vector2(W, H),
    1.6, // bloom strength
    0.4, // radius
    0.05 // threshold
  )
  composer.addPass(bloomPass)

  // ── Point Cloud (LiDAR) ────────────────────────────────────────────────
  const lidarGeo = new THREE.BufferGeometry()
  const positions = new Float32Array(0)
  lidarGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  const lidarMat = new THREE.PointsMaterial({
    color: 0xffb000, // Amber #FFB000
    size: 0.05,
    transparent: true,
    opacity: 0.85
  })
  lidarPointsMesh = new THREE.Points(lidarGeo, lidarMat)
  scene.add(lidarPointsMesh)

  // ── Avoidance Vector Arrow ──────────────────────────────────────────────
  const arrowDir = new THREE.Vector3(0, 0, 1)
  const arrowOrigin = new THREE.Vector3(0, 1.1, 0)
  arrowHelper = new THREE.ArrowHelper(arrowDir, arrowOrigin, 0.1, 0xff3333) // Crimson #FF3333
  arrowHelper.visible = false
  scene.add(arrowHelper)
}

function buildXYZOriginAxes() {
  const size = 1.5
  const createLine = (points: THREE.Vector3[], color: number) => {
    const geo = new THREE.BufferGeometry().setFromPoints(points)
    const mat = new THREE.LineBasicMaterial({ color, linewidth: 2 })
    scene.add(new THREE.Line(geo, mat))
  }

  // X Axis (Cyan)
  createLine([new THREE.Vector3(0, 0, 0), new THREE.Vector3(size, 0, 0)], 0x00ff66)
  // Y Axis (Green)
  createLine([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, size, 0)], 0x00ff66)
  // Z Axis (Amber)
  createLine([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, size)], 0xffb000)
}

function buildHumanoidBody() {
  // Pelvis
  const pelvisGeo = new THREE.BoxGeometry(0.5, 0.15, 0.35)
  pelvisMesh = new THREE.Mesh(pelvisGeo, neonCyanMat)
  pelvisMesh.position.y = 0.85
  humanoidGroup.add(pelvisMesh)

  // Spine/Torso
  const torsoGeo = new THREE.BoxGeometry(0.55, 0.7, 0.38)
  torsoMesh = new THREE.Mesh(torsoGeo, dynamicTorsoMat)
  torsoMesh.position.y = 1.28
  humanoidGroup.add(torsoMesh)

  // Neck
  const neckGeo = new THREE.CylinderGeometry(0.08, 0.08, 0.12, 8)
  const neckMesh = new THREE.Mesh(neckGeo, neonCyanMat)
  neckMesh.position.y = 1.69
  humanoidGroup.add(neckMesh)

  // Head
  const headGeo = new THREE.SphereGeometry(0.2, 12, 10)
  headMesh = new THREE.Mesh(headGeo, neonCyanMat)
  headMesh.position.y = 1.85
  humanoidGroup.add(headMesh)

  // Eye line (visor)
  const visorGeo = new THREE.BoxGeometry(0.3, 0.05, 0.04)
  const visorMesh = new THREE.Mesh(visorGeo, new THREE.MeshBasicMaterial({ color: 0x00ff66 }))
  visorMesh.position.set(0, 1.86, 0.18)
  humanoidGroup.add(visorMesh)

  // Left Arm (Upper + Lower)
  const leftUpperArmGeo = new THREE.CylinderGeometry(0.06, 0.05, 0.35, 6)
  const leftUpperArm = new THREE.Mesh(leftUpperArmGeo, dynamicLimbsMat)
  leftUpperArm.position.set(-0.4, 1.45, 0)
  leftUpperArm.rotation.z = Math.PI / 8
  humanoidGroup.add(leftUpperArm)

  const leftForearmGeo = new THREE.CylinderGeometry(0.05, 0.04, 0.3, 6)
  const leftForearm = new THREE.Mesh(leftForearmGeo, dynamicLimbsMat)
  leftForearm.position.set(-0.48, 1.15, 0)
  leftForearm.rotation.z = Math.PI / 10
  humanoidGroup.add(leftForearm)

  // Visual Right Arm is handled skeletal-wise in buildRightArmSkeleton()

  // Left Leg (Thigh + Shin + Foot)
  const leftThighGeo = new THREE.CylinderGeometry(0.08, 0.06, 0.45, 6)
  const leftThigh = new THREE.Mesh(leftThighGeo, dynamicLimbsMat)
  leftThigh.position.set(-0.18, 0.55, 0)
  humanoidGroup.add(leftThigh)

  const leftShinGeo = new THREE.CylinderGeometry(0.06, 0.05, 0.4, 6)
  const leftShin = new THREE.Mesh(leftShinGeo, dynamicLimbsMat)
  leftShin.position.set(-0.18, 0.18, 0)
  humanoidGroup.add(leftShin)

  // Right Leg (Thigh + Shin + Foot)
  const rightThighGeo = new THREE.CylinderGeometry(0.08, 0.06, 0.45, 6)
  const rightThigh = new THREE.Mesh(rightThighGeo, dynamicLimbsMat)
  rightThigh.position.set(0.18, 0.55, 0)
  humanoidGroup.add(rightThigh)

  const rightShinGeo = new THREE.CylinderGeometry(0.06, 0.05, 0.4, 6)
  const rightShin = new THREE.Mesh(rightShinGeo, dynamicLimbsMat)
  rightShin.position.set(0.18, 0.18, 0)
  humanoidGroup.add(rightShin)
}

function updateHeatmapColors() {
  const f = kinematicsStore.hugForce
  let targetColorHex = 0x00ff66 // Emerald: Healthy / Low force

  if (f > 15) {
    targetColorHex = 0xff3333 // Crimson: Dangerous / High force
  } else if (f > 5) {
    targetColorHex = 0xffb000 // Amber: Warning / Medium force
  }

  // Update material colors dynamically
  dynamicTorsoMat.color.setHex(targetColorHex)
  dynamicLimbsMat.color.setHex(targetColorHex)
}

// Watchers for spatial perception & SLAM Costmap Projection
watch(() => kinematicsStore.lidarPoints, (newPoints) => {
  if (!lidarPointsMesh) return
  const count = newPoints.length
  const positions = new Float32Array(count * 3)
  for (let i = 0; i < count; i++) {
    positions[i * 3] = newPoints[i].x
    positions[i * 3 + 1] = newPoints[i].y
    positions[i * 3 + 2] = newPoints[i].z
  }
  lidarPointsMesh.geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  lidarPointsMesh.geometry.computeBoundingBox()
  lidarPointsMesh.geometry.computeBoundingSphere()

  // Update SLAM Costmap representation
  updateCostmap()
}, { deep: true })

watch(() => kinematicsStore.avoidanceVector, (newVec) => {
  if (!arrowHelper) return
  const length = Math.sqrt(newVec.x * newVec.x + newVec.y * newVec.y + newVec.z * newVec.z)
  if (length < 0.01) {
    arrowHelper.visible = false
  } else {
    arrowHelper.visible = true
    const dir = new THREE.Vector3(newVec.x, newVec.y, newVec.z).normalize()
    arrowHelper.setDirection(dir)
    arrowHelper.setLength(length, 0.2, 0.08)
  }
}, { deep: true })

// Watch for ROS2 JointState updates to move the bones/armatures dynamically
watch(() => kinematicsStore.jointStates, (newStates) => {
  if (!newStates || !newStates.name || !newStates.position) return
  const names = newStates.name
  const positions = newStates.position
  for (let i = 0; i < names.length; i++) {
    const jointName = names[i]
    const angle = positions[i]
    // Search the Three.js hierarchy for matching rigged bones or meshes
    const bone = scene.getObjectByName(jointName)
    if (bone) {
      if (jointName.includes('RightArm') || jointName.includes('RightForeArm')) {
        bone.rotation.z = angle
      } else {
        bone.rotation.y = angle
      }
    }
  }
}, { deep: true })

// ── skeletal bone arm assembly (Procedural Fallback Rig) ──────────────────
function buildRightArmSkeleton() {
  const dummyGeo = new THREE.BufferGeometry()
  const dummyMat = new THREE.MeshBasicMaterial({ visible: false })
  const skinnedMesh = new THREE.SkinnedMesh(dummyGeo, dummyMat)
  humanoidGroup.add(skinnedMesh)

  const rootBone = new THREE.Bone()
  rootBone.position.set(0, 0.85, 0)
  rootBone.name = 'mixamorig_Hips'

  spineBone = new THREE.Bone()
  spineBone.position.set(0, 0.43, 0)
  spineBone.name = 'mixamorig_Spine'

  shoulderBone = new THREE.Bone()
  shoulderBone.position.set(0.4, 0.17, 0)
  shoulderBone.name = 'mixamorig_RightArm' // Right Shoulder

  elbowBone = new THREE.Bone()
  elbowBone.position.set(0.08, -0.3, 0)
  elbowBone.name = 'mixamorig_RightForeArm' // Right Elbow

  handBone = new THREE.Bone()
  handBone.position.set(0.05, -0.28, 0)
  handBone.name = 'mixamorig_RightHand' // Right Hand

  rootBone.add(spineBone)
  spineBone.add(shoulderBone)
  shoulderBone.add(elbowBone)
  elbowBone.add(handBone)
  skinnedMesh.add(rootBone)

  const bonesList = [rootBone, spineBone, shoulderBone, elbowBone, handBone]
  skeleton = new THREE.Skeleton(bonesList)
  skinnedMesh.bind(skeleton)

  // Visual Meshes attached to Bones
  const rightUpperArmGeo = new THREE.CylinderGeometry(0.06, 0.05, 0.35, 6)
  const rightUpperArm = new THREE.Mesh(rightUpperArmGeo, dynamicLimbsMat)
  rightUpperArm.position.set(0.04, -0.15, 0)
  rightUpperArm.rotation.z = -Math.PI / 8
  shoulderBone.add(rightUpperArm)

  const rightForearmGeo = new THREE.CylinderGeometry(0.05, 0.04, 0.3, 6)
  const rightForearm = new THREE.Mesh(rightForearmGeo, dynamicLimbsMat)
  rightForearm.position.set(0.025, -0.14, 0)
  rightForearm.rotation.z = -Math.PI / 10
  elbowBone.add(rightForearm)
}

// ── SLAM Costmap Dynamic Canvas Renderer ─────────────────────────────────
function updateCostmap() {
  if (!costmapCanvas || !costmapTexture) return
  const ctx = costmapCanvas.getContext('2d')
  if (!ctx) return

  // Clear floor grid (fully transparent background)
  ctx.clearRect(0, 0, 256, 256)

  // Occupancy cells: 24x24 layout over a 12m square area
  const gridResolution = 24
  const cellSize = 256 / gridResolution
  const occupancy = Array(gridResolution).fill(0).map(() => Array(gridResolution).fill(false))

  const points = kinematicsStore.lidarPoints
  points.forEach((pt) => {
    const col = Math.floor((pt.x + 6.0) / 12.0 * gridResolution)
    const row = Math.floor((pt.z + 6.0) / 12.0 * gridResolution)
    if (col >= 0 && col < gridResolution && row >= 0 && row < gridResolution) {
      occupancy[row][col] = true
    }
  })

  // Draw cells
  for (let r = 0; r < gridResolution; r++) {
    for (let c = 0; c < gridResolution; c++) {
      const x = c * cellSize
      const y = r * cellSize
      if (occupancy[r][c]) {
        // Red fill and Matrix Red border on occupied elements
        ctx.fillStyle = 'rgba(255, 51, 51, 0.45)'
        ctx.fillRect(x, y, cellSize, cellSize)
        ctx.strokeStyle = '#FF3333'
        ctx.lineWidth = 1.5
        ctx.strokeRect(x, y, cellSize, cellSize)
      } else {
        // Safe grid trace lines
        ctx.strokeStyle = 'rgba(0, 255, 102, 0.05)'
        ctx.lineWidth = 0.5
        ctx.strokeRect(x, y, cellSize, cellSize)
      }
    }
  }
  costmapTexture.needsUpdate = true
}

function animate() {
  animId = requestAnimationFrame(animate)

  controls.update()

  // Dumb Render Position & Orientation mapping from store
  if (humanoidGroup) {
    if (!kinematicsStore.isLive) {
      const t = Date.now() * 0.001
      humanoidGroup.position.y = Math.sin(t * 1.5) * 0.03
      humanoidGroup.rotation.y = Math.sin(t * 0.5) * 0.1
    } else {
      humanoidGroup.position.set(
        kinematicsStore.position.x,
        kinematicsStore.position.y,
        kinematicsStore.position.z
      )
      humanoidGroup.quaternion.set(
        kinematicsStore.rotation.qx,
        kinematicsStore.rotation.qy,
        kinematicsStore.rotation.qz,
        kinematicsStore.rotation.qw
      )
    }
  }

  // Sync avoidance vector origin with robot position
  if (arrowHelper) {
    arrowHelper.position.set(
      kinematicsStore.position.x,
      kinematicsStore.position.y + 1.1,
      kinematicsStore.position.z
    )
  }

  // Heatmap UI updates
  updateHeatmapColors()

  composer.render()
}

function onResize() {
  if (!containerRef.value) return
  const W = containerRef.value.clientWidth
  const H = containerRef.value.clientHeight
  camera.aspect = W / H
  camera.updateProjectionMatrix()
  renderer.setSize(W, H)
  composer.setSize(W, H)
}

onMounted(() => {
  buildScene()
  window.addEventListener('resize', onResize)
  animate()
})

onUnmounted(() => {
  cancelAnimationFrame(animId)
  window.removeEventListener('resize', onResize)

  // Clean resources
  scene.traverse((obj) => {
    const anyObj = obj as any
    if (anyObj.geometry) {
      anyObj.geometry.dispose()
    }
    if (anyObj.material) {
      if (Array.isArray(anyObj.material)) {
        anyObj.material.forEach((m: any) => m.dispose())
      } else {
        anyObj.material.dispose()
      }
    }
  })

  if (costmapTexture) costmapTexture.dispose()

  composer.dispose()
  renderer.dispose()
  controls.dispose()
})
</script>

<style scoped>
.twin-container {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #000000;
  border: 1px solid rgba(0, 255, 102, 0.15);
}

.twin-canvas {
  width: 100% !important;
  height: 100% !important;
  display: block;
}

/* CRT scanlines */
.crt-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%);
  background-size: 100% 4px;
  z-index: 5;
  pointer-events: none;
  opacity: 0.85;
}

/* Neon Glow Vignette */
.glow-vignette {
  position: absolute;
  inset: 0;
  box-shadow: inset 0 0 40px rgba(0, 255, 102, 0.15);
  pointer-events: none;
  z-index: 6;
}

.twin-hud {
  position: absolute;
  top: 10px;
  left: 10px;
  background: rgba(0, 0, 0, 0.8);
  border: 1px solid rgba(0, 255, 102, 0.25);
  padding: 8px 12px;
  border-radius: 2px;
  color: #00ff66;
  display: flex;
  flex-direction: column;
  gap: 4px;
  pointer-events: none;
  z-index: 7;
}

.hud-item {
  display: flex;
  justify-content: space-between;
  gap: 15px;
}

.label {
  color: rgba(0, 255, 102, 0.55);
}

.text-cyan {
  color: #00ff66;
  text-shadow: 0 0 5px rgba(0, 255, 102, 0.8);
}
.text-green {
  color: #00ff66;
  text-shadow: 0 0 5px rgba(0, 255, 102, 0.8);
}
.text-orange {
  color: #ffb000;
  text-shadow: 0 0 5px rgba(255, 176, 0, 0.8);
}
.text-red {
  color: #ff3333;
  text-shadow: 0 0 5px rgba(255, 51, 51, 0.8);
  animation: alarm-blink 0.5s step-end infinite;
}

@keyframes alarm-blink {
  50% { opacity: 0.5; }
}

.offline-watermark {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 8;
  pointer-events: none;
  text-align: center;
}

.watermark-box {
  background: rgba(0, 0, 0, 0.85);
  border: 1px solid rgba(255, 176, 0, 0.4);
  padding: 12px 24px;
  border-radius: 2px;
  box-shadow: 0 0 15px rgba(255, 176, 0, 0.15);
  position: relative;
}

.watermark-box::before,
.watermark-box::after {
  content: '';
  position: absolute;
  width: 8px;
  height: 8px;
  border-color: rgba(255, 176, 0, 0.6);
  border-style: solid;
}
.watermark-box::before {
  top: -1px;
  left: -1px;
  border-width: 1px 0 0 1px;
}
.watermark-box::after {
  bottom: -1px;
  right: -1px;
  border-width: 0 1px 1px 0;
}

.watermark-title {
  color: #ffb000;
  font-family: 'Orbitron', monospace;
  font-size: 13px;
  font-weight: bold;
  letter-spacing: 0.15em;
  text-shadow: 0 0 8px rgba(255, 176, 0, 0.8);
  margin-bottom: 4px;
}

.watermark-subtitle {
  color: rgba(255, 176, 0, 0.65);
  font-family: 'Roboto Mono', monospace;
  font-size: 8px;
  letter-spacing: 0.1em;
}

.animate-pulse {
  animation: watermark-pulse 1.8s ease-in-out infinite;
}

@keyframes watermark-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
