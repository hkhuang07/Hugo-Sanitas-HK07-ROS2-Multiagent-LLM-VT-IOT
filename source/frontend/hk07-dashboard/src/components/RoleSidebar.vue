<template>
  <aside class="sidebar-panel corner-reticle">

    <!-- ─── SIDEBAR HEADER (always visible) ──────────────────────────── -->
    <div class="sidebar-header">
      <span class="text-cyan font-bold text-xs">[ TACTICAL_CONSOLE ]</span>
      <span v-if="authStore.isAuthenticated" class="role-badge">{{ authStore.user?.role }}</span>
      <span v-else class="role-badge role-badge--locked">LOCKED</span>
    </div>

    <!-- ─── NOT AUTHENTICATED — Public / Login prompt ────────────────── -->
    <div v-if="!authStore.isAuthenticated" class="auth-required-block terminal-card">
      <div class="terminal-card-header text-orange">
        [ AUTH_REQUIRED ]
      </div>
      <div class="auth-msg mono">
        <div class="text-dim text-[9px] mb-2">
          &gt;&gt;&gt; [ACCESS_DENIED] System console locked.<br />
          &gt;&gt;&gt; Authentication required to access tactical menu.
        </div>
        <div class="auth-nav-links">
          <router-link to="/login" class="sidebar-nav-item auth-cta">
            <span class="index text-orange">[--]</span> LOGIN_UPLINK
          </router-link>
          <router-link to="/emergency" class="sidebar-nav-item auth-emergency">
            <span class="index text-red">[!!]</span> EMERGENCY_ACCESS
          </router-link>
        </div>
      </div>
    </div>

    <!-- ─── AUTHENTICATED — Full system menu ─────────────────────────── -->
    <template v-else>
      <!-- Navigation Menu -->
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
          <router-link to="/profile" class="sidebar-nav-item" active-class="active">
            <span class="index text-dim">[05]</span> PROFILE_SETTINGS
          </router-link>
          <router-link to="/digital-twin" class="sidebar-nav-item dt-nav-item" active-class="active">
            <span class="index text-cyan">[06]</span> HOLOGRAPHIC_TWIN
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
            <span class="label">OPERATOR:</span>
            <span class="val text-cyan" style="font-size:8px; max-width:80px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">
              {{ authStore.user?.email || 'N/A' }}
            </span>
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
    </template>

    <!-- Footer status (always visible) -->
    <div class="sidebar-status-block">
      <span class="text-dim text-[8px]">
        {{ authStore.isAuthenticated ? '[ CONSOLE_ACTIVE ]' : '[ CONSOLE_LOCKED ]' }}
      </span>
      <span :class="['blink-dot text-[8px]', authStore.isAuthenticated ? 'text-green' : 'text-orange']">●</span>
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
.role-badge--locked {
  color: var(--color-accent-orange) !important;
  background: rgba(255, 102, 0, 0.15) !important;
  border: 1px solid rgba(255, 102, 0, 0.3);
}

/* AUTH REQUIRED block */
.auth-required-block {
  border: 1px solid rgba(255, 102, 0, 0.3);
  background: rgba(255, 102, 0, 0.04);
}
.auth-msg {
  margin-top: 6px;
  line-height: 1.6;
}
.auth-nav-links {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 8px;
}
.auth-cta {
  color: var(--color-accent-orange) !important;
  border-color: rgba(255, 102, 0, 0.3) !important;
}
.auth-cta:hover {
  background: rgba(255, 102, 0, 0.08) !important;
}
.auth-emergency {
  color: var(--color-accent-red) !important;
}
.auth-emergency:hover {
  background: rgba(255, 51, 51, 0.08) !important;
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

/* Digital Twin nav item — holographic glow */
.dt-nav-item {
  border-color: rgba(0, 229, 255, 0.12) !important;
  background: rgba(0, 229, 255, 0.02);
}
.dt-nav-item:hover,
.dt-nav-item.active {
  background: rgba(0, 229, 255, 0.08) !important;
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.15) inset;
  color: #00e5ff !important;
}
</style>
