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

    <!-- SOS Overlay Modal -->
    <div v-if="sosCountdownActive" class="sos-overlay-modal mono">
      <div class="sos-modal-content terminal-card glow-red border-red p-5 text-center">
        <h1 class="text-red font-bold text-xl mb-4 animate-pulse">[!!! CRITICAL MEDICAL ALERT !!!]</h1>
        <p class="text-dim text-xs mb-4" style="line-height: 1.6;">
          {{ wakeupMessage }}
        </p>
        <div class="countdown-value text-red font-bold text-6xl my-4">
          {{ countdownValue }}
        </div>
        <p class="text-xs text-dim mb-4">
          AUTOMATIC SOS DISPATCH IN {{ countdownValue }} SECONDS.
        </p>
        <div class="flex gap-4 justify-center">
          <button @click="cancelSos" class="cmd-btn cancel-btn px-6 py-2">
            [ ABORT EMERGENCY PROTOCOL ]
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from './stores/auth'
import { useVitalsStore } from './stores/vitals'
import { initWebSocket, disconnectWebSocket } from './services/websocket'
import api from './services/api'
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

// SOS Wakeup countdown logic
const sosCountdownActive = ref(false)
const countdownValue = ref(10)
const wakeupMessage = ref('')
let countdownTimer: any = null

function handleWakeupEvent(e: Event) {
  const detail = (e as CustomEvent).detail
  const speechText = detail.outputDecision || "Phát hiện nhịp tim hoặc oxy máu tụt nguy hiểm. Bạn có ổn không?"
  
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(speechText.replace(/\[.*?\]/g, ''))
    const voices = window.speechSynthesis.getVoices()
    const viVoice = voices.find(v => v.lang.includes('vi') || v.lang.includes('VI'))
    if (viVoice) {
      utterance.voice = viVoice
    }
    window.speechSynthesis.speak(utterance)
  }

  wakeupMessage.value = detail.outputDecision || "Phát hiện nhịp tim hoặc oxy máu tụt nguy hiểm."
  sosCountdownActive.value = true
  countdownValue.value = 10
  
  if (countdownTimer) clearInterval(countdownTimer)
  
  countdownTimer = setInterval(async () => {
    countdownValue.value--
    if (countdownValue.value <= 0) {
      clearInterval(countdownTimer)
      sosCountdownActive.value = false
      try {
        console.warn("[SOS] Countdown finished. Triggering emergency SOS dispatch.")
        await api.post('/emergency/sos')
        alert("EMERGENCY SOS DISPATCHED TO GUARDIAN.")
      } catch (err) {
        console.error("SOS dispatch failed:", err)
      }
    }
  }, 1000)
}

function cancelSos() {
  if (countdownTimer) clearInterval(countdownTimer)
  sosCountdownActive.value = false
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel()
    const u = new SpeechSynthesisUtterance("Khẩn cấp đã hủy.")
    window.speechSynthesis.speak(u)
  }
}

onMounted(() => {
  document.addEventListener('hk07:ai-emergency-wakeup', handleWakeupEvent)
})

onUnmounted(() => {
  document.removeEventListener('hk07:ai-emergency-wakeup', handleWakeupEvent)
})
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

/* SOS Overlay */
.sos-overlay-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 6, 36, 0.95);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}
.sos-modal-content {
  max-width: 500px;
  background: #000000;
  box-shadow: 0 0 30px rgba(255, 51, 51, 0.4);
}
.cancel-btn {
  background: rgba(255, 51, 51, 0.1);
  border-color: #ff3333;
  color: #ff3333;
}
.cancel-btn:hover {
  background: #ff3333;
  color: #000;
  box-shadow: 0 0 15px rgba(255, 51, 51, 0.8);
}
</style>
