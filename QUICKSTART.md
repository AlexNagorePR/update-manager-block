# Quick Start - Update Manager

¡Bienvenido! Aquí encontrarás las instrucciones más simples para empezar.

## 1️⃣ Instalación del Entorno (Primera Vez)

```bash
# Clonar o descargar el repositorio
cd update-manager

# Configurar el ambiente de desarrollo automáticamente
make setup

# Activar el virtual environment
source venv/bin/activate

# Instalar todas las dependencias
make install-dev
```

## 2️⃣ Ejecutar los Tests

**La forma más fácil:**

```bash
make test-coverage
```

Esto:
- ✓ Instala dependencias automáticamente si es necesario
- ✓ Ejecuta todos los 30 tests
- ✓ Genera un reporte de cobertura en `htmlcov/index.html`
- ✓ Muestra los resultados en la terminal

**Otras opciones rápidas:**

```bash
make test              # Ejecutar tests simples
make test-verbose      # Tests con más detalles
make clean             # Limpiar archivos generados
```

## 3️⃣ Ver los Resultados

Después de `make test-coverage`, abre el reporte de cobertura:

```bash
# En Linux/Mac
open htmlcov/index.html

# O desde tu navegador
# Navega a: htmlcov/index.html
```

## 4️⃣ Desarrollo

Para trabajar en el código:

```bash
# Asegúrate de estar en el venv
source venv/bin/activate

# Ejecutar tests mientras trabajas
make test

# O para más detalles
make test-verbose
```

## ❓ Ayuda

Para ver todos los comandos disponibles:

```bash
make help
```

## 📋 Requisitos del Sistema

- Python 3.12+
- pip
- make (incluido en Linux/Mac, o instala en Windows)

## 🐛 Solución de Problemas

### Error: "command not found: make"
- **Linux**: `sudo apt-get install build-essential`
- **Mac**: Ya debería estar instalado
- **Windows**: Instala [GNU Make for Windows](http://gnuwin32.sourceforge.net/packages/make.htm)

### Error: "No module named pytest"
- Ejecuta: `make install-dev`

### Tests se quedan colgados
- Limpia el cache: `make clean`
- Intenta de nuevo: `make test`

## 🎯 Flujo Típico

```bash
# Primera vez
make setup
source venv/bin/activate
make install-dev

# Todos los días (o cada sesión)
source venv/bin/activate
make test-coverage
```

¡Listo! Ya estás ejecutando los tests. 🎉
