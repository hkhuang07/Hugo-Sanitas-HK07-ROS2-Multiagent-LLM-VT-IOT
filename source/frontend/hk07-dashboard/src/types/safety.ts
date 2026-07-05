export type ThreatLevel = 'SAFE' | 'CAUTION' | 'WARNING' | 'CRITICAL' | 'UNKNOWN'

export interface LidarScanSnapshot {
  ranges360: number[]
  minDistanceM: number
  closestAngleDeg: number
  timestampMs: number
  scanHz: number
  threatLevel: ThreatLevel
  hugoHint: string
  live: boolean
  sectorCount?: number
}

export interface SafetyInhibitAlert {
  subsumptionActivated: boolean
  triggerType: string
  distanceM?: number
  message?: string
  accelerationG?: number
  lux?: number
}

export interface ActiveSafetyTrigger {
  type: string
  distanceM: number
  message: string
  severity: 'critical' | 'warning'
  detectedAt: number
}
