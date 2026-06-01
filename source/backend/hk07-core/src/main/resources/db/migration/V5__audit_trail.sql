-- Flyway Migration V5: Medical Audit Trail Table
-- [HẠNCHẾ-#11 FIX] Chuẩn hóa log kiểm toán y tế cho các lệnh khẩn cấp.
-- Mỗi hành động SOS/Inhibit/Shutdown được ghi nhận với SHA-256 signature
-- để chống giả mạo hồ sơ y tế (medical record tampering prevention).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE audit_logs (
    id              UUID         PRIMARY KEY DEFAULT (UUID()),

    -- Người thực hiện
    actor_id        UUID         NOT NULL COMMENT 'UUID của Medic/Owner phát lệnh',
    actor_role      VARCHAR(30)  NOT NULL COMMENT 'Role tại thời điểm thực hiện',

    -- Hành động
    action_type     VARCHAR(50)  NOT NULL COMMENT 'INHIBIT|SOS_DISPATCH|SAFE_HOLD|RESUME|SHUTDOWN|THRESHOLD_UPDATE',
    target_device   VARCHAR(100)          COMMENT 'deviceId của robot/wristband liên quan',
    action_payload  TEXT                  COMMENT 'JSON payload của lệnh (tham số chi tiết)',

    -- Kết quả
    outcome         VARCHAR(20)  NOT NULL DEFAULT 'SUCCESS' COMMENT 'SUCCESS|FAILED|DENIED',
    error_message   TEXT                  COMMENT 'Lý do thất bại nếu outcome=FAILED',

    -- Chống giả mạo: SHA-256 hash của (actor_id + action_type + action_payload + executed_at)
    -- Dùng để phát hiện nếu bản ghi bị chỉnh sửa sau khi ghi
    integrity_hash  VARCHAR(64)  NOT NULL COMMENT 'SHA-256(actor_id|action_type|payload|timestamp)',

    -- Metadata
    ip_address      VARCHAR(45)           COMMENT 'IP của client phát lệnh (IPv4/IPv6)',
    executed_at     TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_audit_actor   FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE RESTRICT,
    CONSTRAINT chk_audit_action CHECK (action_type IN (
        'INHIBIT','INHIBIT_CLEAR','SOS_DISPATCH','SAFE_HOLD',
        'RESUME','SHUTDOWN','THRESHOLD_UPDATE','EMERGENCY_BUTTON'
    )),
    CONSTRAINT chk_audit_outcome CHECK (outcome IN ('SUCCESS','FAILED','DENIED'))
);

-- Fast lookup: reverse-chronological by actor and by action type
CREATE INDEX idx_audit_actor_time  ON audit_logs (actor_id, executed_at DESC);
CREATE INDEX idx_audit_action_time ON audit_logs (action_type, executed_at DESC);
CREATE INDEX idx_audit_device_time ON audit_logs (target_device, executed_at DESC);
