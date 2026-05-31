<template>
  <aside class="sidebar-panel corner-reticle">
    <div class="sidebar-header">
      <span class="text-cyan font-bold text-xs">[ TACTICAL_CONSOLE ]</span>
      <span class="role-badge">{{ authStore.user?.role }}</span>
    </div>

    <!-- Minimal Tactical Navigation -->
    <div class="terminal-card">
      <div class="terminal-card-header">[ MENU_NAVIGATION ]</div>
      <div class="nav-links">
        <router-link to="/" class="sidebar-nav-item" active-class="active">
          <span class="index text-dim">[00]</span> DYNAMIC_TELEMETRY
        </router-link>
        <router-link to="/companion" class="sidebar-nav-item" active-class="active">
          <span class="index text-dim">[01]</span> COMPANION_UPLINK
        </router-link>
        <router-link to="/agents" class="sidebar-nav-item" active-class="active">
          <span class="index text-dim">[02]</span> AGENT_SYSTEM_LOG
        </router-link>
        <router-link to="/safety" class="sidebar-nav-item" active-class="active">
          <span class="index text-dim">[03]</span> SAFETY_COORDINATES
        </router-link>
        <router-link to="/history" class="sidebar-nav-item" active-class="active">
          <span class="index text-dim">[04]</span> HISTORICAL_METRICS
        </router-link>
      </div>
    </div>

    <!-- Active Session & Uptime Status -->
    <div class="terminal-card">
      <div class="terminal-card-header">[ SYSTEM_STATUS ]</div>
      <div class="status-grid mono text-[9px]">
        <div class="status-row">
          <span class="label">NODE:</span>
          <span class="val text-cyan">HK07_STATION</span>
        </div>
        <div class="status-row">
          <span class="label">LATENCY:</span>
          <span class="val text-green">1.2ms (SLA)</span>
        </div>
        <div class="status-row">
          <span class="label">UPLINK:</span>
          <span :class="vitalsStore.isConnected ? 'text-green' : 'text-orange'">
            {{ vitalsStore.isConnected ? 'CONNECTED' : 'STANDBY' }}
          </span>
        </div>
      </div>
    </div>

    <div class="sidebar-status-block">
      <span class="text-dim text-[8px]">[ CONSOLE_ACTIVE ]</span>
      <span class="blink-dot text-green text-[8px]">●</span>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { useAuthStore } from '../stores/auth'
import { useVitalsStore } from '../stores/vitals'

const authStore = useAuthStore()
const vitalsStore = useVitalsStore()
</script>

<style scoped>
.sidebar-panel {
  width: 100%;
  background: var(--color-bg-void);
  border-right: 1px solid var(--color-border-dim);
  display: flex;
  flex-direction: column;
  padding: var(--space-sm);
  gap: var(--space-sm);
  overflow-y: auto;
  overflow-x: hidden;
  flex-shrink: 0;
}
.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--font-hud);
  font-size: 9px;
  letter-spacing: 0.1em;
  border-bottom: 1px solid var(--color-border-dim);
  padding-bottom: 6px;
}
.role-badge {
  background: var(--color-border-dim);
  color: var(--color-accent-cyan);
  padding: 1px 4px;
  border-radius: 2px;
  font-weight: bold;
  font-size: 8px;
}
.nav-links {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 4px;
}
.sidebar-nav-item {
  display: flex;
  gap: 6px;
  font-family: var(--font-hud);
  font-size: 9px;
  letter-spacing: 0.1em;
  padding: 6px 8px;
  text-decoration: none;
  color: var(--color-text-dim);
  border: 1px solid transparent;
  transition: all 0.2s ease;
}
.sidebar-nav-item:hover {
  color: var(--color-accent-cyan);
  background: rgba(0, 210, 255, 0.03);
}
.sidebar-nav-item.active {
  color: var(--color-accent-cyan) !important;
  border: 1px solid var(--color-border-dim) !important;
  background: rgba(0, 210, 255, 0.05);
}
.status-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 4px;
}
.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.status-row .label {
  color: var(--color-text-dim);
  font-family: var(--font-hud);
  letter-spacing: 0.05em;
}
.sidebar-status-block {
  margin-top: auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--font-hud);
  font-size: 8px;
  letter-spacing: 0.1em;
  color: var(--color-text-dim);
  padding-top: 6px;
  border-top: 1px solid var(--color-border-dim);
}
.blink-dot {
  animation: pulse-dot 1.5s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.2; }
}
</style>
