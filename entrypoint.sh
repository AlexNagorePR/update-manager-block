#!/bin/bash
set -e

echo "Arrancando update-manager..."

echo "Variables recibidas:"
echo "CYCLONEDDS_NETWORK_INTERFACE=${CYCLONEDDS_NETWORK_INTERFACE:-<no definida>}"
echo "ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-<no definida>}"

# ============================================================================
# ROS_DOMAIN_ID
# ============================================================================

if [ -n "${ROS_DOMAIN_ID:-}" ]; then
  export ROS_DOMAIN_ID="$ROS_DOMAIN_ID"
fi

if [ -z "${ROS_DOMAIN_ID:-}" ]; then
  echo "ERROR: ROS_DOMAIN_ID no está definido."
  echo "Define ROS_DOMAIN_ID en BalenaCloud con un número entero, por ejemplo 0, 1, 10, 42."
  exit 1
fi

if ! [[ "$ROS_DOMAIN_ID" =~ ^[0-9]+$ ]]; then
  echo "ERROR: ROS_DOMAIN_ID debe ser un número entero."
  echo "Valor recibido: '$ROS_DOMAIN_ID'"
  exit 1
fi

echo "ROS_DOMAIN_ID configurado como: $ROS_DOMAIN_ID"

# ============================================================================
# CycloneDDS network interface
# ============================================================================

INTERFACE="${CYCLONEDDS_NETWORK_INTERFACE:-}"

echo "Interfaces disponibles dentro del contenedor:"
ls /sys/class/net || true

if [ -z "$INTERFACE" ]; then
  echo "ERROR: CYCLONEDDS_NETWORK_INTERFACE no está definida."
  exit 1
fi

if [ ! -d "/sys/class/net/$INTERFACE" ]; then
  echo "ERROR: La interfaz '$INTERFACE' no existe dentro del contenedor."
  echo "Interfaces disponibles:"
  ls /sys/class/net || true
  exit 1
fi

echo "Configurando CycloneDDS para la interfaz: $INTERFACE"

cat > /root/cyclonedds.config.xml <<EOF
<CycloneDDS>
  <Domain>
    <General>
      <Interfaces>
        <NetworkInterface name="$INTERFACE" />
      </Interfaces>
    </General>
  </Domain>
</CycloneDDS>
EOF

export CYCLONEDDS_URI="file:///root/cyclonedds.config.xml"

echo "CYCLONEDDS_URI=$CYCLONEDDS_URI"

# ============================================================================
# ROS2 INITIALIZATION
# ============================================================================

set +u
source /opt/ros/humble/setup.bash
set -u

# ============================================================================
# START APPLICATION
# ============================================================================

exec python3 -u /app/update_manager/main.py