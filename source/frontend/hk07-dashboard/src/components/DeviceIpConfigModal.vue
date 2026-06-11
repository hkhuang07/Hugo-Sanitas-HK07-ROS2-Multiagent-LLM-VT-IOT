<template>
  <!-- Trigger button (rendered inline by the parent) -->
  <button class="ip-config-trigger mono" @click="open = true" :title="`IP Điện thoại: ${cfg.phoneIp} | IP Máy tính: ${cfg.pcIp}`">
    <span class="trigger-icon">⚙</span>
    <span class="trigger-label">TEL: {{ cfg.phoneIp }}</span>
    <span class="trigger-dot" :class="dotClass"/>
  </button>

  <!-- Modal backdrop -->
  <teleport to="body">
    <transition name="modal-fade">
      <div v-if="open" class="ip-modal-backdrop" @click.self="handleClose">
        <div class="ip-modal orbitron">

          <!-- Header -->
          <div class="ip-modal-header">
            <span class="header-tag">// HK-07</span>
            <span class="header-title">DEVICE_IP_CONFIG</span>
            <button class="close-btn mono" @click="handleClose">✕</button>
          </div>

          <!-- Status bar -->
          <div class="status-bar" :class="`status-${cfg.status.toLowerCase()}`">
            <span class="status-dot"/>
            <span class="status-text mono">{{ cfg.statusMsg || `CAMERA → ${cfg.phoneIp} | SENSOR RECEIVER → ${cfg.pcIp}` }}</span>
          </div>

          <!-- Form -->
          <div class="ip-form">
            <!-- Phone IP Address -->
            <div class="field-group">
              <label class="field-label mono">// PHONE_IP_ADDRESS (IP Điện thoại)</label>
              <div class="field-hint mono">IPv4 của điện thoại (ví dụ: 192.168.101.103)</div>
              <div class="field-row">
                <div class="field-prefix mono">IP:</div>
                <input
                  v-model="cfg.draftPhoneIp"
                  class="field-input mono"
                  placeholder="192.168.101.103"
                  @keydown.enter="handleConfirm"
                  spellcheck="false"
                />
              </div>
            </div>

            <!-- PC IP Address -->
            <div class="field-group">
              <label class="field-label mono">// PC_IP_ADDRESS (IP Máy tính)</label>
              <div class="field-hint mono">IPv4 của máy tính chạy backend bridge (ví dụ: 192.168.101.49)</div>
              <div class="field-row">
                <div class="field-prefix mono">IP:</div>
                <input
                  v-model="cfg.draftPcIp"
                  class="field-input mono"
                  placeholder="192.168.101.49"
                  @keydown.enter="handleConfirm"
                  spellcheck="false"
                />
              </div>
            </div>

            <!-- Camera Port -->
            <div class="field-group">
              <label class="field-label mono">// CAMERA_PORT (IP Webcam App)</label>
              <div class="field-hint mono">Default <b>8080</b> · Endpoint: <b>/video</b> → MJPEG stream</div>
              <div class="field-row">
                <div class="field-prefix mono">PORT:</div>
                <input
                  v-model="cfg.draftCameraPort"
                  class="field-input mono"
                  placeholder="8080"
                  @keydown.enter="handleConfirm"
                />
              </div>
            </div>

            <!-- Sensor Port -->
            <div class="field-group">
              <label class="field-label mono">// SENSOR_BRIDGE_PORT (SensorLogs / MQTT Bridge)</label>
              <div class="field-hint mono">Default <b>5005</b> · Endpoint: <b>/data</b> → JSON sensor payload</div>
              <div class="field-row">
                <div class="field-prefix mono">PORT:</div>
                <input
                  v-model="cfg.draftSensorPort"
                  class="field-input mono"
                  placeholder="8080"
                  @keydown.enter="handleConfirm"
                />
              </div>
            </div>

            <!-- Preview URLs -->
            <div class="preview-block">
              <div class="preview-row mono">
                <span class="preview-label">📹 CAMERA:</span>
                <span class="preview-url">http://{{ cfg.draftPhoneIp }}:{{ cfg.draftCameraPort }}/video</span>
              </div>
              <div class="preview-row mono">
                <span class="preview-label">📡 SENSOR:</span>
                <span class="preview-url">http://{{ cfg.draftPcIp }}:{{ cfg.draftSensorPort }}/data</span>
              </div>
            </div>
          </div>

          <!-- Action row -->
          <div class="action-row">
            <button class="action-btn btn-reset mono" @click="cfg.resetDraft()">
              [ RESET ]
            </button>
            <button
              class="action-btn btn-confirm mono"
              :disabled="cfg.status === 'TESTING'"
              @click="handleConfirm"
            >
              <span v-if="cfg.status !== 'TESTING'">[ XÁC NHẬN &amp; KẾT NỐI ]</span>
              <span v-else class="blink">... ĐANG KIỂM TRA ...</span>
            </button>
          </div>

          <!-- Corner reticles -->
          <span class="cr tl">+</span>
          <span class="cr tr">+</span>
          <span class="cr bl">+</span>
          <span class="cr br">+</span>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useDeviceConfigStore } from '../stores/deviceConfig'

const cfg = useDeviceConfigStore()
const open = ref(false)

const dotClass = computed(() => {
  if (cfg.status === 'ONLINE') return 'dot-online'
  if (cfg.status === 'TESTING') return 'dot-testing'
  if (cfg.status === 'ERROR') return 'dot-error'
  return 'dot-idle'
})

async function handleConfirm() {
  await cfg.confirmIp()
}

function handleClose() {
  cfg.resetDraft()
  open.value = false
}
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Roboto+Mono:wght@400;500&display=swap');

/* ── Trigger button ─────────────────────────────────────────────────────────── */
.ip-config-trigger {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: rgba(0,229,255,0.04);
  border: 1px solid rgba(0,229,255,0.25);
  color: rgba(0,229,255,0.7);
  font-size: 9px;
  padding: 3px 8px;
  cursor: pointer;
  letter-spacing: 0.08em;
  transition: all 0.15s;
  white-space: nowrap;
  font-family: 'Roboto Mono', monospace;
}
.ip-config-trigger:hover {
  border-color: #00E5FF;
  color: #00E5FF;
  background: rgba(0,229,255,0.1);
  box-shadow: 0 0 8px rgba(0,229,255,0.2);
}
.trigger-icon { font-size: 11px; }
.trigger-label { letter-spacing: 0.05em; }
.trigger-dot {
  width: 5px; height: 5px; border-radius: 50%;
  display: inline-block; flex-shrink: 0;
}
.dot-online  { background: #00FF66; box-shadow: 0 0 4px #00FF66; }
.dot-testing { background: #FFB000; animation: blink-anim 0.5s step-end infinite; }
.dot-error   { background: #FF3333; box-shadow: 0 0 4px #FF3333; }
.dot-idle    { background: rgba(0,229,255,0.3); }

/* ── Backdrop ───────────────────────────────────────────────────────────────── */
.ip-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.75);
  backdrop-filter: blur(4px);
  z-index: 9000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.modal-fade-enter-active, .modal-fade-leave-active {
  transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
}
.modal-fade-enter-from, .modal-fade-leave-to {
  opacity: 0;
  transform: scale(0.94) translateY(-12px);
}

/* ── Modal box ──────────────────────────────────────────────────────────────── */
.ip-modal {
  position: relative;
  background: #050505;
  border: 1px solid rgba(0,229,255,0.3);
  box-shadow: 0 0 40px rgba(0,229,255,0.15), inset 0 0 80px rgba(0,229,255,0.02);
  width: min(520px, 95vw);
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background-image: repeating-linear-gradient(
    0deg, transparent, transparent 2px,
    rgba(0,229,255,0.015) 2px, rgba(0,229,255,0.015) 4px
  );
}

/* Corner reticles */
.cr { position: absolute; color: rgba(0,229,255,0.3); font-size: 14px; font-family: monospace; }
.cr.tl { top: 4px; left: 4px; }
.cr.tr { top: 4px; right: 4px; }
.cr.bl { bottom: 4px; left: 4px; }
.cr.br { bottom: 4px; right: 4px; }

/* ── Header ─────────────────────────────────────────────────────────────────── */
.ip-modal-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(0,229,255,0.15);
}
.header-tag { font-size: 9px; color: rgba(0,229,255,0.4); font-family: 'Roboto Mono', monospace; }
.header-title { flex: 1; font-size: 14px; letter-spacing: 0.25em; color: #00E5FF; }
.close-btn {
  background: transparent; border: 1px solid rgba(0,229,255,0.2);
  color: rgba(0,229,255,0.5); width: 22px; height: 22px;
  cursor: pointer; font-size: 10px; display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.close-btn:hover { border-color: #FF3333; color: #FF3333; }

/* ── Status bar ─────────────────────────────────────────────────────────────── */
.status-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 10px;
  border: 1px solid;
  font-size: 9px;
}
.status-idle    { border-color: rgba(0,229,255,0.15); color: rgba(0,229,255,0.5); }
.status-testing { border-color: #FFB000; color: #FFB000; }
.status-online  { border-color: #00FF66; color: #00FF66; background: rgba(0,255,102,0.04); }
.status-error   { border-color: #FF3333; color: #FF3333; }
.status-dot {
  width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex-shrink: 0;
}
.status-testing .status-dot { animation: blink-anim 0.5s step-end infinite; }
.status-text { font-family: 'Roboto Mono', monospace; letter-spacing: 0.06em; }

/* ── Form ───────────────────────────────────────────────────────────────────── */
.ip-form { display: flex; flex-direction: column; gap: 12px; }
.field-group { display: flex; flex-direction: column; gap: 4px; }
.field-label { font-size: 8px; letter-spacing: 0.18em; color: rgba(0,229,255,0.6); text-transform: uppercase; }
.field-hint { font-size: 8px; color: rgba(224,255,232,0.3); margin-bottom: 2px; }
.field-row {
  display: flex; align-items: stretch;
  border: 1px solid rgba(0,229,255,0.2);
  transition: border-color 0.2s;
}
.field-row:focus-within {
  border-color: #00E5FF;
  box-shadow: 0 0 8px rgba(0,229,255,0.2);
}
.field-prefix {
  padding: 7px 10px;
  background: rgba(0,229,255,0.06);
  border-right: 1px solid rgba(0,229,255,0.15);
  font-size: 9px;
  color: #00E5FF;
  white-space: nowrap;
  display: flex; align-items: center;
}
.field-input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  padding: 7px 10px;
  color: #E0FFE8;
  font-size: 11px;
  font-family: 'Roboto Mono', monospace;
  letter-spacing: 0.05em;
}
.field-input::placeholder { color: rgba(224,255,232,0.2); }

/* ── Preview block ──────────────────────────────────────────────────────────── */
.preview-block {
  background: rgba(0,229,255,0.03);
  border: 1px solid rgba(0,229,255,0.1);
  padding: 8px 12px;
  display: flex; flex-direction: column; gap: 4px;
}
.preview-row { display: flex; align-items: center; gap: 8px; font-size: 8px; }
.preview-label { color: rgba(0,229,255,0.5); flex-shrink: 0; }
.preview-url {
  color: #00E5FF;
  letter-spacing: 0.04em;
  word-break: break-all;
  font-size: 9px;
}

/* ── Actions ────────────────────────────────────────────────────────────────── */
.action-row { display: flex; gap: 10px; }
.action-btn {
  flex: 1; padding: 9px 12px;
  background: transparent; cursor: pointer;
  font-size: 10px; letter-spacing: 0.12em;
  text-transform: uppercase;
  transition: all 0.15s;
  font-family: 'Roboto Mono', monospace;
}
.btn-reset {
  border: 1px solid rgba(0,229,255,0.2);
  color: rgba(0,229,255,0.5);
  flex: 0 0 auto;
  padding: 9px 16px;
}
.btn-reset:hover { border-color: #00E5FF; color: #00E5FF; }
.btn-confirm {
  border: 1px solid #00E5FF;
  color: #00E5FF;
  background: rgba(0,229,255,0.06);
}
.btn-confirm:hover:not(:disabled) {
  background: rgba(0,229,255,0.15);
  box-shadow: 0 0 12px rgba(0,229,255,0.3);
}
.btn-confirm:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Animations ─────────────────────────────────────────────────────────────── */
.blink { animation: blink-anim 0.8s step-end infinite; }
@keyframes blink-anim { 50% { opacity: 0.1; } }
</style>
