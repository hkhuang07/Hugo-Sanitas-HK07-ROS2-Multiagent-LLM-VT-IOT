#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# HK-07 MQTT Password File Generator
# Run this script ONCE to generate the Mosquitto password hash file.
# Requires: mosquitto_passwd (from mosquitto-clients package)
# ─────────────────────────────────────────────────────────────────────────────

PASSWD_FILE="$(dirname "$0")/passwd"

echo ">>> [HK-07] Generating Mosquitto password file..."

# Create fresh password file
mosquitto_passwd -c -b "$PASSWD_FILE" hk07core  hk07mqtt2026
mosquitto_passwd    -b "$PASSWD_FILE" hk07agent hk07mqtt2026
mosquitto_passwd    -b "$PASSWD_FILE" hk07sim   hk07mqtt2026

echo ">>> [HK-07] Password file created at: $PASSWD_FILE"
echo ">>> Users created: hk07core, hk07agent, hk07sim"
echo ">>> IMPORTANT: Keep this file secure and never commit to git."
