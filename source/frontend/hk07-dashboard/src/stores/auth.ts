import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export const useAuthStore = defineStore('auth', () => {
  // In-memory token — NOT saved to localStorage for security
  const accessToken = ref<string | null>(null)
  
  // Minimal user info (can be saved securely or fetched on boot)
  const user = ref<{ id: string, email: string, role: string } | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)
  const isOwner = computed(() => user.value?.role === 'OWNER')

  function setAuth(token: string, userData: any) {
    accessToken.value = token
    user.value = userData
  }

  function clearAuth() {
    accessToken.value = null
    user.value = null
  }

  async function refreshSession(): Promise<boolean> {
    try {
      const resp = await axios.post('/api/v1/auth/refresh')
      const newToken = resp.data.data.accessToken
      setAuth(newToken, user.value)
      return true
    } catch (err) {
      clearAuth()
      document.dispatchEvent(new CustomEvent('hk07:unauthorized'))
      return false
    }
  }

  async function tryAutoLogin(): Promise<boolean> {
    try {
      const resp = await axios.post('/api/v1/auth/refresh')
      const newToken = resp.data.data.accessToken
      const userId = resp.data.data.userId
      const role = resp.data.data.role
      setAuth(newToken, { id: userId, email: '', role: role })
      return true
    } catch (err) {
      clearAuth()
      return false
    }
  }

  return {
    accessToken,
    user,
    isAuthenticated,
    isOwner,
    setAuth,
    clearAuth,
    refreshSession,
    tryAutoLogin
  }
})
