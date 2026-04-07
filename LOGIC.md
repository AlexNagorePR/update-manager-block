# Update Manager - Lógica de Funcionamiento

## Propósito

El Update Manager gestiona un archivo de lock (`/tmp/balena/updates`) para coordinar cuándo se permite hacer actualizaciones en un dispositivo Balena. Actúa como guardián que bloquea o permite las actualizaciones según el estado del robot y las condiciones configuradas.

## Arquitectura General

El sistema está dividido en dos componentes principales:

### 1. **ROS2 Node** (Asincrónico)
- Se ejecuta en un thread separado (`spin_thread`)
- Se suscribe a dos tópicos:
  - `/update_allowed` - Autorización para actualizar (0=no, 1=sí)
  - `/state` - Estado actual del robot
- Publica en `/update_pending` el estado de la actualización
- Los callbacks evalúan las condiciones de desbloqueo en tiempo real

### 2. **Main Loop** (Síncrono, cada 10 segundos)
- Consulta el Supervisor de Balena
- Detecta cambios en el estado de actualización
- Maneja la reacquisición del lock después de una actualización

## Estado del Lock: Máquina de Estados

```
┌─────────────────────────┐
│ INICIALIZATION          │
│ ensure_lock_owned()     │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ LOCK ADQUIRIDO          │
│ (Bloqueadas updates)    │
│ loop principal corriendo│
└────────────┬────────────┘
             │
             │ Se cumplen condiciones:
             │ • update_allowed == 1
             │ • robot_state ∈ SAVE_UPDATE_STATES
             │ • waiting_for_update == True
             │ • lock está adquirido
             ▼
┌─────────────────────────┐
│ LOCK LIBERADO           │
│ (Permitida update)      │
└────────────┬────────────┘
             │
             │ Update termina
             │ (waiting → False)
             ▼
┌─────────────────────────┐
│ LOCK RE-ADQUIRIDO       │
│ (Update completada)     │
└─────────────────────────┘
```

## Flujo de Ejecución Detallado

### Fase 1: Inicialización

```python
ensure_lock_owned()
```

1. **Detecta lock heredado**: Si existe un lock del proceso anterior que falló
2. **Lo rompe**: Usa `break_lock()` para forzar su liberación
3. **Adquiere nuevo lock**: Obtiene un lock fresco para esta instancia

**Decisión de diseño**: Los locks huérfanos NO se limpian automáticamente. Si el servicio falla, las actualizaciones permanecen bloqueadas (fail-safe).

### Fase 2: Loop Principal (cada 10 segundos)

```
Fetch device state
    ↓
Evalúa: waiting = update_pending AND update_failed
    ↓
Compara con estado anterior
    ↓
    ├─ waiting cambió True → False
    │  └─ Si nosotros liberamos el lock previamente
    │     └─ Re-adquiere el lock
    │
    └─ Publica estado en /update_pending
        ↓
        Evalúa condiciones de desbloqueo
```

### Fase 3: Monitoreo en Tiempo Real (ROS2 Callbacks)

Los callbacks se ejecutan de manera asincrónica cuando llegan mensajes:

#### `state_callback(robot_state)`
```
Actualiza robot_state
    ↓
Evalúa condiciones de desbloqueo
```

#### `update_allowed_callback(update_allowed)`
```
Actualiza update_allowed
    ↓
Log si cambió
    ↓
Evalúa condiciones de desbloqueo
```

### Fase 4: Evaluación de Desbloqueo

```python
evaluate_unlock_condition()
```

Se verifica si **TODAS** estas condiciones son verdaderas:

| Condición | Origen | Significado |
|-----------|--------|-------------|
| `update_allowed == 1` | `/update_allowed` | Autorizado actualizar |
| `robot_state ∈ SAVE_UPDATE_STATES` | `/state` | Estado compatible |
| `waiting_for_update == True` | Supervisor Balena | Hay update pendiente |
| `lock.is_locked()` | File system | Nosotros tenemos el lock |

**Si todas son verdaderas**: Libera el lock → Permite actualización

### Fase 5: Post-Actualización

```
waiting → False (update terminó)
    ↓
    ├─ Detecta cambio
    │
    ├─ Comprueba:
    │  • previous_waiting == True
    │  • waiting == False
    │  • Nosotros liberamos el lock
    │  • Lock no está adquirido
    │
    └─ Re-adquiere el lock
       └─ lock_released_for_update = False
```

## Variables de Estado Globales

| Variable | Tipo | Propósito |
|----------|------|----------|
| `waiting_for_update` | bool | ¿Hay actualización pendiente? |
| `update_allowed` | bool | ¿Está autorizada la actualización? |
| `robot_state` | int | Estado actual del robot |
| `lock_released_for_update` | bool | ¿Liberamos el lock para una update? |

Todas protegidas por `state_lock` (mutex).

## Thread Safety

- **`state_lock`**: Mutex que protege acceso a variables globales
- Se usa en:
  - Callbacks de ROS2
  - Funciones de lock/unlock
  - Actualización de estado
  - Evaluación de condiciones

## Manejo de Errores

### En Callbacks
```python
try:
    # Actualizar estado
    evaluate_unlock_condition()
except Exception as e:
    logger.error("Error: %s", e)
    # Continúa ejecutándose, no rompe ROS2
```

### En Loop Principal
```python
try:
    fetch_device_state()
    # Procesar datos
except Exception as e:
    logger.error("Error fetching device state: %s", e)
    # Continúa en el siguiente ciclo
```

### En ROS2 Shutdown
```python
try:
    node.destroy_node()
    rclpy.shutdown()
except Exception as e:
    logger.warning("Error durante shutdown: %s", e)
    # Continúa limpieza
```

## Configuración Requerida

### Variables de Entorno
- `BALENA_SUPERVISOR_ADDRESS`: Dirección del supervisor (ej: `http://127.0.0.1:48484`)
- `BALENA_SUPERVISOR_API_KEY`: API key para autenticación
- `SAVE_UPDATE_STATES`: Estados donde se permite actualizar (comma-separated, ej: `1,2,3`)

### Archivo de Lock
- **Ubicación**: `/tmp/balena/updates`
- **Propósito**: Coordina con otros procesos
- **Comportamiento**: Persiste entre reinicios (fail-safe)

## Garantías y Comportamientos

### ✅ Garantizada
- El lock se libera **solo** cuando se cumplen las 4 condiciones
- La re-adquisición ocurre cuando la update termina
- Thread-safe: toda la sincronización es atómica

### ⚠️ Con Fallos
- Si el proceso falla: lock queda huérfano (by design - seguridad)
- Próximo arranque: `ensure_lock_owned()` lo limpia
- Las updates permanecen bloqueadas hasta nueva autorización

### ❌ No Garantizado
- El Supervisor responda en 5 segundos
- Los tópicos ROS2 lleguen en tiempo real
- La red esté disponible

## Diagrama de Flujo Completo

```
START
  ↓
ensure_lock_owned() ─→ Adquiere lock
  ↓
Inicia ROS2 thread
  ↓
LOOP:
  ├─ Fetch device state (timeout 5s)
  ├─ Calcula: waiting = update_pending AND update_failed
  ├─ Publica en /update_pending
  ├─ Evalúa desbloqueo:
  │   Si todas condiciones → libera lock
  ├─ Detecta transición waiting True→False
  │   Si es nuestra → re-adquiere lock
  └─ Sleep 10 segundos
  
CALLBACKS (ROS2 threads):
  ├─ state_callback()
  │   └─ Evalúa desbloqueo
  └─ update_allowed_callback()
      └─ Evalúa desbloqueo

SHUTDOWN:
  ├─ Detiene main loop
  ├─ Para ROS2 thread
  ├─ Limpia nodo
  └─ END
```

## Casos de Uso

### Caso 1: Actualización Normal
```
1. Robot en estado permitido, update autorizada
2. update_pending=true, update_failed=false → waiting=false (aún no problemas)
3. update_pending=true, update_failed=true → waiting=true
4. Condiciones cumplidas → LOCK SE LIBERA
5. Updater realiza actualización
6. waiting → false (update terminó)
7. Detecta cambio, re-adquiere lock
```

### Caso 2: Robot No en Estado Permitido
```
1. waiting=true, update_allowed=true
2. Pero robot_state ∉ SAVE_UPDATE_STATES
3. Bloquea → Lock NO se libera
4. Espera a que robot cambie estado
5. Cuando entra en SAVE_UPDATE_STATES → Desbloquea
```

### Caso 3: Fallo y Reinicio
```
1. Proceso falla
2. Lock queda en /tmp/balena/updates
3. Servicio reinicia
4. ensure_lock_owned() → break_lock() + acquire()
5. Limpia y continúa
```

## Monitoreo y Debugging

### Logs Importantes
- `"Lock adquirido en /tmp/balena/updates"` - Arranque exitoso
- `"update_allowed cambiado: False -> True"` - Cambio de autorización
- `"Estado del robot actualizado: X"` - Estado cambió
- `"Condición de desbloqueo cumplida, liberando lock"` - Update permitida
- `"Update terminada; reintentando adquirir lock"` - Re-bloquea

### Comandos Útiles
```bash
# Ver si existe el lock
ls -la /tmp/balena/updates

# Ver logs del servicio
journalctl -u update-manager -f
```
