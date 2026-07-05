
* **[WSL TERMINAL 1]: ROS2 Server Bridge (WSL2 Ubuntu Environment)**
  * **Purpose**: Establishes the primary WebSocket communication bridge network gateway operating on Port 9090. This node acts as the foundational translation layer enabling real-time bi-directional telemetry data synchronization between the ROS2 robotic domain, the Python Multi-Agent systems, and the user interface dashboard.
  * **Execution Path**: `source/robotics`
  * **Step-by-Step Commands**:
    ```bash
        cd source/robotics

	# 1. Quét sạch log tồn đọng của ROS2 để giải phóng I/O
	rm -rf ~/.ros/log/*

	source /opt/ros/humble/setup.bash

	# 2. Khởi chạy Bridge với giới hạn Log-level WARN (Chỉ báo lỗi/cảnh báo, tắt log Info rác)
	ros2 launch rosbridge_server rosbridge_websocket_launch.xml 
	# hoặc
	ros2 launch rosbridge_server rosbridge_websocket_launch.xml unregister_timeout:=5.0 call_services_in_new_thread:=true send_action_goals_in_new_thread:=true
    ```

* **[WSL TERMINAL 2]: ROS2 Sensors Orchestrator Node (WSL2 Ubuntu Environment)**
  * **Purpose**: Fires up the core consolidated robotics ingestion loop. This high-performance Python node captures raw high-frequency mobile sensor payloads from the network gateway, parses IMU quaternions, processes the non-contact rPPG facial video metrics, and computes Artificial Potential Field (APF) obstacle repulsion vectors.
  * **Execution Path**: `source/robotics`
  * **Step-by-Step Commands**:
    ```bash 
	cd source/robotics
	# 1. Dọn dẹp thư mục log của các bản build trước đó
	rm -rf log/
	source /opt/ros/humble/setup.bash

	# 2. Xây dựng lại Workspace (CHỈ CHẠY lệnh này nếu Sếp vừa thêm file mới hoặc sửa setup.py)
	colcon build --packages-select sensors --symlink-install

	source install/setup.bash

	# 3. Khởi chạy Orchestrator
	ros2 run sensors hk07_runtime_orchestrator
    ```
