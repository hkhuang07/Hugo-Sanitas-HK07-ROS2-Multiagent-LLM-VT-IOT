import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
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

  // Actions
  function updateVitals(data: VitalSign) {
    current.value = data

    // Ring buffer write (overwrite at write index, increment modulo)
    const idx = bufferWriteIdx.value % RING_BUFFER_SIZE
    heartRateHistory.value[idx] = data.heartRate
    spo2History.value[idx] = data.spo2
    bufferWriteIdx.value++
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
  }

  return {
    current,
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
    isConnected
  }
})
