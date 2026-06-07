#!/usr/bin/env python3
import sys
import logging
import rclpy
import os
import subprocess
from rclpy.executors import SingleThreadedExecutor

from simulation.balance_controller import BalanceController
from simulation.baymax_telemetry_sim import BaymaxTelemetrySim
from simulation.hk07_physics_node import Hk07PhysicsNode
from simulation.lidar_pointcloud_sim import LidarPointCloudSim
from simulation.navigation_agent import NavigationAgent
from simulation.ros2_mqtt_bridge_node import Ros2MqttBridge
from simulation.rppg_thermal_node import RppgThermalNode
from simulation.rtos_watchdog_simulator import RtosWatchdogSimulator

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("runtime_orchestrator")

def main(args=None):
    rclpy.init(args=args)
    log.info("=== INITIALIZING ROS2 PROCESS UNIFICATION: SingleThreadedExecutor ===")

    balance_node = None
    baymax_node = None
    physics_node = None
    lidar_node = None
    nav_node = None
    mqtt_node = None
    rppg_node = None
    watchdog_node = None
    fusion_process = None

    try:
        # Spawn hk07_sensor_fusion.py as a subprocess to run alongside other nodes
        orchestrator_dir = os.path.dirname(os.path.abspath(__file__))
        sensor_fusion_path = os.path.abspath(os.path.join(orchestrator_dir, "..", "vision_sensor", "hk07_sensor_fusion.py"))
        log.info(f"=== Spawning Sensor Fusion subprocess from: {sensor_fusion_path} ===")
        
        # Spawn the subprocess inheriting standard streams (no redirection)
        # to ensure X11/Wayland GUI window support
        fusion_process = subprocess.Popen(
            [sys.executable, "-u", sensor_fusion_path],
            env=os.environ
        )

        balance_node = BalanceController()
        baymax_node = BaymaxTelemetrySim()
        physics_node = Hk07PhysicsNode()
        lidar_node = LidarPointCloudSim()
        nav_node = NavigationAgent()
        mqtt_node = Ros2MqttBridge()
        rppg_node = RppgThermalNode()
        watchdog_node = RtosWatchdogSimulator()

        executor = SingleThreadedExecutor()
        executor.add_node(balance_node)
        executor.add_node(baymax_node)
        executor.add_node(physics_node)
        executor.add_node(lidar_node)
        executor.add_node(nav_node)
        executor.add_node(mqtt_node)
        executor.add_node(rppg_node)
        executor.add_node(watchdog_node)

        log.info("=== SPINNING consolidated nodes in single thread process ===")
        executor.spin()

    except KeyboardInterrupt:
        log.info("=== Process interrupted by user (KeyboardInterrupt) ===")
    except Exception as e:
        log.exception(f"Unexpected error in runtime orchestrator: {e}")
    finally:
        log.info("=== TEARDOWN: Releasing resources and shutting down ROS2 ===")
        # Release OpenCV Video Capture inside RppgThermalNode if initialized
        if rppg_node is not None:
            if getattr(rppg_node, 'cap', None) and rppg_node.cap is not None:
                try:
                    rppg_node.cap.release()
                    log.info("[rPPG_THERMAL] OpenCV video capture resource released successfully.")
                except Exception as ex:
                    log.error(f"Failed to release video capture: {ex}")
            try:
                rppg_node.destroy_node()
            except Exception:
                pass

        # Disconnect MQTT connection
        if mqtt_node is not None:
            if getattr(mqtt_node, 'mqtt_client', None) and mqtt_node.mqtt_client is not None:
                try:
                    mqtt_node.mqtt_client.disconnect()
                    log.info("[MQTT_BRIDGE] MQTT client disconnected successfully.")
                except Exception as ex:
                    log.error(f"Failed to disconnect MQTT client: {ex}")
            try:
                mqtt_node.destroy_node()
            except Exception:
                pass

        # Clean up remaining nodes
        for node in [balance_node, baymax_node, physics_node, lidar_node, nav_node, watchdog_node]:
            if node is not None:
                try:
                    node.destroy_node()
                except Exception:
                    pass

        # Terminate fusion subprocess if spawned
        if fusion_process is not None:
            try:
                log.info("=== Terminating Sensor Fusion subprocess ===")
                fusion_process.terminate()
                fusion_process.wait(timeout=5)
            except Exception as pe:
                log.error(f"Failed to cleanly terminate Sensor Fusion subprocess: {pe}")

        try:
            rclpy.shutdown()
        except Exception:
            pass
        log.info("=== TEARDOWN COMPLETE ===")

if __name__ == '__main__':
    main()
