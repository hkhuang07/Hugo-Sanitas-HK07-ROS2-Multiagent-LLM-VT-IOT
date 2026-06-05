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
      <div v-if="showModal" class="login-modal terminal-card corner-reticle" :style="{ width: activeTab === 'register' ? '600px' : '440px' }">
        <div class="terminal-card-header text-center">
          [ HK-07 SYSTEM // AUTH_UPLINK ]
        </div>

        <!-- Emergency Override Button -->
        <div class="emergency-container" v-if="activeTab !== 'register' || registerStep !== 4">
          <router-link to="/emergency" class="cmd-btn emergency-btn mono text-red glow-red">
            >>> EMERGENCY ACCESS &lt;&lt;&lt;
          </router-link>
        </div>

        <!-- Tab Switches -->
        <div class="tabs-header mono" v-if="activeTab !== 'forgot' && (activeTab !== 'register' || registerStep !== 4)">
          <button 
            type="button" 
            class="tab-btn" 
            :class="{ active: activeTab === 'operator' }"
            @click="activeTab = 'operator'"
          >
            [ OPERATOR LOGIN ]
          </button>
          <button 
            type="button" 
            class="tab-btn" 
            :class="{ active: activeTab === 'pairing' }"
            @click="activeTab = 'pairing'"
          >
            [ DEVICE PAIRING ]
          </button>
          <button 
            type="button" 
            class="tab-btn" 
            :class="{ active: activeTab === 'register' }"
            @click="activeTab = 'register'; registerStep = 1"
          >
            [ ONBOARDING ]
          </button>
        </div>
        
        <!-- Tab Content 1: Operator Login -->
        <form v-if="activeTab === 'operator'" @submit.prevent="handleLogin" class="login-form">
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
            <div class="text-right mt-1">
              <a href="#" @click.prevent="activeTab = 'forgot'" class="forgot-link mono text-xs text-dim">
                [ FORGOT PASSPHRASE? ]
              </a>
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

        <!-- Tab Content 2: Device Pairing -->
        <div v-else-if="activeTab === 'pairing'" class="pairing-mockup text-center mono">
          <div class="pairing-scanner">
            <div class="scan-line"></div>
            <span class="text-dim" v-if="!pinLoading">WAITING FOR DEVICE SCAN...</span>
            <span class="text-cyan" v-else>>>> AUTHENTICATING PIN...</span>
          </div>

          <form @submit.prevent="handlePinLogin" class="login-form" style="margin-top: 20px; text-align: left;">
            <div class="input-group">
              <label class="text-dim">>> OR ENTER DEVICE PIN CODE: <span class="text-cyan">PIN> {{ pinCode || 'xxx-xxx' }}</span></label>
              <div class="tactical-input-wrapper" :class="{ 'input-active': pinCode.length > 0 }">
                <span class="prefix">PIN&gt;</span>
                <input
                  ref="pinInput"
                  type="text"
                  v-model="pinCode"
                  class="tactical-input"
                  placeholder="Enter device PIN (e.g. 0J6M-LZNJ)"
                  maxlength="9"
                  autocomplete="off"
                  spellcheck="false"
                  @input="onPinInput"
                />
              </div>
              <div class="text-dim text-small mt-1" style="font-size: 9px; text-align: right;">
                FORMAT: XXXX-XXXX (8 chars + dash) — AUTO-SUBMIT ON COMPLETE
              </div>
            </div>

            <div v-if="pinError" class="error-msg mono text-red glow-red">
              [PIN_AUTH_FAILED] {{ pinError }}
            </div>
            <div v-if="pinSuccess" class="error-msg mono text-green" style="color: #00FF66;">
              [PIN_VERIFIED] {{ pinSuccess }}
            </div>

            <button
              type="submit"
              class="cmd-btn auth-btn"
              :disabled="pinLoading || pinCode.replace('-','').length < 8"
            >
              <span v-if="!pinLoading">>> EXECUTE_PIN_UPLINK</span>
              <span v-else class="loading-spinner">... VERIFYING PIN ...</span>
            </button>
          </form>

          <div class="text-dim text-small" style="margin-top: 12px; font-size: 10px;">
            Place NFC Card / Band near the reader OR enter your 8-character device PIN above.
          </div>
        </div>

        <!-- Tab Content 3: Onboarding Wizard (Multi-step) -->
        <div v-else-if="activeTab === 'register'" class="onboarding-wizard mono">
          <!-- Steps Navigation Status -->
          <div class="step-indicator text-xs text-dim mb-3">
            STEP {{ registerStep }} / 4: 
            <span v-if="registerStep === 1" class="text-cyan">ACCOUNT SETUP</span>
            <span v-else-if="registerStep === 2" class="text-cyan">MEDICAL BASELINE</span>
            <span v-else-if="registerStep === 3" class="text-cyan">EMERGENCY CONTACTS</span>
            <span v-else-if="registerStep === 4" class="text-success glow-green">RECOVERY DATA GENERATION</span>
          </div>

          <!-- Step 1: Account Setup -->
          <form v-if="registerStep === 1" @submit.prevent="registerStep = 2" class="login-form">
            <div class="input-group">
              <label class="text-dim">>>> ASSIGN_DISPLAY_NAME:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">NAME></span>
                <input v-model="registerForm.displayName" type="text" class="tactical-input" required />
              </div>
            </div>
            <div class="input-group">
              <label class="text-dim">>>> ASSIGN_OPERATOR_EMAIL:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">EMAIL></span>
                <input v-model="registerForm.email" type="email" class="tactical-input" required />
              </div>
            </div>
            <div class="input-group">
              <label class="text-dim">>>> ASSIGN_SECURITY_PASSPHRASE:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">PASS></span>
                <input v-model="registerForm.password" type="password" class="tactical-input" required />
              </div>
            </div>
            <div class="input-group">
              <label class="text-dim">>>> CONFIRM_SECURITY_PASSPHRASE:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">PASS></span>
                <input v-model="registerForm.confirmPassword" type="password" class="tactical-input" required />
              </div>
            </div>
            <div v-if="registerError" class="error-msg text-red">{{ registerError }}</div>
            <button type="submit" class="cmd-btn mt-3">>>> CONTINUE_TO_MEDICAL_BASELINE</button>
          </form>

          <!-- Step 2: Medical Baseline -->
          <form v-else-if="registerStep === 2" @submit.prevent="registerStep = 3" class="login-form">
            <div class="form-row-2">
              <div class="input-group">
                <label class="text-dim">>>> FULL_NAME:</label>
                <div class="tactical-input-wrapper">
                  <input v-model="registerForm.fullName" type="text" class="tactical-input" required />
                </div>
              </div>
              <div class="input-group">
                <label class="text-dim">>>> AGE:</label>
                <div class="tactical-input-wrapper">
                  <input v-model.number="registerForm.age" type="number" class="tactical-input" required />
                </div>
              </div>
            </div>
            <div class="form-row-3">
              <div class="input-group">
                <label class="text-dim">>>> GENDER:</label>
                <div class="tactical-input-wrapper">
                  <select v-model="registerForm.gender" class="tactical-input select-input" required>
                    <option value="MALE">MALE (Nam)</option>
                    <option value="FEMALE">FEMALE (Nữ)</option>
                    <option value="OTHER">OTHER (Khác)</option>
                  </select>
                </div>
              </div>
              <div class="input-group">
                <label class="text-dim">>>> HEIGHT (CM):</label>
                <div class="tactical-input-wrapper">
                  <input v-model.number="registerForm.height" type="number" step="0.1" class="tactical-input" required />
                </div>
              </div>
              <div class="input-group">
                <label class="text-dim">>>> WEIGHT (KG):</label>
                <div class="tactical-input-wrapper">
                  <input v-model.number="registerForm.weight" type="number" step="0.1" class="tactical-input" required />
                </div>
              </div>
            </div>
            <div class="input-group">
              <label class="text-dim">>>> BLOOD_TYPE:</label>
              <div class="tactical-input-wrapper">
                <select v-model="registerForm.bloodType" class="tactical-input select-input" required>
                  <option value="A+">A+</option>
                  <option value="A-">A-</option>
                  <option value="B+">B+</option>
                  <option value="B-">B-</option>
                  <option value="O+">O+</option>
                  <option value="O-">O-</option>
                  <option value="AB+">AB+</option>
                  <option value="AB-">AB-</option>
                </select>
              </div>
            </div>
            <div class="input-group">
              <label class="text-dim">>>> CHRONIC_MEDICAL_HISTORY:</label>
              <textarea v-model="registerForm.medicalHistory" class="tactical-textarea" placeholder="Bệnh nền, tim mạch, huyết áp..."></textarea>
            </div>
            <div class="input-group">
              <label class="text-dim">>>> ALLERGIES:</label>
              <textarea v-model="registerForm.allergies" class="tactical-textarea" placeholder="Thuốc hoặc hóa chất dị ứng..."></textarea>
            </div>
            <div class="wizard-actions mt-3">
              <button type="button" class="cmd-btn" @click="registerStep = 1">[&lt;&lt; BACK]</button>
              <button type="submit" class="cmd-btn">>>> CONTINUE_TO_CONTACTS</button>
            </div>
          </form>

          <!-- Step 3: Emergency Contacts -->
          <form v-else-if="registerStep === 3" @submit.prevent="handleRegister" class="login-form">
            <div class="input-group">
              <label class="text-dim">>>> EMERGENCY_CONTACT_NAME:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">NAME></span>
                <input v-model="registerForm.emergencyContactName" type="text" class="tactical-input" required />
              </div>
            </div>
            <div class="input-group mt-2">
              <label class="text-dim">>>> EMERGENCY_CONTACT_PHONE:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">PHONE></span>
                <input v-model="registerForm.emergencyContactPhone" type="text" class="tactical-input" required />
              </div>
            </div>

            <div v-if="registerError" class="error-msg text-red mt-2">{{ registerError }}</div>

            <div class="wizard-actions mt-4">
              <button type="button" class="cmd-btn" @click="registerStep = 2" :disabled="loading">[&lt;&lt; BACK]</button>
              <button type="submit" class="cmd-btn" :disabled="loading">
                <span v-if="!loading">>>> EXECUTE_ONBOARDING</span>
                <span v-else>... SAVING PATIENT baseline ...</span>
              </button>
            </div>
          </form>

          <!-- Step 4: Recovery Codes Display -->
          <div v-else-if="registerStep === 4" class="recovery-codes-display text-center">
            <div class="alert-box border border-[#ff3333] p-3 text-xs text-red bg-red-opacity mb-3">
              [CRITICAL_SECURITY_ALERT] VUI LÒNG LƯU LẠI 5 MÃ KHÔI PHỤC DƯỚI ĐÂY. 
              CHÚNG LÀ CƠ HỘI DUY NHẤT ĐỂ RESET MẬT KHẨU KHI BỊ MẤT.
            </div>

            <div class="codes-container font-mono text-cyan p-3 bg-black border border-[#0052ff]/30 text-lg mb-3">
              <div v-for="(code, idx) in generatedRecoveryCodes" :key="idx" class="code-line">
                [{{ idx + 1 }}] {{ code }}
              </div>
            </div>

            <button type="button" class="cmd-btn w-full mb-3" @click="copyRecoveryCodes">
              >>> COPY_CODES_TO_CLIPBOARD
            </button>

            <div class="checkbox-group flex items-center justify-center gap-2 mb-3">
              <input type="checkbox" id="savedCodes" v-model="recordedCodesCheckbox" />
              <label for="savedCodes" class="text-xs text-dim cursor-pointer">Tôi đã lưu lại 5 mã khôi phục an toàn.</label>
            </div>

            <button 
              type="button" 
              class="cmd-btn w-full active-success" 
              :disabled="!recordedCodesCheckbox"
              @click="completeOnboarding"
            >
              >>> COMPLETE_ONBOARDING_UPLINK
            </button>
          </div>
        </div>

        <!-- Forgot Password Flow -->
        <div v-else-if="activeTab === 'forgot'" class="forgot-passphrase-flow mono">
          <div class="terminal-card-header text-cyan mb-3">
            [ SECURITY_PASSPHRASE_RECOVERY ]
          </div>
          
          <form @submit.prevent="handleForgotPassword" class="login-form">
            <div class="input-group">
              <label class="text-dim">>>> OPERATOR_EMAIL:</label>
              <div class="tactical-input-wrapper">
                <input v-model="forgotForm.email" type="email" class="tactical-input" required />
              </div>
            </div>
            <div class="input-group">
              <label class="text-dim">>>> SECURITY_RECOVERY_CODE:</label>
              <div class="tactical-input-wrapper">
                <input v-model="forgotForm.recoveryCode" type="text" maxlength="8" class="tactical-input" placeholder="8-char code" required />
              </div>
            </div>
            <div class="input-group">
              <label class="text-dim">>>> NEW_PASSPHRASE:</label>
              <div class="tactical-input-wrapper">
                <input v-model="forgotForm.newPassword" type="password" class="tactical-input" required />
              </div>
            </div>
            <div class="input-group">
              <label class="text-dim">>>> CONFIRM_NEW_PASSPHRASE:</label>
              <div class="tactical-input-wrapper">
                <input v-model="forgotForm.confirmPassword" type="password" class="tactical-input" required />
              </div>
            </div>

            <div v-if="forgotMessage" :class="['error-msg text-xs mt-2', forgotStatus]">
              {{ forgotMessage }}
            </div>

            <div class="wizard-actions mt-4">
              <button type="button" class="cmd-btn" @click="activeTab = 'operator'">[&lt;&lt; RETURN_TO_LOGIN]</button>
              <button type="submit" class="cmd-btn" :disabled="loading">
                <span v-if="!loading">>>> RESET_PASSPHRASE</span>
                <span v-else>... VERIFYING AND RESETTING ...</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import axios from 'axios'

const router = useRouter()
const authStore = useAuthStore()

const activeTab = ref<'operator' | 'pairing' | 'register' | 'forgot'>('operator')

// ── PIN Login State ────────────────────────────────────────────────────────────
const pinCode   = ref('')
const pinError  = ref('')
const pinSuccess = ref('')
const pinLoading = ref(false)
const pinInput  = ref<HTMLInputElement | null>(null)

const form = ref({
  email: 'owner@hk07.local',
  password: 'HK07-Admin-Change-Me!'
})

const loading = ref(false)
const errorMsg = ref('')

// Onboarding Wizard registration state
const registerStep = ref(1)
const registerError = ref('')
const generatedRecoveryCodes = ref<string[]>([])
const recordedCodesCheckbox = ref(false)
const registerForm = ref({
  displayName: '',
  email: '',
  password: '',
  confirmPassword: '',
  fullName: '',
  age: undefined as number | undefined,
  gender: 'MALE',
  height: undefined as number | undefined,
  weight: undefined as number | undefined,
  bloodType: 'O+',
  medicalHistory: '',
  allergies: '',
  emergencyContactName: '',
  emergencyContactPhone: ''
})

// Forgot password state
const forgotForm = ref({
  email: '',
  recoveryCode: '',
  newPassword: '',
  confirmPassword: ''
})
const forgotMessage = ref('')
const forgotStatus = ref('')

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
    delay += Math.random() * 150 + 50
  })
})

async function handleLogin() {
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''
  
  try {
    const res = await axios.post('/api/v1/auth/login', form.value)
    if (!res.data || !res.data.data) {
      throw new Error('Invalid API response format')
    }

    const { accessToken, userId, role } = res.data.data
    const userPayload = { id: userId, email: form.value.email, role: role }
    authStore.setAuth(accessToken, userPayload)
    await router.push('/')
  } catch (e: any) {
    console.error('[LOGIN_ERROR] Execution failed:', e)
    if (e.response && e.response.status === 401) {
      errorMsg.value = "INVALID CREDENTIALS"
    } else {
      errorMsg.value = `BACKEND CONNECTION FAILED (${e.message || 'Unknown Error'})`
    }
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (registerForm.value.password !== registerForm.value.confirmPassword) {
    registerError.value = 'Mật khẩu xác nhận không khớp.'
    return
  }

  loading.value = true
  registerError.value = ''

  try {
    const res = await axios.post('/api/v1/auth/register', registerForm.value)
    if (res.data && res.data.data) {
      generatedRecoveryCodes.value = res.data.data.recoveryCodes || []
      // Temporarily store credentials for auto-login
      form.value.email = registerForm.value.email
      form.value.password = registerForm.value.password
      
      // Proceed to the recovery codes screen
      registerStep.value = 4
    }
  } catch (e: any) {
    console.error('[REGISTER_ERROR]', e)
    registerError.value = e.response?.data?.message || 'Không thể đăng ký tài khoản mới.'
  } finally {
    loading.value = false
  }
}

function copyRecoveryCodes() {
  const codesText = generatedRecoveryCodes.value.map((c, i) => `[Code ${i+1}] ${c}`).join('\n')
  navigator.clipboard.writeText(codesText)
  alert('Đã sao chép 5 mã khôi phục vào clipboard!')
}

async function completeOnboarding() {
  // Auto login using the newly onboarded account
  await handleLogin()
  
  if (!authStore.isAuthenticated) {
    activeTab.value = 'operator'
  }
}

async function handleForgotPassword() {
  if (forgotForm.value.newPassword !== forgotForm.value.confirmPassword) {
    forgotStatus.value = 'text-red'
    forgotMessage.value = 'Mật khẩu mới xác nhận không khớp.'
    return
  }

  loading.value = true
  forgotStatus.value = ''
  forgotMessage.value = ''

  try {
    await axios.post('/api/v1/auth/reset-password', {
      email: forgotForm.value.email,
      recoveryCode: forgotForm.value.recoveryCode,
      newPassword: forgotForm.value.newPassword
    })
    
    forgotStatus.value = 'text-success'
    forgotMessage.value = 'Đặt lại mật khẩu thành công! Quay lại đăng nhập.'
    setTimeout(() => {
      activeTab.value = 'operator'
      form.value.email = forgotForm.value.email
      form.value.password = forgotForm.value.newPassword
    }, 1500)
  } catch (e: any) {
    console.error('[FORGOT_PASSWORD_ERROR]', e)
    forgotStatus.value = 'text-red'
    forgotMessage.value = e.response?.data?.message || 'Khôi phục mật khẩu thất bại. Kiểm tra lại mã khôi phục.'
  } finally {
    loading.value = false
  }
}

// ── PIN Login ─────────────────────────────────────────────────────────────────
function onPinInput() {
  // Auto-format: insert dash after 4 chars
  let raw = pinCode.value.replace(/-/g, '').toUpperCase().slice(0, 8)
  if (raw.length > 4) {
    pinCode.value = raw.slice(0, 4) + '-' + raw.slice(4)
  } else {
    pinCode.value = raw
  }
  // Auto-submit when fully typed (8 alphanumeric = 9 with dash)
  if (pinCode.value.replace('-', '').length === 8) {
    handlePinLogin()
  }
}

async function handlePinLogin() {
  const rawPin = pinCode.value.replace('-', '').trim()
  if (rawPin.length < 8) {
    pinError.value = 'PIN must be 8 characters (format: XXXX-XXXX)'
    return
  }
  if (pinLoading.value) return

  pinLoading.value = true
  pinError.value   = ''
  pinSuccess.value = ''

  try {
    // POST to backend PIN auth endpoint
    // Falls back to email/password login using PIN as a device token
    const res = await axios.post('/api/v1/auth/pin-login', { pin: rawPin })

    if (!res.data || !res.data.data) {
      throw new Error('Invalid API response format')
    }

    const { accessToken, userId, role } = res.data.data
    const userPayload = { id: userId, email: `device-${rawPin}@hk07.local`, role: role }
    authStore.setAuth(accessToken, userPayload)
    pinSuccess.value = 'DEVICE AUTHENTICATED — REDIRECTING...'
    setTimeout(() => router.push('/'), 800)

  } catch (e: any) {
    console.error('[PIN_LOGIN_ERROR]', e)
    if (e.response?.status === 401 || e.response?.status === 404) {
      pinError.value = 'INVALID DEVICE PIN — AUTHENTICATION FAILED'
    } else if (e.response?.status === 405 || e.message?.includes('404')) {
      // Endpoint not yet implemented — inform user clearly
      pinError.value = 'PIN_AUTH ENDPOINT NOT DEPLOYED ON SERVER YET'
    } else {
      pinError.value = `CONNECTION FAILED: ${e.message || 'Unknown Error'}`
    }
  } finally {
    pinLoading.value = false
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
  padding: 32px;
  background: #000000;
  border: 1px solid var(--color-border);
  box-shadow: 0 0 20px rgba(0, 82, 255, 0.2);
  z-index: 10;
  transition: width 0.3s ease;
}

.terminal-card-header {
  font-size: 14px;
  color: var(--color-border-blue);
  border-bottom: 1px solid var(--color-border-dim);
  padding-bottom: 12px;
  margin-bottom: 20px;
  letter-spacing: 0.2em;
}

.emergency-container {
  margin-bottom: 20px;
}

.emergency-btn {
  display: block;
  text-align: center;
  padding: 12px;
  font-size: 12px;
  background: rgba(255, 51, 51, 0.1);
  border: 1px solid #ff3333;
  color: #ff3333;
  text-decoration: none;
  font-weight: bold;
  animation: pulse-border 2s infinite alternate;
}
.emergency-btn:hover {
  background: #ff3333;
  color: #000;
  box-shadow: 0 0 15px rgba(255, 51, 51, 0.6);
}

@keyframes pulse-border {
  0% { box-shadow: 0 0 2px rgba(255, 51, 51, 0.2); }
  100% { box-shadow: 0 0 10px rgba(255, 51, 51, 0.5); }
}

.tabs-header {
  display: flex;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--color-border-dim);
}

.tab-btn {
  flex: 1;
  background: transparent;
  border: none;
  padding: 10px;
  color: var(--color-text-dim);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.3s;
  white-space: nowrap;
}
.tab-btn:hover {
  color: var(--color-text-primary);
}
.tab-btn.active {
  color: var(--color-border-blue);
  border-bottom: 2px solid var(--color-border-blue);
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
  background: #000000;
  transition: border-color 0.3s;
}
.tactical-input-wrapper:focus-within {
  border-color: var(--color-border);
  box-shadow: 0 0 8px rgba(0, 82, 255, 0.4);
}
.tactical-input-wrapper.input-active {
  border-color: var(--color-border-blue);
  box-shadow: 0 0 6px rgba(0, 82, 255, 0.3);
}

.prefix {
  padding: 8px 10px;
  font-family: var(--font-data);
  font-size: 11px;
  color: var(--color-border-blue);
  background: rgba(0, 82, 255, 0.1);
  border-right: 1px solid var(--color-border-dim);
}

.tactical-input {
  flex: 1;
  background: transparent;
  border: none;
  padding: 8px 12px;
  color: var(--color-text-primary);
  font-family: var(--font-data);
  font-size: 12px;
  outline: none;
}

.tactical-textarea {
  background: #000000;
  border: 1px solid var(--color-border-dim);
  color: var(--color-text-primary);
  font-family: var(--font-data);
  font-size: 11px;
  padding: 10px;
  height: 60px;
  resize: vertical;
  outline: none;
}
.tactical-textarea:focus {
  border-color: var(--color-border);
}

.select-input {
  color: var(--color-text-primary);
  background: #000000;
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
  border-color: var(--color-border);
}
.auth-btn:hover:not(:disabled) {
  background: var(--color-border);
  color: #000;
  box-shadow: 0 0 15px rgba(0, 82, 255, 0.6);
}
.auth-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pairing-mockup {
  padding: 20px 0 10px;
}

.pairing-scanner {
  height: 120px;
  border: 1px dashed var(--color-border-dim);
  background: rgba(0, 82, 255, 0.02);
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  font-size: 11px;
}

.scan-line {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 2px;
  background: var(--color-border-blue);
  box-shadow: 0 0 8px var(--color-border-blue);
  animation: scan 3s infinite linear;
}

@keyframes scan {
  0% { top: 0; }
  50% { top: 100%; }
  100% { top: 0; }
}

.text-small {
  font-size: 10px;
  line-height: 1.5;
}

.wizard-actions {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.wizard-actions .cmd-btn {
  flex: 1;
}

.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.form-row-3 {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
}

.forgot-link {
  text-decoration: underline;
  cursor: pointer;
}
.forgot-link:hover {
  color: var(--color-border-blue);
}

.alert-box {
  background: rgba(255, 51, 51, 0.1);
  line-height: 1.5;
}

.bg-red-opacity {
  background-color: rgba(255, 51, 51, 0.05);
}

.code-line {
  letter-spacing: 0.1em;
  padding: 4px 0;
}

.active-success {
  border-color: #00FF66;
  color: #00FF66;
}
.active-success:hover:not(:disabled) {
  background: #00FF66;
  color: #000;
  box-shadow: 0 0 15px rgba(0, 255, 102, 0.6);
}

/* Transitions */
.fade-up-enter-active { transition: all 0.5s ease-out; }
.fade-up-enter-from { opacity: 0; transform: translateY(20px); }
.fade-up-enter-to { opacity: 1; transform: translateY(0); }
</style>
