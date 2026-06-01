import axios from 'axios'
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

axios.defaults.withCredentials = true

/**
 * Axios instance with JWT interceptor.
 * - Injects Authorization: Bearer header from Pinia auth store
 * - On 401: clears tokens and redirects to login
 */
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 10_000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true
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
      
      try {
        // Attempt silent refresh
        const resp = await axios.post(`${import.meta.env.VITE_API_URL || '/api/v1'}/auth/refresh`)
        const newToken = resp.data.data.accessToken
        
        // Update in-memory store
        authStore.setAuth(newToken, authStore.user)
        
        // Retry original request
        originalRequest.headers.Authorization = `Bearer ${newToken}`
        return api(originalRequest)
      } catch (refreshError) {
        // Refresh failed — wipe memory and trigger redirect
        authStore.clearAuth()
        document.dispatchEvent(new CustomEvent('hk07:unauthorized'))
        return Promise.reject(refreshError)
      }
    }
    return Promise.reject(error)
  }
)

export default api
