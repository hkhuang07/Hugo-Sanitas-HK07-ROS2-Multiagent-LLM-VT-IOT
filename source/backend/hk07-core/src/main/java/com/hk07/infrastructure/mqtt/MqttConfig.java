package com.hk07.infrastructure.mqtt;

import lombok.extern.slf4j.Slf4j;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.integration.channel.DirectChannel;
import org.springframework.integration.mqtt.core.DefaultMqttPahoClientFactory;
import org.springframework.integration.mqtt.core.MqttPahoClientFactory;
import org.springframework.integration.mqtt.inbound.MqttPahoMessageDrivenChannelAdapter;
import org.springframework.integration.mqtt.outbound.MqttPahoMessageHandler;
import org.springframework.integration.mqtt.support.DefaultPahoMessageConverter;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.MessageHandler;

/**
 * MQTT Configuration — Eclipse Mosquitto Integration
 *
 * Subscribes to sensor data topics from:
 * - Wristband BLE gateway (vital signs)
 * - Wokwi ESP32 simulator (mock sensors via browser MQTT)
 * - ROS 2 bridge nodes (LiDAR, IMU data)
 *
 * Hardware optimization:
 * - maxInflight = 10 (controls in-flight message queue, prevents RAM overflow)
 * - keepAliveInterval = 30s (reduces CPU wake-up frequency)
 * - Mosquitto configured with max_queued_messages = 100
 */
@Configuration
@Slf4j
public class MqttConfig {

    @Value("${hk07.mqtt.broker-url:tcp://localhost:1883}")
    private String brokerUrl;

    @Value("${hk07.mqtt.client-id:hk07-core-backend}")
    private String clientId;

    @Value("${hk07.mqtt.username:}")
    private String username;

    @Value("${hk07.mqtt.password:}")
    private String password;

    @Bean
    public MqttPahoClientFactory mqttClientFactory() {
        DefaultMqttPahoClientFactory factory = new DefaultMqttPahoClientFactory();
        MqttConnectOptions options = new MqttConnectOptions();
        options.setServerURIs(new String[]{brokerUrl});
        options.setCleanSession(true);
        options.setKeepAliveInterval(30);    // Ping broker every 30s (saves CPU)
        options.setConnectionTimeout(10);
        options.setMaxInflight(10);          // Limit in-flight messages (saves RAM)
        options.setAutomaticReconnect(true);

        if (!username.isBlank()) {
            options.setUserName(username);
            options.setPassword(password.toCharArray());
        }

        factory.setConnectionOptions(options);
        log.info("[MQTT_CONFIG] Broker: {} | ClientId: {}", brokerUrl, clientId);
        return factory;
    }

    // ─────────── INBOUND (Subscribe) ───────────

    @Bean
    public MessageChannel mqttInboundChannel() {
        return new DirectChannel();
    }

    @Bean
    public MqttPahoMessageDrivenChannelAdapter mqttInboundAdapter() {
        MqttPahoMessageDrivenChannelAdapter adapter =
            new MqttPahoMessageDrivenChannelAdapter(
                clientId + "-sub",
                mqttClientFactory(),
                // Subscribe to all sensor and agent output topics
                "hk07/sensors/wristband/+/vitals",
                "hk07/sensors/imu/state",
                "hk07/control/subsumption/inhibit",
                "hk07/agents/+/output",
                "hk07/system/heartbeat",
                "hk07/telemetry/imu",
                "hk07/telemetry/pneumatic",
                "hk07/telemetry/sensors/tactile",
                "hk07/telemetry/actuators/joints",
                "hk07/telemetry/pmu",
                "hk07/perception/clinical",
                "hk07/telemetry/avoidance",
                "hk07/telemetry/joint_states",
                "hk07/sensors/camera/thermal_rppg",
                "hk07/telemetry/skeleton",
                "hk07/perception/biomarkers",
                "hk07/care/decision",
                // Mobile Phone Sensor Bridge topics (vivo_http_mqtt_bridge.py via WiFi Hotspot)
                "hk07/sensors/imu/target",
                "hk07/sensors/environment/state",
                "hk07/sensors/location/gps",
                "hk07/sensors/activity/metrics",
                "hk07/sensors/audio/hearing"
            );

        adapter.setCompletionTimeout(5000);
        DefaultPahoMessageConverter converter = new DefaultPahoMessageConverter();
        converter.setPayloadAsBytes(true);
        adapter.setConverter(converter);
        adapter.setQos(1);  // At-Least-Once for agent outputs; vital signs use QoS 0
        adapter.setOutputChannel(mqttInboundChannel());
        return adapter;
    }

    // ─────────── OUTBOUND (Publish) ───────────

    @Bean
    public MessageChannel mqttOutboundChannel() {
        return new DirectChannel();
    }

    @Bean
    @ServiceActivator(inputChannel = "mqttOutboundChannel")
    public MessageHandler mqttOutboundHandler() {
        MqttPahoMessageHandler handler =
            new MqttPahoMessageHandler(clientId + "-pub", mqttClientFactory());
        handler.setAsync(true);         // Non-blocking publish (Virtual Thread friendly)
        handler.setDefaultQos(1);
        handler.setDefaultTopic("hk07/control/motion/command");
        return handler;
    }

    @Bean
    public MessageChannel errorChannel() {
        return new org.springframework.integration.channel.PublishSubscribeChannel();
    }

    @Bean
    public org.springframework.integration.support.channel.HeaderChannelRegistry integrationHeaderChannelRegistry() {
        return new org.springframework.integration.channel.DefaultHeaderChannelRegistry();
    }
}
