-- Flyway Migration V2: Seed Default Data (MySQL Version)
-- Creates default OWNER account for initial dashboard login.
-- Password: "HK07-Admin-Change-Me!"

-- Default owner account
INSERT IGNORE INTO users (id, display_name, email, password_hash, role)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'HK-07 Owner',
    'owner@hk07.local',
    '$2a$12$vRY5eeMqrCPS5nV5tKRzieQX9/VyVuh/ayI59P6czJSBSAeO8MVKy',
    'OWNER'
);

-- Default wristband config for owner (Wokwi simulator device)
INSERT IGNORE INTO wristband_configs (
    user_id, device_id, mqtt_topic,
    heart_rate_threshold_min, heart_rate_threshold_max,
    blood_pressure_systolic_max, spo2_min, stroke_alert_enabled
)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'wristband-sim-001',
    'hk07/sensors/wristband/wristband-sim-001/vitals',
    50, 120, 140.0, 92.0, TRUE
);

-- Seed one safety alert log for dashboard demo
INSERT INTO safety_alerts (level, trigger_type, distance_meters, message, subsumption_activated, response_time_ms)
VALUES ('WARNING', 'OBSTACLE', 0.48, 'Demo: Obstacle detected at 0.48m during system initialization check.', FALSE, 1.23);
