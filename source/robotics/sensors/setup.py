from setuptools import setup, find_packages
import os
from glob import glob

package_name = 'sensors'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Admin maintainer',
    maintainer_email='admin@hk07.local',
    description='ROS2 sensors simulation package for HK-07',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'hk07_physics_node = simulation.hk07_physics_node:main',
            'hugo_telemetry_sim = simulation.hugo_telemetry_sim:main',
            'hugo_action_controller_node = simulation.hugo_action_controller_node:main',
            'rppg_thermal_node = simulation.rppg_thermal_node:main',
            'rtos_watchdog_simulator = simulation.rtos_watchdog_simulator:main',
            'balance_controller = simulation.balance_controller:main',
            'navigation_agent = simulation.navigation_agent:main',
            'hk07_runtime_orchestrator = simulation.hk07_runtime_orchestrator:main',
        ],
    },
)
