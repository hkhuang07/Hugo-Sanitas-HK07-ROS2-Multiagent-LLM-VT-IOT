#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# HK-07 MQTT Password File Generator (manual / native use)
# Run this ONCE to generate the Mosquitto password hash file for a native
# (non-Docker) broker. The Docker stack generates this automatically via
# docker-entrypoint.sh, so you do NOT need this script for `docker compose up`.
#
# Requires: mosquitto_passwd (from the mosquitto-clients package)
# Usage:    MQTT_PASSWORD=your_password ./generate_passwd.sh
# ─────────────────────────────────────────────────────────────────────────────
set -e

: "${MQTT_PASSWORD:?Set MQTT_PASSWORD before running, e.g. MQTT_PASSWORD=secret ./generate_passwd.sh}"

PASSWD_FILE="$(dirname "$0")/passwd"

echo ">>> [HK-07] Generating Mosquitto password file..."

# Create fresh password file from the MQTT_PASSWORD env var (never hardcoded).
mosquitto_passwd -c -b "$PASSWD_FILE" hk07core  "$MQTT_PASSWORD"
mosquitto_passwd    -b "$PASSWD_FILE" hk07agent "$MQTT_PASSWORD"
mosquitto_passwd    -b "$PASSWD_FILE" hk07sim   "$MQTT_PASSWORD"

echo ">>> [HK-07] Password file created at: $PASSWD_FILE"
echo ">>> Users created: hk07core, hk07agent, hk07sim"
echo ">>> IMPORTANT: Keep this file secure and never commit to git (already in .gitignore)."
