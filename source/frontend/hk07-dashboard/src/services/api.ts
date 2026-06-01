import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

/**
 * Axios instance with JWT interceptor.
 * - Injects Authorization: Bearer header from Pinia auth store
 * - On 401: clears tokens and redirects to login
 */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.accessToken) {
    config.headers.Authorization = `Bearer ${authStore.accessToken}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    
    // Auto-refresh token logic on 401
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      const authStore = useAuthStore()
      
      if (authStore.refreshToken) {
        try {
          // Attempt silent refresh
          const resp = await axios.post(`${import.meta.env.VITE_API_URL || '/api/v1'}/auth/refresh`, {
            refreshToken: authStore.refreshToken
          })
          const newToken = resp.data.data.accessToken
          const newRefresh = resp.data.data.refreshToken
          
          // Update in-memory store
          authStore.setAuth(newToken, newRefresh, authStore.user)
          
          // Retry original request
          originalRequest.headers.Authorization = `Bearer ${newToken}`
          return axios(originalRequest)
        } catch (refreshError) {
          // Refresh failed — wipe memory and trigger redirect
          authStore.clearAuth()
          document.dispatchEvent(new CustomEvent('hk07:unauthorized'))
          return Promise.reject(refreshError)
        }
      } else {
        // No refresh token available in memory
        authStore.clearAuth()
        document.dispatchEvent(new CustomEvent('hk07:unauthorized'))
      }
    }
    return Promise.reject(error)
  }
)

export default api
