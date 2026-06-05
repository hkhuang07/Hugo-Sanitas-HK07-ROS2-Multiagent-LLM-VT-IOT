<template>
  <header class="hud-header">
    <div class="header-left">
      <!-- Hamburger Toggle — emits 'toggle-sidebar' to App.vue -->
      <button
        class="hamburger-btn"
        @click="emit('toggle-sidebar')"
        :title="'Toggle Sidebar'"
        aria-label="Toggle sidebar navigation"
      >
        <span class="ham-bar"></span>
        <span class="ham-bar"></span>
        <span class="ham-bar"></span>
      </button>

      <img src="/images/main_logo.jpg" alt="Logo" class="logo-img" />
      <img src="/images/logo_name.jpg" alt="Logo Name" class="logo-name-img" />
      <span class="terminal-id">[ TERMINAL: HUGO-SANITAS-HK07 ]</span>
      <span class="text-dim"> // </span>
      <span class="text-dim current-path">{{ currentPath }}</span>
    </div>
    
    <nav class="header-nav">
      <template v-if="authStore.isAuthenticated">
        <router-link to="/" class="nav-item" active-class="nav-active">VITALS</router-link>
        <router-link to="/companion" class="nav-item" active-class="nav-active">COMPANION</router-link>
        <router-link to="/agents" class="nav-item" active-class="nav-active">AGENTS</router-link>
        <router-link to="/safety" class="nav-item" active-class="nav-active">SAFETY</router-link>
        <router-link to="/history" class="nav-item" active-class="nav-active">HISTORY</router-link>
      </template>
      <template v-else>
        <span class="nav-item static-nav">PUBLIC_PORTAL</span>
      </template>
    </nav>
    
    <div class="header-right">
      <template v-if="authStore.isAuthenticated">
        <span class="user-role-badge">[ {{ authStore.user?.role }} ]</span>
        <span :class="['system-state-badge hud', stateClass]">[ {{ systemState }} ]</span>
        <button class="cmd-btn logout-btn" @click="handleLogout">LOGOUT</button>
      </template>
      <template v-else>
        <span class="system-state-badge hud text-dim">[ AUTH_REQUIRED ]</span>
      </template>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useVitalsStore } from '../stores/vitals'
import { useAgentsStore } from '../stores/agents'

const emit = defineEmits<{ (e: 'toggle-sidebar'): void }>()

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const vitalsStore = useVitalsStore()
const agentsStore = useAgentsStore()

const currentPath = computed(() => {
  const path = route.path
  if (path === '/') return 'PATH: /v1/hk07/core/vitals'
  if (path === '/companion') return 'PATH: /v1/hk07/agents/empathetic/chat'
  if (path === '/agents') return 'PATH: /v1/hk07/agents/stream'
  if (path === '/safety') return 'PATH: /v1/hk07/safety/sensors'
  if (path === '/history') return 'PATH: /v1/hk07/health/history'
  if (path === '/login') return 'PATH: /v1/hk07/auth/login'
  return `PATH: ${path}`
})

const systemState = computed(() => {
  if (vitalsStore.isEmergency) return 'EMERGENCY_ALERT'
  if (agentsStore.subsumptionActive) return 'SAFETY_OVERRIDE'
  return vitalsStore.current.deviceId ? 'SYSTEM_ACTIVE' : 'OFFLINE_MODE'
})

const stateClass = computed(() => {
  if (vitalsStore.isEmergency) return 'status-crit text-red'
  if (agentsStore.subsumptionActive) return 'status-warn text-orange'
  return vitalsStore.current.deviceId ? 'status-ok text-green' : 'text-dim'
})

function handleLogout() {
  authStore.clearAuth()
  router.push('/login')
}
</script>

<style scoped>
.hud-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 6px 12px;
  background: var(--color-bg-void);
  border-bottom: 1px solid var(--color-border-dim);
  font-family: var(--font-hud);
  font-size: clamp(7px, 0.8vw, 10px);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--color-text-dim);
  flex-shrink: 0;
  user-select: none;
  flex-wrap: wrap;
  min-height: 48px;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  flex-shrink: 1;
  min-width: 0;
}
.header-nav {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
  flex: 1;
  justify-content: center;
  min-width: 0;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  flex-shrink: 0;
}
.logo-img {
  height: 36px;
  flex-shrink: 0;
}
.logo-name-img {
  height: 36px;
  flex-shrink: 0;
}
.main-logo-img {
  height: 18px;
  margin-right: 6px;
  flex-shrink: 0;
}
.terminal-id {
  color: var(--color-accent-green);
  font-weight: bold;
  flex-shrink: 1;
  white-space: normal;
  word-break: break-word;
  font-size: clamp(7px, 0.75vw, 10px);
}
.current-path {
  font-size: clamp(7px, 0.65vw, 9px);
  font-family: var(--font-data);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: clamp(80px, 12vw, 180px);
  flex-shrink: 1;
}
.nav-item {
  color: var(--color-text-dim);
  text-decoration: none;
  font-weight: bold;
  padding: 3px 5px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
  white-space: nowrap;
  flex-shrink: 0;
  letter-spacing: 0.06em;
  font-size: clamp(7px, 0.7vw, 10px);
}
.nav-item:hover {
  color: var(--color-accent-green);
  border-bottom: 1px solid var(--color-accent-green);
}
.nav-active {
  color: var(--color-accent-green) !important;
  border: 1px solid var(--color-border-dim) !important;
  background: rgba(0, 255, 102, 0.05);
}
.static-nav {
  border: 1px solid var(--color-border-dim);
  color: var(--color-accent-cyan);
}
.user-role-badge {
  color: var(--color-accent-cyan);
  font-weight: bold;
  white-space: nowrap;
  flex-shrink: 0;
}
.system-state-badge {
  padding: 2px 4px;
  white-space: nowrap;
  flex-shrink: 0;
}
.status-ok {
  color: var(--color-accent-green);
}
.status-warn {
  color: var(--color-accent-orange);
}
.status-crit {
  color: var(--color-accent-red);
  animation: blink-crit 1s step-end infinite;
}
@keyframes blink-crit {
  50% { opacity: 0.4; }
}
.logout-btn {
  font-size: 9px;
  padding: 2px 6px;
  border-color: var(--color-accent-red);
  color: var(--color-accent-red);
  white-space: nowrap;
  flex-shrink: 0;
}
.logout-btn:hover {
  background: var(--color-accent-red);
  color: var(--color-bg-void);
}

/* ─── Hamburger Button ─────────────────────────────────────────────────────── */
.hamburger-btn {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  padding: 4px 6px;
  background: transparent;
  border: 1px solid transparent;
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.2s ease, background 0.2s ease;
  height: 30px;
  width: 30px;
}
.hamburger-btn:hover {
  border-color: var(--color-border-dim);
  background: rgba(0, 82, 255, 0.08);
  box-shadow: 0 0 6px rgba(0, 82, 255, 0.3);
}
.hamburger-btn:hover .ham-bar {
  background: var(--color-border-blue);
}
.ham-bar {
  display: block;
  width: 16px;
  height: 2px;
  background: var(--color-text-dim);
  transition: background 0.2s ease;
  flex-shrink: 0;
}
</style>
