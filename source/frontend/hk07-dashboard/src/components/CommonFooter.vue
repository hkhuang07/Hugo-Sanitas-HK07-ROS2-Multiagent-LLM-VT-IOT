<template>
  <footer class="hud-footer">
    <div class="footer-left">
      <span class="system-revision">HK-07 COMMAND CENTER // REV. 1.0.0-ALPHA // BUILD_742</span>
      <span class="text-dim"> | </span>
      <span class="license-info">LICENSE_ID: HK07-AUTH-SECURE-99</span>
    </div>
    
    <div class="footer-center">
      <span class="hardware-spec">SYS_MEM: LOW_PRESSURE_OK</span>
      <span class="text-dim"> | </span>
      <span class="telemetry-hz">TELEMETRY: 60Hz</span>
      <span class="text-dim"> | </span>
      <span class="latency-sla" :class="latencyClass">SLA: {{ latencyText }}</span>
    </div>
    
    <div class="footer-right">
      <span class="copyright-info">© 2026 HUGO SANITAS HUANG LAB. ALL RIGHTS RESERVED.</span>
    </div>
  </footer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAgentsStore } from '../stores/agents'

const agentsStore = useAgentsStore()

const latestSafetyEvent = computed(() => 
  agentsStore.events.find(e => e.agentType === 'SAFETY')
)

const latencyText = computed(() => {
  if (!latestSafetyEvent.value) return '0.00ms (TARGET < 5.0ms)'
  return `${latestSafetyEvent.value.latencyMs.toFixed(2)}ms`
})

const latencyClass = computed(() => {
  if (!latestSafetyEvent.value) return 'text-green'
  return latestSafetyEvent.value.latencyMs < 5.0 ? 'text-green' : 'text-red'
})
</script>

<style scoped>
.hud-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  background: var(--color-bg-void);
  border-top: 1px solid var(--color-border-dim);
  font-family: var(--font-hud);
  font-size: 8px;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--color-text-dim);
  flex-shrink: 0;
  user-select: none;
  flex-wrap: nowrap;
  overflow: hidden;
}
.footer-left, .footer-center, .footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  flex-shrink: 0;
  white-space: nowrap;
}
.system-revision {
  color: var(--color-accent-green);
}
.license-info {
  color: var(--color-accent-cyan);
}
.hardware-spec {
  color: var(--color-accent-orange);
}
.telemetry-hz {
  color: var(--color-accent-green);
}
.copyright-info {
  color: var(--color-text-dim);
}
</style>
