<template>
  <div class="vision-shell">
    <!-- Cinematic HUD Terminal Loader -->
    <div v-if="cfg.isConfigLoading" class="hud-terminal-loader">
      <span class="loader-text font-mono">[ CRITICAL_SYSTEM_UPLINK: FETCHING_ENV_METRICS... ]</span>
    </div>

    <!-- ── FULL-SCREEN CAMERA BACKGROUND ──────────────────────────────────── -->
    <div class="camera-bg-layer">
      <img
        v-if="cameraOnline"
        :src="mjpegUrl"
        class="camera-bg-feed"
        @error="handleCameraError"
        @load="handleCameraLoad"
        alt="Baymax Optical Stream"
      />
      <div v-else class="camera-bg-offline">
        <div class="noise-bg"></div>
        <div class="offline-text font-mono">
          <span class="glow-red blink-fast">[ OPTICAL FEED SIGNAL LOSS ]</span><br/>
          <span class="dim-text text-xs">AWAITING MJPEG ON {{ cameraIp }}:8080/video</span>
        </div>
      </div>
      <!-- Scanline overlay -->
      <div class="scanlines-overlay"></div>
      <!-- Teal tint wash (very subtle, like Baymax optical filter) -->
      <div class="vision-tint"></div>
    </div>

    <!-- ── HUD OVERLAY LAYER ────────────────────────────────────────────────── -->
    <div class="hud-overlay">

      <!-- ┌───── HEADER BAR ──────────────────────────────────────────────────── -->
      <header class="hud-header">
        <div class="header-left">
          <span class="sys-tag">//</span>
          <span class="sys-title orbitron">BAYMAX / OPTICAL_SCAN_v4</span>
          <span class="sys-tag"> //</span>
        </div>
        <div class="header-center">
          <span class="scan-chip" :class="vitalsStore.isEmergency ? 'chip-crit' : 'chip-ok'">
            {{ vitalsStore.isEmergency ? '⚠ CRITICAL' : '✓ NOMINAL' }}
          </span>
        </div>
        <div class="header-right mono">
          <span class="dim">HR:</span>
          <span :class="vitalsStore.isEmergency ? 'text-crit' : 'text-em'">{{ heartRate }}</span>
          <span class="dim ml-2">SpO₂:</span>
          <span :class="spo2 < 95 ? 'text-crit' : 'text-em'">{{ spo2 }}%</span>
          <span class="dim ml-2">TEMP:</span>
          <span :class="temperature > 38.5 ? 'text-crit' : 'text-em'">{{ temperature }}°C</span>
        </div>
      </header>

      <!-- ┌───── MAIN BODY ────────────────────────────────────────────────────── -->
      <div class="hud-body">

        <!-- LEFT COLUMN — Biometric Stream -->
        <aside class="hud-col hud-col-left">
          <!-- Diagonal connector line from reticle -->
          <svg class="connector-line-left" preserveAspectRatio="none" viewBox="0 0 100 100">
            <line x1="100" y1="0" x2="0" y2="100" stroke="#00E5FF" stroke-width="0.8" stroke-dasharray="4,3" opacity="0.4"/>
          </svg>

          <transition name="panel-swap" mode="out-in">
            <div :key="leftPanel" class="glass-panel">
              <!-- CLINICAL DIAGNOSIS -->
              <template v-if="leftPanel === 0">
                <div class="panel-tag cyan">[ CLINICAL_DIAGNOSIS ]</div>
                <div class="diag-line">
                  <span class="diag-key dim">DIAGNOSIS:</span>
                  <span class="diag-val orbitron text-sm" :class="riskColorClass">{{ calculatedDiagnosis }}</span>
                </div>
                <div class="diag-line mt-2">
                  <span class="diag-key dim">TREATMENT:</span>
                  <span class="diag-val mono text-xs text-em">{{ calculatedTreatment }}</span>
                </div>
                <div class="diag-divider"></div>
                <div class="panel-tag cyan mt-2">[ SCAN_SYMPTOMS ]</div>
                <div v-for="(sym, idx) in currentSymptoms" :key="idx" class="symptom-row">
                  <span :class="vitalsStore.isEmergency ? 'text-crit' : 'text-em'">►</span>
                  <span class="mono text-xs ml-1 uppercase">{{ sym }}</span>
                </div>
                <div v-if="latestScan?.notes" class="notes-block">
                  <span class="dim text-xs">[AI_NOTE]</span>
                  <p class="mono text-xs text-em leading-tight">{{ latestScan.notes }}</p>
                </div>
              </template>

              <!-- PATIENT BODY SCAN -->
              <template v-else>
                <div class="panel-tag cyan">[ PATIENT_BODY_SCAN ]</div>
                <div class="body-scan-wrap">
                  <svg viewBox="0 0 100 220" class="body-svg">
                    <circle cx="50" cy="25" r="12" stroke="#00FF66" stroke-width="1.2" fill="none" class="pulse-border"/>
                    <line x1="50" y1="37" x2="50" y2="45" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="30" y1="45" x2="70" y2="45" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="30" y1="45" x2="22" y2="100" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="70" y1="45" x2="78" y2="100" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="34" y1="45" x2="34" y2="115" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="66" y1="45" x2="66" y2="115" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="34" y1="115" x2="66" y2="115" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="50" y1="45" x2="50" y2="115" stroke="#00FF66" stroke-width="0.8" stroke-dasharray="2,2"/>
                    <circle cx="45" cy="58" r="4.5" :fill="vitalsStore.isEmergency ? '#FF3333' : '#00FF66'" class="heart-node"/>
                    <circle cx="50" cy="23" r="3.5" :fill="stressIndex > 0.7 ? '#FF3333' : '#00E5FF'" class="brain-node"/>
                    <line x1="34" y1="115" x2="38" y2="195" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="66" y1="115" x2="62" y2="195" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="38" y1="195" x2="30" y2="199" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="62" y1="195" x2="70" y2="199" stroke="#00FF66" stroke-width="1.2"/>
                    <line x1="5" :y1="scanY" x2="95" :y2="scanY" stroke="#00E5FF" stroke-width="1.2" class="scan-beam"/>
                  </svg>
                  <div class="body-meta mono">
                    <div class="bm-row"><span class="dim">POSTURE:</span> <span class="text-orange text-xs">{{ latestScan?.posture_risk || 'LOW_RISK' }}</span></div>
                    <div class="bm-row"><span class="dim">INJURIES:</span> <span class="text-em text-xs">{{ latestScan?.visible_injuries?.join(', ') || 'NONE' }}</span></div>
                    <div class="bm-row"><span class="dim">RISK_LVL:</span> <span :class="latestScan?.overall_risk === 'HIGH' ? 'text-crit' : 'text-em'" class="text-xs">{{ latestScan?.overall_risk || 'LOW' }}</span></div>
                  </div>
                </div>
              </template>
            </div>
          </transition>

          <!-- Left manual nav -->
          <div class="panel-nav">
            <button class="nav-btn mono" @click="leftPanel = (leftPanel - 1 + 2) % 2" title="Previous">◄</button>
            <div class="nav-dots">
              <span v-for="i in 2" :key="i" class="nav-dot" :class="{ active: leftPanel === i - 1 }"/>
            </div>
            <button class="nav-btn mono" @click="leftPanel = (leftPanel + 1) % 2" title="Next">►</button>
            <span class="nav-label mono">{{ ['DIAGNOSIS', 'BODY_SCAN'][leftPanel] }}</span>
          </div>
        </aside>

        <!-- CENTER VIEWPORT -->
        <main class="hud-center">
          <!-- Reticle ring SVG overlay -->
          <div class="reticle-wrap">
            <svg class="reticle-svg" viewBox="0 0 300 300">
              <!-- center circle -->
              <circle cx="150" cy="150" r="70" fill="none" stroke="#00E5FF" stroke-width="1" opacity="0.6"/>
              <!-- dashed outer ring -->
              <circle cx="150" cy="150" r="100" fill="none" stroke="#00E5FF" stroke-width="0.5" stroke-dasharray="6,6" opacity="0.3"/>
              <!-- crosshairs -->
              <line x1="150" y1="80" x2="150" y2="120" stroke="#00E5FF" stroke-width="1" opacity="0.7"/>
              <line x1="150" y1="180" x2="150" y2="220" stroke="#00E5FF" stroke-width="1" opacity="0.7"/>
              <line x1="80" y1="150" x2="120" y2="150" stroke="#00E5FF" stroke-width="1" opacity="0.7"/>
              <line x1="180" y1="150" x2="220" y2="150" stroke="#00E5FF" stroke-width="1" opacity="0.7"/>
              <!-- Corner brackets -->
              <polyline points="50,50 50,70 70,70" fill="none" stroke="#00E5FF" stroke-width="1.5" opacity="0.8"/>
              <polyline points="250,50 250,70 230,70" fill="none" stroke="#00E5FF" stroke-width="1.5" opacity="0.8"/>
              <polyline points="50,250 50,230 70,230" fill="none" stroke="#00E5FF" stroke-width="1.5" opacity="0.8"/>
              <polyline points="250,250 250,230 230,230" fill="none" stroke="#00E5FF" stroke-width="1.5" opacity="0.8"/>
              <!-- target lock indicator -->
              <circle cx="150" cy="150" r="4" fill="#00FF66" class="target-dot"/>
            </svg>

            <!-- Dynamic face tracker -->
            <div class="face-tracker" :style="trackerStyle" v-if="cameraOnline">
              <span class="tracker-tag mono">TGT: PATIENT</span>
            </div>
          </div>

          <!-- Subtitle overlay -->
          <div class="subtitle-layer">
            <p class="subtitle-text">{{ currentSubtitle }}</p>
          </div>
        </main>

        <!-- RIGHT COLUMN — Neurological Stream -->
        <aside class="hud-col hud-col-right">
          <!-- Diagonal connector line from reticle -->
          <svg class="connector-line-right" preserveAspectRatio="none" viewBox="0 0 100 100">
            <line x1="0" y1="0" x2="100" y2="100" stroke="#00E5FF" stroke-width="0.8" stroke-dasharray="4,3" opacity="0.4"/>
          </svg>

          <transition name="panel-swap" mode="out-in">
            <div :key="rightPanel" class="glass-panel">
              <!-- BRAIN SCANS -->
              <template v-if="rightPanel === 0">
                <div class="panel-tag cyan">[ BRAIN_ACTIVITY_SCANS ]</div>
                <div class="brain-row">
                  <div class="brain-box">
                    <div class="dim text-xs mb-1">BASELINE</div>
                    <svg viewBox="0 0 100 80" class="brain-svg">
                      <path d="M50 15 C30 15, 20 25, 20 45 C20 60, 35 65, 50 65 Z" stroke="#00FF66" stroke-width="1" fill="none" opacity="0.7"/>
                      <path d="M50 15 C70 15, 80 25, 80 45 C80 60, 65 65, 50 65 Z" stroke="#00FF66" stroke-width="1" fill="none" opacity="0.7"/>
                      <circle cx="35" cy="30" r="1.5" fill="#00FF66"/>
                      <circle cx="45" cy="40" r="1.5" fill="#00FF66"/>
                      <circle cx="65" cy="30" r="1.5" fill="#00FF66"/>
                      <circle cx="55" cy="40" r="1.5" fill="#00FF66"/>
                    </svg>
                    <div class="text-em mono text-xs font-bold">[ NOMINAL ]</div>
                  </div>
                  <div class="brain-box">
                    <div class="dim text-xs mb-1">PATIENT</div>
                    <svg viewBox="0 0 100 80" class="brain-svg">
                      <path d="M50 15 C30 15, 20 25, 20 45 C20 60, 35 65, 50 65 Z" stroke="#00E5FF" stroke-width="1" fill="none"/>
                      <path d="M50 15 C70 15, 80 25, 80 45 C80 60, 65 65, 50 65 Z" stroke="#00E5FF" stroke-width="1" fill="none"/>
                      <circle cx="35" cy="30" r="2" :fill="stressIndex > 0.6 ? '#FF3333' : '#00FF66'" class="blink-fast"/>
                      <circle cx="45" cy="40" r="1.5" :fill="stressIndex > 0.6 ? '#FFB000' : '#00FF66'"/>
                      <circle cx="65" cy="30" r="1.5" fill="#00FF66"/>
                      <circle cx="55" cy="40" r="2" :fill="stressIndex > 0.6 ? '#FFB000' : '#00FF66'"/>
                      <path d="M25 28 Q35 22 45 35" :stroke="stressIndex > 0.6 ? '#FF3333' : '#00E5FF'" stroke-width="0.8" stroke-dasharray="2,1" fill="none"/>
                    </svg>
                    <div class="mono text-xs font-bold" :class="stressIndex > 0.6 ? 'text-orange blink' : 'text-cyan'">
                      {{ stressIndex > 0.6 ? '[ DISTRESS ]' : '[ COHERENT ]' }}
                    </div>
                  </div>
                </div>
              </template>

              <!-- NEUROTRANSMITTERS -->
              <template v-else-if="rightPanel === 1">
                <div class="panel-tag cyan">[ NEUROTRANSMITTER_LEVELS ]</div>
                <div class="neuro-list">
                  <div class="neuro-row">
                    <div class="nr-labels"><span>DOP (DOPAMINE)</span><span class="text-em">{{ dopVal }} pg/mL</span></div>
                    <div class="seg-bar">
                      <div v-for="i in 10" :key="`d${i}`" class="seg-block" :style="{background: getBarColor(dopVal, 100, i)}"/>
                    </div>
                  </div>
                  <div class="neuro-row">
                    <div class="nr-labels"><span>SER (SEROTONIN)</span><span class="text-cyan">{{ serVal }} ng/mL</span></div>
                    <div class="seg-bar">
                      <div v-for="i in 10" :key="`s${i}`" class="seg-block" :style="{background: getBarColor(serVal, 200, i)}"/>
                    </div>
                  </div>
                  <div class="neuro-row">
                    <div class="nr-labels"><span>EPI (EPINEPHRINE)</span><span :class="stressIndex > 0.6 ? 'text-crit' : 'text-orange'">{{ epiVal }} pg/mL</span></div>
                    <div class="seg-bar">
                      <div v-for="i in 10" :key="`e${i}`" class="seg-block" :style="{background: getBarColor(epiVal, 180, i, true)}"/>
                    </div>
                  </div>
                </div>
                <div class="diag-divider"></div>
                <div class="panel-tag cyan mt-2">[ HORMONES_BLOOD_ASSAY ]</div>
                <div class="hormones-grid">
                  <div class="horm-item"><span class="dim text-xs">GnRH</span><span class="mono text-sm text-em">{{ gnrhVal }}</span></div>
                  <div class="horm-item"><span class="dim text-xs">LH</span><span class="mono text-sm text-em">{{ lhVal }}</span></div>
                  <div class="horm-item"><span class="dim text-xs">FSH</span><span class="mono text-sm text-em">{{ fshVal }}</span></div>
                  <div class="horm-item"><span class="dim text-xs">TESTO.</span><span class="mono text-sm text-em">{{ testosteroneVal }}</span></div>
                  <div class="horm-item"><span class="dim text-xs">E2</span><span class="mono text-sm text-em">{{ estradiolVal }}</span></div>
                  <div class="horm-item"><span class="dim text-xs">CORTISOL</span><span class="mono text-sm" :class="stressIndex > 0.7 ? 'text-crit font-bold' : 'text-em'">{{ cortisolVal }}</span></div>
                </div>
              </template>

              <!-- SOCIAL NETWORK -->
              <template v-else>
                <div class="panel-tag cyan">[ SOCIAL_CONTACTS_NETWORK ]</div>
                <div class="social-wrap">
                  <svg viewBox="0 0 100 85" class="social-svg">
                    <line x1="50" y1="45" x2="30" y2="25" stroke="rgba(0,229,255,0.25)" stroke-width="0.8"/>
                    <line x1="50" y1="45" x2="70" y2="25" stroke="rgba(0,229,255,0.25)" stroke-width="0.8"/>
                    <line x1="50" y1="45" x2="50" y2="15" stroke="rgba(0,229,255,0.25)" stroke-width="0.8"/>
                    <line x1="50" y1="45" x2="22" y2="45" stroke="rgba(0,229,255,0.25)" stroke-width="0.8"/>
                    <line x1="50" y1="45" x2="78" y2="45" stroke="rgba(0,229,255,0.25)" stroke-width="0.8"/>
                    <line x1="50" y1="45" x2="35" y2="68" stroke="rgba(0,229,255,0.25)" stroke-width="0.8"/>
                    <line x1="50" y1="45" x2="65" y2="68" stroke="rgba(0,229,255,0.25)" stroke-width="0.8"/>
                    <circle cx="50" cy="45" r="5" fill="#00FF66" stroke="#00E5FF" stroke-width="1.5" class="pulse-node"/>
                    <circle cx="50" cy="15" r="3" fill="#00E5FF" class="glow-node"/>
                    <circle cx="30" cy="25" r="3" fill="#00E5FF" class="glow-node"/>
                    <circle cx="70" cy="25" r="3" fill="#00E5FF"/>
                    <circle cx="22" cy="45" r="3" fill="#00E5FF"/>
                    <circle cx="78" cy="45" r="3" fill="#00E5FF"/>
                    <circle cx="35" cy="68" r="3" fill="#00E5FF"/>
                    <circle cx="65" cy="68" r="3" fill="#00FF66" class="glow-node"/>
                  </svg>
                  <div class="dim mono text-xs text-center mt-1">CONTACT_GRAPH: ACTIVE</div>
                </div>
              </template>
            </div>
          </transition>

          <!-- Right manual nav -->
          <div class="panel-nav">
            <button class="nav-btn mono" @click="rightPanel = (rightPanel - 1 + 3) % 3" title="Previous">◄</button>
            <div class="nav-dots">
              <span v-for="i in 3" :key="i" class="nav-dot" :class="{ active: rightPanel === i - 1 }"/>
            </div>
            <button class="nav-btn mono" @click="rightPanel = (rightPanel + 1) % 3" title="Next">►</button>
            <span class="nav-label mono">{{ ['BRAIN_SCAN', 'NEURO_DATA', 'SOCIAL_NET'][rightPanel] }}</span>
          </div>
        </aside>
      </div>

      <!-- ┌───── FOOTER BAR ──────────────────────────────────────────────────── -->
      <footer class="hud-footer mono">
        <div class="ft-cell">
          <span class="dim">SYS_STABLE:</span>
          <span class="text-em">99.87%</span>
        </div>
        <div class="ft-cell">
          <span class="dim">SENSOR_FREQ:</span>
          <span class="text-cyan">10Hz</span>
        </div>
        <div class="ft-cell">
          <span class="dim">STRESS_IDX:</span>
          <span :class="stressIndex > 0.6 ? 'text-crit' : 'text-em'">{{ (stressIndex * 100).toFixed(0) }}/100</span>
        </div>
        <div class="ft-cell">
          <span class="dim">CAM_HOST:</span>
          <span class="text-cyan">{{ cfg.phoneIp }}:{{ cfg.cameraPort }}</span>
        </div>
        <div class="ft-cell">
          <span class="dim">UPLINK:</span>
          <span :class="cameraOnline ? 'text-em' : 'text-orange'">{{ cameraOnline ? 'STREAMING' : 'OFFLINE' }}</span>
        </div>
        <div class="ft-cell">
          <span class="dim">SLA_LATENCY:</span>
          <span class="text-em">1.2ms</span>
        </div>
        <!-- Device IP config modal trigger -->
        <div class="ft-cell">
          <DeviceIpConfigModal />
        </div>
        <!-- Scan trigger -->
        <div class="ft-cell">
          <button class="scan-btn" :disabled="scanning" @click="triggerPerceptionScan">
            {{ scanning ? '[ SCANNING... ]' : '[ TRIGGER_SCAN ]' }}
          </button>
        </div>
      </footer>

    </div><!-- /hud-overlay -->
  </div><!-- /vision-shell -->
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useVitalsStore } from '../stores/vitals.ts';
import { useSensorTelemetryStore } from '../stores/sensorTelemetry.ts';
import { useKinematicsStore } from '../stores/kinematics.ts';
import { useDeviceConfigStore } from '../stores/deviceConfig.ts';
import DeviceIpConfigModal from '../components/DeviceIpConfigModal.vue';
import api from '../services/api.ts';

const vitalsStore = useVitalsStore();
const sensorStore = useSensorTelemetryStore();
const kinematicsStore = useKinematicsStore();
const cfg = useDeviceConfigStore();
const cameraIp = computed(() => cfg.phoneIp);

// ── Panel cycle state ──────────────────────────────────────────────────────
const leftPanel = ref(0);   // 0 = CLINICAL_DIAGNOSIS, 1 = PATIENT_BODY_SCAN
const rightPanel = ref(0);  // 0 = BRAIN, 1 = NEURO, 2 = SOCIAL

// ── Camera / Scan state ────────────────────────────────────────────────────
// IP is now owned by deviceConfig store — no local cameraIp ref needed
const cameraOnline = ref(false);
const scanning = ref(false);
const latestScan = ref<any>(null);
const scanY = ref(15);
const scanDirection = ref(1);

// ── Bounding Box Tracker ───────────────────────────────────────────────────
const trackerStyle = computed(() => {
  if (!cameraOnline.value || !kinematicsStore.isLive) {
    return { display: 'none' };
  }
  const { x, y, width, height } = kinematicsStore.tracker;
  return {
    top: `${y}%`,
    left: `${x}%`,
    width: `${width}%`,
    height: `${height}%`,
  };
});

// MJPEG URL driven by the shared deviceConfig store
const mjpegUrl = computed(() => cfg.cameraUrl);

// ── Vitals ─────────────────────────────────────────────────────────────────
const heartRate = computed(() => {
  if (cameraOnline.value && kinematicsStore.rppgHeartRate > 0) {
    return Math.round(kinematicsStore.rppgHeartRate);
  }
  return vitalsStore.current.heartRate || 74;
});
const spo2 = computed(() => vitalsStore.current.spo2 || 98);
const temperature = computed(() => {
  if (cameraOnline.value && kinematicsStore.thermalTemperature > 0) {
    return parseFloat(kinematicsStore.thermalTemperature.toFixed(1));
  }
  return vitalsStore.current.bodyTemperature || 36.6;
});
const steps = computed(() => sensorStore.activity?.pedometer_steps || 1420);

// ── Stress index ───────────────────────────────────────────────────────────
const stressIndex = computed(() => {
  const hrDev = Math.max(0, heartRate.value - 75) / 55;
  const o2Dev = Math.max(0, 97 - spo2.value) / 7;
  return Math.min(1, Math.max(0, (hrDev * 1.3 + o2Dev * 0.7) / 2));
});

// ── Neurotransmitters / hormones ───────────────────────────────────────────
const dopVal = computed(() => Math.round(Math.max(10, 85 - stressIndex.value * 45 + (steps.value % 60) * 0.1)));
const serVal = computed(() => Math.round(Math.max(30, 160 - stressIndex.value * 70)));
const epiVal = computed(() => Math.round(25 + stressIndex.value * 135));
const gnrhVal = computed(() => Math.round(4 + stressIndex.value * 6));
const lhVal = computed(() => Math.round(62 + stressIndex.value * 23));
const fshVal = computed(() => Math.round(45 + stressIndex.value * 16));
const testosteroneVal = computed(() => Math.round(145 + (1 - stressIndex.value) * 45 + (steps.value % 40) * 0.2));
const estradiolVal = computed(() => Math.round(18 + stressIndex.value * 7));
const cortisolVal = computed(() => Math.round(4 + stressIndex.value * 14));

// ── Diagnosis ──────────────────────────────────────────────────────────────
const calculatedDiagnosis = computed(() => {
  if (vitalsStore.isEmergency) return 'CRITICAL PHYSICAL TRAUMA';
  const isGrief = latestScan.value?.notes?.toLowerCase().includes('grief');
  if (isGrief) return 'ACUTE BEREAVEMENT / GRIEF';
  if (stressIndex.value > 0.6) return 'ACUTE EMOTIONAL INSTABILITY';
  if (stressIndex.value > 0.35) return 'ELEVATED STRESS ARCHITECTURE';
  return 'NOMINAL PHYSIOLOGICAL STATE';
});
const calculatedTreatment = computed(() => {
  if (vitalsStore.isEmergency) return 'IMMEDIATE DISPATCH & CRITICAL ASSIST';
  if (calculatedDiagnosis.value.includes('BEREAVEMENT')) return 'LIÊN LẠC VỚI BẠN BÈ VÀ GIA ĐÌNH';
  if (stressIndex.value > 0.6) return 'COGNITIVE REFOCUS & EMOTIONAL RE-ANCHOR';
  if (stressIndex.value > 0.35) return 'CALIBRATED DEEP BREATHING EXERCISE';
  return 'CONTINUOUS PASSIVE OBSERVATION';
});
const riskColorClass = computed(() => {
  if (vitalsStore.isEmergency) return 'text-crit';
  if (stressIndex.value > 0.6) return 'text-orange';
  return 'text-em';
});
const currentSymptoms = computed(() => {
  const list: string[] = [];
  if (vitalsStore.isEmergency) { list.push('Severe Posture Collapse'); list.push('High Trauma Threshold'); }
  if (stressIndex.value > 0.6) { list.push('GPR54 Detected'); list.push('High levels GnRH'); list.push('Emotional Instability'); }
  else if (stressIndex.value > 0.35) { list.push('Elevated Heart Rate'); list.push('Adrenal Response Spike'); }
  else { list.push('No Physical Injury'); list.push('Optimal Synaptic Coherence'); }
  latestScan.value?.visible_injuries?.forEach((inj: string) => list.push(inj));
  return list;
});
const currentSubtitle = computed(() => {
  if (vitalsStore.isEmergency) return 'CẢNH BÁO NGUY CẤP: PHÁT HIỆN SỰ CỐ TÉ NGÃ!';
  if (calculatedDiagnosis.value.includes('BEREAVEMENT')) return 'Liệu pháp: liên lạc bạn bè và gia đình.';
  if (stressIndex.value > 0.6) return 'Bạn đang có tâm trạng bất thường.';
  return 'Chỉ số sinh hóa ổn định. Hệ thống quan sát nominal.';
});

// ── Bar helper ─────────────────────────────────────────────────────────────
function getBarColor(val: number, max: number, idx: number, warnHigh = false): string {
  const pct = (val / max) * 100;
  if (pct >= (idx / 10) * 100) {
    if (warnHigh && pct > 65) return '#FF3333';
    if (pct < 40) return '#00E5FF';
    return '#00FF66';
  }
  return 'rgba(0,255,102,0.08)';
}

// ── Camera handlers ────────────────────────────────────────────────────────
function handleCameraLoad() { cameraOnline.value = true; }
function handleCameraError() { cameraOnline.value = false; }

// Reload camera when user confirms a new IP in DeviceIpConfigModal
watch(() => cfg.confirmedAt, () => {
  cameraOnline.value = false;
  // Brief delay lets Vue re-render the img src before re-probing
  setTimeout(() => {
    const img = new Image();
    img.src = cfg.cameraUrl + '?' + Date.now();
    img.onload = () => { cameraOnline.value = true; };
    img.onerror = () => { cameraOnline.value = false; };
  }, 400);
});

async function triggerPerceptionScan() {
  if (scanning.value) return;
  scanning.value = true;
  try {
    const res = await api.post('/agents/perception/scan', {}, { timeout: 30000 });
    const data = res.data?.data;
    if (data?.status === 'ok') latestScan.value = data.scan;
  } catch (e) { console.warn('[VISION] Scan error:', e); }
  finally { scanning.value = false; }
}
async function fetchLatestScan() {
  try {
    const res = await api.get('/agents/perception/latest');
    const data = res.data?.data;
    if (data?.status === 'ok') latestScan.value = data.scan;
  } catch (e) { /* silent */ }
}

// ── Timers ────────────────────────────────────────────────────────────────
let tickTimerId: any = null;
let pollTimerId: any = null;

onMounted(async () => {
  // Try to load dynamic IP configuration from backend first
  await cfg.fetchBackendConfig();

  // Probe camera with current confirmed IP from store
  const img = new Image();
  img.src = cfg.cameraUrl;
  img.onload = () => { cameraOnline.value = true; };
  img.onerror = () => { cameraOnline.value = false; };

  fetchLatestScan();
  pollTimerId = setInterval(fetchLatestScan, 5000);

  // Scan beam movement
  tickTimerId = setInterval(() => {
    scanY.value += scanDirection.value * 1.5;
    if (scanY.value > 195) scanDirection.value = -1;
    else if (scanY.value < 20) scanDirection.value = 1;
  }, 50);

  // No auto-cycle — user controls panel switching manually
});

onUnmounted(() => {
  clearInterval(tickTimerId);
  clearInterval(pollTimerId);
});
</script>

<style scoped>
/* ── FONTS ──────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@400;600;700&family=VT323&family=Roboto+Mono:wght@400;500&display=swap');

/* ── ROOT SHELL ─────────────────────────────────────────────────────────── */
.vision-shell {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
  font-family: 'Roboto Mono', monospace;
  color: #E0FFE8;
  background: #000;
}
.orbitron { font-family: 'Orbitron', sans-serif; }
.mono { font-family: 'Roboto Mono', monospace; }

/* ── CINEMATIC HUD TERMINAL LOADER ───────────────────────────────────────── */
.hud-terminal-loader {
  position: absolute;
  inset: 0;
  background: #000000;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}
.loader-text {
  font-family: 'Roboto Mono', monospace;
  color: #00FF66;
  font-size: 14px;
  letter-spacing: 2px;
  animation: scanning-glow 1.5s ease-in-out infinite;
}
@keyframes scanning-glow {
  0%, 100% { opacity: 0.3; text-shadow: 0 0 2px rgba(0, 255, 102, 0.2); }
  50% { opacity: 1; text-shadow: 0 0 10px rgba(0, 255, 102, 0.8); }
}

/* ── CAMERA BACKGROUND ─────────────────────────────────────────────────── */
.camera-bg-layer {
  position: absolute;
  inset: 0;
  z-index: 0;
}
.camera-bg-feed {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: contrast(1.1) brightness(0.75) saturate(0.8) sepia(0.1);
}
.camera-bg-offline {
  width: 100%; height: 100%;
  position: relative;
  background: radial-gradient(circle, rgba(0,229,255,0.04) 0%, #000 80%);
  display: flex; align-items: center; justify-content: center;
}
.noise-bg {
  position: absolute; inset: 0;
  background-image: radial-gradient(rgba(0,229,255,0.15) 10%, transparent 10%);
  background-size: 8px 8px;
  opacity: 0.06;
  animation: noise-flicker 0.15s infinite;
}
@keyframes noise-flicker { 50% { opacity: 0.03; } }
.offline-text { text-align: center; z-index: 2; line-height: 2; }
.scanlines-overlay {
  position: absolute; inset: 0; pointer-events: none;
  background: repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.18) 2px, rgba(0,0,0,0.18) 4px);
  z-index: 1;
}
.vision-tint {
  position: absolute; inset: 0; pointer-events: none;
  background: rgba(0, 229, 255, 0.04);
  z-index: 2;
}

/* ── HUD OVERLAY ─────────────────────────────────────────────────────────── */
.hud-overlay {
  position: absolute;
  inset: 0;
  z-index: 10;
  display: flex;
  flex-direction: column;
  pointer-events: none;
}
.hud-overlay > * { pointer-events: auto; }

/* ── HEADER ──────────────────────────────────────────────────────────────── */
.hud-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  background: rgba(0,229,255,0.05);
  backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(0,229,255,0.2);
  font-size: 11px;
}
.sys-tag { color: rgba(0,229,255,0.4); font-family: 'Roboto Mono', monospace; }
.sys-title { font-size: 13px; letter-spacing: 0.2em; color: #00E5FF; }
.scan-chip {
  padding: 2px 10px;
  border: 1px solid;
  border-radius: 2px;
  font-family: 'Roboto Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
}
.chip-ok { border-color: #00FF66; color: #00FF66; }
.chip-crit { border-color: #FF3333; color: #FF3333; animation: blink-anim 1s step-end infinite; }
.header-right { font-size: 11px; display: flex; align-items: center; gap: 4px; }

/* ── MAIN BODY ───────────────────────────────────────────────────────────── */
.hud-body {
  flex: 1;
  display: grid;
  grid-template-columns: 260px 1fr 260px;
  gap: 0;
  overflow: hidden;
}

/* ── COLUMNS ─────────────────────────────────────────────────────────────── */
.hud-col {
  display: flex;
  flex-direction: column;
  padding: 12px 10px;
  gap: 8px;
  overflow: hidden;
  position: relative;
}
.hud-col-left { align-items: flex-start; }
.hud-col-right { align-items: flex-end; }

/* Diagonal connector SVGs */
.connector-line-left {
  position: absolute;
  top: 0; right: -30px;
  width: 80px; height: 100%;
  pointer-events: none;
  z-index: 5;
}
.connector-line-right {
  position: absolute;
  top: 0; left: -30px;
  width: 80px; height: 100%;
  pointer-events: none;
  z-index: 5;
}

/* ── GLASS PANEL ─────────────────────────────────────────────────────────── */
.glass-panel {
  width: 100%;
  background: rgba(0,229,255,0.03);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(0,229,255,0.18);
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  overflow-y: auto;
}
.glass-panel::-webkit-scrollbar { width: 2px; }
.glass-panel::-webkit-scrollbar-thumb { background: rgba(0,229,255,0.3); }

/* ── PANEL SWAP TRANSITION ───────────────────────────────────────────────── */
.panel-swap-enter-active, .panel-swap-leave-active {
  transition: all 0.5s cubic-bezier(0.4,0,0.2,1);
}
.panel-swap-enter-from { opacity: 0; transform: translateY(20px); }
.panel-swap-leave-to   { opacity: 0; transform: translateY(-20px); }

/* ── PANEL NAV (manual ◄/►) ──────────────────────────────────────────────── */
.panel-nav {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0 2px;
  border-top: 1px solid rgba(0,229,255,0.1);
  width: 100%;
}
.nav-btn {
  background: transparent;
  border: 1px solid rgba(0,229,255,0.3);
  color: rgba(0,229,255,0.7);
  font-size: 10px;
  width: 22px;
  height: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
  padding: 0;
  line-height: 1;
}
.nav-btn:hover {
  border-color: #00E5FF;
  color: #00E5FF;
  background: rgba(0,229,255,0.08);
  box-shadow: 0 0 6px rgba(0,229,255,0.25);
}
.nav-btn:active { transform: scale(0.92); }
.nav-dots {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.nav-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: rgba(0,229,255,0.2);
  border: 1px solid rgba(0,229,255,0.3);
  display: block;
  transition: all 0.2s;
}
.nav-dot.active {
  background: #00E5FF;
  border-color: #00E5FF;
  box-shadow: 0 0 5px rgba(0,229,255,0.7);
}
.nav-label {
  font-size: 8px;
  letter-spacing: 0.12em;
  color: rgba(0,229,255,0.55);
  text-transform: uppercase;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── PANEL TAG ───────────────────────────────────────────────────────────── */
.panel-tag {
  font-family: 'Roboto Mono', monospace;
  font-size: 8px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(0,229,255,0.15);
  margin-bottom: 4px;
}
.panel-tag.cyan { color: #00E5FF; }

/* ── DIAGNOSIS ───────────────────────────────────────────────────────────── */
.diag-line { display: flex; flex-direction: column; gap: 2px; }
.diag-key { font-size: 7px; letter-spacing: 0.12em; text-transform: uppercase; }
.diag-val { font-size: 11px; line-height: 1.3; }
.diag-divider { height: 1px; background: rgba(0,229,255,0.12); margin: 4px 0; }
.symptom-row { display: flex; align-items: center; font-size: 9px; }
.notes-block { background: rgba(0,229,255,0.04); border-left: 2px solid rgba(0,229,255,0.3); padding: 4px 6px; }

/* ── BODY SCAN ───────────────────────────────────────────────────────────── */
.body-scan-wrap { display: flex; gap: 8px; align-items: flex-start; }
.body-svg { width: 70px; flex-shrink: 0; }
.body-meta { display: flex; flex-direction: column; gap: 4px; flex: 1; }
.bm-row { font-size: 8px; display: flex; gap: 4px; }

/* ── BRAIN SCANS ─────────────────────────────────────────────────────────── */
.brain-row { display: flex; gap: 8px; }
.brain-box { display: flex; flex-direction: column; align-items: center; flex: 1; }
.brain-svg { width: 80px; }

/* ── NEUROTRANSMITTERS ───────────────────────────────────────────────────── */
.neuro-list { display: flex; flex-direction: column; gap: 8px; }
.neuro-row { display: flex; flex-direction: column; gap: 3px; }
.nr-labels { display: flex; justify-content: space-between; font-size: 8px; }
.seg-bar { display: flex; gap: 2px; height: 5px; }
.seg-block { flex: 1; border-radius: 1px; transition: background 0.3s; }

/* ── HORMONES ────────────────────────────────────────────────────────────── */
.hormones-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 4px; }
.horm-item { display: flex; flex-direction: column; align-items: center; border: 1px solid rgba(0,229,255,0.12); padding: 4px 2px; }

/* ── SOCIAL NETWORK ──────────────────────────────────────────────────────── */
.social-wrap { display: flex; flex-direction: column; align-items: center; }
.social-svg { width: 140px; height: auto; }

/* ── CENTER VIEWPORT ─────────────────────────────────────────────────────── */
.hud-center {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.reticle-wrap {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.reticle-svg {
  width: min(60vmin, 300px);
  height: min(60vmin, 300px);
  filter: drop-shadow(0 0 8px rgba(0,229,255,0.4));
}
.target-dot {
  animation: pulse-node-scale 1.2s ease-in-out infinite;
  transform-origin: 150px 150px;
}
@keyframes pulse-node-scale {
  0%,100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.6); opacity: 0.5; }
}
.face-tracker {
  position: absolute;
  border: 1px dashed rgba(0,255,102,0.7);
  box-shadow: 0 0 6px rgba(0,255,102,0.2);
  pointer-events: none;
}
.tracker-tag {
  font-size: 7px;
  color: #00E5FF;
  padding: 0 2px;
  background: rgba(0,0,0,0.4);
  position: absolute;
  top: -14px; left: 0;
}
.subtitle-layer {
  position: absolute;
  bottom: 10%;
  left: 5%; right: 5%;
  text-align: center;
  pointer-events: none;
}
.subtitle-text {
  font-family: 'Rajdhani', sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000, 0 0 10px rgba(0,229,255,0.8);
  letter-spacing: 0.03em;
}

/* ── FOOTER ──────────────────────────────────────────────────────────────── */
.hud-footer {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 5px 16px;
  background: rgba(0,229,255,0.05);
  backdrop-filter: blur(8px);
  border-top: 1px solid rgba(0,229,255,0.2);
  font-size: 9px;
  letter-spacing: 0.08em;
  flex-wrap: nowrap;
  overflow-x: auto;
}
.ft-cell {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 14px;
  border-right: 1px solid rgba(0,229,255,0.12);
  white-space: nowrap;
}
.ft-cell:last-child { border-right: none; }
.ft-cell-input { flex: 1; }
.ip-input {
  background: transparent;
  border: none;
  border-bottom: 1px solid rgba(0,229,255,0.3);
  color: #00E5FF;
  font-size: 9px;
  font-family: 'Roboto Mono', monospace;
  width: 110px;
  outline: none;
}
.scan-btn {
  background: transparent;
  border: 1px solid rgba(0,229,255,0.4);
  color: #00E5FF;
  font-family: 'Roboto Mono', monospace;
  font-size: 9px;
  padding: 3px 8px;
  cursor: pointer;
  letter-spacing: 0.08em;
  transition: all 0.2s;
}
.scan-btn:hover { background: rgba(0,229,255,0.08); }
.scan-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── COLOR TOKENS ────────────────────────────────────────────────────────── */
.dim { color: rgba(224,255,232,0.35); }
.text-em { color: #00FF66; }
.text-cyan { color: #00E5FF; }
.text-crit { color: #FF3333; }
.text-orange { color: #FFB000; }
.glow-red { color: #FF3333; filter: drop-shadow(0 0 6px #FF3333); }

/* ── SVG NODE ANIMATIONS ─────────────────────────────────────────────────── */
.pulse-border { animation: pulse-border-anim 1.5s ease-in-out infinite; }
@keyframes pulse-border-anim { 50% { stroke-opacity: 0.3; } }
.heart-node { animation: pulse-node-s 0.8s ease-in-out infinite; transform-origin: 45px 58px; }
.brain-node { animation: pulse-node-s 1.3s ease-in-out infinite; transform-origin: 50px 23px; }
@keyframes pulse-node-s { 0%,100% { transform: scale(1); } 50% { transform: scale(1.4); opacity: 0.5; } }
.scan-beam { filter: drop-shadow(0 0 3px #00E5FF); }
.pulse-node { animation: pulse-node-scale 1.5s infinite; transform-origin: 50px 45px; }
.glow-node { filter: drop-shadow(0 0 3px #00E5FF); }

/* ── BLINKING ────────────────────────────────────────────────────────────── */
.blink-fast { animation: blink-fast-anim 0.6s step-end infinite; }
@keyframes blink-fast-anim { 50% { opacity: 0.1; } }
.blink { animation: blink-anim 1.2s step-end infinite; }
@keyframes blink-anim { 50% { opacity: 0.2; } }

/* ── SCROLLBARS ──────────────────────────────────────────────────────────── */
.hud-footer::-webkit-scrollbar { height: 2px; }
.hud-footer::-webkit-scrollbar-thumb { background: rgba(0,229,255,0.3); }
</style>
