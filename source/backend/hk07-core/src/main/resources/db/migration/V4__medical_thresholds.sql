-- Flyway Migration V4: Dynamic Medical Thresholds Table
-- [HẠNCHẾ-#9 FIX] Replace hardcoded constants with per-patient DB-backed thresholds.
-- Allows Medic/Owner to configure personalized alert limits via API.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE medical_thresholds (
    id                          VARCHAR(36)  PRIMARY KEY DEFAULT (UUID()),
    user_id                     VARCHAR(36)  NOT NULL,
    device_id                   VARCHAR(100) NOT NULL,

    -- Heart Rate thresholds (BPM)
    hr_min                      INT          NOT NULL DEFAULT 50,
    hr_max                      INT          NOT NULL DEFAULT 120,

    -- Blood Pressure thresholds (mmHg)
    systolic_max                FLOAT        NOT NULL DEFAULT 140.0,
    diastolic_max               FLOAT        NOT NULL DEFAULT 90.0,

    -- SpO2 threshold (%)
    spo2_min                    FLOAT        NOT NULL DEFAULT 92.0,

    -- Body Temperature (°C)
    temp_max                    FLOAT        NOT NULL DEFAULT 38.5,

    -- Feature flags
    stroke_alert_enabled        BOOLEAN      NOT NULL DEFAULT TRUE,
    emergency_button_enabled    BOOLEAN      NOT NULL DEFAULT TRUE,

    -- Metadata
    label                       VARCHAR(100)          DEFAULT NULL COMMENT 'Human-readable label (e.g. Post-cardiac surgery profile)',
    configured_by               VARCHAR(36)           DEFAULT NULL COMMENT 'UUID of the Medic/Owner who last configured this',
    updated_at                  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at                  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_threshold_user   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_threshold_device UNIQUE (user_id, device_id)
);

-- Default thresholds for existing wristband configs (migrate existing data)
INSERT INTO medical_thresholds (user_id, device_id, hr_min, hr_max, systolic_max, spo2_min, stroke_alert_enabled)
SELECT
    wc.user_id,
    wc.device_id,
    wc.heart_rate_threshold_min,
    wc.heart_rate_threshold_max,
    wc.blood_pressure_systolic_max,
    wc.spo2_min,
    wc.stroke_alert_enabled
FROM wristband_configs wc
ON DUPLICATE KEY UPDATE updated_at = NOW();

-- Index for fast lookup by user + device
CREATE INDEX idx_threshold_user_device ON medical_thresholds (user_id, device_id);
