import fcntl
import logging

LOCK_PATH = "/tmp/balena/updates.lock"
_lock_file = None

def acquire_lock() -> None:
    global _lock_file
    if _lock_file is not None:
        return
    _lock_file = open(LOCK_PATH, "w")
    fcntl.flock(_lock_file, fcntl.LOCK_EX)
    logging.info("Update lock adquirido")

def release_lock() -> None:
    global _lock_file
    if _lock_file is None:
        return
    fcntl.flock(_lock_file, fcntl.LOCK_UN)
    _lock_file.close()
    _lock_file = None
    logging.info("Update lock liberado")

def is_locked() -> bool:
    return _lock_file is not None