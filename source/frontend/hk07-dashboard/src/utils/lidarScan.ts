import type { LidarScanSnapshot, ThreatLevel } from '../types/safety'

export const OBSTACLE_STOP_M = 0.5
export const CAUTION_M = 1.0
export const WARNING_M = 2.0
export const BEARINGS = 360
export const STALE_MS = 3000

export function normalizeRangesTo360(raw: number[], meta?: {
  angle_min?: number
  angle_increment?: number
}): number[] {
  const out = new Array(BEARINGS).fill(0)
  const n = raw.length
  if (n === 0) return out
  if (n === BEARINGS) return raw.slice()
  const angleMin = meta?.angle_min ?? -Math.PI
  const angleInc = meta?.angle_increment ?? (2 * Math.PI) / n
  for (let deg = 0; deg < BEARINGS; deg++) {
    const rad = (deg * Math.PI) / 180
    let idx = Math.round((rad - angleMin) / angleInc)
    if (idx < 0) idx = 0
    if (idx >= n) idx = n - 1
    out[deg] = raw[idx]
  }
  return out
}

export function classifyThreat(minDist: number): ThreatLevel {
  if (minDist <= 0.01) return 'UNKNOWN'
  if (minDist < OBSTACLE_STOP_M) return 'CRITICAL'
  if (minDist < CAUTION_M) return 'WARNING'
  if (minDist < WARNING_M) return 'CAUTION'
  return 'SAFE'
}

export function hugoHint(minDist: number, closeSectors: number): string {
  if (minDist <= 0.01) {
    return 'Chưa nhận tín hiệu thị giác IPWebcam — tôi đang lắng nghe môi trường xung quanh bạn.'
  }
  if (minDist < OBSTACLE_STOP_M) {
    return 'Có vật thể quá gần — tôi sẽ dừng lại ngay để bảo vệ bạn.'
  }
  if (minDist < CAUTION_M) {
    return 'Không gian phía trước đang hẹp. Tôi sẽ đi chậm và giữ khoảng cách an toàn.'
  }
  if (minDist < WARNING_M || closeSectors > 0) {
    return 'Có vật thể trong vùng lân cận — tôi quan sát và điều chỉnh đường đi nhẹ nhàng.'
  }
  return 'Vùng xung quanh bạn đang thoáng. Tôi có thể đồng hành an toàn.'
}

export function analyzeRawScan(body: Record<string, unknown>): LidarScanSnapshot {
  const rangesRaw = Array.isArray(body.ranges) ? (body.ranges as number[]) : []
  const ranges360 = body.ranges360
    ? (body.ranges360 as number[])
    : normalizeRangesTo360(rangesRaw, {
        angle_min: body.angle_min as number | undefined,
        angle_increment: body.angle_increment as number | undefined,
      })

  let minDist = Infinity
  let closestAngle = 0
  let closeSectors = 0
  for (let deg = 0; deg < ranges360.length; deg++) {
    const d = ranges360[deg]
    if (d <= 0.01 || !Number.isFinite(d)) continue
    if (d < minDist) {
      minDist = d
      closestAngle = deg
    }
    if (d < OBSTACLE_STOP_M) closeSectors++
  }
  if (!Number.isFinite(minDist)) minDist = 0

  const ts = typeof body.timestampMs === 'number' ? body.timestampMs
    : typeof body.timestamp_ms === 'number' ? body.timestamp_ms
    : Date.now()

  return {
    ranges360,
    minDistanceM: minDist === Infinity ? 0 : minDist,
    closestAngleDeg: closestAngle,
    timestampMs: ts,
    scanHz: typeof body.scanHz === 'number' ? body.scanHz : 0,
    threatLevel: (body.threatLevel as ThreatLevel) || classifyThreat(minDist === Infinity ? 0 : minDist),
    hugoHint: (body.hugoHint as string) || (body.baymaxHint as string) || hugoHint(minDist === Infinity ? 0 : minDist, closeSectors),
    live: body.live === true,
    sectorCount: typeof body.sectorCount === 'number' ? body.sectorCount : rangesRaw.length,
  }
}

export function pointColor(distanceM: number): string {
  if (distanceM <= 0.01) return 'rgba(80, 80, 80, 0.3)'
  if (distanceM < OBSTACLE_STOP_M) return '#FF3333'
  if (distanceM < CAUTION_M) return '#FF8800'
  if (distanceM < WARNING_M) return '#FFCC00'
  return '#00FF66'
}
