import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface KinematicsData {
  header?: {
    stamp: {
      sec: number
      nanosec: number
    }
    frame_id: string
  }
  orientation?: {
    x: number
    y: number
    z: number
    w: number
  }
  angular_velocity?: {
    x: number
    y: number
    z: number
  }
  linear_acceleration?: {
    x: number
    y: number
    z: number
  }
  position?: {
    x: number
    y: number
    z: number
  }
  x?: number
  y?: number
  z?: number
  qw?: number
  qx?: number
  qy?: number
  qz?: number
  timestampMs?: number
}

export interface PneumaticData {
  press_L: number
  press_R: number
  pump_active: boolean
  relief_active: boolean
  timestamp_ms: number
}

export interface TactileData {
  hug_force: number
  flex_rate: number
  timestamp_ms: number
}

export interface PmuData {
  voltage: number
  current: number
  soc: number
  temp: number
  timestamp_ms: number
}

export interface JointData {
  name: string
  angle: number
  torque: number
  temp: number
}



export interface Vector3D {
  x: number
  y: number
  z: number
}

export interface JointState {
  name: string[]
  position: number[]
  velocity?: number[]
  effort?: number[]
}

export const useKinematicsStore = defineStore('kinematics', () => {
  const position = ref({ x: 0, y: 0, z: 0 })
  const rotation = ref({ qw: 1.0, qx: 0.0, qy: 0.0, qz: 0.0 })
  const timestampMs = ref(0)
  const isLive = ref(false)
  const lastUpdateMs = ref(0)
  const isSimulated = ref(true)

  function touch() {
    lastUpdateMs.value = Date.now()
    isLive.value = true
  }

  // Watchdog timer to automatically invalidate live telemetry status on timeout
  setInterval(() => {
    if (isLive.value && lastUpdateMs.value > 0 && Date.now() - lastUpdateMs.value > 60000) {
      isLive.value = false
    }
  }, 1000)

  // Spatial perception states

  const avoidanceVector = ref<Vector3D>({ x: 0, y: 0, z: 0 })
  const jointStates = ref<JointState>({ name: [], position: [] })

  // Physical telemetry
  const pressureL = ref(1.8)
  const pressureR = ref(1.8)
  const pumpActive = ref(false)
  const reliefActive = ref(false)
  const hugForce = ref(0.0)
  const flexRate = ref(5.0)

  // OpenCV rPPG & Thermal Vision telemetry
  const rppgHeartRate = ref(0.0)
  const thermalTemperature = ref(36.6)
  const feverAlert = ref(false)
  const tracker = ref({ x: 42.0, y: 52.0, width: 80.0, height: 85.0 })

  const pmu = ref({
    voltage: 24.0,
    current: 0.7,
    soc: 100.0,
    temp: 32.0
  })

  const joints = ref<JointData[]>([])

  const positionFormatted = computed(() => ({
    x: position.value.x.toFixed(3),
    y: position.value.y.toFixed(3),
    z: position.value.z.toFixed(3),
  }))

  // Convert quaternion back to Euler angles for HUD metrics display
  const rotationFormatted = computed(() => {
    const { qw, qx, qy, qz } = rotation.value

    // Roll (x-axis rotation)
    const sinr_cosp = 2 * (qw * qx + qy * qz)
    const cosr_cosp = 1 - 2 * (qx * qx + qy * qy)
    const roll = Math.atan2(sinr_cosp, cosr_cosp)

    // Pitch (y-axis rotation)
    const sinp = 2 * (qw * qy - qz * qx)
    let pitch = 0
    if (Math.abs(sinp) >= 1) {
      pitch = (sinp >= 0 ? 1 : -1) * (Math.PI / 2) // sign fallback
    } else {
      pitch = Math.asin(sinp)
    }

    // Yaw (z-axis rotation)
    const siny_cosp = 2 * (qw * qz + qx * qy)
    const cosy_cosp = 1 - 2 * (qy * qy + qz * qz)
    const yaw = Math.atan2(siny_cosp, cosy_cosp)

    return {
      pitch: (pitch * (180 / Math.PI)).toFixed(1) + '°',
      yaw:   (yaw   * (180 / Math.PI)).toFixed(1) + '°',
      roll:  (roll  * (180 / Math.PI)).toFixed(1) + '°',
    }
  })

  function updateKinematics(data: any) {
    touch()
    isSimulated.value = data.is_simulated ?? true
    if (data.orientation) {
      rotation.value.qw = data.orientation.w ?? data.orientation.qw ?? 1.0
      rotation.value.qx = data.orientation.x ?? data.orientation.qx ?? 0.0
      rotation.value.qy = data.orientation.y ?? data.orientation.qy ?? 0.0
      rotation.value.qz = data.orientation.z ?? data.orientation.qz ?? 0.0
    } else {
      if (data.qw !== undefined) rotation.value.qw = data.qw
      if (data.qx !== undefined) rotation.value.qx = data.qx
      if (data.qy !== undefined) rotation.value.qy = data.qy
      if (data.qz !== undefined) rotation.value.qz = data.qz
    }

    if (data.position) {
      position.value.x = data.position.x
      position.value.y = data.position.y
      position.value.z = data.position.z
    } else {
      if (data.x !== undefined) position.value.x = data.x
      if (data.y !== undefined) position.value.y = data.y
      if (data.z !== undefined) position.value.z = data.z
    }

    if (data.header?.stamp) {
      timestampMs.value = data.header.stamp.sec * 1000 + Math.floor(data.header.stamp.nanosec / 1000000)
    } else if (data.timestampMs !== undefined) {
      timestampMs.value = data.timestampMs
    }
  }



  function updateAvoidanceVector(data: any) {
    touch()
    if (data && data.linear) {
      avoidanceVector.value = {
        x: data.linear.x ?? 0,
        y: data.linear.y ?? 0,
        z: data.linear.z ?? 0
      }
    } else if (data) {
      avoidanceVector.value = {
        x: data.x ?? 0,
        y: data.y ?? 0,
        z: data.z ?? 0
      }
    }
  }

  function updateJointStates(data: JointState) {
    touch()
    jointStates.value = data
  }

  function updatePneumatic(data: any) {
    touch()
    isSimulated.value = data.is_simulated ?? true
    if (data.press_L !== undefined) pressureL.value = data.press_L
    if (data.press_R !== undefined) pressureR.value = data.press_R
    if (data.pump_active !== undefined) pumpActive.value = data.pump_active
    if (data.relief_active !== undefined) reliefActive.value = data.relief_active
  }

  function updateTactile(data: Partial<TactileData>) {
    touch()
    if (data.hug_force !== undefined) hugForce.value = data.hug_force
    if (data.flex_rate !== undefined) flexRate.value = data.flex_rate
  }

  function updatePmu(data: any) {
    touch()
    isSimulated.value = data.is_simulated ?? true
    if (data.voltage !== undefined) pmu.value.voltage = data.voltage
    if (data.current !== undefined) pmu.value.current = data.current
    if (data.soc !== undefined) pmu.value.soc = data.soc
    if (data.temp !== undefined) pmu.value.temp = data.temp
  }

  function updateJoints(data: any) {
    touch()
    if (Array.isArray(data)) {
      joints.value = data
    } else if (data && Array.isArray(data.joints)) {
      joints.value = data.joints
      isSimulated.value = data.is_simulated ?? true
    }
  }

  function updateThermalRppg(data: any) {
    touch()
    if (data.rppg_heart_rate !== undefined) rppgHeartRate.value = data.rppg_heart_rate
    if (data.thermal_temperature !== undefined) thermalTemperature.value = data.thermal_temperature
    if (data.fever_alert !== undefined) feverAlert.value = data.fever_alert
    if (data.tracker) tracker.value = data.tracker
  }

  function setLive(live: boolean) {
    isLive.value = live
    if (live) {
      lastUpdateMs.value = Date.now()
    } else {
      lastUpdateMs.value = 0
    }
  }

  function reset() {
    position.value = { x: 0, y: 0, z: 0 }
    rotation.value = { qw: 1.0, qx: 0.0, qy: 0.0, qz: 0.0 }
    timestampMs.value = 0
    isLive.value = false
    lastUpdateMs.value = 0

    avoidanceVector.value = { x: 0, y: 0, z: 0 }
    pressureL.value = 1.8
    pressureR.value = 1.8
    pumpActive.value = false
    reliefActive.value = false
    hugForce.value = 0.0
    flexRate.value = 5.0
    pmu.value = {
      voltage: 24.0,
      current: 0.7,
      soc: 100.0,
      temp: 32.0
    }
    joints.value = []
    jointStates.value = { name: [], position: [] }
    isSimulated.value = true
  }

  return {
    position,
    rotation,
    timestampMs,
    isLive,
    isSimulated,
    avoidanceVector,
    pressureL,
    pressureR,
    pumpActive,
    reliefActive,
    hugForce,
    flexRate,
    pmu,
    joints,
    jointStates,
    positionFormatted,
    rotationFormatted,
    updateKinematics,
    updateAvoidanceVector,
    updateJointStates,
    updatePneumatic,
    updateTactile,
    updatePmu,
    updateJoints,
    updateThermalRppg,
    setLive,
    reset,
    rppgHeartRate,
    thermalTemperature,
    feverAlert,
    tracker
  }
})
