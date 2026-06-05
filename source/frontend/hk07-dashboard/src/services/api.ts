/**
 * API Axios Instance — HK-07 Dashboard
 *
 * Features:
 *   - Request interceptor: injects Authorization: Bearer header
 *   - Response interceptor: silent 401 refresh via TokenService (mutex-safe)
 *   - Retry: original request is replayed once after successful refresh
 *   - No raw axios calls — all auth ops go through TokenService
 */
import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import { TokenService } from './TokenService'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,  // Required: sends HttpOnly cookie on all requests
})

// ── Request interceptor: inject current access token ─────────────────────
api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.accessToken) {
    config.headers.Authorization = `Bearer ${authStore.accessToken}`
  }
  return config
})

// ── Response interceptor: mutex-safe silent refresh on 401 ───────────────
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    // Only attempt refresh once per request (_retry guard prevents infinite loop)
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      const authStore = useAuthStore()

      try {
        // TokenService.refresh() is mutex-safe: concurrent 401s share one refresh call.
        // If 5 tabs fire simultaneously, only 1 POST /auth/refresh is issued.
        const data = await TokenService.refresh()

        authStore.setAuth(data.accessToken, {
          id: data.userId,
          email: data.email ?? authStore.user?.email ?? '',
          role: data.role,
        })

        // Replay the original request with the new token
        originalRequest.headers.Authorization = `Bearer ${data.accessToken}`
        return api(originalRequest)
      } catch (refreshError) {
        // Refresh failed (cookie expired/revoked) — force re-login
        authStore.clearAuth()
        document.dispatchEvent(new CustomEvent('hk07:unauthorized'))
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

// ── Named exports (feature-specific helpers) ──────────────────────────────

/** E-STOP — triggers emergency SOS protocol on the robot core */
export function triggerRobotSosTrigger() {
  return api.post('/robot/sos-trigger')
}

/** Latest LiDAR snapshot (360 bearings) from MQTT pipeline */
export function fetchLidarSnapshot() {
  return api.get<{ data: import('../types/safety').LidarScanSnapshot }>('/safety/lidar/snapshot')
}

export default api
