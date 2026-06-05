-- HK-07 Local Database Initialization Script
-- Configured for MySQL 8.x/9.x Environment

DROP DATABASE IF EXISTS hk07db;
CREATE DATABASE hk07db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create and grant permissions for localhost
CREATE USER IF NOT EXISTS 'hk07user'@'localhost' IDENTIFIED BY 'HK040103';
ALTER USER 'hk07user'@'localhost' IDENTIFIED BY 'HK040103';
GRANT ALL PRIVILEGES ON hk07db.* TO 'hk07user'@'localhost';

-- Create and grant permissions for 127.0.0.1 (JDBC default)
CREATE USER IF NOT EXISTS 'hk07user'@'127.0.0.1' IDENTIFIED BY 'HK040103';
ALTER USER 'hk07user'@'127.0.0.1' IDENTIFIED BY 'HK040103';
GRANT ALL PRIVILEGES ON hk07db.* TO 'hk07user'@'127.0.0.1';

FLUSH PRIVILEGES;
