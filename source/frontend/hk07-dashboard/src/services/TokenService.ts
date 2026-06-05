/**
 * TokenService — Single source of truth for all refresh token operations.
 *
 * Implements the Mutex Refresh Pattern:
 *   - If a refresh is already in flight, all subsequent callers AWAIT the
 *     SAME promise (no duplicate refresh requests)
 *   - Uses a dedicated axios instance with withCredentials: true (explicit)
 *   - Never uses raw axios for auth calls
 *
 * WebSocket swap contract: This module is the ONLY place that touches
 * the /auth/refresh endpoint. Replacing the transport (e.g. adding OAuth2)
 * requires changing ONLY this file.
 */
import axios from 'axios'

const authAxios = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  withCredentials: true,  // EXPLICIT — sends HttpOnly cookie hk07_refresh_token
  timeout: 8_000,
})

export interface RefreshResult {
  accessToken: string
  userId: string
  role: string
  email?: string
}

// ── Mutex: one in-flight refresh at a time ────────────────────────────────
let _refreshPromise: Promise<RefreshResult> | null = null

export const TokenService = {
  /**
   * Refresh the access token using the HttpOnly cookie.
   * Mutex pattern: if a refresh is already in-flight, all concurrent callers
   * receive the SAME promise — preventing duplicate cookie rotations that
   * would trigger a Redis "token already revoked" rejection.
   */
  async refresh(): Promise<RefreshResult> {
    if (_refreshPromise) {
      return _refreshPromise
    }

    _refreshPromise = authAxios
      .post<{ data: RefreshResult }>('/auth/refresh')
      .then(res => {
        const d = res.data.data
        // Validate essential fields before propagating
        if (!d?.accessToken || !d?.userId || !d?.role) {
          throw new Error('[TokenService] Malformed refresh response from server')
        }
        return d
      })
      .finally(() => {
        _refreshPromise = null  // Release mutex — whether success or failure
      })

    return _refreshPromise
  },

  /** True while a refresh is in-flight (use for UI indicators) */
  get isRefreshing(): boolean {
    return _refreshPromise !== null
  },
}
