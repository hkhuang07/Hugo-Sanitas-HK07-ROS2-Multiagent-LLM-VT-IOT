import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { TokenService } from '../services/TokenService'

export const useAuthStore = defineStore('auth', () => {
  // ── State ──────────────────────────────────────────────────────────────────
  // accessToken: in-memory ONLY. Never persisted to localStorage (XSS risk).
  // Wiped on page unload by design. Restored via HttpOnly cookie on reload.
  const accessToken = ref<string | null>(null)
  const user = ref<{ id: string; email: string; role: string } | null>(null)

  // ── Computed ───────────────────────────────────────────────────────────────
  const isAuthenticated = computed(() => !!accessToken.value)
  const isOwner = computed(() => user.value?.role === 'OWNER')

  // ── Actions ────────────────────────────────────────────────────────────────
  function setAuth(token: string, userData: { id: string; email: string; role: string }) {
    accessToken.value = token
    user.value = userData
  }

  function clearAuth() {
    accessToken.value = null
    user.value = null
  }

  /**
   * Called on app boot (main.ts — before mount).
   *
   * Sends POST /auth/refresh with the HttpOnly cookie hk07_refresh_token.
   * The cookie is set by the browser automatically (withCredentials: true in TokenService).
   * No token is read from localStorage — this is fully stateless from the JS perspective.
   *
   * Returns: true = session restored, false = must login
   */
  async function tryAutoLogin(): Promise<boolean> {
    try {
      const data = await TokenService.refresh()
      setAuth(data.accessToken, {
        id: data.userId,
        // Preserve existing email if server did not return one (backward compat)
        email: data.email ?? user.value?.email ?? '',
        role: data.role,
      })
      return true
    } catch {
      clearAuth()
      return false
    }
  }

  /**
   * Silent token refresh — delegates to TokenService (mutex-safe).
   *
   * Called by:
   *   - services/api.ts — 401 response interceptor
   *   - services/websocket.ts — beforeConnect hook
   *
   * Both callers share the same mutex Promise if called simultaneously.
   */
  async function refreshSession(): Promise<boolean> {
    try {
      const data = await TokenService.refresh()
      setAuth(data.accessToken, {
        id: data.userId,
        email: data.email ?? user.value?.email ?? '',
        role: data.role,
      })
      return true
    } catch {
      clearAuth()
      document.dispatchEvent(new CustomEvent('hk07:unauthorized'))
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
    tryAutoLogin,
    refreshSession,
  }
})
