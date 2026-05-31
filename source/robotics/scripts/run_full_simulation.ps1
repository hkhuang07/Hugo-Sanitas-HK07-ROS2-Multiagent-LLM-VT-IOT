# HK-07 Sim Controller Script for Windows PowerShell

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "   HK-07 HUGO SANITAS — INTERACTIVE SIMULATOR CLIENT     " -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "Select the simulation event to publish via MQTT:"
Write-Host "1) Normal Vitals (Heart rate: 75, SpO2: 98.5%)"
Write-Host "2) Heart Attack (Heart rate: 165, SpO2: 88.5% - SOS)"
Write-Host "3) Fall Detected (IMU Accelerometer spikes - Safety Stop)"
Write-Host "4) Front Obstacle (LiDAR < 0.5m detected - Safety Stop)"
Write-Host "5) SOS Button (Vitals Panic button pressed - SOS)"
Write-Host "6) Exit"
Write-Host "=========================================================" -ForegroundColor Cyan

$choice = Read-Host "Enter choice [1-6]"

switch ($choice) {
    "1" { python trigger_normal_vitals.py }
    "2" { python trigger_heart_attack.py }
    "3" { python trigger_fall.py }
    "4" { python trigger_obstacle.py }
    "5" { python trigger_emergency_button.py }
    "6" { Write-Host "Exiting simulator..."; exit 0 }
    Default { Write-Host "Invalid option. Exiting." -ForegroundColor Red; exit 1 }
}
