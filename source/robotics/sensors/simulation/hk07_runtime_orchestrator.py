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
from simulation.navigation_agent import NavigationAgent
from simulation.hugo_action_controller_node import HugoActionControllerNode
from simulation.rppg_thermal_node import RppgThermalNode
from simulation.rtos_watchdog_simulator import RtosWatchdogSimulator
from mobile_gateway.vivo_http_mqtt_bridge import HugoPerceptionBridgeNode
from vision_sensor.hk07_sensor_fusion import Hk07SensorFusionNode
from simulation.lidar_pointcloud_sim import Hk07LidarSimulator

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
    nav_node = None
    rppg_node = None
    watchdog_node = None
    perception_bridge_node = None
    sensor_fusion_node = None
    action_controller_node = None
    lidar_node = None

    try:
        balance_node = BalanceController()
        baymax_node = BaymaxTelemetrySim()
        physics_node = Hk07PhysicsNode()
        nav_node = NavigationAgent()
        rppg_node = RppgThermalNode()
        watchdog_node = RtosWatchdogSimulator()
        perception_bridge_node = HugoPerceptionBridgeNode()
        sensor_fusion_node = Hk07SensorFusionNode()
        action_controller_node = HugoActionControllerNode()

        lidar_hardware_absent = os.getenv("LIDAR_HARDWARE_ABSENT", "true").lower() == "true"
        if not lidar_hardware_absent:
            lidar_node = Hk07LidarSimulator()
        else:
            log.info(">>> [ORCHESTRATOR]: Lidar Hardware Absent. Completely shutting down or sleeping execution thread of hk07_lidar_simulator.")

        executor = SingleThreadedExecutor()
        executor.add_node(balance_node)
        executor.add_node(baymax_node)
        executor.add_node(physics_node)
        executor.add_node(nav_node)
        executor.add_node(rppg_node)
        executor.add_node(watchdog_node)
        executor.add_node(perception_bridge_node)
        executor.add_node(sensor_fusion_node)
        executor.add_node(action_controller_node)
        if lidar_node is not None:
            executor.add_node(lidar_node)

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

        # Shutdown http server in bridge
        if perception_bridge_node is not None and getattr(perception_bridge_node, 'server', None):
            try:
                perception_bridge_node.server.shutdown()
                log.info("[PERCEPTION_BRIDGE] HTTP server shut down successfully.")
            except Exception as ex:
                log.error(f"Failed to shutdown HTTP server: {ex}")

        # Clean up remaining nodes
        nodes_to_cleanup = [
            balance_node, baymax_node, physics_node,
            nav_node, watchdog_node, perception_bridge_node,
            sensor_fusion_node, action_controller_node, lidar_node
        ]
        for node in nodes_to_cleanup:
            if node is not None:
                try:
                    node.destroy_node()
                except Exception:
                    pass

        try:
            rclpy.shutdown()
        except Exception:
            pass
        log.info("=== TEARDOWN COMPLETE ===")

if __name__ == '__main__':
    main()
