#!/bin/bash
set -e

echo "Arrancando update-manager..."

# Usamos el valor de la variable de Balena, o 'eth0' por defecto si no existe
INTERFACE=${CYCLONEDDS_NETWORK_INTERFACE:-eth0}

# Escribimos el XML dinámicamente
echo "Configurando CycloneDDS para la interfaz: $INTERFACE"

# Escribimos el XML dinámicamente
echo "<CycloneDDS>
  <Domain>
    <General>
      <Interfaces>
        <NetworkInterface name=\"$INTERFACE\" />
      </Interfaces>
    </General>
  </Domain>
</CycloneDDS>" > /root/cyclonedds.config.xml

set +u
source /opt/ros/humble/setup.bash
set -u

exec python3 -u /app/update_manager/main.py