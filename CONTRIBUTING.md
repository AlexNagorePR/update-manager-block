# Contributing - Update Manager

¡Gracias por querer contribuir al Update Manager! Aquí encontrarás las pautas para developers.

## Setup para Desarrollo

```bash
# Clonar el repositorio
git clone <repo-url>
cd update-manager

# Setup automático
make setup
source venv/bin/activate
make install-dev
```

## Estructura del Proyecto

```
update-manager/
├── update_manager/
│   ├── __init__.py
│   └── main.py                 # Código principal
├── tests/
│   ├── __init__.py
│   ├── conftest.py             # Fixtures compartidas
│   └── test_main.py            # Tests unitarios
├── Dockerfile
├── docker-compose.yaml
├── requirements.txt            # Dependencias runtime
├── requirements-dev.txt        # Dependencias desarrollo/testing
├── pytest.ini                  # Configuración pytest
├── setup.py                    # Configuración del paquete
├── run_tests.sh               # Script para ejecutar tests
├── Makefile                    # Comandos útiles
└── README.md                   # Documentación principal
```

## Antes de Hacer un Commit

1. **Ejecutar tests localmente:**
   ```bash
   make test-coverage
   ```

2. **Asegurar que todos los tests pasan:**
   - Los 30 tests deben marcar ✓
   - La cobertura debe ser >= 70%

3. **Verificar estilo de código:**
   ```bash
   # Si tienes flake8 instalado
   flake8 update_manager/ tests/
   ```

4. **Limpiar artifacts generados:**
   ```bash
   make clean
   ```

## Escribir Tests

Los tests están organizados por funcionalidad. Para agregar nuevos tests:

1. Agrega test methods a la clase correspondiente en `tests/test_main.py`
2. Usa el naming convention: `test_<función>_<escenario>`
3. Utiliza las fixtures de `conftest.py`

Ejemplo:
```python
def test_nueva_funcionalidad_caso_exitoso(self):
    """Descripción clara del test."""
    import update_manager.main as main
    
    # Arrange
    resultado_esperado = True
    
    # Act
    resultado = main.nueva_funcion()
    
    # Assert
    assert resultado == resultado_esperado
```

## Fixtures Disponibles

Todas las fixtures están definidas en `tests/conftest.py`:

- `mock_rclpy`: Mock del módulo rclpy
- `mock_supervisor_response`: Respuesta típica del supervisor
- `mock_lock`: Mock del lockfile
- `env_vars`: Variables de entorno necesarias
- `reset_globals`: Reset de estado global entre tests

## Checklist de Pull Request

- [ ] Todos los tests pasan: `make test`
- [ ] Cobertura >= 70%: `make test-coverage` y revisar `htmlcov/index.html`
- [ ] El código sigue las convenciones Python (PEP 8)
- [ ] Se agregaron tests para nuevas funcionalidades
- [ ] Se actualiza la documentación si es necesario
- [ ] No hay artifacts generados en el commit

## Comandos Útiles

```bash
# Tests
make test                  # Rápido
make test-verbose          # Con detalles
make test-coverage         # Con cobertura

# Limpiar
make clean                 # Elimina __pycache__, .pytest_cache, etc.

# Instalar dependencias
make install               # Runtime
make install-dev           # Para desarrollo/testing
```

## Reporte de Problemas

Si encuentras un bug:

1. Crea un test que reproduzca el problema
2. Arregla el bug
3. Verifica que el test ahora pase
4. Haz commit del test y del fix juntos

## Contacto

Para preguntas o discusiones:
- Abre un Issue en el repositorio
- Contacta al equipo de Balena

¡Gracias por contribuir! 🙌
