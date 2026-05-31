-- Flyway Migration V3: Add missing columns and performance views (MariaDB / MySQL Version)

-- Add device_id to health_records if not exists (MariaDB supports ADD COLUMN IF NOT EXISTS)
ALTER TABLE health_records ADD COLUMN IF NOT EXISTS device_id VARCHAR(100);

-- Add updated_at to wristband_configs
ALTER TABLE wristband_configs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;

-- ─── View: 24h health summary per user
CREATE OR REPLACE VIEW v_health_hourly_summary AS
SELECT
    user_id,
    FROM_UNIXTIME(FLOOR(UNIX_TIMESTAMP(recorded_at)/3600)*3600) AS bucket_hour,
    CAST(ROUND(AVG(heart_rate)) AS SIGNED) AS avg_hr,
    CAST(MAX(heart_rate) AS SIGNED) AS max_hr,
    CAST(MIN(heart_rate) AS SIGNED) AS min_hr,
    ROUND(AVG(systolic), 1) AS avg_systolic,
    ROUND(AVG(spo2), 1) AS avg_spo2,
    ROUND(AVG(body_temperature), 1) AS avg_temp,
    COUNT(*) AS sample_count,
    MAX(alert_level) AS worst_alert
FROM health_records
WHERE recorded_at >= NOW() - INTERVAL 24 HOUR
GROUP BY user_id, bucket_hour
ORDER BY bucket_hour DESC;

-- ─── View: Last 7 days daily safety alert count
CREATE OR REPLACE VIEW v_safety_daily_count AS
SELECT
    CAST(detected_at AS DATE) AS alert_day,
    trigger_type,
    COUNT(*) AS alert_count,
    AVG(response_time_ms) AS avg_response_ms,
    SUM(CASE WHEN subsumption_activated THEN 1 ELSE 0 END) AS inhibit_count
FROM safety_alerts
WHERE detected_at >= NOW() - INTERVAL 7 DAY
GROUP BY CAST(detected_at AS DATE), trigger_type
ORDER BY alert_day DESC;
