package com.hk07.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.DatabaseMetaData;

@Component
public class DatabaseStartupLogger implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(DatabaseStartupLogger.class);

    @Autowired
    private DataSource dataSource;

    @Value("${spring.data.redis.host:127.0.0.1}")
    private String redisHost;

    @Value("${spring.data.redis.port:6379}")
    private int redisPort;

    @Value("${hk07.mqtt.broker-url:tcp://127.0.0.1:1883}")
    private String mqttBrokerUrl;

    @Override
    public void run(String... args) {
        try (Connection connection = dataSource.getConnection()) {
            DatabaseMetaData metaData = connection.getMetaData();
            String dbUrl = metaData.getURL();
            String dbUser = metaData.getUserName();
            String dbProduct = metaData.getDatabaseProductName();
            String dbVersion = metaData.getDatabaseProductVersion();
            String driverName = metaData.getDriverName();

            System.out.printf("""
                    %n╔═════════════════════════════════════════════════════════════════════╗
                    ║   DATABASE & SYSTEM UPLINK CONNECTION DETAILS                         ║
                    ╠═══════════════════════════════════════════════════════════════════════╣
                    ║   DB Type:     %-53s ║
                    ║   DB Version:  %-53s ║
                    ║   DB URL:      %-37s ║
                    ║   DB User:     %-53s ║
                    ║   DB Driver:   %-53s ║
                    ║   Redis Host:  %-53s ║
                    ║   Redis Port:  %-53d ║
                    ║   MQTT Broker: %-53s ║
                    ╚═══════════════════════════════════════════════════════════════════════╝%n
                    """,
                    dbProduct,
                    dbVersion,
                    dbUrl,
                    dbUser,
                    driverName,
                    redisHost,
                    redisPort,
                    mqttBrokerUrl
            );
        } catch (Exception e) {
            log.error("Failed to retrieve database metadata on startup", e);
        }
    }
}
