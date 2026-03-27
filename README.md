# Update Manager — Pruebas en local

Este servicio expone una API HTTP para gestionar el bloqueo y desbloqueo de actualizaciones, usando el estado publicado en ROS 2 para decidir si el robot está en modo manual.

## Requisitos

- ROS 2 instalado y configurado
- Python 3
- Dependencias Python instaladas
- Variable de entorno `UNLOCK_TOKEN` definida

## Preparación del entorno

Abrir una terminal en la carpeta del proyecto y cargar el entorno:

```bash
source /opt/ros/jazzy/setup.bash
source venv/bin/activate
export UNLOCK_TOKEN=1234
```

> Ajustar `jazzy` si se está usando otra distribución de ROS 2.

## 1. Lanzar el servicio

En una terminal, arrancar el servicio:

```bash
python3 main.py
```

Si todo va bien, deberían aparecer logs similares a estos:

```text
Arrancando update-manager
ROS2 listener iniciado
Lock adquirido en /tmp/balena/updates
Servidor HTTP escuchando en puerto 8080
```

## 2. Publicar el estado del sistema

El servicio escucha el tópico `/state` de tipo `std_msgs/msg/UInt16`.

### Publicar un estado no manual

En otra terminal:

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic pub /state std_msgs/msg/UInt16 "{data: 3}" --once
```

## 3. Consultar `/status`

En otra terminal, comprobar el estado del servicio:

```bash
curl http://localhost:8080/status
```

Respuesta esperada, por ejemplo en modo no manual:

```json
{
  "locked": true,
  "lock_path": "/tmp/balena/updates",
  "running": true,
  "robot_state": 3,
  "manual_mode": false
}
```

## 4. Probar `unlock` sin modo manual

Con el estado publicado como `3`, probar el desbloqueo:

```bash
curl -X POST http://localhost:8080/unlock \
  -H "Authorization: Bearer 1234"
```

Respuesta esperada:

```json
{
  "ok": false,
  "error": "forbidden",
  "reason": "robot_not_in_manual_mode"
}
```

## 5. Cambiar a modo manual

Publicar el estado manual:

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic pub /state std_msgs/msg/UInt16 "{data: 5}" --once
```

Comprobar de nuevo:

```bash
curl http://localhost:8080/status
```

Se debería ver:

```json
{
  "locked": true,
  "lock_path": "/tmp/balena/updates",
  "running": true,
  "robot_state": 5,
  "manual_mode": true
}
```

## 6. Probar `unlock` con modo manual

Con el robot en modo manual, probar el desbloqueo:

```bash
curl -X POST http://localhost:8080/unlock \
  -H "Authorization: Bearer 1234"
```

Respuesta esperada:

```json
{
  "ok": true,
  "locked": false
}
```

## 7. Probar `lock`

Una vez desbloqueado, volver a bloquear:

```bash
curl -X POST http://localhost:8080/lock \
  -H "Authorization: Bearer 1234"
```

Respuesta esperada:

```json
{
  "ok": true,
  "locked": true
}
```

Si ya estaba bloqueado, la respuesta esperada es:

```json
{
  "ok": false,
  "error": "already_locked",
  "locked": true
}
```

## Resumen del flujo de prueba

### Terminal 1: servicio

```bash
source /opt/ros/jazzy/setup.bash
source venv/bin/activate
export UNLOCK_TOKEN=1234
python3 main.py
```

### Terminal 2: publicación de estado

Modo no manual:

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic pub /state std_msgs/msg/UInt16 "{data: 3}" -r 1
```

Modo manual:

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic pub /state std_msgs/msg/UInt16 "{data: 5}" -r 1
```

### Terminal 3: llamadas HTTP

Consultar estado:

```bash
curl http://localhost:8080/status
```

Intentar desbloquear sin manual:

```bash
curl -X POST http://localhost:8080/unlock \
  -H "Authorization: Bearer 1234"
```

Desbloquear con manual:

```bash
curl -X POST http://localhost:8080/unlock \
  -H "Authorization: Bearer 1234"
```

Bloquear de nuevo:

```bash
curl -X POST http://localhost:8080/lock \
  -H "Authorization: Bearer 1234"
```

## Notas

- El token usado en los ejemplos es `1234`. Sustituirlo por el valor real definido en `UNLOCK_TOKEN`.
- El estado manual corresponde al valor `5`.
- El endpoint `/status` no requiere autenticación.
- Los endpoints `/lock` y `/unlock` requieren cabecera `Authorization: Bearer <token>`.