import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useAuthStore = defineStore('auth', () => {
  // In-memory tokens — NOT saved to localStorage for security
  const accessToken = ref<string | null>(null)
  const refreshToken = ref<string | null>(null)
  
  // Minimal user info (can be saved securely or fetched on boot)
  const user = ref<{ id: string, email: string, role: string } | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)
  const isOwner = computed(() => user.value?.role === 'OWNER')

  function setAuth(token: string, refresh: string, userData: any) {
    accessToken.value = token
    refreshToken.value = refresh
    user.value = userData
  }

  function clearAuth() {
    accessToken.value = null
    refreshToken.value = null
    user.value = null
  }

  async function refreshSession(): Promise<boolean> {
    if (!refreshToken.value) return false
    try {
      const resp = await axios.post('/api/v1/auth/refresh', {
        refreshToken: refreshToken.value
      })
      const newToken = resp.data.data.accessToken
      const newRefresh = resp.data.data.refreshToken
      setAuth(newToken, newRefresh, user.value)
      return true
    } catch (err) {
      clearAuth()
      document.dispatchEvent(new CustomEvent('hk07:unauthorized'))
      return false
    }
  }

  return {
    accessToken,
    refreshToken,
    user,
    isAuthenticated,
    isOwner,
    setAuth,
    clearAuth,
    refreshSession
  }
})
