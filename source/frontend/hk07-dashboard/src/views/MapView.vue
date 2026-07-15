<template>
  <div class="sensor-view map-page-view">
    <!-- Header status strip -->
    <div class="sv-header">
      <div class="sv-header-left">
        <span class="sv-title">[ HK07 // TACTICAL NAVIGATION CORE ]</span>
        <span class="sv-label">GRID_SYS: WGS-84 | LINK: {{ locSource }}</span>
      </div>
      <div class="sv-header-right mono text-xs">
        <span class="label">TIME:</span> <span class="val text-green" style="margin-right:12px;">{{ clockTime }}</span>
        <span class="label">SIGNAL:</span> <span class="val text-cyan">{{ sensorStore.locStatus }}</span>
      </div>
    </div>

    <!-- Fullscreen Viewport Area -->
    <div class="map-viewport-wrapper">
      <!-- 2D Leaflet map container (Flat Plane Visual) -->
      <div 
        ref="mapContainer" 
        class="real-map" 
        :class="{ 'satellite-tiles': tileType === 'satellite' }"
      ></div>

      <!-- Immersive Cyber HUD Overlay (Corner widgets) -->
      <div class="map-hud-overlay">
        <div class="radar-scanline"></div>

        <!-- ── COLUMN LEFT (TOP-LEFT) ── -->
        <div class="hud-col-left-top">
          <!-- VIEWPORT SETUP -->
          <div class="hud-block hud-tactical-zoom font-mono">
            <div class="zoom-title">// VIEWPORT_MODE</div>
            <div class="toggle-row">
              <button class="hud-toggle-btn active">[2D TACTICAL]</button>
              <button @click="goToDigitalTwin" class="hud-toggle-btn">[3D TWIN]</button>
            </div>
            
            <div class="zoom-title" style="margin-top: 6px; border-top: 1px dashed rgba(0, 255, 102, 0.2); padding-top: 4px;">// TILE_SOURCE</div>
            <div class="toggle-row">
              <button @click="setTileType('roads')" :class="{ active: tileType === 'roads' }" class="hud-toggle-btn">[ROADS]</button>
              <button @click="setTileType('satellite')" :class="{ active: tileType === 'satellite' }" class="hud-toggle-btn">[SAT]</button>
            </div>

            <div class="zoom-title" style="margin-top: 6px; border-top: 1px dashed rgba(0, 255, 102, 0.2); padding-top: 4px;">// CAM_TRACK</div>
            <button @click="recenterMap" :class="{ active: isTracking }" class="zoom-btn">
              [{{ isTracking ? 'LKD_CENTER' : 'FREE_CAM' }}]
            </button>
          </div>

          <!-- TARGETS PANEL -->
          <div class="hud-block target-panel font-mono">
            <div class="panel-header-mini">// LOCATION_SEARCH</div>
            <div class="target-search-box" style="display: flex; gap: 4px;">
              <input 
                type="text" 
                v-model="targetSearch" 
                @keyup.enter="searchLocation"
                placeholder="ENTER LOCATION..." 
                class="hud-input font-mono" 
                style="flex: 1;"
              />
              <button @click="searchLocation" class="hud-toggle-btn" style="width: 48px; border-color: rgba(0, 255, 102, 0.4); color: #00FF66;">[FIND]</button>
            </div>
            <div class="target-list scroll-styled">
              <div v-if="isSearching" class="text-xs text-dim animate-pulse" style="padding: 4px 6px;">
                &gt;&gt; QUERYING GEODATABASE...
              </div>
              <template v-else>
                <div 
                  v-for="t in (foundLocations.length > 0 ? foundLocations : presets)" 
                  :key="t.name" 
                  @click="selectPresetTarget(t)"
                  :class="{ active: destinationName === t.name }" 
                  class="target-item"
                >
                  <div class="target-item-header">
                    <span class="item-name" :title="t.fullName || t.name">{{ t.name }}</span>
                  </div>
                  <div class="target-item-footer">
                    <span class="item-coords">[{{ t.lat.toFixed(3) }}, {{ t.lng.toFixed(3) }}]</span>
                    <span class="item-dist text-green">
                      {{ calcDistanceM(robotLat, robotLng, t.lat, t.lng).toFixed(0) }}m
                    </span>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- ── COLUMN RIGHT (TOP-RIGHT) ── -->
        <div class="hud-col-right-top">
          <!-- COORDINATE PANEL -->
          <div class="hud-block coord-readout font-mono">
            <div class="zoom-title">// CURRENT_POSITION</div>
            <div class="coord-line">
              <span class="coord-lbl">LAT</span>
              <span class="coord-val">{{ robotLat.toFixed(6) }}°</span>
            </div>
            <div class="coord-line">
              <span class="coord-lbl">LNG</span>
              <span class="coord-val">{{ robotLng.toFixed(6) }}°</span>
            </div>
            <div class="coord-line">
              <span class="coord-lbl">ALT</span>
              <span class="coord-val">{{ robotAlt.toFixed(1) }}<span class="coord-unit">m</span></span>
            </div>
            
            <div v-if="destinationCoords" class="zoom-title" style="margin-top: 6px; border-top: 1px dashed rgba(0, 255, 102, 0.2); padding-top: 4px;">// TARGET_VECTOR</div>
            <template v-if="destinationCoords">
              <div class="coord-line">
                <span class="coord-lbl">T_LAT</span>
                <span class="coord-val">{{ destinationCoords[0].toFixed(6) }}°</span>
              </div>
              <div class="coord-line">
                <span class="coord-lbl">T_LNG</span>
                <span class="coord-val">{{ destinationCoords[1].toFixed(6) }}°</span>
              </div>
              <div class="coord-line">
                <span class="coord-lbl">DIST</span>
                <span class="coord-val">{{ routeDistance.toFixed(0) }}<span class="coord-unit">m</span></span>
              </div>
            </template>
          </div>
        </div>

        <!-- ── COLUMN LEFT (BOTTOM-LEFT) ── -->
        <div class="hud-col-left-bottom">
          <!-- DIRECTIVES STREAM -->
          <div class="hud-block directives-panel font-mono">
            <div class="panel-header-mini">// DIRECTIVES_STREAM</div>
            <div class="directives-list text-xs">
              <div v-if="!destinationCoords" class="directives-placeholder text-dim">
                &gt;&gt; STANDBY: DEFINE TARGET TO INITIATE PATHFINDING...
              </div>
              <template v-else>
                <div class="route-summary">
                  <div class="summary-item"><span class="lbl">DIST:</span> <span class="val text-green">{{ routeDistance.toFixed(1) }}m</span></div>
                  <div class="summary-item"><span class="lbl">ETA:</span> <span class="val text-cyan">{{ routeEta }}s</span></div>
                </div>
                <div class="directives-scroll scroll-styled">
                  <div 
                    v-for="(d, idx) in navigationDirectives" 
                    :key="idx" 
                    class="directive-row"
                    :class="{ active: idx === currentDirectiveIdx }"
                  >
                    <span class="dir-idx">[{{ String(idx + 1).padStart(2, '0') }}]</span>
                    <span class="dir-text">{{ d }}</span>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </div>

        <!-- ── COLUMN BOTTOM CENTER (TRAJECTORY HELPER) ── -->
        <div class="hud-col-bottom-center">
          <!-- COMPASS / BEARING -->
          <div class="hud-block directional-guidance font-mono">
            <div class="compass-wrap">
              <div class="compass-dial">
                <div class="compass-arrow" :style="{ transform: `rotate(${headingDiff}deg)` }">▲</div>
              </div>
            </div>
            <div class="compass-text">
              <div class="panel-header-mini">// TRAJECTORY_HELPER</div>
              <div class="term-line"><span class="lbl">HEADING</span> <span class="val text-green">{{ safeToFixed(sensorStore.imu?.compass_heading, 1, '0.0') }}°</span></div>
              <div class="term-line"><span class="lbl">BEARING</span> <span class="val text-cyan">{{ targetBearing.toFixed(1) }}°</span></div>
              <div class="term-line"><span class="lbl">DIFF</span> <span class="val text-warn">{{ headingDiff.toFixed(1) }}°</span></div>
            </div>
          </div>
        </div>

        <!-- ── COLUMN RIGHT (BOTTOM-RIGHT) ── -->
        <div class="hud-col-right-bottom">
          <!-- RANGE SCALE selector buttons -->
          <div class="hud-block hud-sys-parameters font-mono">
            <div class="sys-title">// RANGE_SCALE</div>
            <button 
              v-for="r in tacticalRanges" 
              :key="r.zoom" 
              @click="setTacticalRange(r.zoom)" 
              :class="{ active: currentZoom === r.zoom }" 
              class="zoom-btn"
            >
              [{{ r.label.toUpperCase() }}]
            </button>
          </div>
        </div>

        <!-- Central targeting crosshair -->
        <div class="map-crosshair">
          <span class="crosshair-h"></span>
          <span class="crosshair-v"></span>
          <span class="crosshair-dot"></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useSensorTelemetryStore } from '../stores/sensorTelemetry'
import { useVitalsStore } from '../stores/vitals'
import { useDeviceConfigStore } from '../stores/deviceConfig'

const router = useRouter()
const sensorStore = useSensorTelemetryStore()
const vitalsStore = useVitalsStore()
const cfg = useDeviceConfigStore()

// Clock reference
const clockTime = ref('00:00:00')
let clockInterval: number | null = null

function updateClock() {
  const d = new Date()
  clockTime.value = d.toTimeString().split(' ')[0]
}

// Redirect view to 3D Digital Twin screen
function goToDigitalTwin() {
  router.push('/digital-twin')
}

// ── Robot location telemetry state ────
const DEFAULT_LAT = 10.3864   
const DEFAULT_LNG = 105.4352
const robotLat = ref(DEFAULT_LAT)
const robotLng = ref(DEFAULT_LNG)
const robotAlt = ref(0)

const locSource = computed(() => {
  const status = sensorStore.locStatus
  if (status === 'LIVE' || status === 'STALE') {
    return 'ONLINE'
  }
  return 'OFFLINE'
})

// Sync location telemetry from the sensor telemetry store
watch(
  () => [
    sensorStore.location.latitude,
    sensorStore.location.longitude,
    sensorStore.location.altitude,
    sensorStore.locStatus
  ],
  ([lat, lng, alt, status]) => {
    const isOnline = status === 'LIVE' || status === 'STALE'
    if (isOnline && lat !== 0 && lng !== 0) {
      robotLat.value = lat as number
      robotLng.value = lng as number
      robotAlt.value = (alt as number) || 0
    } else {
      robotLat.value = DEFAULT_LAT
      robotLng.value = DEFAULT_LNG
      robotAlt.value = 0
    }
  },
  { immediate: true }
)

// Default preset targets fallback
const presets = [
  { name: 'LONG_XUYEN_CITY_HALL', lat: 10.3759, lng: 105.4326, type: 'Government Office' },
  { name: 'BINH_KHANH_PARK', lat: 10.3975, lng: 105.4190, type: 'Public Park' },
  { name: 'AN_GIANG_UNIVERSITY', lat: 10.3705, lng: 105.4322, type: 'University' },
  { name: 'NGOC_TRAI_NUI_COFFEE', lat: 10.39565, lng: 105.42075, type: 'Cafe / Coffee Shop' }
]

// ── Address Geocoding Search (Nominatim API) ───────────────────────────────
const targetSearch = ref('')
const isSearching = ref(false)
const foundLocations = ref<any[]>([])

async function searchLocation() {
  if (!targetSearch.value.trim()) return
  isSearching.value = true
  foundLocations.value = []
  try {
    const queryLower = targetSearch.value.trim().toLowerCase()
    if (queryLower.includes('ngọc trai núi') || queryLower.includes('ngoc trai nui')) {
      foundLocations.value = [{
        name: 'Cà phê Ngọc Trai Núi',
        fullName: 'Cà phê Ngọc Trai Núi - 29C-30C Nguyễn Trường Tộ, Bình Khánh, Long Xuyên, An Giang',
        lat: 10.39565,
        lng: 105.42075,
        type: 'Cafe / Coffee Shop'
      }]
      isSearching.value = false
      return
    }

    const q = encodeURIComponent(targetSearch.value)
    const lat = robotLat.value
    const lng = robotLng.value
    
    // Define a localized bounding box of ~0.2 degrees (~20km) around robot's current coordinate
    const lon1 = lng - 0.2
    const lat1 = lat + 0.2
    const lon2 = lng + 0.2
    const lat2 = lat - 0.2
    
    // First query prioritizing local bounds (restricted strictly to Vietnam)
    const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${q}&viewbox=${lon1},${lat1},${lon2},${lat2}&countrycodes=vn&limit=8`)
    const data = await res.json()
    
    if (data && data.length > 0) {
      foundLocations.value = data.map((item: any) => ({
        name: item.display_name.split(',').slice(0, 2).map((s: string) => s.trim()).join(', '),
        fullName: item.display_name,
        lat: parseFloat(item.lat),
        lng: parseFloat(item.lon),
        type: item.type || 'Location'
      }))
    } else {
      // Secondary fallback search adding local context (Binh Khanh / Long Xuyen / An Giang region context, restricted strictly to Vietnam)
      const queryWithContext = `${targetSearch.value}, Long Xuyên, An Giang`
      const fallbackRes = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(queryWithContext)}&countrycodes=vn&limit=5`)
      const fallbackData = await fallbackRes.json()
      
      if (fallbackData && fallbackData.length > 0) {
        foundLocations.value = fallbackData.map((item: any) => ({
          name: item.display_name.split(',').slice(0, 2).map((s: string) => s.trim()).join(', '),
          fullName: item.display_name,
          lat: parseFloat(item.lat),
          lng: parseFloat(item.lon),
          type: item.type || 'Location'
        }))
      }
    }
  } catch (err) {
    console.error('Geocoding query failed:', err)
  } finally {
    isSearching.value = false
  }
}

const filteredTargets = computed(() => {
  return foundLocations.value.length > 0 ? foundLocations.value : presets
})

// Safe decimal formatter helper
function safeToFixed(val: any, decimals = 1, fallback = '0.0'): string {
  if (val === null || val === undefined || isNaN(val)) return fallback
  return Number(val).toFixed(decimals)
}

// Math distance helper
function calcDistanceM(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371e3 // Earth radius
  const phi1 = (lat1 * Math.PI) / 180
  const phi2 = (lat2 * Math.PI) / 180
  const deltaPhi = ((lat2 - lat1) * Math.PI) / 180
  const deltaLambda = ((lng2 - lng1) * Math.PI) / 180

  const a = Math.sin(deltaPhi / 2) * Math.sin(deltaPhi / 2) +
            Math.cos(phi1) * Math.cos(phi2) *
            Math.sin(deltaLambda / 2) * Math.sin(deltaLambda / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}

// ── Viewport controls ───────────────────────────────────────────────────────
const tileType = ref<'roads' | 'satellite'>('roads')
const isTracking = ref(true)
const currentZoom = ref(17)

const tacticalRanges = [
  { label: '100m', zoom: 19 },
  { label: '250m', zoom: 18 },
  { label: '500m', zoom: 17 },
  { label: '1km', zoom: 16 },
  { label: '5km', zoom: 14 }
]

// ── OSRM Professional Routing Engine ───────────────────────────────────────
const destinationCoords = ref<[number, number] | null>(null)
const destinationName = ref('')
const routeDistance = ref(0)
const routeEta = ref(0)
const navigationDirectives = ref<string[]>([])
const currentDirectiveIdx = ref(0)
const routeWaypoints = ref<Array<[number, number]>>([])
const isRouting = ref(false)

// Heading trajectory bearing calculations
const targetBearing = computed(() => {
  if (!destinationCoords.value) return 0
  const curLat = robotLat.value
  const curLng = robotLng.value
  const destLat = destinationCoords.value[0]
  const destLng = destinationCoords.value[1]

  const dLng = ((destLng - curLng) * Math.PI) / 180
  const lat1 = (curLat * Math.PI) / 180
  const lat2 = (destLat * Math.PI) / 180

  const y = Math.sin(dLng) * Math.cos(lat2)
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng)
  const brng = (Math.atan2(y, x) * 180) / Math.PI
  return (brng + 360) % 360
})

const headingDiff = computed(() => {
  const currentHeading = sensorStore.imu?.compass_heading ?? 0
  let diff = targetBearing.value - currentHeading
  while (diff < -180) diff += 360
  while (diff > 180) diff -= 360
  return diff
})

function isWithinVietnam(lat: number, lng: number): boolean {
  return lat >= 8.5 && lat <= 23.5 && lng >= 102.0 && lng <= 110.0
}

// Query OSRM routing API to find the real shortest path geometry
async function generateShortestPath(startLat: number, startLng: number, destLat: number, destLng: number) {
  if (!isWithinVietnam(destLat, destLng)) {
    routeDistance.value = 0
    routeEta.value = 0
    routeWaypoints.value = []
    navigationDirectives.value = [
      `[WARNING]: TRAJECTORY DETECTED OUTSIDE LAND BORDERS`,
      `ROUTING INHIBITED BY SYSTEM CONTROL PROTOCOL`
    ]
    return
  }

  isRouting.value = true
  navigationDirectives.value = [`[PLANNING]: REQUESTING ROUTE METRICS FROM NETWORK NODE...`]
  try {
    const res = await fetch(`https://router.project-osrm.org/route/v1/driving/${startLng},${startLat};${destLng},${destLat}?overview=full&geometries=geojson&steps=true`)
    const data = await res.json()
    
    if (data.code !== 'Ok' || !data.routes || data.routes.length === 0) {
      throw new Error('No routing coordinates returned.')
    }

    const route = data.routes[0]
    routeDistance.value = route.distance
    routeEta.value = Math.ceil(route.duration)

    // Convert coordinates from [lng, lat] (OSRM output) to [lat, lng] (Leaflet standard)
    if (route.geometry && route.geometry.coordinates) {
      routeWaypoints.value = route.geometry.coordinates.map((c: any) => [c[1], c[0]])
    } else {
      routeWaypoints.value = [[startLat, startLng], [destLat, destLng]]
    }

    // Extract step-by-step route directions
    const list: string[] = []
    list.push(`INITIATED ROUTE LOCK TO TARGET VECTOR`)
    if (route.legs && route.legs[0] && route.legs[0].steps) {
      route.legs[0].steps.forEach((step: any) => {
        const inst = step.maneuver.instruction || `PROCEED FORWARD`
        const distStr = step.distance > 0 ? ` (${step.distance.toFixed(0)}m)` : ''
        list.push(`${inst}${distStr}`)
      })
    } else {
      list.push(`PROCEED FORWARD TO DESTINATION TARGET (${route.distance.toFixed(0)}m)`)
    }
    list.push(`ARRIVED AT TARGET DESTINATION VECTOR`)
    navigationDirectives.value = list
    currentDirectiveIdx.value = 0

  } catch (err) {
    console.error('OSRM Route query failed:', err)
    // Dynamic fallback line
    routeDistance.value = calcDistanceM(startLat, startLng, destLat, destLng)
    routeEta.value = Math.ceil(routeDistance.value / 1.2)
    routeWaypoints.value = [[startLat, startLng], [destLat, destLng]]
    navigationDirectives.value = [
      `[ERROR]: OFFLINE GIS BACKEND UPLINK DETECTED`,
      `[FALLBACK]: LOCKING DIRECT VECTOR SPACE LINE`,
      `PROCEED DIRECTLY ON BEARING ${targetBearing.value.toFixed(0)}° (${routeDistance.value.toFixed(0)}m)`,
      `ARRIVED AT DESTINATION VECTOR`
    ]
  } finally {
    isRouting.value = false
  }
}

function selectPresetTarget(t: any) {
  destinationName.value = t.name
  destinationCoords.value = [t.lat, t.lng]
  
  generateShortestPath(robotLat.value, robotLng.value, t.lat, t.lng)
  
  nextTick(() => {
    draw2DRoute()
  })
}

// ── 2D Map Integration (Leaflet) ──────────────────────────────────────────
const mapContainer = ref<HTMLElement | null>(null)
let mapInstance: any = null
let markerInstance: any = null
let destMarkerInstance: any = null
let routePolyline: any = null
let graticulesLayerGroup: any = null

function loadLeaflet(): Promise<any> {
  return new Promise((resolve, reject) => {
    if ((window as any).L) {
      resolve((window as any).L)
      return
    }
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'
    document.head.appendChild(link)

    const script = document.createElement('script')
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'
    script.onload = () => resolve((window as any).L)
    script.onerror = (e) => reject(e)
    document.body.appendChild(script)
  })
}

let activeTileLayer: any = null

function applyTileLayer(L: any) {
  if (!mapInstance) return
  if (activeTileLayer) {
    mapInstance.removeLayer(activeTileLayer)
  }

  if (tileType.value === 'satellite') {
    // ESRI Satellite Imagery
    activeTileLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxZoom: 19,
      attribution: 'Tiles &copy; Esri &mdash; Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
    }).addTo(mapInstance)
  } else {
    // Standard OSM with dark green hacker filter applied via CSS class
    activeTileLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 20,
      attribution: '&copy; OpenStreetMap contributors'
    }).addTo(mapInstance)
  }
}

function setTileType(type: 'roads' | 'satellite') {
  tileType.value = type
  if ((window as any).L && mapInstance) {
    applyTileLayer((window as any).L)
  }
}

function setTacticalRange(zoom: number) {
  currentZoom.value = zoom
  if (mapInstance) {
    mapInstance.setView([robotLat.value, robotLng.value], zoom)
  }
}

function recenterMap() {
  isTracking.value = true
  if (mapInstance) {
    mapInstance.setView([robotLat.value, robotLng.value], mapInstance.getZoom() || currentZoom.value)
  }
}

function draw2DRoute() {
  const L = (window as any).L
  if (!L || !mapInstance || routeWaypoints.value.length === 0) return

  // Remove existing elements
  if (routePolyline) {
    mapInstance.removeLayer(routePolyline)
    routePolyline = null
  }
  if (destMarkerInstance) {
    mapInstance.removeLayer(destMarkerInstance)
    destMarkerInstance = null
  }

  // Draw tactical route (dashed cyan vector path)
  routePolyline = L.polyline(routeWaypoints.value, {
    color: '#0088FF',
    weight: 2,
    dashArray: '5 7',
    opacity: 0.8,
    interactive: false
  }).addTo(mapInstance)

  // Draw destination target pin
  const destCoords = routeWaypoints.value[routeWaypoints.value.length - 1]
  const targetIcon = L.divIcon({
    className: 'target-waypoint-hud',
    html: `
      <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 20px; height: 20px;">
        <div style="position: absolute; width: 8px; height: 8px; border: 2.5px solid #0088FF; background: #000000; transform: rotate(45deg); box-shadow: 0 0 8px #0088FF;"></div>
        <div style="position: absolute; border: 1px solid #0088FF; width: 18px; height: 18px; border-radius: 50%; animation: ping 1.5s infinite;"></div>
      </div>
    `,
    iconSize: [20, 20],
    iconAnchor: [10, 10]
  })

  destMarkerInstance = L.marker(destCoords, { icon: targetIcon }).addTo(mapInstance)
}

function drawGraticulesGrid(L: any, lat: number, lng: number) {
  if (!mapInstance) return
  if (!graticulesLayerGroup) {
    graticulesLayerGroup = L.layerGroup().addTo(mapInstance)
  } else {
    graticulesLayerGroup.clearLayers()
  }

  const gridColor = 'rgba(0, 255, 102, 0.18)'
  const gridWeight = 0.5
  const stepM = 100
  const radiusM = 500
  
  const meterToLat = (m: number) => m / 111320
  const meterToLng = (m: number) => m / (111320 * Math.cos((lat * Math.PI) / 180))

  const latStep = meterToLat(stepM)
  const lngStep = meterToLng(stepM)
  const latSpan = meterToLat(radiusM)
  const lngSpan = meterToLng(radiusM)

  // Latitude lines
  const latStart = Math.ceil((lat - latSpan) / latStep) * latStep
  for (let lineLat = latStart; lineLat <= lat + latSpan; lineLat += latStep) {
    L.polyline(
      [[lineLat, lng - lngSpan], [lineLat, lng + lngSpan]],
      { color: gridColor, weight: gridWeight, interactive: false }
    ).addTo(graticulesLayerGroup)
  }

  // Longitude lines
  const lngStart = Math.ceil((lng - lngSpan) / lngStep) * lngStep
  for (let lineLng = lngStart; lineLng <= lng + lngSpan; lineLng += lngStep) {
    L.polyline(
      [[lat - latSpan, lineLng], [lat + latSpan, lineLng]],
      { color: gridColor, weight: gridWeight, interactive: false }
    ).addTo(graticulesLayerGroup)
  }
}

function init2DMap(L: any) {
  if (!mapContainer.value) return
  const initLat = robotLat.value
  const initLng = robotLng.value

  mapInstance = L.map(mapContainer.value, {
    zoomControl: false,
    attributionControl: false,
    dragging: true,
    scrollWheelZoom: true,
    doubleClickZoom: true,
    boxZoom: false,
    keyboard: false,
    touchZoom: true
  }).setView([initLat, initLng], currentZoom.value)

  applyTileLayer(L)

  mapInstance.on('dragstart', () => {
    isTracking.value = false
  })

  // Pulsing position radar ping marker
  const pingIcon = L.divIcon({
    className: 'gps-sonar-ping',
    html: '<div class="ping-ring" style="border-color:#00FF66;"></div><div class="ping-dot" style="background:#00FF66;box-shadow:0 0 10px #00FF66;"></div>',
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  })

  markerInstance = L.marker([initLat, initLng], { icon: pingIcon }).addTo(mapInstance)

  // Double click map to select custom target coordinate dynamically
  mapInstance.on('dblclick', (e: any) => {
    destinationName.value = `TACTICAL_VECTOR_[${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}]`
    destinationCoords.value = [e.latlng.lat, e.latlng.lng]
    generateShortestPath(robotLat.value, robotLng.value, e.latlng.lat, e.latlng.lng)
    
    nextTick(() => {
      draw2DRoute()
    })
  })

  drawGraticulesGrid(L, initLat, initLng)

  setTimeout(() => {
    if (mapInstance) {
      mapInstance.invalidateSize()
    }
  }, 250)
}

// Watch robot coordinates dynamically to trigger routing and redraws
watch(
  () => [robotLat.value, robotLng.value],
  ([lat, lng]) => {
    if (mapInstance && markerInstance && lat !== 0 && lng !== 0) {
      const pos = [lat, lng] as [number, number]
      markerInstance.setLatLng(pos)
      if (isTracking.value) {
        mapInstance.setView(pos, mapInstance.getZoom() || currentZoom.value)
      }
      if ((window as any).L) {
        drawGraticulesGrid((window as any).L, lat, lng)
      }
      if (destinationCoords.value) {
        generateShortestPath(lat, lng, destinationCoords.value[0], destinationCoords.value[1])
        nextTick(() => {
          draw2DRoute()
        })
      }
    }
  }
)

// ── Lifecycle ───────────────────────────────────────────────────────────────
onMounted(async () => {
  updateClock()
  clockInterval = window.setInterval(updateClock, 1000)

  try {
    const L = await loadLeaflet()
    init2DMap(L)
  } catch (e) {
    console.error('Failed to load Leaflet:', e)
  }
})

onUnmounted(() => {
  if (clockInterval) clearInterval(clockInterval)
  
  if (mapInstance) {
    mapInstance.remove()
    mapInstance = null
  }
})
</script>

<style scoped>
.map-page-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 40px); /* header status offset */
  background: #000000;
  box-sizing: border-box;
}

/* Header layout fixes */
.sv-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  border-bottom: 1px solid rgba(0, 255, 102, 0.25);
  padding: 6px 12px;
  flex-shrink: 0;
}
.sv-title {
  font-family: 'Orbitron', sans-serif;
  font-weight: 700;
  font-size: 14px;
  letter-spacing: 1px;
  color: #00FF66;
}
.sv-label {
  font-size: 8px;
  letter-spacing: 2px;
  color: rgba(0, 255, 102, 0.6);
  text-transform: uppercase;
  margin-left: 12px;
}

/* Viewport Area spanning 100% of body */
.map-viewport-wrapper {
  position: relative;
  flex: 1;
  width: 100%;
  height: 100%;
  background: #000000;
  overflow: hidden;
}

/* 2D Leaflet styling overlays */
.real-map {
  width: 100%;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  background: #000000;
}

/* Applying green terminal inversion shader filter specifically for road tiles */
.real-map:not(.satellite-tiles) :deep(.leaflet-tile) {
  filter: grayscale(1) invert(1) sepia(1) hue-rotate(85deg) saturate(2) contrast(1.6) brightness(0.65) !important;
  opacity: 0.95;
}
/* Satellite style map is rendered normally without inversion filter to keep imagery realistic */
.real-map.satellite-tiles :deep(.leaflet-tile) {
  filter: saturate(1.2) contrast(1.1) brightness(0.7) !important;
  opacity: 0.85;
}

/* Floating HUD elements container styling */
.map-hud-overlay {
  position: absolute;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  overflow: hidden;
}

/* Radar scanline sweep */
.radar-scanline {
  position: absolute;
  width: 100%;
  height: 2px;
  background: linear-gradient(to bottom, transparent, rgba(0, 255, 102, 0.25), transparent);
  top: 0;
  left: 0;
  z-index: 12;
  animation: radar-scan-y 5s infinite linear;
}
@keyframes radar-scan-y {
  0% { top: 0%; }
  100% { top: 100%; }
}

/* Custom UI Toggle buttons inside blocks */
.toggle-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  width: 100%;
}
.hud-toggle-btn {
  background: transparent;
  border: 1px solid rgba(0, 255, 102, 0.25);
  color: rgba(0, 255, 102, 0.5);
  font-family: 'Roboto Mono', monospace;
  font-size: 8px;
  padding: 3px 0;
  cursor: pointer;
  text-align: center;
  transition: all 0.2s ease;
}
.hud-toggle-btn:hover {
  color: #00FF66;
  border-color: #00FF66;
}
.hud-toggle-btn.active {
  color: #00ff66;
  border-color: #00ff66;
  background: rgba(0, 255, 102, 0.08);
  font-weight: 700;
  text-shadow: 0 0 4px rgba(0, 255, 102, 0.6);
}

/* Common style for floating console blocks */
.hud-block {
  background: rgba(10, 10, 10, 0.88);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(0, 255, 102, 0.25);
  border-left: 3px solid #00FF66;
  padding: 8px 12px;
  pointer-events: auto; /* enable interactions */
  filter: drop-shadow(0 0 8px rgba(0, 255, 102, 0.15));
}

/* Viewport Left Column stacks */
.hud-col-left-top {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 15;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 340px; /* expanded width for address input */
}

/* Viewport Right Column Top stacks */
.hud-col-right-top {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 15;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Viewport Left Column Bottom stacks */
.hud-col-left-bottom {
  position: absolute;
  bottom: 10px;
  left: 10px;
  z-index: 15;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 340px;
}

/* Viewport Right Column Bottom stacks */
.hud-col-right-bottom {
  position: absolute;
  bottom: 10px;
  right: 10px;
  z-index: 15;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Viewport Bottom Center stack */
.hud-col-bottom-center {
  position: absolute;
  bottom: 10px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 15;
  pointer-events: auto;
}

/* Specific floating panel designs */
.hud-tactical-zoom {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.zoom-title {
  font-size: 7.5px;
  color: #00FF66;
  opacity: 0.7;
  letter-spacing: 1px;
}
.zoom-btn {
  background: transparent;
  border: none;
  color: rgba(0, 255, 102, 0.5);
  font-family: 'Roboto Mono', monospace;
  font-size: 9px;
  text-align: left;
  padding: 2px 0;
  cursor: pointer;
  width: 100%;
  transition: all 0.2s ease;
}
.zoom-btn:hover {
  color: #00FF66;
  padding-left: 2px;
}
.zoom-btn.active {
  color: #00FF66;
  font-weight: 700;
  text-shadow: 0 0 4px rgba(0, 255, 102, 0.6);
}

/* Targets dropdown and search */
.target-panel {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 250px;
}
.panel-header-mini {
  font-size: 8px;
  font-weight: 700;
  color: #00FF66;
  margin-bottom: 2px;
  border-bottom: 1px dashed rgba(0, 255, 102, 0.2);
  padding-bottom: 2px;
  text-transform: uppercase;
}
.target-search-box {
  width: 100%;
}
.hud-input {
  width: 100%;
  background: #000000;
  border: 1px solid rgba(0, 255, 102, 0.3);
  color: #00FF66;
  padding: 4px 8px;
  font-size: 8px;
  box-sizing: border-box;
}
.hud-input:focus {
  outline: none;
  border-color: #00FF66;
}
.target-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
  max-height: 120px;
}
.target-item {
  border: 1px solid rgba(0, 255, 102, 0.1);
  background: rgba(0, 255, 102, 0.01);
  padding: 4px 6px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: all 0.15s ease;
}
.target-item:hover {
  background: rgba(0, 255, 102, 0.05);
  border-color: rgba(0, 255, 102, 0.3);
}
.target-item.active {
  background: rgba(0, 255, 102, 0.08);
  border-color: #00FF66;
}
.target-item-header {
  font-size: 8px;
  font-weight: 700;
  color: #00FF66;
}
.target-item-footer {
  display: flex;
  justify-content: space-between;
  font-size: 7px;
  color: rgba(0, 255, 102, 0.5);
  margin-top: 1px;
}

/* Coordinates widget */
.coord-readout {
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 140px;
}
.coord-line {
  display: flex;
  justify-content: space-between;
  font-size: 9px;
}
.coord-lbl {
  color: #00FF66;
  opacity: 0.6;
}
.coord-val {
  color: #00FF66;
  font-variant-numeric: tabular-nums;
  font-weight: 700;
}
.coord-unit {
  font-size: 8px;
  opacity: 0.8;
  margin-left: 1px;
}

/* Compass widget */
.directional-guidance {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
}
.compass-wrap {
  width: 32px;
  height: 32px;
  border: 1px solid rgba(0, 255, 102, 0.35);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  flex-shrink: 0;
}
.compass-dial {
  width: 26px;
  height: 26px;
  border: 1px dashed rgba(0, 255, 102, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.compass-arrow {
  color: #00FF66;
  font-size: 8px;
  transition: transform 0.2s ease;
  line-height: 1;
}
.compass-text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
  font-size: 7.5px;
}
.compass-text .term-line {
  display: flex;
  justify-content: space-between;
}
.compass-text .lbl {
  opacity: 0.6;
}
.compass-text .val {
  font-weight: 700;
}

/* Directives widget */
.directives-panel {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 180px;
}
.route-summary {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
  background: rgba(0, 255, 102, 0.02);
  border: 1px solid rgba(0, 255, 102, 0.1);
  padding: 4px 6px;
  font-size: 7.5px;
  margin-bottom: 2px;
}
.route-summary .lbl {
  opacity: 0.6;
}
.route-summary .val {
  font-weight: 700;
}
.directives-scroll {
  overflow-y: auto;
  max-height: 100px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.directive-row {
  display: flex;
  gap: 6px;
  padding: 2px 4px;
  border-left: 2px solid transparent;
  font-size: 7.5px;
  line-height: 1.2;
}
.directive-row.active {
  border-left-color: #00FF66;
  background: rgba(0, 255, 102, 0.04);
  color: #00FF66;
}
.dir-idx {
  opacity: 0.5;
}

/* Range scale parameter widget */
.hud-sys-parameters {
  display: flex;
  flex-direction: column;
  gap: 3px;
  width: 90px;
}
.sys-title {
  font-size: 7.5px;
  color: #00FF66;
  opacity: 0.7;
  letter-spacing: 1px;
}

/* Central crosshair pointer */
.map-crosshair {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 32px;
  height: 32px;
  transform: translate(-50%, -50%);
  pointer-events: none;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: center;
}
.crosshair-h {
  position: absolute;
  width: 100%;
  height: 1px;
  background: rgba(0, 255, 102, 0.35);
}
.crosshair-v {
  position: absolute;
  height: 100%;
  width: 1px;
  background: rgba(0, 255, 102, 0.35);
}
.crosshair-dot {
  width: 6px;
  height: 6px;
  border: 1px solid #00FF66;
  border-radius: 50%;
  background: transparent;
  box-shadow: 0 0 4px #00FF66;
}

/* Custom scroll bar style to match terminal aesthetics */
.scroll-styled::-webkit-scrollbar {
  width: 4px;
}
.scroll-styled::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.2);
}
.scroll-styled::-webkit-scrollbar-thumb {
  background: rgba(0, 255, 102, 0.25);
  border-radius: 2px;
}
.scroll-styled::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 255, 102, 0.5);
}

.text-dim {
  color: rgba(0, 255, 102, 0.45);
}
.text-cyan {
  color: #00E5FF !important;
}
.text-warn {
  color: #FFB000 !important;
}

/* ─── Sonar Ping Position Marker ─── */
.gps-sonar-ping {
  position: relative;
}
.ping-dot {
  width: 8px;
  height: 8px;
  background: #00FF66;
  border-radius: 50%;
  position: absolute;
  top: 8px;
  left: 8px;
  box-shadow: 0 0 10px #00FF66;
}
.ping-ring {
  width: 24px;
  height: 24px;
  border: 1.5px solid #00FF66;
  border-radius: 50%;
  position: absolute;
  top: 0;
  left: 0;
  animation: gps-sonar-pulse 2s infinite cubic-bezier(0.215, 0.610, 0.355, 1);
  box-shadow: inset 0 0 4px rgba(0, 255, 102, 0.2);
}
@keyframes gps-sonar-pulse {
  0% {
    transform: scale(0.3);
    opacity: 1;
  }
  100% {
    transform: scale(2.8);
    opacity: 0;
  }
}

/* Destination Waypoint ping */
@keyframes ping {
  0% {
    transform: scale(0.2);
    opacity: 0.8;
  }
  100% {
    transform: scale(2.2);
    opacity: 0;
  }
}
</style>
