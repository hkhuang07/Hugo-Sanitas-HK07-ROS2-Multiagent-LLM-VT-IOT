-- Flyway Migration V8: Add System Agent User for Auditing
-- Bổ sung user SYSTEM_AGENT để dùng khi actor_id bị null trong các tác vụ hệ thống tự động.
-- HK07-Admin-Change-Me!

INSERT IGNORE INTO users (id, display_name, email, password_hash, role)
VALUES (
    '00000000-0000-0000-0000-000000000000',
    'SYSTEM_AGENT',
    'system@hk07.local',
    '$2a$12$vRY5eeMqrCPS5nV5tKRzieQX9/VyVuh/ayI59P6czJSBSAeO8MVKy',
    'OWNER'
);
