#!/bin/sh
set -eu

echo "Arrancando update-manager..."

export ROS_DOMAIN_ID="${DEV_ROS_DOMAIN_ID:-9}"
export CYCLONEDDS_NETWORK_INTERFACE="${DEV_CYCLONEDDS_NETWORK_INTERFACE:-eth0}"

export SAVE_UPDATE_STATES="${FLE_SAVE_UPDATE_STATES:-5}"

export POLL_INTERVAL="${POLL_INTERVAL:-10}"

exec python3 -u /app/main.py