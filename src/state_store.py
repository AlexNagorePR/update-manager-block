import json
import logging
from .config import STATE_FILE

def is_safe_to_update() -> bool:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return bool(data.get("safe_to_update", False))
    except FileNotFoundError:
        logging.warning("No existe state file, se asume no seguro")
        return False
    except Exception as exc:
        logging.error("Error leyendo state file: %s", exc)
        return False