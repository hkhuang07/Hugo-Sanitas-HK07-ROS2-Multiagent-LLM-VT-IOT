<template>
  <div class="profile-settings-canvas">
    <div class="hud-status-strip mono text-dim mb-4">
      [ STATION_ID: {{ authStore.user?.email || 'OWNER_MODE' }} ] >>> [ SECTION: PROFILE_SECURITY_MANAGEMENT ]
    </div>

    <div class="settings-grid">
      <!-- Left Column: Medical Profile Baseline (70%) -->
      <section class="settings-main terminal-card corner-reticle">
        <div class="terminal-card-header">[ MEDICAL_BASELINE_PROFILE ]</div>
        
        <div v-if="profileLoading" class="loading-overlay mono text-center">
          <span class="pulse-text text-cyan">>>> DOWNLOADING HEALTH RECORDS FROM STATION DATABASE...</span>
        </div>

        <form v-else @submit.prevent="saveProfile" class="tactical-form">
          <div class="form-row-2">
            <div class="input-group">
              <label class="mono text-dim">>>> PATIENT_FULL_NAME:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">NAME></span>
                <input v-model="profileForm.fullName" type="text" class="tactical-input" placeholder="e.g. Nguyễn Văn A" />
              </div>
            </div>
            <div class="input-group">
              <label class="mono text-dim">>>> PATIENT_AGE:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">AGE></span>
                <input v-model.number="profileForm.age" type="number" class="tactical-input" placeholder="e.g. 24" />
              </div>
            </div>
          </div>

          <div class="form-row-3">
            <div class="input-group">
              <label class="mono text-dim">>>> PATIENT_GENDER:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">GEN></span>
                <select v-model="profileForm.gender" class="tactical-input select-input">
                  <option value="MALE">MALE (Nam)</option>
                  <option value="FEMALE">FEMALE (Nữ)</option>
                  <option value="OTHER">OTHER (Khác)</option>
                </select>
              </div>
            </div>
            <div class="input-group">
              <label class="mono text-dim">>>> HEIGHT (CM):</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">HGT></span>
                <input v-model.number="profileForm.height" type="number" step="0.1" class="tactical-input" placeholder="175" />
              </div>
            </div>
            <div class="input-group">
              <label class="mono text-dim">>>> WEIGHT (KG):</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">WGT></span>
                <input v-model.number="profileForm.weight" type="number" step="0.1" class="tactical-input" placeholder="70" />
              </div>
            </div>
          </div>

          <div class="form-row-1">
            <div class="input-group">
              <label class="mono text-dim">>>> BLOOD_TYPE:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">BLOOD></span>
                <select v-model="profileForm.bloodType" class="tactical-input select-input">
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
          </div>

          <div class="input-group">
            <label class="mono text-dim">>>> CHRONIC_DISEASE_HISTORY (Bệnh nền / Tiền sử bệnh lý):</label>
            <textarea v-model="profileForm.medicalHistory" class="tactical-textarea" placeholder="Nhập tiền sử bệnh lý (tim mạch, huyết áp, tiểu đường...). Nếu không có, điền 'None'"></textarea>
          </div>

          <div class="input-group">
            <label class="mono text-dim">>>> KNOWN_ALLERGIES (Dị ứng):</label>
            <textarea v-model="profileForm.allergies" class="tactical-textarea" placeholder="Nhập các chất/thuốc bị dị ứng. Nếu không có, điền 'None'"></textarea>
          </div>

          <div class="form-row-2">
            <div class="input-group">
              <label class="mono text-dim">>>> EMERGENCY_CONTACT_NAME:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">CONTACT></span>
                <input v-model="profileForm.emergencyContactName" type="text" class="tactical-input" placeholder="Người liên hệ khẩn cấp" />
              </div>
            </div>
            <div class="input-group">
              <label class="mono text-dim">>>> EMERGENCY_CONTACT_PHONE:</label>
              <div class="tactical-input-wrapper">
                <span class="prefix">PHONE></span>
                <input v-model="profileForm.emergencyContactPhone" type="text" class="tactical-input" placeholder="Số điện thoại liên hệ khẩn cấp" />
              </div>
            </div>
          </div>

          <div v-if="profileMessage" :class="['message-log mono text-xs mt-2', profileStatus]">
            [{{ profileStatus === 'text-success' ? 'SYNC_SUCCESS' : 'SYNC_FAILED' }}] {{ profileMessage }}
          </div>

          <div class="form-actions mt-4">
            <button type="submit" class="cmd-btn" :disabled="savingProfile">
              <span v-if="!savingProfile">>>> SAVE_AND_SYNC_WITH_AI</span>
              <span v-else>... SYNCHRONIZING LANCEDb VECTORS ...</span>
            </button>
          </div>
        </form>
      </section>

      <!-- Right Column: Passphrase Reset & Info (30%) -->
      <aside class="settings-sidebar">
        <!-- Change Password Card -->
        <div class="terminal-card mb-4">
          <div class="terminal-card-header">[ UPLINK_AUTHENTICATION ]</div>
          <form @submit.prevent="changePassword" class="tactical-form">
            <div class="input-group">
              <label class="mono text-dim">>>> CURRENT_PASSPHRASE:</label>
              <div class="tactical-input-wrapper">
                <input v-model="securityForm.oldPassword" type="password" class="tactical-input" required />
              </div>
            </div>
            <div class="input-group mt-2">
              <label class="mono text-dim">>>> NEW_PASSPHRASE:</label>
              <div class="tactical-input-wrapper">
                <input v-model="securityForm.newPassword" type="password" class="tactical-input" required />
              </div>
            </div>
            <div class="input-group mt-2">
              <label class="mono text-dim">>>> CONFIRM_NEW_PASSPHRASE:</label>
              <div class="tactical-input-wrapper">
                <input v-model="securityForm.confirmPassword" type="password" class="tactical-input" required />
              </div>
            </div>

            <div v-if="securityMessage" :class="['message-log mono text-xs mt-2', securityStatus]">
              [{{ securityStatus === 'text-success' ? 'MUTATION_SUCCESS' : 'MUTATION_FAILED' }}] {{ securityMessage }}
            </div>

            <button type="submit" class="cmd-btn mt-4 w-full" :disabled="changingPassword">
              <span v-if="!changingPassword">>>> MUTATE_PASSPHRASE</span>
              <span v-else>... COMMITTING HASH TO DATABASE ...</span>
            </button>
          </form>
        </div>

        <!-- Security Policy Warning Card -->
        <div class="terminal-card">
          <div class="terminal-card-header">[ HEALTH_POLICY_COMPLIANCE ]</div>
          <div class="policy-details text-dim text-xs mono">
            <p>1. Hồ sơ y tế này được sử dụng làm baseline siêu ngữ cảnh cho Medical và Empathetic Agent của HK-07.</p>
            <p class="mt-2 text-cyan">2. Mọi chỉnh sửa sẽ tự động đồng bộ hóa sang LanceDB vector store của AI sau 1.5 giây thông qua Webhook nội bộ.</p>
            <p class="mt-2">3. Trong trường hợp khẩn cấp, robot Hugo sẽ tự động gọi/gửi SMS tới Emergency Contact đã cấu hình phía dưới.</p>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import api from '../services/api'

const authStore = useAuthStore()

// Profile State
const profileLoading = ref(true)
const savingProfile = ref(false)
const profileStatus = ref('')
const profileMessage = ref('')

const profileForm = ref({
  fullName: '',
  age: 0,
  gender: 'MALE',
  height: 0.0,
  weight: 0.0,
  bloodType: 'O+',
  medicalHistory: '',
  allergies: '',
  emergencyContactName: '',
  emergencyContactPhone: ''
})

// Security State
const changingPassword = ref(false)
const securityStatus = ref('')
const securityMessage = ref('')

const securityForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

async function fetchProfile() {
  profileLoading.value = true
  try {
    const res = await api.get('/profile/me')
    if (res.data && res.data.data) {
      profileForm.value = { ...res.data.data }
    }
  } catch (err: any) {
    console.error('[PROFILE_FETCH_FAILED]', err)
    profileStatus.value = 'text-red'
    profileMessage.value = 'Không thể tải hồ sơ bệnh nhân từ hệ thống.'
  } finally {
    profileLoading.value = false
  }
}

async function saveProfile() {
  savingProfile.value = true
  profileMessage.value = ''
  profileStatus.value = ''
  try {
    const res = await api.post('/profile/update', profileForm.value)
    profileStatus.value = 'text-success'
    profileMessage.value = 'Cập nhật và đồng bộ hồ sơ y tế thành công.'
  } catch (err: any) {
    console.error('[PROFILE_SAVE_FAILED]', err)
    profileStatus.value = 'text-red'
    profileMessage.value = err.response?.data?.message || 'Lỗi đồng bộ hồ sơ lên máy chủ.'
  } finally {
    savingProfile.value = false
  }
}

async function changePassword() {
  if (securityForm.value.newPassword !== securityForm.value.confirmPassword) {
    securityStatus.value = 'text-red'
    securityMessage.value = 'Mật khẩu mới xác nhận không khớp.'
    return
  }

  changingPassword.value = true
  securityStatus.value = ''
  securityMessage.value = ''

  try {
    await api.post('/auth/change-password', {
      oldPassword: securityForm.value.oldPassword,
      newPassword: securityForm.value.newPassword
    })
    securityStatus.value = 'text-success'
    securityMessage.value = 'Đổi mật khẩu thành công. Vui lòng ghi nhớ mật khẩu mới.'
    securityForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  } catch (err: any) {
    console.error('[PASSWORD_CHANGE_FAILED]', err)
    securityStatus.value = 'text-red'
    securityMessage.value = err.response?.data?.message || 'Đổi mật khẩu thất bại. Kiểm tra mật khẩu cũ.'
  } finally {
    changingPassword.value = false
  }
}

onMounted(() => {
  fetchProfile()
})
</script>

<style scoped>
.profile-settings-canvas {
  flex: 1;
  padding: 24px;
  background: var(--color-bg-void);
  overflow-y: auto;
}

.hud-status-strip {
  font-family: var(--font-hud);
  font-size: 10px;
  letter-spacing: 0.15em;
  border-bottom: 1px solid var(--color-border-dim);
  padding-bottom: 6px;
}

.settings-grid {
  display: grid;
  grid-template-columns: 7fr 3fr;
  gap: 24px;
  align-items: start;
}

.settings-main {
  background: #000000;
  padding: 24px;
  border: 1px solid var(--color-border-dim);
}

.loading-overlay {
  padding: 40px 0;
}

.pulse-text {
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.tactical-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
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

.form-row-1 {
  display: grid;
  grid-template-columns: 1fr;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-group label {
  font-size: 10px;
  letter-spacing: 0.05em;
}

.tactical-input-wrapper {
  display: flex;
  align-items: center;
  border: 1px solid var(--color-border-dim);
  background: #000000;
  transition: border-color 0.2s;
}

.tactical-input-wrapper:focus-within {
  border-color: var(--color-border);
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.3);
}

.prefix {
  padding: 6px 10px;
  font-family: var(--font-data);
  font-size: 10px;
  color: var(--color-border-blue);
  background: rgba(0, 229, 255, 0.08);
  border-right: 1px solid var(--color-border-dim);
  white-space: nowrap;
}

.tactical-input {
  flex: 1;
  background: transparent;
  border: none;
  padding: 6px 12px;
  color: var(--color-text-primary);
  font-family: var(--font-data);
  font-size: 11px;
  outline: none;
}

.select-input {
  appearance: none;
  -webkit-appearance: none;
  color: var(--color-text-primary);
  background: #000000;
  cursor: pointer;
}

.tactical-textarea {
  background: #000000;
  border: 1px solid var(--color-border-dim);
  color: var(--color-text-primary);
  font-family: var(--font-data);
  font-size: 11px;
  padding: 10px;
  height: 80px;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s;
}

.tactical-textarea:focus {
  border-color: var(--color-border);
  box-shadow: 0 0 8px rgba(0, 229, 255, 0.3);
}

.message-log {
  border: 1px solid currentColor;
  padding: 8px;
  background: rgba(0, 0, 0, 0.4);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}

.settings-sidebar {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.policy-details p {
  line-height: 1.6;
}

select option {
  background: #000000;
  color: var(--color-text-primary);
}
</style>
