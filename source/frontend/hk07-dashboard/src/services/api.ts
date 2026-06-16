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
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,  // Required: sends HttpOnly cookie on all requests
})

let isRefreshing = false
let refreshSubscribers: ((token: string) => void)[] = []

function subscribeTokenRefresh(cb: (token: string) => void) {
  refreshSubscribers.push(cb)
}

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token))
  refreshSubscribers = []
}

api.interceptors.request.use(async (config) => {
  const authStore = useAuthStore()
  let token = authStore.accessToken

  const isPublicRoute = config.url && (
    config.url.includes('/auth/') ||
    config.url === '/health' ||
    config.url === '/error' ||
    config.url.includes('/actuator/')
  )

  const isSecureAgentRoute = config.url && (
    config.url.includes('/agents/') || 
    config.url.includes('/safety/')
  )

  if (isSecureAgentRoute && (!token || token === 'undefined' || token === 'null')) {
    if (isRefreshing) {
      return new Promise((resolve) => {
        subscribeTokenRefresh((newToken) => {
          config.headers = config.headers || {}
          config.headers.Authorization = `Bearer ${newToken}`
          resolve(config)
        })
      })
    }

    isRefreshing = true
    try {
      const success = await authStore.refreshSession()
      if (success) {
        token = authStore.accessToken
        onRefreshed(token!)
      }
    } catch (err) {
      console.warn("[API_INTERCEPTOR] Silent refresh failed before secure request:", err)
    } finally {
      isRefreshing = false
    }
  }

  if (token && token !== 'undefined' && token !== 'null') {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  } else if (isSecureAgentRoute) {
    return Promise.reject(new Error("BLOCKED_BY_INTERCEPTOR: Missing valid access token for secure path"))
  }
  return config
}, (error) => {
  return Promise.reject(error)
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      const authStore = useAuthStore()

      if (isRefreshing) {
        return new Promise((resolve) => {
          subscribeTokenRefresh((newToken) => {
            originalRequest.headers = originalRequest.headers || {}
            originalRequest.headers.Authorization = `Bearer ${newToken}`
            resolve(api(originalRequest))
          })
        })
      }

      isRefreshing = true
      try {
        const data = await TokenService.refresh()
        authStore.setAuth(data.accessToken, {
          id: data.userId,
          email: data.email ?? authStore.user?.email ?? '',
          role: data.role,
        })

        const newToken = data.accessToken
        onRefreshed(newToken)

        const retryConfig = {
          ...originalRequest,
          headers: {
            ...originalRequest.headers,
            Authorization: `Bearer ${newToken}`,
          },
        }
        return api(retryConfig)
      } catch (refreshError) {
        authStore.clearSession()
        
        // Clear all active polling intervals/timeouts globally to prevent background leakage
        for (let i = 1; i < 10000; i++) {
          window.clearInterval(i);
          window.clearTimeout(i);
        }

        document.dispatchEvent(new CustomEvent('hk07:unauthorized'))
        document.dispatchEvent(new CustomEvent('hk07:toast', {
          detail: {
            severity: 'error',
            agent: 'AUTH',
            message: '[SESSION_EXPIRED] Phiên đăng nhập hết hạn. Đang chuyển hướng đến trang đăng nhập...',
            duration: 4000
          }
        }))
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
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



export default api
