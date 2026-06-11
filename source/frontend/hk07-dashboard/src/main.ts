import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { router } from './router'
import App from './App.vue'
import './assets/cyber.css'
import { useAuthStore } from './stores/auth'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

const authStore = useAuthStore(pinia)

/**
 * authReadyPromise — exported so router/index.ts can await it in beforeEach.
 *
 * Problem: router.beforeEach() fires synchronously during initial navigation
 * (before app.mount), at which point tryAutoLogin() has NOT yet resolved.
 * isAuthenticated is therefore false, causing /history or any protected route
 * to redirect to /login on every page refresh (F5).
 *
 * Solution: export this Promise and await it in the guard before checking
 * isAuthenticated. The cost is a single extra tick on first navigation only.
 */
export const authReadyPromise: Promise<boolean> = authStore.tryAutoLogin()

authReadyPromise.finally(() => {
  app.mount('#app')
})
