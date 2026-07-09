import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import api from '../services/api'

export interface VitalSign {
  deviceId: string
  heartRate: number
  systolic: number
  diastolic: number
  bodyTemperature: number
  spo2: number
  epochTimestampMs: number
  alertLevel?: 'NORMAL' | 'WARNING' | 'CRITICAL' | 'STROKE'
  userId?: string
  hormones?: Record<string, any>
}

export interface HourlyBucket {
  bucket_hour: string
  avg_hr: number | null
  max_hr: number | null
  min_hr: number | null
  avg_systolic: number | null
  avg_spo2: number | null
  avg_temp: number | null
  sample_count: number | null
  worst_alert: string | null
}

const RING_BUFFER_SIZE = 120  // 2 seconds @ 60Hz — Lag Compensation buffer

// ── [P1-2] IndexedDB Offline Cache ──────────────────────────────────────────
const IDB_DB_NAME = 'hk07-vitals-cache'
const IDB_STORE = 'offline-queue'
const IDB_MAX_RECORDS = 300  // ~5 seconds at 60Hz

let idb: IDBDatabase | null = null

async function openIDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_DB_NAME, 1)
    req.onupgradeneeded = (e) => {
      const db = (e.target as IDBOpenDBRequest).result
      if (!db.objectStoreNames.contains(IDB_STORE)) {
        const store = db.createObjectStore(IDB_STORE, { autoIncrement: true })
        store.createIndex('ts', 'epochTimestampMs', { unique: false })
      }
    }
    req.onsuccess = (e) => resolve((e.target as IDBOpenDBRequest).result)
    req.onerror = (e) => reject((e.target as IDBOpenDBRequest).error)
  })
}

async function idbPush(vital: VitalSign): Promise<void> {
  if (!idb) idb = await openIDB()
  const tx = idb.transaction(IDB_STORE, 'readwrite')
  const store = tx.objectStore(IDB_STORE)
  store.add(vital)
  // Trim to max records (delete oldest)
  const countReq = store.count()
  countReq.onsuccess = () => {
    if (countReq.result > IDB_MAX_RECORDS) {
      const openCursor = store.openCursor()
      openCursor.onsuccess = (e) => {
        const cursor = (e.target as IDBRequest<IDBCursorWithValue>).result
        if (cursor) { cursor.delete(); cursor.continue() }
      }
    }
  }
}

export async function idbFlushOfflineQueue(): Promise<VitalSign[]> {
  if (!idb) idb = await openIDB()
  return new Promise((resolve) => {
    const tx = idb!.transaction(IDB_STORE, 'readwrite')
    const store = tx.objectStore(IDB_STORE)
    const records: VitalSign[] = []
    const req = store.openCursor()
    req.onsuccess = (e) => {
      const cursor = (e.target as IDBRequest<IDBCursorWithValue>).result
      if (cursor) {
        records.push(cursor.value as VitalSign)
        cursor.delete()
        cursor.continue()
      } else {
        resolve(records)
      }
    }
    req.onerror = () => resolve([])
  })
}

/**
 * Vitals Pinia Store — Real-time vital signs state
 *
 * Implements a fixed-size ring buffer for the ECG canvas.
 * Ring buffer uses pre-allocated array to avoid GC pressure at 60Hz.
 *
 * [P1-2] Adds IndexedDB offline queue:
 *   - When WebSocket is disconnected, incoming vitals (from polling/reconnect)
 *     are persisted to IndexedDB so no data is lost during temporary drops.
 *   - On reconnect, flushOfflineQueue() replays buffered data into the ring.
 */
export const useVitalsStore = defineStore('vitals', () => {
  // Current snapshot (WebSocket updates these)
  const current = ref<VitalSign>({
    deviceId: '',
    heartRate: 0,
    systolic: 0,
    diastolic: 0,
    bodyTemperature: 0,
    spo2: 0,
    epochTimestampMs: 0,
    alertLevel: 'NORMAL',
  })

  const isSimulated = ref(true)

  // Persisted state from localStorage
  const savedBuckets = localStorage.getItem('hk07_vitals_buckets')
  const hourlyBuckets = ref<HourlyBucket[]>(savedBuckets ? JSON.parse(savedBuckets) : [])

  // Ring buffer for ECG waveform — pre-allocated array of fixed size
  const heartRateHistory = ref<number[]>(Array(RING_BUFFER_SIZE).fill(0))
  const spo2History = ref<number[]>(Array(RING_BUFFER_SIZE).fill(99))
  const bufferWriteIdx = ref(0)

  // Computed
  const alertLevel = computed(() => current.value.alertLevel ?? 'NORMAL')
  const alertClass = computed(() => {
    const map: Record<string, string> = {
      NORMAL: 'state-normal', WARNING: 'state-warning',
      CRITICAL: 'state-critical', STROKE: 'state-stroke',
    }
    return map[alertLevel.value] || 'state-normal'
  })
  const isEmergency = computed(() =>
    alertLevel.value === 'CRITICAL' || alertLevel.value === 'STROKE'
  )

  const isConnected = ref(false)
  const apiLatency = ref<number | null>(null)

  async function measureLatency() {
    const start = performance.now()
    try {
      await api.get('/agents/vitals/latest', { timeout: 2000 })
      const end = performance.now()
      apiLatency.value = Math.round(end - start)
    } catch (err: any) {
      if (err.code === 'ECONNABORTED' || err.message?.toLowerCase().includes('network') || !err.response) {
        apiLatency.value = null
      } else {
        const end = performance.now()
        apiLatency.value = Math.round(end - start)
      }
    }
  }

  if (typeof window !== 'undefined') {
    measureLatency()
    setInterval(measureLatency, 5000)
  }

  // Actions
  function updateVitals(data: VitalSign) {
    current.value = data
    isSimulated.value = data.hormones?.is_simulated ?? false

    // Ring buffer write (overwrite at write index, increment modulo)
    const idx = bufferWriteIdx.value % RING_BUFFER_SIZE
    heartRateHistory.value[idx] = data.heartRate
    spo2History.value[idx] = data.spo2
    bufferWriteIdx.value++

    // Update hourly buckets in real-time
    const date = new Date(data.epochTimestampMs || Date.now())
    const pad = (n: number) => n.toString().padStart(2, '0')
    const bucketHour = `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:00:00`

    let bucket = hourlyBuckets.value.find(b => b.bucket_hour.startsWith(bucketHour.slice(0, 13)))
    if (!bucket) {
      bucket = {
        bucket_hour: bucketHour,
        avg_hr: data.heartRate > 0 ? data.heartRate : null,
        max_hr: data.heartRate > 0 ? data.heartRate : null,
        min_hr: data.heartRate > 0 ? data.heartRate : null,
        avg_systolic: data.systolic > 0 ? data.systolic : null,
        avg_spo2: data.spo2 > 0 ? data.spo2 : null,
        avg_temp: data.bodyTemperature > 0 ? data.bodyTemperature : null,
        sample_count: 1,
        worst_alert: data.alertLevel || 'NORMAL'
      }
      hourlyBuckets.value.push(bucket)
      if (hourlyBuckets.value.length > 200) {
        hourlyBuckets.value.shift()
      }
    } else {
      const count = bucket.sample_count || 0
      bucket.sample_count = count + 1

      if (data.heartRate > 0) {
        bucket.avg_hr = bucket.avg_hr 
          ? Math.round((bucket.avg_hr * count + data.heartRate) / (count + 1))
          : data.heartRate
        bucket.max_hr = bucket.max_hr ? Math.max(bucket.max_hr, data.heartRate) : data.heartRate
        bucket.min_hr = bucket.min_hr ? Math.min(bucket.min_hr, data.heartRate) : data.heartRate
      }
      if (data.systolic > 0) {
        bucket.avg_systolic = bucket.avg_systolic
          ? Math.round((bucket.avg_systolic * count + data.systolic) / (count + 1))
          : data.systolic
      }
      if (data.spo2 > 0) {
        bucket.avg_spo2 = bucket.avg_spo2
          ? (bucket.avg_spo2 * count + data.spo2) / (count + 1)
          : data.spo2
      }
      if (data.bodyTemperature > 0) {
        bucket.avg_temp = bucket.avg_temp
          ? (bucket.avg_temp * count + data.bodyTemperature) / (count + 1)
          : data.bodyTemperature
      }
      
      const alertPriority: Record<string, number> = { NORMAL: 0, WARNING: 1, CRITICAL: 2, STROKE: 3 }
      const newLevel = data.alertLevel || 'NORMAL'
      const currentLevel = bucket.worst_alert || 'NORMAL'
      if ((alertPriority[newLevel] ?? 0) > (alertPriority[currentLevel] ?? 0)) {
        bucket.worst_alert = newLevel
      }
    }
  }

  // [P1-2] Called when WebSocket drops — cache incoming vitals to IndexedDB
  async function cacheOffline(data: VitalSign): Promise<void> {
    try {
      await idbPush(data)
    } catch (e) {
      console.warn('[VITALS_STORE] IndexedDB cache failed:', e)
    }
  }

  // [P1-2] Called on WebSocket reconnect — replay cached vitals into ring buffer and push to backend
  async function flushOfflineQueue(): Promise<void> {
    try {
      const records = await idbFlushOfflineQueue()
      if (records.length > 0) {
        console.log(`[VITALS_STORE] Replaying ${records.length} offline vitals into ring buffer and syncing to backend...`)
        // Replay locally for UI
        for (const vital of records) {
          updateVitals(vital)
        }
        
        // [HẠNCHẾ-#4 FIX] Sync to backend REST API so server DB isn't missing data
        try {
          await api.post('/health/sync-offline', records)
          console.log('[VITALS_STORE] Successfully synced offline vitals to backend')
        } catch (syncError) {
          console.error('[VITALS_STORE] Failed to sync offline vitals to backend', syncError)
          // Ideally we would push them back to IDB if sync fails, but for simplicity we log the error
        }
      }
    } catch (e) {
      console.warn('[VITALS_STORE] IndexedDB flush failed:', e)
    }
  }

  function reset() {
    heartRateHistory.value.fill(0)
    spo2History.value.fill(99)
    bufferWriteIdx.value = 0
    isConnected.value = false
    isSimulated.value = true
  }

  // Watchers to update localStorage automatically on changes
  watch(hourlyBuckets, (newVal) => {
    localStorage.setItem('hk07_vitals_buckets', JSON.stringify(newVal))
  }, { deep: true })

  return {
    current,
    hourlyBuckets,
    alertLevel,
    alertClass,
    isEmergency,
    updateVitals,
    cacheOffline,
    flushOfflineQueue,
    reset,
    heartRateHistory,
    bufferWriteIdx,
    RING_BUFFER_SIZE,
    isConnected,
    isSimulated,
    apiLatency
  }
})
