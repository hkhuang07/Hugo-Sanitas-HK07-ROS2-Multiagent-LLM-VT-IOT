#!/bin/sh
# ─────────────────────────────────────────────────────────────────────────────
# HK-07 Mosquitto entrypoint
# Generates the password file from $MQTT_PASSWORD at container start so that no
# plaintext broker password is ever committed to git. Also substitutes the
# bridge password placeholder (__MQTT_PASSWORD__) used by the replica config.
# ─────────────────────────────────────────────────────────────────────────────
set -e

: "${MQTT_PASSWORD:?MQTT_PASSWORD env var is required (see source/backend/.env.example)}"

SRC_CONF="/mosquitto/config/mosquitto.conf"
ACTIVE_CONF="/mosquitto/config/active.conf"
PASSWD_FILE="/mosquitto/config/passwd"

# 1. (Re)generate the password hash file for all broker accounts.
mosquitto_passwd -c -b "$PASSWD_FILE" hk07core  "$MQTT_PASSWORD"
mosquitto_passwd    -b "$PASSWD_FILE" hk07agent "$MQTT_PASSWORD"
mosquitto_passwd    -b "$PASSWD_FILE" hk07sim   "$MQTT_PASSWORD"

# mosquitto drops privileges to the `mosquitto` user after reading config, so the
# password file must be owned/readable by it (entrypoint runs as root).
chown mosquitto:mosquitto "$PASSWD_FILE" 2>/dev/null || true
chmod 0600 "$PASSWD_FILE" 2>/dev/null || true

# 2. Work on a copy so the git-tracked config bind-mount is never mutated.
cp "$SRC_CONF" "$ACTIVE_CONF"
sed -i "s|__MQTT_PASSWORD__|${MQTT_PASSWORD}|g" "$ACTIVE_CONF"

# 3. Hand off to the broker.
exec mosquitto -c "$ACTIVE_CONF"
