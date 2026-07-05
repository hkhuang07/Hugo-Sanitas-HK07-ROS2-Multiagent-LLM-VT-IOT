-- Flyway Migration V12: Add camera device config & fix wristband_configs to support multiple devices per user

-- Step 1: Drop FK temporarily to allow index restructuring
SET FOREIGN_KEY_CHECKS=0;
ALTER TABLE wristband_configs DROP FOREIGN KEY fk_wristband_user;

-- Step 2: Drop the single-device-per-user constraint
ALTER TABLE wristband_configs DROP INDEX uq_wristband_user;

-- Step 3: Add composite unique index (user_id, device_id) — allows multiple devices per user but prevents duplicates
ALTER TABLE wristband_configs ADD UNIQUE KEY uq_wristband_user_device (user_id, device_id);

-- Step 4: Re-attach the cascade foreign key
ALTER TABLE wristband_configs ADD CONSTRAINT fk_wristband_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE;
SET FOREIGN_KEY_CHECKS=1;

-- Step 5: Seed camera device config for default owner
INSERT IGNORE INTO wristband_configs (
    user_id, device_id, mqtt_topic,
    heart_rate_threshold_min, heart_rate_threshold_max,
    blood_pressure_systolic_max, spo2_min, stroke_alert_enabled
)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'camera',
    'hk07/sensors/wristband/camera/vitals',
    50, 120, 140.0, 92.0, 1
);
