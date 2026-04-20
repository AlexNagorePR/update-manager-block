# Update Manager para Balena

Gestor de actualizaciones para dispositivos Balena que coordina el timing de las actualizaciones de firmware mediante un sistema de locks y monitoreo de estado del robot.

## Descripción General

El Update Manager actúa como intermediario entre el Supervisor de Balena y el sistema de control del robot, asegurando que las actualizaciones de firmware solo ocurran cuando el robot está en un estado seguro. Utiliza:

- **Lock file** (`/tmp/balena/updates`) para coordinar acceso
- **ROS2** para comunicación en tiempo real  
- **Supervisor API** de Balena para detectar actualizaciones pendientes

## Requisitos

- Python 3.12+
- ROS2 Jazzy
- Docker (para despliegue en Balena)
- Balena CLI (para push a balenaCloud)

### Variables de Entorno Requeridas

```bash
BALENA_SUPERVISOR_ADDRESS=http://localhost:48484
BALENA_SUPERVISOR_API_KEY=<your-api-key>
FLE_SAFE_UPDATE_STATES=1,2,3  # Estados seguros para actualizar
```

## Instalación

### Desarrollo Local

```bash
# Crear virtual environment
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt

# Instalar dependencias de desarrollo (para tests)
pip install -r requirements-dev.txt
```

### Construcción Docker

```bash
docker build -t update-manager:latest .
```

## Ejecución

### Modo Local (Desarrollo)

```bash
source venv/bin/activate

export BALENA_SUPERVISOR_ADDRESS=http://localhost:48484
export BALENA_SUPERVISOR_API_KEY=your-key
export FLE_SAFE_UPDATE_STATES=1,2,3

python main.py
```

### Modo Docker (Balena)

```bash
balena push <app-name>
```

## Testing

### Ejecutar Tests

```bash
# Instalar dependencias de test (si no lo has hecho)
pip install -r requirements-dev.txt

# Ejecutar toda la suite
pytest

# Con output verboso
pytest -v

# Con cobertura en terminal
pytest --cov=. --cov-report=term-missing

# Generar reporte HTML de cobertura
pytest --cov=. --cov-report=html
# Abre htmlcov/index.html en el navegador
```

### Cobertura de Tests

Se incluyen **25 tests** con **71% de cobertura**:

| Clase | Tests | Descripción |
|-------|-------|-------------|
| `TestLockOperations` | 6 | Adquisición, liberación y estado de locks |
| `TestUpdateStateLogic` | 5 | Determinación de actualizaciones pendientes |
| `TestUnlockCondition` | 5 | Evaluación de condiciones de desbloqueo |
| `TestFetchDeviceState` | 2 | Obtención de estado del supervisor |
| `TestNodeCallbacks` | 4 | Callbacks de ROS2 |
| `TestEnsureLockOwned` | 3 | Seguridad de propiedad del lock |

## Servicios ROS2

### Publisher: `/update_pending`

**Tipo:** `std_msgs/Bool`  
**Frecuencia:** Variable (cuando hay cambios)

Publica el estado de actualización pendiente:
- `true` - Actualización en progreso esperando permiso
- `false` - Sin actualización pendiente

### Service: `/get_update_state`

**Tipo:** `update_manager/srv/GetUpdateState`

Permite consultar el estado actual de la actualización:

```bash
ros2 service call /get_update_state update_manager/srv/GetUpdateState
```

**Respuesta:**
```
response:
  update_pending: false
```

### Subscriber: `/state`

**Tipo:** `std_msgs/UInt16`

Estado del robot. Solo se libera el lock si el estado está en `FLE_SAFE_UPDATE_STATES`.

### Subscriber: `/update_allowed`

**Tipo:** `std_msgs/Bool`

Autorización para proceder con la actualización.

## Arquitectura

```
┌──────────────────────────────────┐
│     Update Manager Node          │
├──────────────────────────────────┤
│                                  │
│  Main Loop (cada 10s)            │
│  ├─ Fetch device state           │
│  ├─ Manage lock                  │
│  └─ Detect transitions           │
│                                  │
│  ROS2 Thread (async)             │
│  ├─ Subscribe /state             │
│  ├─ Subscribe /update_allowed    │
│  ├─ Publish /update_pending      │
│  └─ Service /get_update_state    │
│                                  │
└──────────────────────────────────┘
      ↓                    ↓
   Supervisor API      ROS2 Network
   (Balena)          (Robot System)
```

## Máquina de Estados

```
INICIALIZACIÓN
    ├─ Detecta lock previo (break_lock)
    └─ Adquiere nuevo lock
         ↓
LOCK ADQUIRIDO
    (bloqueadas actualizaciones)
         │
         ├─ Se cumplen condiciones:
         │  • update_allowed = True
         │  • robot_state ∈ SAFE_STATES
         │  • waiting_for_update = True
         │  • lock adquirido
         │
         ▼
LOCK LIBERADO
    (permitida actualización)
         │
         ├─ Update en progreso
         ├─ waiting → False (completa)
         │
         ▼
LOCK RE-ADQUIRIDO
    (ciclo nuevo)
```

## Condición de Desbloqueo

El lock se libera solo cuando **TODAS** estas condiciones son verdaderas:

```python
if (
    update_allowed                          # De /update_allowed
    and robot_state in FLE_SAFE_UPDATE_STATES  # De /state  
    and waiting_for_update                  # Del Supervisor
    and lock.is_locked()                    # Nosotros lo poseemos
):
    release_lock()
```

## Configuración

### Variables de Entorno

```bash
BALENA_SUPERVISOR_ADDRESS    # URL del Supervisor
BALENA_SUPERVISOR_API_KEY    # API key del Supervisor
FLE_SAFE_UPDATE_STATES       # Estados permitidos (ej: 1,2,3)
```

### Constantes (en main.py)

```python
POLL_INTERVAL = 10           # Segundos entre polls
LOCK_PATH = "/tmp/balena/updates"
```

## Troubleshooting

### "Lock ya existente"

El lock previo no fue liberado. **Esto es fail-safe** - actualizaciones permanecen bloqueadas.

Soluciones:
- El servicio intenta romper y re-adquirir automáticamente
- Verifica que el proceso anterior se terminó correctamente

### "Update no se libera"

Verificar que:
1. `/update_allowed` esté en `true`
2. `/state` esté en `FLE_SAFE_UPDATE_STATES`  
3. Supervisor reporte `update_pending=true` Y `update_failed=true`

```bash
# Ver estado del robot
ros2 topic echo /state

# Ver permiso de actualización
ros2 topic echo /update_allowed

# Consultar estado de actualización
ros2 service call /get_update_state update_manager/srv/GetUpdateState
```

## Logs

Formato: `YYYY-MM-DD HH:MM:SS - LEVEL - MESSAGE`

Eventos importantes:
```
2024-04-20 10:30:45 - INFO - Lock adquirido en /tmp/balena/updates
2024-04-20 10:30:45 - INFO - update_allowed cambiado: False -> True
2024-04-20 10:30:55 - INFO - Estado del robot actualizado: 1
2024-04-20 10:30:55 - INFO - Condicion de desbloqueo cumplida, liberando lock
2024-04-20 10:31:05 - INFO - Update terminada; reintentando adquirir lock
```

## Estructura del Proyecto

```
update-manager/
├── main.py                    # Aplicación principal
├── requirements.txt           # Deps de producción
├── requirements-dev.txt       # Deps de desarrollo
├── package.xml                # Configuración ROS2
├── CMakeLists.txt             # Build configuration
├── Dockerfile                 # Build para Balena
├── docker-compose.yaml        # Compose local
├── .dockerignore              # Exclusiones Docker
├── .gitignore                 # Exclusiones Git
├── srv/
│   └── GetUpdateState.srv     # Definición de servicio
└── tests/
    ├── test_main.py           # Suite de tests
    ├── conftest.py            # Fixtures
    └── README.md              # Docs de tests
```

## Thread Safety

- Todas las variables globales protegidas por `state_lock` (mutex)
- ROS2 callbacks y main loop se sincronizan correctamente
- Operaciones de lock son atómicas

## Garantías

✅ **Garantizado:**
- Lock se libera solo si se cumplen las 4 condiciones
- Re-adquisición cuando termina la actualización
- Thread-safe

⚠️ **Con fallos:**
- Si el proceso falla: lock queda huérfano (fail-safe)
- Próximo arranque: se limpia automáticamente

❌ **No garantizado:**
- Respuesta del Supervisor en 5 segundos
- Tópicos ROS2 en tiempo real
- Conectividad de red

## Desarrollo

### Añadir Tests

```python
# En tests/test_main.py
def test_mi_feature(mock_lock, env_vars):
    """Descripción del test."""
    import main
    # Tu código aquí
    assert resultado == esperado
```

Ejecutar solo uno:
```bash
pytest tests/test_main.py::test_mi_feature -v
```

## Licencia

Apache-2.0
