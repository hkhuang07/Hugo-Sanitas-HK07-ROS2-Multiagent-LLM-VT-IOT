/**
 * BAYMAX TELEMETRY COMPOSABLE
 * Real-time WebSocket/MQTT data ingestion for Vue 3 components
 * 
 * Usage:
 *   const { telemetry, isConnected, connect, disconnect } = useBayMaxTelemetry();
 *   onMounted(() => connect('wss://your-ws-server/telemetry'));
 */

import { ref, Ref } from 'vue';
import type { RobotTelemetry } from '../components/telemetry/types';

export function useBayMaxTelemetry() {
  const telemetry: Ref<RobotTelemetry | null> = ref(null);
  const isConnected = ref(false);
  const latencyMs = ref(0);
  let ws: WebSocket | null = null;
  let lastMessageTime = 0;

  function connect(url: string) {
    try {
      ws = new WebSocket(url);

      ws.onopen = () => {
        console.log('[TELEMETRY] Connected to server:', url);
        isConnected.value = true;
      };

      ws.onmessage = (event) => {
        const receivedTime = Date.now();
        try {
          const payload = JSON.parse(event.data);
          
          // Calculate latency (time since last message)
          if (lastMessageTime > 0) {
            latencyMs.value = receivedTime - lastMessageTime;
          }
          lastMessageTime = receivedTime;

          // Validate telemetry structure
          if (validateTelemetryPayload(payload)) {
            telemetry.value = payload;
          } else {
            console.warn('[TELEMETRY] Invalid payload structure:', payload);
          }
        } catch (e) {
          console.error('[TELEMETRY] Failed to parse message:', e);
        }
      };

      ws.onerror = (error) => {
        console.error('[TELEMETRY] WebSocket error:', error);
        isConnected.value = false;
      };

      ws.onclose = () => {
        console.log('[TELEMETRY] Connection closed');
        isConnected.value = false;
      };
    } catch (error) {
      console.error('[TELEMETRY] Failed to connect:', error);
      isConnected.value = false;
    }
  }

  function disconnect() {
    if (ws) {
      ws.close();
      ws = null;
      isConnected.value = false;
    }
  }

  function validateTelemetryPayload(payload: any): payload is RobotTelemetry {
    return (
      payload &&
      typeof payload === 'object' &&
      'messageId' in payload &&
      'sessionId' in payload &&
      'deviceId' in payload &&
      'hr' in payload &&
      'spO2' in payload &&
      'light' in payload &&
      'pressure' in payload &&
      'yaw' in payload &&
      'fallState' in payload &&
      'rawAccel' in payload &&
      'sensorStatus' in payload
    );
  }

  return {
    telemetry,
    isConnected,
    latencyMs,
    connect,
    disconnect
  };
}

export function useMQTTClient() {
  const isConnected = ref(false);
  const topics = ref<Map<string, any>>(new Map());
  let client: any = null;

  async function connect(brokerUrl: string, clientId: string = 'baymax-viewer') {
    try {
      // Requires paho-mqtt library
      // const mqtt = await import('paho-mqtt');
      // client = new mqtt.Client(brokerUrl, clientId);
      // client.onConnectionLost = onConnectionLost;
      // client.onMessageArrived = onMessageArrived;
      // client.connect({
      //   onSuccess: () => { isConnected.value = true; }
      // });

      console.warn('[MQTT] MQTT client requires paho-mqtt library. Add to package.json:');
      console.warn('npm install paho-mqtt');
    } catch (error) {
      console.error('[MQTT] Connection failed:', error);
    }
  }

  function subscribe(topic: string) {
    if (client && isConnected.value) {
      client.subscribe(topic);
      console.log('[MQTT] Subscribed to:', topic);
    }
  }

  function disconnect() {
    if (client && isConnected.value) {
      client.disconnect();
      isConnected.value = false;
    }
  }

  return {
    isConnected,
    topics,
    connect,
    subscribe,
    disconnect
  };
}
