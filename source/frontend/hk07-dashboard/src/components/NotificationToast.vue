<template>
  <!-- NotificationToast — Cyber-Cinematic style alert notifications -->
  <Teleport to="body">
    <div class="toast-container" aria-live="polite">
      <TransitionGroup name="toast-slide">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          :class="['toast-item', `toast-${toast.severity}`]"
          role="alert"
          @click="dismiss(toast.id)"
        >
          <!-- Severity indicator bar -->
          <div class="toast-severity-bar"></div>

          <div class="toast-content">
            <div class="toast-header">
              <span class="toast-icon">{{ severityIcon(toast.severity) }}</span>
              <span class="toast-agent hud">[ {{ toast.agent }} ]</span>
              <span class="toast-time mono text-dim">{{ toast.time }}</span>
              <button class="toast-close" @click.stop="dismiss(toast.id)">✕</button>
            </div>
            <div class="toast-message mono">{{ toast.message }}</div>
            <!-- Countdown progress bar -->
            <div class="toast-progress">
              <div class="toast-progress-fill"
                   :style="{ animationDuration: toast.duration + 'ms' }"></div>
            </div>
          </div>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'

export interface Toast {
  id: string
  severity: 'warning' | 'critical' | 'stroke' | 'info'
  agent: string
  message: string
  time: string
  duration: number
}

const toasts = ref<Toast[]>([])
const timers = new Map<string, ReturnType<typeof setTimeout>>()

const MAX_TOASTS = 5

function push(toast: Omit<Toast, 'id' | 'time'>) {
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
  const newToast: Toast = {
    ...toast,
    id,
    time: new Date().toTimeString().slice(0, 8),
  }

  // Hard cap — remove oldest if over limit
  if (toasts.value.length >= MAX_TOASTS) {
    const oldest = toasts.value[0]
    dismiss(oldest.id)
  }

  toasts.value.push(newToast)

  // Auto-dismiss after duration
  const timer = setTimeout(() => dismiss(id), toast.duration)
  timers.set(id, timer)
}

function dismiss(id: string) {
  const idx = toasts.value.findIndex(t => t.id === id)
  if (idx !== -1) toasts.value.splice(idx, 1)
  const timer = timers.get(id)
  if (timer) { clearTimeout(timer); timers.delete(id) }
}

function severityIcon(severity: string) {
  const icons: Record<string, string> = {
    warning: '⚠', critical: '🚨', stroke: '☠', info: 'ℹ'
  }
  return icons[severity] || '●'
}

// ─── WebSocket event listener ─────────────────────────────────────────────────
// The DashboardView WebSocket service dispatches CustomEvents.
// NotificationToast listens globally and fires toasts automatically.
function onVitalAlert(e: Event) {
  const ev = (e as CustomEvent).detail
  if (!ev || ev.alertLevel === 'NORMAL') return

  const severityMap: Record<string, 'warning' | 'critical' | 'stroke' | 'info'> = {
    WARNING: 'warning', CRITICAL: 'critical', STROKE: 'stroke', INFO: 'info'
  }

  push({
    severity: severityMap[ev.alertLevel] || 'info',
    agent: ev.agentType || 'MEDICAL',
    message: ev.message || `Alert: HR=${ev.vitals?.heartRate}bpm SpO₂=${ev.vitals?.spo2}%`,
    duration: ev.alertLevel === 'STROKE' ? 30_000 : ev.alertLevel === 'CRITICAL' ? 15_000 : 8_000,
  })
}

function onSubsumptionAlert(e: Event) {
  const data = (e as CustomEvent).detail
  push({
    severity: 'critical',
    agent: 'SAFETY',
    message: `SUBSUMPTION ACTIVATED: ${data?.trigger || 'UNKNOWN_TRIGGER'} — MOTION INHIBITED`,
    duration: 10_000,
  })
}

function onToast(e: Event) {
  const ev = (e as CustomEvent).detail
  push({
    severity: ev.severity || 'info',
    agent: ev.agent || 'SYSTEM',
    message: ev.message,
    duration: ev.duration || 5000,
  })
}

// Expose push function globally for programmatic use
defineExpose({ push, dismiss })

onMounted(() => {
  document.addEventListener('hk07:vital-alert', onVitalAlert)
  document.addEventListener('hk07:subsumption-alert', onSubsumptionAlert)
  document.addEventListener('hk07:toast', onToast)
})

onUnmounted(() => {
  document.removeEventListener('hk07:vital-alert', onVitalAlert)
  document.removeEventListener('hk07:subsumption-alert', onSubsumptionAlert)
  document.removeEventListener('hk07:toast', onToast)
  timers.forEach(t => clearTimeout(t))
  timers.clear()
})
</script>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 16px;
  right: 16px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-width: 380px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  pointer-events: all;
  cursor: pointer;
  background: #0a0a0a;
  border: 1px solid;
  overflow: hidden;
}

/* Severity colors */
.toast-warning  { border-color: var(--color-accent-orange); }
.toast-critical { border-color: var(--color-accent-red); }
.toast-stroke   { border-color: #FF0000; animation: blink-border 0.5s step-end infinite; }
.toast-info     { border-color: var(--color-border-dim); }

@keyframes blink-border { 50% { border-color: transparent; } }

.toast-severity-bar {
  width: 3px; flex-shrink: 0;
  .toast-warning &  { background: var(--color-accent-orange); }
  .toast-critical & { background: var(--color-accent-red); }
  .toast-stroke &   { background: #FF0000; }
  .toast-info &     { background: var(--color-border-dim); }
}

.toast-content { flex: 1; padding: 8px 10px; min-width: 0; }

.toast-header {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 4px;
}
.toast-icon { font-size: 12px; flex-shrink: 0; }
.toast-agent { font-size: 9px; letter-spacing: 0.15em; color: var(--color-accent-green); flex: 1; }
.toast-time { font-size: 9px; }
.toast-close {
  background: none; border: none; color: var(--color-text-dim);
  cursor: pointer; font-size: 10px; padding: 0 2px;
  &:hover { color: var(--color-accent-green); }
}

.toast-message { font-size: 10px; line-height: 1.5; color: var(--color-text-primary); word-break: break-word; }

.toast-progress {
  height: 2px; background: rgba(255,255,255,0.05); margin-top: 8px; overflow: hidden;
}
.toast-progress-fill {
  height: 100%; width: 100%;
  .toast-warning &  { background: var(--color-accent-orange); }
  .toast-critical & { background: var(--color-accent-red); }
  .toast-stroke &   { background: #FF0000; }
  .toast-info &     { background: var(--color-accent-green); }
  animation: progress-drain linear forwards;
  transform-origin: left;
}
@keyframes progress-drain { from { transform: scaleX(1); } to { transform: scaleX(0); } }

/* TransitionGroup animations */
.toast-slide-enter-active { transition: all 200ms ease; }
.toast-slide-leave-active  { transition: all 150ms ease; }
.toast-slide-enter-from    { transform: translateX(100%); opacity: 0; }
.toast-slide-leave-to      { transform: translateX(100%); opacity: 0; }
</style>
