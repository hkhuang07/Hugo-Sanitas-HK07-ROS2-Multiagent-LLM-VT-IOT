#!/bin/bash

# HK-07 Sim Controller Script for Linux/WSL

echo "========================================================="
echo "   HK-07 HUGO SANITAS — INTERACTIVE SIMULATOR CLIENT     "
echo "========================================================="
echo "Select the simulation event to publish via MQTT:"
echo "1) Normal Vitals (Heart rate: 75, SpO2: 98.5%)"
echo "2) Heart Attack (Heart rate: 165, SpO2: 88.5% - SOS)"
echo "3) Fall Detected (IMU Accelerometer spikes - Safety Stop)"
echo "4) Front Obstacle (LiDAR < 0.5m detected - Safety Stop)"
echo "5) SOS Button (Vitals Panic button pressed - SOS)"
echo "6) Exit"
echo "========================================================="
read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        python3 trigger_normal_vitals.py
        ;;
    2)
        python3 trigger_heart_attack.py
        ;;
    3)
        python3 trigger_fall.py
        ;;
    4)
        python3 trigger_obstacle.py
        ;;
    5)
        python3 trigger_emergency_button.py
        ;;
    6)
        echo "Exiting simulator..."
        exit 0
        ;;
    *)
        echo "Invalid option. Exiting."
        exit 1
        ;;
esac
