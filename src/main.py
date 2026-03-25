import logging
import time

from .config import LOCK_ON_BOOT, POLL_INTERVAL_SECONDS, LOG_LEVEL
from .lock_manager import acquire_lock, release_lock, is_locked
from .supervisor_client import get_device_state
from .backend_client import notify_pending_if_needed, get_approval
from .state_store import is_safe_to_update

def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

def main() -> None:
    setup_logging()
    logging.info("Iniciando update-manager")

    if LOCK_ON_BOOT:
        acquire_lock()

    while True:
        try:
            device_state = get_device_state()
            update_pending = device_state.update_pending or device_state.update_downloaded

            if not update_pending:
                if not is_locked():
                    acquire_lock()
                logging.info("Sin update pendiente, lock mantenido")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            notify_pending_if_needed(
                update_pending=device_state.update_pending,
                update_downloaded=device_state.update_downloaded,
            )

            approval = get_approval()
            safe_to_update = is_safe_to_update()

            logging.info(
                "Update pendiente=%s approved=%s safe=%s",
                update_pending,
                approval.approved,
                safe_to_update,
            )

            if approval.approved and safe_to_update:
                if is_locked():
                    release_lock()
                logging.info("Unlock realizado, balena puede aplicar la actualización")
            else:
                if not is_locked():
                    acquire_lock()

            time.sleep(POLL_INTERVAL_SECONDS)

        except Exception as exc:
            logging.exception("Error en bucle principal: %s", exc)
            if not is_locked():
                acquire_lock()
            time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()