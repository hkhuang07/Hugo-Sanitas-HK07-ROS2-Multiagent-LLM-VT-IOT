-- Flyway Migration V6: Extend llm_provider length in agent_logs
-- Project: Hugo Sanitas HK-07
-- Version: 1.0.0-ALPHA

ALTER TABLE agent_logs MODIFY COLUMN llm_provider VARCHAR(100);
