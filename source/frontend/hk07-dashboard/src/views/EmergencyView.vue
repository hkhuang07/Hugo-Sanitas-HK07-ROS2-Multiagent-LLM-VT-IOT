<template>
  <div class="emergency-shell cyber-scanlines mono">
    <div class="emergency-container terminal-card corner-reticle">
      <div class="alert-banner text-red glow-red">
        [ WARNING // EMERGENCY OVERRIDE ACTIVE ]
      </div>
      
      <div class="status-content">
        <h1 class="glow-red">Emergency Vitals Monitoring Active</h1>
        <p class="text-dim">
          All system command actions have been disabled. This view is restricted to vital signs telemetry and read-only diagnostic logs.
        </p>

        <!-- Simulated Telemetry Grid -->
        <div class="telemetry-grid">
          <div class="telemetry-box border-red">
            <span class="label text-dim">HEART_RATE:</span>
            <span class="value text-red glow-red">72 <span class="unit">BPM</span></span>
          </div>
          <div class="telemetry-box border-red">
            <span class="label text-dim">SPO2:</span>
            <span class="value text-red glow-red">98 <span class="unit">%</span></span>
          </div>
        </div>

        <div class="logs-container">
          <div class="log-title text-dim">>>> OVERRIDE_AUDIT_LOG:</div>
          <div class="log-line">>>> [00.00] TRIAGE OPERATOR BYPASSED AUTHENTICATION SUCCESSFUL</div>
          <div class="log-line">>>> [00.02] SYSTEM COMMAND INGESTION DISABLED</div>
          <div class="log-line">>>> [00.05] BROADCASTING TELEMETRY VIA LOCAL PORT...</div>
        </div>
      </div>

      <div class="actions">
        <router-link to="/login" class="cmd-btn exit-btn">
          &lt;&lt;&lt; EXIT OVERRIDE (QUAY LẠI)
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// Simple static view representing the emergency console mockup.
</script>

<style scoped>
.emergency-shell {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  background: #000624;
  position: relative;
  overflow: hidden;
  padding: 20px;
}

/* Scanline Effect */
.cyber-scanlines::before {
  content: " ";
  display: block;
  position: absolute;
  top: 0; left: 0; bottom: 0; right: 0;
  background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.15) 50%);
  background-size: 100% 4px;
  z-index: 10;
  pointer-events: none;
}

.emergency-container {
  max-width: 600px;
  width: 100%;
  padding: 32px;
  background: #000000;
  border: 1px solid #ff3333;
  box-shadow: 0 0 20px rgba(255, 51, 51, 0.2);
  z-index: 5;
}

.alert-banner {
  font-size: 13px;
  font-weight: bold;
  letter-spacing: 0.2em;
  border-bottom: 1px solid rgba(255, 51, 51, 0.3);
  padding-bottom: 16px;
  margin-bottom: 24px;
  text-align: center;
}

.status-content h1 {
  font-size: 20px;
  margin: 0 0 12px 0;
  color: #ff3333;
  letter-spacing: 0.05em;
}

.text-dim {
  color: var(--color-text-dim, #888);
  font-size: 12px;
  line-height: 1.6;
}

.telemetry-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin: 30px 0;
}

.telemetry-box {
  padding: 20px;
  background: rgba(255, 51, 51, 0.03);
  border: 1px solid rgba(255, 51, 51, 0.4);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.telemetry-box .label {
  font-size: 10px;
  margin-bottom: 8px;
}

.telemetry-box .value {
  font-size: 32px;
  font-weight: bold;
}

.telemetry-box .unit {
  font-size: 14px;
  font-weight: normal;
}

.glow-red {
  text-shadow: 0 0 8px rgba(255, 51, 51, 0.6);
}

.border-red {
  border-color: rgba(255, 51, 51, 0.5);
}

.logs-container {
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid #333;
  padding: 16px;
  border-radius: 4px;
  font-size: 11px;
  line-height: 1.8;
  color: #00ff66;
  margin-bottom: 30px;
  text-align: left;
}

.log-title {
  margin-bottom: 8px;
  font-weight: bold;
  color: #888;
}

.actions {
  display: flex;
  justify-content: center;
}

.exit-btn {
  padding: 12px 24px;
  font-size: 12px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--color-border-dim, #333);
  color: var(--color-text-dim, #888);
  text-decoration: none;
  transition: all 0.3s;
}
.exit-btn:hover {
  background: #ffffff;
  color: #000000;
  box-shadow: 0 0 10px rgba(255, 255, 255, 0.4);
}
</style>
