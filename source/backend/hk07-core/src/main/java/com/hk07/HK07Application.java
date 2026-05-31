package com.hk07;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;

/**
 * HK-07 Core Backend — Hugo Sanitas Robot Companion
 *
 * Entry point for the Spring Boot application.
 * Java 21 Virtual Threads are enabled via VirtualThreadConfig.
 * This backend serves as the central middleware hub between:
 *   - MQTT sensor streams (Wristband BLE, LiDAR mock)
 *   - Python Multi-Agent Engine (Empathetic / Medical / Safety)
 *   - Vue.js Dashboard (WebSocket + REST)
 *
 * Hardware constraint: Dell Latitude E7270 (8GB RAM, 1.6GHz dual-core)
 * JVM heap: -Xms256m -Xmx512m (enforced in pom.xml & Dockerfile)
 */
@SpringBootApplication
@EnableAsync
public class HK07Application {

    public static void main(String[] args) {
        // Print RAM warning banner for developer awareness
        long maxHeap = Runtime.getRuntime().maxMemory() / (1024 * 1024);
        System.out.printf("""
                %n╔══════════════════════════════════════════════════════╗
                ║   HUGO SANITAS HK-07 — CORE ENGINE BOOTING...        ║
                ║   JVM Max Heap: %dMB (Target: ≤512MB)               ║
                ║   Virtual Threads: ACTIVE (Java 21)                  ║
                ║   devtools: DISABLED (saves ~150MB)                  ║
                ╚══════════════════════════════════════════════════════╝%n
                """, maxHeap);

        SpringApplication.run(HK07Application.class, args);
    }
}
