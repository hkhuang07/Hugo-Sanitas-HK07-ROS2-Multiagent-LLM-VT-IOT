<template>
  <div class="login-shell">
    <!-- Boot Sequence / Terminal Background -->
    <div class="boot-sequence mono text-dim">
      <div v-for="(log, idx) in bootLogs" :key="idx" class="boot-log">
        {{ log }}
      </div>
      <div class="cursor-blink" v-if="!isBooting">_</div>
    </div>

    <!-- Login Modal -->
    <transition name="fade-up">
      <div v-if="showModal" class="login-modal terminal-card corner-reticle">
        <div class="terminal-card-header text-center">
          [ HK-07 SYSTEM // AUTH_UPLINK ]
        </div>
        
        <form @submit.prevent="handleLogin" class="login-form">
          <div class="input-group">
            <label class="mono text-dim">>>> ENTER_OPERATOR_EMAIL:</label>
            <div class="tactical-input-wrapper">
              <span class="prefix">EMAIL></span>
              <input 
                ref="emailInput"
                type="email" 
                v-model="form.email" 
                class="tactical-input" 
                required 
                autocomplete="email"
                spellcheck="false"
              />
            </div>
          </div>
          
          <div class="input-group">
            <label class="mono text-dim">>>> ENTER_SECURITY_PASSPHRASE:</label>
            <div class="tactical-input-wrapper">
              <span class="prefix">PASS></span>
              <input 
                type="password" 
                v-model="form.password" 
                class="tactical-input" 
                required 
                autocomplete="current-password"
              />
            </div>
          </div>

          <div v-if="errorMsg" class="error-msg mono text-red glow-red">
            [ACCESS_DENIED] {{ errorMsg }}
          </div>

          <button type="submit" class="cmd-btn auth-btn" :disabled="loading">
            <span v-if="!loading">>>> EXECUTE_UPLINK</span>
            <span v-else class="loading-spinner">... AUTHENTICATING ...</span>
          </button>
        </form>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import axios from 'axios'

const router = useRouter()
const authStore = useAuthStore()

const form = ref({
  email: 'owner@hk07.local',
  password: 'HK07-Admin-Change-Me!'
})

const loading = ref(false)
const errorMsg = ref('')

// Boot Sequence state
const bootLogs = ref<string[]>([])
const isBooting = ref(true)
const showModal = ref(false)
const emailInput = ref<HTMLInputElement | null>(null)

const bootSequenceLogs = [
  ">>> INITIALIZING HUGO-SANITAS HK-07 BIOS...",
  ">>> MEMORY CHECK: 8192MB OK",
  ">>> CPU KERNEL: ACTIVE",
  ">>> MOUNTING VIRTUAL THREAD POOL... SUCCESS",
  ">>> CONNECTING TO MQTT BROKER (QoS 2 ENABLED)... OK",
  ">>> SUBSUMPTION ARCHITECTURE: TIER 0 ARMED",
  ">>> LANCEDB VECTOR STORE: INDEX LOADED",
  ">>> WARNING: AUTHORIZATION REQUIRED TO ACCESS DASHBOARD",
  ">>> ESTABLISHING SECURE HANDSHAKE..."
]

onMounted(() => {
  // Simulate hacker terminal boot sequence
  let delay = 0
  bootSequenceLogs.forEach((logText, index) => {
    setTimeout(() => {
      bootLogs.value.push(logText)
      if (index === bootSequenceLogs.length - 1) {
        setTimeout(() => {
          isBooting.value = false
          showModal.value = true
          setTimeout(() => emailInput.value?.focus(), 100)
        }, 500)
      }
    }, delay)
    // Randomize boot typing speed
    delay += Math.random() * 150 + 50
  })
})

async function handleLogin() {
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''
  
  try {
    console.log('[LOGIN] Sending credentials to backend...');
    const res = await axios.post('/api/v1/auth/login', form.value)
    console.log('[LOGIN] Response received:', res.data);
    
    if (!res.data || !res.data.data) {
      throw new Error('Invalid API response format (missing data field)');
    }

    const { accessToken, refreshToken, userId, role } = res.data.data
    console.log('[LOGIN] Destructured fields:', { accessToken: !!accessToken, refreshToken: !!refreshToken, userId, role });
    
    const userPayload = {
      id: userId,
      email: form.value.email,
      role: role
    };
    console.log('[LOGIN] Saving to Auth Store with payload:', userPayload);
    
    // Save to in-memory store (Cyber-security requirement: NO LOCALSTORAGE)
    authStore.setAuth(accessToken, refreshToken, userPayload)
    console.log('[LOGIN] Saved to store. Is authenticated:', authStore.isAuthenticated);
    
    // Redirect to dashboard
    console.log('[LOGIN] Triggering router redirect to /');
    await router.push('/')
    console.log('[LOGIN] Router redirect call finished.');
  } catch (e: any) {
    console.error('[LOGIN_ERROR] Execution failed:', e);
    if (e.response && e.response.status === 401) {
      errorMsg.value = "INVALID CREDENTIALS"
    } else {
      errorMsg.value = `BACKEND CONNECTION FAILED (${e.message || 'Unknown Error'})`
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-shell {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  background: var(--color-bg-void);
  position: relative;
  overflow: hidden;
}

.boot-sequence {
  position: absolute;
  top: 16px;
  left: 16px;
  font-size: 11px;
  line-height: 1.6;
  opacity: 0.7;
  pointer-events: none;
}
.cursor-blink { display: inline-block; animation: blink 1s step-end infinite; }
@keyframes blink { 50% { opacity: 0; } }

.login-modal {
  width: 420px;
  padding: 32px;
  background: #000000;
  border-color: var(--color-accent-blue);
  box-shadow: 0 0 20px rgba(0, 82, 255, 0.2);
  z-index: 10;
}

.terminal-card-header {
  font-size: 14px;
  color: var(--color-accent-blue);
  border-bottom: 1px solid var(--color-border-dim);
  padding-bottom: 12px;
  margin-bottom: 24px;
  letter-spacing: 0.2em;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.input-group label {
  display: block;
  font-size: 10px;
  margin-bottom: 6px;
}

.tactical-input-wrapper {
  display: flex;
  align-items: center;
  border: 1px solid var(--color-border-dim);
  background: #0a0a0a;
  transition: border-color 0.3s;
}
.tactical-input-wrapper:focus-within {
  border-color: var(--color-accent-blue);
  box-shadow: 0 0 8px rgba(0, 82, 255, 0.4);
}

.prefix {
  padding: 8px 10px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-accent-blue);
  background: rgba(0, 82, 255, 0.1);
  border-right: 1px solid var(--color-border-dim);
}

.tactical-input {
  flex: 1;
  background: transparent;
  border: none;
  padding: 8px 12px;
  color: var(--color-text-primary);
  font-family: var(--font-mono);
  font-size: 12px;
  outline: none;
}

.error-msg {
  font-size: 11px;
  text-align: center;
}

.auth-btn {
  margin-top: 10px;
  width: 100%;
  padding: 12px;
  font-size: 12px;
  background: rgba(0, 82, 255, 0.1);
  border-color: var(--color-accent-blue);
}
.auth-btn:hover:not(:disabled) {
  background: var(--color-accent-blue);
  color: #000;
  box-shadow: 0 0 15px rgba(0, 82, 255, 0.6);
}
.auth-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Transitions */
.fade-up-enter-active { transition: all 0.5s ease-out; }
.fade-up-enter-from { opacity: 0; transform: translateY(20px); }
.fade-up-enter-to { opacity: 1; transform: translateY(0); }
</style>
