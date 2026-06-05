-- Flyway Migration V1: Full Schema Initialization (MySQL Version)
-- Project: Hugo Sanitas HK-07
-- Version: 1.0.0-ALPHA
--

-- ─── Users ───────────────────────────────────────────────────────────────────
CREATE TABLE users (
    id              VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    display_name    VARCHAR(100)  NOT NULL,
    email           VARCHAR(255)  NOT NULL,
    password_hash   VARCHAR(255)  NOT NULL,
    role            VARCHAR(30)   NOT NULL DEFAULT 'OWNER',
    created_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_seen_at    TIMESTAMP     NULL,
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT chk_users_role CHECK (role IN ('OWNER','OPERATOR','EMERGENCY_CONTACT','TECHNICIAN'))
);

-- ─── Wristband Configurations ─────────────────────────────────────────────────
CREATE TABLE wristband_configs (
    id                         VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id                    VARCHAR(36)  NOT NULL,
    device_id                  VARCHAR(100) NOT NULL,
    mqtt_topic                 VARCHAR(200) NOT NULL,
    heart_rate_threshold_min   INT          NOT NULL DEFAULT 50,
    heart_rate_threshold_max   INT          NOT NULL DEFAULT 120,
    blood_pressure_systolic_max FLOAT       NOT NULL DEFAULT 140.0,
    spo2_min                   FLOAT        NOT NULL DEFAULT 92.0,
    stroke_alert_enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_wristband_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT uq_wristband_user UNIQUE (user_id)
);

-- ─── Health Records ──────────────────────────────────────────────────────────
CREATE TABLE health_records (
    id               VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    user_id          VARCHAR(36) NOT NULL,
    heart_rate       INT,
    systolic         FLOAT,
    diastolic        FLOAT,
    body_temperature FLOAT,
    spo2             FLOAT,
    device_id        VARCHAR(100),
    agent_analysis   TEXT,
    alert_level      VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
    recorded_at      TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_health_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT chk_health_alert CHECK (alert_level IN ('NORMAL','INFO','WARNING','CRITICAL','STROKE'))
);

-- ─── Agent Logs ──────────────────────────────────────────────────────────────
CREATE TABLE agent_logs (
    id               VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    agent_type       VARCHAR(20) NOT NULL,
    input_context    TEXT,
    output_decision  TEXT,
    llm_provider     VARCHAR(20),
    latency_ms       INT,
    triggered_at     TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_agent_type CHECK (agent_type IN ('EMPATHETIC','MEDICAL','SAFETY'))
);

-- ─── Safety Alerts ───────────────────────────────────────────────────────────
CREATE TABLE safety_alerts (
    id                     VARCHAR(36) PRIMARY KEY DEFAULT (UUID()),
    level                  VARCHAR(20) NOT NULL,
    trigger_type           VARCHAR(30) NOT NULL,
    distance_meters        FLOAT,
    message                TEXT,
    subsumption_activated  BOOLEAN     NOT NULL DEFAULT FALSE,
    response_time_ms       FLOAT,
    detected_at            TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_safety_trigger CHECK (
        trigger_type IN ('OBSTACLE','CLIFF','FALL_RISK','TRAFFIC','WEATHER','LOW_BATTERY','OWNER_EMERGENCY')
    )
);

-- ─── Indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX idx_health_user_time    ON health_records (user_id, recorded_at DESC);
CREATE INDEX idx_health_alert_level  ON health_records (alert_level);
CREATE INDEX idx_agent_logs_type     ON agent_logs (agent_type, triggered_at DESC);
CREATE INDEX idx_safety_alerts_time  ON safety_alerts (detected_at DESC);
CREATE INDEX idx_safety_subsumption  ON safety_alerts (subsumption_activated, detected_at DESC);
