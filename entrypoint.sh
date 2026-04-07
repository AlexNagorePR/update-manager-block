#!/bin/sh
set -eu

echo "Entrypoint arrancando"
echo "Python: $(python3 --version)"
echo "Main: /app/main.py"

exec python3 -u /app/main.py