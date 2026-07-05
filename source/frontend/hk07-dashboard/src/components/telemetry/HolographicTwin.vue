<template>
  <div class="holographic-twin-container" :class="{ 'fall-state-active': telemetry.fallState }">
    <!-- FALL ALERT OVERLAY -->
    <transition name="alert-fade">
      <div v-if="telemetry.fallState" class="fall-alert-overlay">
        <div class="alert-content">
          <div class="alert-text">
            [ALERT: SUDDEN ACCELERATION DETECTED - G: {{ (telemetry.gForceMagnitude || 0).toFixed(2) }}g]
          </div>
          <div class="fall-confidence">
            CONFIDENCE: {{ formatNumber(telemetry.fallConfidence || 0.95, 2) }}
          </div>
          <div class="g-force-display">
            G-FORCE: {{ formatNumber(telemetry.gForceMagnitude || 0, 2) }}g
          </div>
        </div>
      </div>
    </transition>

    <!-- VIEWPORT BORDER (Dynamic Cyan/Red) -->
    <div
      class="viewport-frame"
      :style="{ borderColor: telemetry.fallState ? themeConfig.dangerRed : themeConfig.borderCyan }"
    >
      <!-- HEADER INFO -->
      <div class="viewport-header">
        <span class="header-label">HOLOGRAPHIC TWIN VIEWPORT</span>
        <span class="device-id">{{ telemetry.deviceId }}</span>
      </div>

      <!-- 3D CANVAS CONTAINER -->
      <div class="canvas-wrapper">
        <canvas
          ref="threeCanvas"
          class="three-canvas"
        />
        <!-- GRID OVERLAY -->
        <div class="grid-overlay" />
      </div>

      <!-- TELEMETRY READOUT (Bottom Bar) -->
      <div class="telemetry-readout">
        <div class="readout-item">
          <span class="readout-label">ACCEL:</span>
          <span class="readout-value">
            X:{{ formatNumber(telemetry.rawAccel.x, 1) }} Y:{{ formatNumber(telemetry.rawAccel.y, 1) }} Z:{{ formatNumber(telemetry.rawAccel.z, 1) }}
          </span>
        </div>
        <div class="readout-item">
          <span class="readout-label">ORIENT:</span>
          <span class="readout-value">
            YAW:{{ formatNumber(telemetry.yaw, 1) }}° PITCH:{{ formatNumber(telemetry.pitch || 0, 1) }}° ROLL:{{ formatNumber(telemetry.roll || 0, 1) }}°
          </span>
        </div>
        <div class="readout-item">
          <span class="readout-label">STATE:</span>
          <span class="readout-value" :style="{ color: telemetry.fallState ? themeConfig.dangerRed : themeConfig.successGreen }">
            {{ telemetry.fallState ? 'FALL_DETECTED' : 'NOMINAL' }}
          </span>
        </div>
      </div>
    </div>

    <!-- STATS PANEL (Right side) -->
    <div class="stats-panel">
      <div class="stats-title">MESH STATE</div>
      <div class="stats-content">
        <div class="stat-row">
          <span class="stat-label">Vertices:</span>
          <span class="stat-value">{{ meshStats.vertices }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Faces:</span>
          <span class="stat-value">{{ meshStats.faces }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Frame Rate:</span>
          <span class="stat-value">{{ meshStats.fps }} FPS</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Rotation:</span>
          <span class="stat-value">
            X:{{ formatNumber(meshRotation.x, 1) }} Y:{{ formatNumber(meshRotation.y, 1) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import type { RobotTelemetry, WidgetTheme } from './types';
import { BAYMAX_THEME } from './types';

// Import Three.js (assumed to be available via npm install three)
let THREE: any = null;

interface Props {
  telemetry: RobotTelemetry;
  theme?: WidgetTheme;
}

const props = withDefaults(defineProps<Props>(), {
  theme: () => BAYMAX_THEME
});

const threeCanvas = ref<HTMLCanvasElement | null>(null);
const themeConfig = computed(() => props.theme);

const meshStats = ref({
  vertices: 0,
  faces: 0,
  fps: 0
});

const meshRotation = ref({ x: 0, y: 0, z: 0 });

let scene: any = null;
let camera: any = null;
let renderer: any = null;
let wireframeMesh: any = null;
let animationFrameId: number | null = null;
let frameCount = 0;
let lastFrameTime = Date.now();

function formatNumber(value: number, decimals: number = 0): string {
  if (decimals === 0) {
    return Math.round(value).toString().padStart(3, ' ');
  }
  return value.toFixed(decimals).padStart(6, ' ');
}

function createWireframeMesh() {
  // Create a geometric robot representation - cube with additional geometry
  const geometry = new THREE.Group();

  // Main torso box
  const torsoGeom = new THREE.BoxGeometry(1, 1.5, 0.8);
  const torsoWire = new THREE.LineSegments(
    torsoGeom,
    new THREE.LineBasicMaterial({ color: 0x00FFCC, linewidth: 1 })
  );
  geometry.add(torsoWire);

  // Head (small sphere wireframe)
  const headGeom = new THREE.IcosahedronGeometry(0.3, 2);
  const headWire = new THREE.LineSegments(
    headGeom,
    new THREE.LineBasicMaterial({ color: 0x00FFCC })
  );
  headWire.position.y = 1.2;
  geometry.add(headWire);

  // Limbs (boxes)
  const limbGeom = new THREE.BoxGeometry(0.2, 1, 0.2);
  const limbs = [
    { pos: [-0.4, -0.5, 0], name: 'left-arm' },
    { pos: [0.4, -0.5, 0], name: 'right-arm' },
    { pos: [-0.3, -1.2, 0], name: 'left-leg' },
    { pos: [0.3, -1.2, 0], name: 'right-leg' }
  ];

  limbs.forEach((limb) => {
    const limbWire = new THREE.LineSegments(
      limbGeom,
      new THREE.LineBasicMaterial({ color: 0x00FFCC })
    );
    limbWire.position.set(limb.pos[0], limb.pos[1], limb.pos[2]);
    geometry.add(limbWire);
  });

  return geometry;
}

function initializeThree() {
  if (!threeCanvas.value) return;

  // Try to load Three.js
  try {
    // Check if Three is available globally (script tag) or import it
    if (typeof window !== 'undefined' && (window as any).THREE) {
      THREE = (window as any).THREE;
    } else {
      console.warn('THREE.js not available. Ensure it is loaded via CDN or npm.');
      return;
    }
  } catch (e) {
    console.error('Failed to initialize Three.js:', e);
    return;
  }

  const width = threeCanvas.value.clientWidth;
  const height = threeCanvas.value.clientHeight;

  // Scene setup
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x000000);

  // Camera setup
  camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 1000);
  camera.position.z = 3;

  // Renderer setup
  renderer = new THREE.WebGLRenderer({ canvas: threeCanvas.value, antialias: true, alpha: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(window.devicePixelRatio);

  // Create grid background
  const gridHelper = new THREE.GridHelper(10, 20);
  gridHelper.position.y = -2;
  gridHelper.material.color.setHex(0x00FFCC);
  gridHelper.material.linewidth = 0.5;
  gridHelper.material.opacity = 0.1;
  gridHelper.material.transparent = true;
  scene.add(gridHelper);

  // Create wireframe mesh
  wireframeMesh = createWireframeMesh();
  scene.add(wireframeMesh);

  // Lighting (subtle)
  const light = new THREE.AmbientLight(0xffffff, 0.3);
  scene.add(light);

  const directionalLight = new THREE.DirectionalLight(0x00FFCC, 0.2);
  directionalLight.position.set(5, 5, 5);
  scene.add(directionalLight);

  // Update mesh stats
  wireframeMesh.traverse((child: any) => {
    if (child.geometry && child.geometry.attributes && child.geometry.attributes.position) {
      meshStats.value.vertices += child.geometry.attributes.position.count;
    }
  });

  // Start animation loop
  animate();
}

function animate() {
  animationFrameId = requestAnimationFrame(animate);

  if (!scene || !renderer || !camera || !wireframeMesh) return;

  // Directly set the rotation to the actual pitch, yaw, and roll received in props.telemetry
  const pitchRad = ((props.telemetry.pitch || 0) * Math.PI) / 180;
  const yawRad = ((props.telemetry.yaw || 0) * Math.PI) / 180;
  const rollRad = ((props.telemetry.roll || 0) * Math.PI) / 180;

  wireframeMesh.rotation.x = pitchRad;
  wireframeMesh.rotation.y = yawRad;
  wireframeMesh.rotation.z = rollRad;

  // Add pulsing effect on fall detection
  if (props.telemetry.fallState) {
    const pulse = Math.sin(Date.now() * 0.01) * 0.1 + 1;
    wireframeMesh.scale.set(pulse, pulse, pulse);
  } else {
    wireframeMesh.scale.set(1, 1, 1);
  }

  // Calculate FPS
  frameCount++;
  const now = Date.now();
  if (now - lastFrameTime >= 1000) {
    meshStats.value.fps = frameCount;
    frameCount = 0;
    lastFrameTime = now;
  }

  // Render
  renderer.render(scene, camera);
}

function onWindowResize() {
  if (!threeCanvas.value || !renderer || !camera) return;

  const width = threeCanvas.value.clientWidth;
  const height = threeCanvas.value.clientHeight;

  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height);
}

onMounted(() => {
  initializeThree();
  window.addEventListener('resize', onWindowResize);
});

onUnmounted(() => {
  window.removeEventListener('resize', onWindowResize);
  if (animationFrameId !== null) {
    cancelAnimationFrame(animationFrameId);
  }
  if (renderer) {
    renderer.dispose();
  }
});
</script>

<style scoped>
.holographic-twin-container {
  position: relative;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 12px;
  font-family: 'Share Tech Mono', monospace;
  background-color: #000000;
  color: #F0F8FF;
  padding: 12px;
}

.holographic-twin-container.fall-state-active {
  animation: crimson-pulse 0.4s infinite;
}

@keyframes crimson-pulse {
  0%, 100% {
    filter: drop-shadow(0 0 4px #FF3333);
  }
  50% {
    filter: drop-shadow(0 0 8px #FF3333);
  }
}

.fall-alert-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: linear-gradient(180deg, rgba(255, 51, 51, 0.15) 0%, transparent 100%);
  padding: 12px;
  border-bottom: 2px solid #FF3333;
  animation: alert-slide-in 0.3s ease-out;
}

@keyframes alert-slide-in {
  from {
    transform: translateY(-100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.alert-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.alert-text {
  font-size: 9px;
  letter-spacing: 1px;
  color: #FF3333;
  font-weight: 700;
  text-transform: uppercase;
}

.fall-confidence {
  font-size: 8px;
  color: #FF6600;
  letter-spacing: 0.5px;
}

.g-force-display {
  font-size: 10px;
  font-family: 'VT323', monospace;
  color: #FF3333;
  letter-spacing: 1px;
}

.alert-fade-enter-active,
.alert-fade-leave-active {
  transition: all 0.3s ease;
}

.alert-fade-enter-from,
.alert-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.viewport-frame {
  flex: 1;
  border: 2px solid #00FFCC;
  border-radius: 0;
  background-color: #000000;
  box-shadow: inset 0 0 12px rgba(0, 255, 204, 0.15), 0 0 16px rgba(0, 255, 204, 0.2);
  display: flex;
  flex-direction: column;
  transition: all 0.3s ease;
  position: relative;
}

.viewport-frame.fall-state-active {
  border-color: #FF3333;
  box-shadow: inset 0 0 12px rgba(255, 51, 51, 0.2), 0 0 16px rgba(255, 51, 51, 0.3);
}

.viewport-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px;
  border-bottom: 1px solid rgba(0, 255, 204, 0.3);
  font-size: 8px;
  letter-spacing: 1px;
  text-transform: uppercase;
}

.header-label {
  color: #F0F8FF;
  font-weight: 700;
}

.device-id {
  color: #00FFCC;
}

.canvas-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  min-height: 300px;
}

.three-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.grid-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image:
    linear-gradient(0deg, transparent 24%, rgba(0, 255, 204, 0.02) 25%, rgba(0, 255, 204, 0.02) 26%, transparent 27%, transparent 74%, rgba(0, 255, 204, 0.02) 75%, rgba(0, 255, 204, 0.02) 76%, transparent 77%, transparent),
    linear-gradient(90deg, transparent 24%, rgba(0, 255, 204, 0.02) 25%, rgba(0, 255, 204, 0.02) 26%, transparent 27%, transparent 74%, rgba(0, 255, 204, 0.02) 75%, rgba(0, 255, 204, 0.02) 76%, transparent 77%, transparent);
  background-size: 50px 50px;
  pointer-events: none;
}

.telemetry-readout {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  border-top: 1px solid rgba(0, 255, 204, 0.2);
  background-color: rgba(0, 0, 0, 0.5);
  font-size: 8px;
  letter-spacing: 0.5px;
}

.readout-item {
  display: flex;
  gap: 6px;
}

.readout-label {
  color: #00FFCC;
  font-weight: 600;
  min-width: 60px;
}

.readout-value {
  color: #F0F8FF;
  font-family: 'VT323', monospace;
  flex: 1;
  text-align: right;
}

.stats-panel {
  width: 160px;
  border: 1px solid #00FFCC;
  border-radius: 0;
  padding: 8px;
  background-color: #000000;
  box-shadow: inset 0 0 8px rgba(0, 255, 204, 0.1), 0 0 12px rgba(0, 255, 204, 0.15);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stats-title {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: #F0F8FF;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(0, 255, 204, 0.2);
}

.stats-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.stat-row {
  display: flex;
  justify-content: space-between;
  font-size: 8px;
}

.stat-label {
  color: #00FFCC;
  letter-spacing: 0.5px;
}

.stat-value {
  color: #F0F8FF;
  font-family: 'VT323', monospace;
  letter-spacing: 1px;
}
</style>
