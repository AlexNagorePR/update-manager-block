# Tests

Suite completa de tests para el update-manager.

## Instalación

Instala las dependencias de desarrollo:

```bash
pip install -r requirements-dev.txt
```

## Ejecutar tests

### Todos los tests
```bash
pytest
```

### Tests con salida verbosa
```bash
pytest -v
```

### Tests con cobertura
```bash
pytest --cov=. --cov-report=term-missing
```

### Tests con reporte HTML
```bash
pytest --cov=. --cov-report=html
# Abre htmlcov/index.html en el navegador
```

### Tests específicos
```bash
# Una clase de test
pytest tests/test_main.py::TestLockOperations

# Un test específico
pytest tests/test_main.py::TestLockOperations::test_acquire_lock_success
```

### Usar script automatizado
```bash
chmod +x run_tests.sh
./run_tests.sh
```

## Cobertura de tests

Los tests cubren:

### TestLockOperations
- Adquisición exitosa de lock
- Manejo de lock ya existente
- Liberación exitosa de lock
- Manejo de lock no poseído
- Verificación de estado del lock

### TestUpdateStateLogic
- Determinación de actualización pendiente
- Diferentes combinaciones de flags de supervisor
- Manejo de campos faltantes

### TestUnlockCondition
- Evaluación correcta de condiciones de desbloqueo
- Validación de cada criterio individualmente
- Casos edge con estados no seguros

### TestFetchDeviceState
- Obtención exitosa del estado del dispositivo
- Inclusión correcta de credenciales API
- Parseo de respuestas JSON

### TestNodeCallbacks
- Callback de estado (robot state)
- Callback de actualización permitida
- Callback del servicio de consulta
- Publicación de estado pendiente

### TestEnsureLockOwned
- Adquisición inicial de lock
- Ruptura de locks existentes
- Manejo de fallos en adquisición

## Estructura de tests

- `conftest.py`: Fixtures compartidas y configuración común
- `test_main.py`: Tests principales del módulo

### Fixtures disponibles
- `mock_rclpy`: Mock de módulo rclpy
- `mock_supervisor_response`: Respuesta típica del supervisor
- `mock_lock`: Mock de lockfile
- `env_vars`: Variables de entorno requeridas
- `reset_globals`: Reset de estado global entre tests
