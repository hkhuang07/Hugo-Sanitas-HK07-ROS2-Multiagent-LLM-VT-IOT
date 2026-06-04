"""
Continuous 360° LiDAR mock — 10 Hz on hk07/sensors/lidar/scan

Used with Mosquitto + hk07-core + safety_agent.py for real pipeline testing.
Run: python lidar_scan_publisher.py
Optional: python lidar_scan_publisher.py --obstacle-deg 30 --obstacle-m 0.4
"""
import argparse
import json
import math
import time

import paho.mqtt.client as mqtt

BEARINGS = 360
BASE_RANGE_M = 3.0


def build_scan(obstacle_deg: int | None, obstacle_m: float) -> dict:
    ranges = []
    for deg in range(BEARINGS):
        d = BASE_RANGE_M + 0.05 * math.sin(math.radians(deg * 4))
        if obstacle_deg is not None and abs(deg - obstacle_deg) <= 8:
            d = obstacle_m
        ranges.append(round(d, 3))
    return {
        "ranges": ranges,
        "angle_min": 0.0,
        "angle_max": math.radians(359),
        "angle_increment": math.radians(1),
        "range_min": 0.1,
        "range_max": 10.0,
        "timestamp_ms": int(time.time() * 1000),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--broker", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--hz", type=float, default=10.0)
    parser.add_argument("--obstacle-deg", type=int, default=None)
    parser.add_argument("--obstacle-m", type=float, default=0.4)
    args = parser.parse_args()

    client = mqtt.Client(client_id="lidar-360-publisher", protocol=mqtt.MQTTv311)
    client.connect(args.broker, args.port, 60)
    interval = 1.0 / args.hz
    print(f">>> Publishing 360-point LiDAR @ {args.hz}Hz to hk07/sensors/lidar/scan")

    try:
        while True:
            payload = build_scan(args.obstacle_deg, args.obstacle_m)
            client.publish("hk07/sensors/lidar/scan", json.dumps(payload), qos=0)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n>>> Stopped.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
