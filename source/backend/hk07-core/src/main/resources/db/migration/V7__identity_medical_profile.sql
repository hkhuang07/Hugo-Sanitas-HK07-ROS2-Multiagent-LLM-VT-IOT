-- Flyway Migration V7: Identity & Medical Profile (MariaDB / MySQL Version)
-- Project: Hugo Sanitas HK-07
-- Version: 1.0.0-ALPHA
--

-- ─── Medical Profiles ──────────────────────────────────────────────────────────
CREATE TABLE medical_profiles (
    id                     UUID PRIMARY KEY DEFAULT (UUID()),
    user_id                UUID         NOT NULL,
    full_name              VARCHAR(100) NULL,
    age                    INT          NULL,
    gender                 VARCHAR(10)  NULL,
    height                 FLOAT        NULL,
    weight                 FLOAT        NULL,
    blood_type             VARCHAR(10)  NULL,
    medical_history        TEXT         NULL,
    allergies              TEXT         NULL,
    emergency_contact_name  VARCHAR(100) NULL,
    emergency_contact_phone VARCHAR(30)  NULL,
    created_at             TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_medical_profile_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_medical_profile_user UNIQUE (user_id)
);

-- ─── Recovery Codes ────────────────────────────────────────────────────────────
CREATE TABLE recovery_codes (
    id          UUID PRIMARY KEY DEFAULT (UUID()),
    user_id     UUID        NOT NULL,
    code        VARCHAR(8)  NOT NULL,
    used        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_recovery_code_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_recovery_code_user_code UNIQUE (user_id, code)
);

-- ─── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX idx_medical_profile_user ON medical_profiles (user_id);
CREATE INDEX idx_recovery_code_lookup ON recovery_codes (user_id, code, used);
