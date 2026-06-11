-- Flyway Migration V9: Add User ID reference to Agent Logs
-- Supports session isolation and per-user audit trail separation.

ALTER TABLE agent_logs ADD COLUMN user_id VARCHAR(36);
ALTER TABLE agent_logs ADD CONSTRAINT fk_agent_logs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
