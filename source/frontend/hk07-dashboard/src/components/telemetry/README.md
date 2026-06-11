# BAYMAX BIO-TELEMETRY DASHBOARD
## Cyber-Cinematic Vue 3 Real-Time Telemetry Interface

### Overview
The BAYMAX dashboard is a production-ready Vue 3 (Composition API) frontend for real-time bio-telemetry visualization, robotics sensor fusion, and emergency fall detection. Built with Tailwind CSS v3 and a military-grade cyber-cinematic aesthetic.

---

## Component Architecture

### 1. **BioTelemetryWidget.vue**
Real-time clinical vital signs display with hardware sensor validation.

**Features:**
- Heart Rate (HR) monitoring with real-time BPM display
- Oxygen Saturation (SpO2) percentage tracking
- Segmented vertical progress bars (pixel-perfect aesthetic)
- Hardware sensor status indicators with blinking state
- Warning state activation when `sensorStatus.hrValid === false`
  - Flashes Cyber Orange (#FF6600) border
  - Displays: `[WARNING: SENSOR_NULL - SAFE_DEFAULT_ENGAGED]`
- Real-time status text: BRADYCARDIA / TACHYCARDIA / NOMINAL

**Props:**
```typescript
interface Props {
  telemetry: RobotTelemetry;
  theme?: WidgetTheme;
}
```

**Styling:**
- Pure jet black background (#000000)
- AliceBlue text (#F0F8FF) for crisp readability
- Electric Cyan borders (#00FFCC) with subtle shadow effects
- Emerald Green for healthy states (#00FF66)
- Cyber Orange for warnings (#FF6600)

---

### 2. **KinematicsWidget.vue**
Environmental sensors and 9-DOF IMU telemetry with real-time waveform visualization.

**Features:**
- **Environmental Metrics:**
  - Ambient Light (lux) with horizontal progress bar
  - Atmospheric Pressure (hPa) with delta tracking
  - Pressure Delta visualization for dual-factor fall detection

- **IMU Orientation (9-DoF):**
  - Yaw angle with animated compass dial
  - Pitch and Roll angles (if available)
  - Real-time orientation tracking

- **Raw Accelerometer Data:**
  - X, Y, Z axis values with color coding
  - Axis colors: Cyan (normal) → Orange (high) → Red (critical)
  - G-Magnitude calculation with threshold-based coloring

- **Canvas Waveform Display:**
  - 60 FPS real-time waveform ticker
  - 120-sample history buffer
  - Reference gravity line (9.81 m/s²)
  - Subtle grid background for scale reference

**Props:**
```typescript
interface Props {
  telemetry: RobotTelemetry;
  theme?: WidgetTheme;
}
```

---

### 3. **HolographicTwin.vue**
3D wireframe visualization with fall detection state synchronization.

**Features:**
- **3D Viewport:**
  - Three.js WebGL renderer
  - Electric Cyan (#00FFCC) monocromatic wireframe mesh
  - Robot representation: torso (box) + head (icosahedron) + limbs (boxes)
  - Fine pixel grid background overlay

- **Fall Detection Integration:**
  - Dynamic border color: Cyan (normal) → Crimson Red (fall detected)
  - Full-viewport blinking red glow animation
  - Overlay alert text: `[ALERT: SUDDEN ACCELERATION DETECTED - MODE: LINEAR/RAW]`
  - Mesh pulsing animation on fall state
  - Fall confidence and G-force magnitude display

- **Real-Time 3D Rotation:**
  - Mesh X/Y rotation synchronized to accelerometer data
  - Z rotation (yaw) synchronized to compass heading
  - Rotation sensitivity: 0.02 rad/m·s²

- **Stats Panel:**
  - Vertex and face count
  - Real-time FPS counter
  - Current rotation angles (X, Y, Z)
  - Device ID display

**Props:**
```typescript
interface Props {
  telemetry: RobotTelemetry;
  theme?: WidgetTheme;
}
```

**Dependencies:**
- Three.js v140+ (load via CDN or npm)

---

### 4. **BayMaxDashboard.vue**
Main dashboard page integrating all components with connection status.

**Features:**
- Full-page cyber-cinematic interface
- Scanlines overlay (2% opacity for authenticity)
- Responsive grid layout (bio-telemetry → holographic → kinematics)
- Live connection status bar (fixed bottom)
- Mock telemetry generator (30 FPS updates)
- Latency indicator

**Layout Structure:**
```
┌─────────────────────────────────────────┐
│  SCANLINES OVERLAY (subtle texture)     │
├─────────────────────────────────────────┤
│  BioTelemetryWidget (HR + SpO2)         │
├─────────────────────────────────────────┤
│  HolographicTwin (3D + Fall Detection)  │
├─────────────────────────────────────────┤
│  KinematicsWidget (IMU + Environment)   │
├─────────────────────────────────────────┤
│ [STATUS] MQTT: CONNECTED | TIME | LAT  │
└─────────────────────────────────────────┘
```

---

## Type Definitions

### RobotTelemetry
```typescript
interface RobotTelemetry {
  // Identification
  messageId: string;
  sessionId: string;
  deviceId: string;
  
  // Clinical Vitals (Part A)
  hr: number;                    // Heart rate in BPM
  spO2: number;                  // Oxygen saturation (%)
  
  // Environmental Sensors (Part B)
  light: number;                 // Ambient light (lux)
  pressure: number;              // Barometric pressure (hPa)
  pressureDelta?: number;        // Pressure change (hPa)
  
  // Spatial Safety - 9-DoF IMU (Part C)
  yaw: number;                   // Heading (degrees)
  pitch?: number;                // Pitch angle (degrees)
  roll?: number;                 // Roll angle (degrees)
  
  // Emergency Location (Part D)
  latitude?: number;
  longitude?: number;
  altitude?: number;
  
  // Activity Metrics (Part E)
  steps?: number;
  activityType?: string;
  
  // Fall Detection
  fallState: boolean;            // True if fall detected
  fallConfidence?: number;       // 0-1 confidence score
  gForceMagnitude?: number;      // G-force value
  
  // Raw Accelerometer
  rawAccel: RawAccelerometerVector;
  
  // Hardware Status
  sensorStatus: SensorStatus;
  
  // Timestamp
  timestamp: number;             // Unix milliseconds
}

interface RawAccelerometerVector {
  x: number;
  y: number;
  z: number;
  magnitude?: number;
}

interface SensorStatus {
  hrValid: boolean;
  spo2Valid?: boolean;
  lightValid?: boolean;
  pressureValid?: boolean;
  yawValid?: boolean;
  accelValid?: boolean;
}
```

---

## Installation & Setup

### Prerequisites
- Vue 3.x with Composition API
- Tailwind CSS v3
- Three.js (for 3D viewport)

### File Structure
```
src/
├── components/
│   ├── BayMaxDashboard.vue
│   └── telemetry/
│       ├── BioTelemetryWidget.vue
│       ├── KinematicsWidget.vue
│       ├── HolographicTwin.vue
│       └── types.ts
├── composables/
│   └── useBayMaxTelemetry.ts
└── [other app files]
```

### Installation Steps

1. **Copy component files** to `src/components/telemetry/`
2. **Copy composable** to `src/composables/`
3. **Install dependencies:**
```bash
npm install three
# Optional: for MQTT support
npm install paho-mqtt
```

4. **Configure Tailwind CSS** - ensure these files are processed:
```javascript
// tailwind.config.js
module.exports = {
  content: [
    './src/components/**/*.vue',
    './src/views/**/*.vue'
  ],
  theme: {
    extend: {
      fontFamily: {
        orbitron: ['Orbitron', 'sans-serif'],
        'tech-mono': ['Share Tech Mono', 'monospace'],
        vt323: ['VT323', 'monospace']
      }
    }
  }
};
```

5. **Add Google Fonts to index.html:**
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&family=VT323&display=swap" rel="stylesheet">
```

6. **Load Three.js** (via CDN in index.html):
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
```

---

## Usage Example

### In a parent Vue component:
```vue
<template>
  <BayMaxDashboard />
</template>

<script setup lang="ts">
import BayMaxDashboard from '@/components/BayMaxDashboard.vue';
</script>
```

### With real-time WebSocket data:
```vue
<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue';
import { useBayMaxTelemetry } from '@/composables/useBayMaxTelemetry';
import BayMaxDashboard from '@/components/BayMaxDashboard.vue';

const { telemetry, connect, disconnect } = useBayMaxTelemetry();

onMounted(() => {
  // Connect to your WebSocket server
  connect('wss://your-server/telemetry');
});

onUnmounted(() => {
  disconnect();
});
</script>

<template>
  <BayMaxDashboard v-if="telemetry" :telemetry="telemetry" />
</template>
```

---

## Backend Integration

### Expected MQTT Topics
The dashboard subscribes to these topics from the sensor bridge (`vivo_http_mqtt_bridge.py`):

| Topic | Payload |
|-------|---------|
| `hk07/sensors/wristband/*/vitals` | HR, SpO2, temperature |
| `hk07/sensors/environment/state` | Light, pressure, pressure delta |
| `hk07/sensors/imu/state` | Raw accelerometer |
| `hk07/sensors/imu/target` | 9-DoF kinematics (with quaternion) |
| `hk07/sensors/location/gps` | Emergency GPS coordinates |
| `hk07/sensors/activity/metrics` | Steps, activity, wrist motion |

### WebSocket Server (recommended)
Implement a WebSocket gateway that aggregates MQTT messages:
```javascript
// Node.js example with mqtt and ws libraries
const mqtt = require('mqtt');
const WebSocket = require('ws');

const mqttClient = mqtt.connect('mqtt://broker:1883');
const wss = new WebSocket.Server({ port: 8080 });

mqttClient.subscribe('hk07/sensors/#');

mqttClient.on('message', (topic, message) => {
  const payload = JSON.parse(message);
  wss.clients.forEach(client => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(JSON.stringify(payload));
    }
  });
});
```

---

## Color Theme Reference

| Element | Color | Hex | Usage |
|---------|-------|-----|-------|
| Background | Jet Black | #000000 | Main canvas |
| Primary Text | AliceBlue | #F0F8FF | Data values, labels |
| Border/Accent | Electric Cyan | #00FFCC | Borders, active state |
| Success | Emerald Green | #00FF66 | Healthy sensors, normal state |
| Warning | Cyber Orange | #FF6600 | Sensor warnings |
| Critical | Crimson Red | #FF3333 | Fall detection, emergency |

---

## Performance Optimization

- **Canvas Rendering:** 60 FPS with requestAnimationFrame
- **Component Updates:** Only affected props trigger re-renders (Vue reactivity)
- **Waveform Buffer:** Limited to 120 samples (scrolling history)
- **Mesh Stats:** Cached and updated at 1 Hz

---

## Accessibility & Browser Support

- **Modern Browsers:** Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **Mobile Support:** Responsive design adapts to tablet/mobile (though optimized for desktop)
- **Keyboard Navigation:** Tab navigation through status bar
- **Color Contrast:** WCAG AA compliant for primary text elements

---

## Troubleshooting

### Three.js not loading
```
Error: THREE is not defined
Solution: Ensure Three.js is loaded BEFORE component renders
```

### Waveform not animating
```
Check browser console for requestAnimationFrame support
Ensure canvas ref is properly mounted
```

### Sensors showing NULL warnings
```
Verify telemetry.sensorStatus.hrValid is true
Check that mock data generation includes all required fields
```

---

## Future Enhancements

- [ ] Real-time alert sound integration
- [ ] Historical data logging and playback
- [ ] Multi-device dashboard switching
- [ ] Advanced analytics (heart rate variability, accel trends)
- [ ] AR overlay for spatial visualization
- [ ] Custom theme editor

---

**BAYMAX TELEMETRY SYSTEM v1.0**
*Cyber-cinematic UI for autonomous medical robotics*
