<template>
  <div class="app-shell cyber-scanlines">
    <NotificationToast />
    
    <!-- Standardized Header (Common Navbar) -->
    <HeaderStatusStrip />
    
    <!-- Main Area: Sidebar + Page Content -->
    <div :class="['app-layout-body', showSidebar ? 'has-sidebar' : '']">
      <RoleSidebar v-if="showSidebar" />
      <main class="app-main-content">
        <!-- Emergency banner visible on all pages when critical -->
        <div v-if="authStore.isAuthenticated && vitalsStore.isEmergency" class="emergency-banner">
          ⚠ ALERT: {{ vitalsStore.alertLevel }} — HR={{ vitalsStore.current.heartRate }}bpm
          SpO₂={{ vitalsStore.current.spo2 }}% — MEDICAL AGENT ANALYZING...
        </div>
        
        <router-view />
      </main>
    </div>
    
    <!-- Standardized Footer -->
    <CommonFooter />
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useVitalsStore } from './stores/vitals'
import { initWebSocket, disconnectWebSocket } from './services/websocket'
import NotificationToast from './components/NotificationToast.vue'
import HeaderStatusStrip from './components/HeaderStatusStrip.vue'
import RoleSidebar from './components/RoleSidebar.vue'
import CommonFooter from './components/CommonFooter.vue'

const route = useRoute()
const authStore = useAuthStore()
const vitalsStore = useVitalsStore()

const showSidebar = computed(() => {
  return authStore.isAuthenticated && route.name !== 'Login'
})

watch(() => authStore.isAuthenticated, (authed) => {
  if (authed) {
    initWebSocket()
  } else {
    disconnectWebSocket()
  }
}, { immediate: true })
</script>

<style>
/* Global App Shell Styles */
.app-shell {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--color-bg-void);
  color: var(--color-text-primary);
}

.app-layout-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.app-layout-body.has-sidebar {
  display: grid;
  grid-template-columns: 2fr 8fr;
}

.app-main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  background: var(--color-bg-void);
}

.emergency-banner {
  background: rgba(255, 51, 51, 0.15);
  border-bottom: 1px solid var(--color-accent-red);
  color: var(--color-accent-red);
  font-family: var(--font-hud);
  font-size: 10px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  padding: 6px 16px;
  text-align: center;
  animation: blink-danger 0.8s step-end infinite;
  flex-shrink: 0;
  z-index: 99;
}

@keyframes blink-danger {
  50% { opacity: 0.6; }
}
</style>
