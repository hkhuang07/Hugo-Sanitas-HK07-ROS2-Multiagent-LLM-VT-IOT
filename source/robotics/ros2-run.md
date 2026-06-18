
* **[WSL TERMINAL 1]: ROS2 Server Bridge (WSL2 Ubuntu Environment)**
  * **Purpose**: Establishes the primary WebSocket communication bridge network gateway operating on Port 9090. This node acts as the foundational translation layer enabling real-time bi-directional telemetry data synchronization between the ROS2 robotic domain, the Python Multi-Agent systems, and the user interface dashboard.
  * **Execution Path**: `source/robotics`
  * **Step-by-Step Commands**:
    ```bash
    cd source/robotics
    source /opt/ros/humble/setup.bash
    ros2 launch rosbridge_server rosbridge_websocket_launch.xml
    ```

* **[WSL TERMINAL 2]: ROS2 Sensors Orchestrator Node (WSL2 Ubuntu Environment)**
  * **Purpose**: Fires up the core consolidated robotics ingestion loop. This high-performance Python node captures raw high-frequency mobile sensor payloads from the network gateway, parses IMU quaternions, processes the non-contact rPPG facial video metrics, and computes Artificial Potential Field (APF) obstacle repulsion vectors.
  * **Execution Path**: `source/robotics`
  * **Step-by-Step Commands**:
    ```bash
    cd source/robotics
    source /opt/ros/humble/setup.bash
    colcon build --packages-select sensors --symlink-install
    source install/setup.bash
    ros2 run sensors hk07_runtime_orchestrator
    ```