import json
import logging
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from lockfile import LockFile, AlreadyLocked, NotLocked

LOCK_PATH = "/tmp/balena/updates"
PORT = int(os.getenv("PORT", "8080"))
UNLOCK_TOKEN = os.getenv("UNLOCK_TOKEN")

if not UNLOCK_TOKEN:
    raise RuntimeError("UNLOCK_TOKEN no está definido")

os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)

lock = LockFile(LOCK_PATH)
state_lock = threading.Lock()
running = True

def acquire_lock() -> None:
    with state_lock:
        try:
            lock.acquire(timeout=0)
            logging.info("Lock adquirido en %s", LOCK_PATH)
        except AlreadyLocked:
            logging.info("El lock ya está adquirido")    

def release_lock() -> None:
    with state_lock:
        try:
            lock.release()
            logging.info("Lock liberado")
        except NotLocked:
            logging.warning("El lock ya estaba liberado")
        

def is_locked() -> bool:
    with state_lock:
        return lock.is_locked()
    
def check_token(handler: BaseHTTPRequestHandler) -> bool:
    expected = f"Bearer {UNLOCK_TOKEN}"
    auth = handler.headers.get("Authorization", "")
    return auth == expected

class Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/status":
            self._send_json(
                200,
                {
                    "locked": is_locked(),
                    "lock_path": LOCK_PATH,
                    "running": running,
                },
            )
            return
        
        self._send_json(404, { "error": "not_found"})

    def do_POST(self):
        if not check_token(self):
            self._send_json(401, { "error": "unauthorized" })
            return
        
        if self.path == "/unlock":
            release_lock()
            self._send_json(200, { "ok": True, "locked": is_locked() })
            return
        
        if self.path == "/lock":
            try:
                acquire_lock()
                self._send_json(200, { "ok": True, "locked": is_locked() })
            except Exception as exc:
                logging.exception("Error adquiriendo lock %s", exc)
                self._send_json(500, { "ok": False, "error": str(exc) })
            return
        
        self._send_json(404, { "error": "not_found" })

    def log_message(self, format, *args):
        logging.info("HTTP %s", format % args)

def serve_http() -> None:
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    server.timeout=1
    logging.info("Servidor HTTP escuchando en puerto %s", PORT)

    try:
        while running:
            server.handle_request()
    finally:
        server.server_close()

def handle_signal(signum, frame) -> None:
    global running
    logging.info("Señal recibida, cerrando update-manager")
    running = False
    release_lock()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    logging.info("Arrancando update-manager")
    acquire_lock()
    
    http_thread = threading.Thread(target=serve_http, daemon=True)
    http_thread.start()

    while running:
        time.sleep(1)
    
    http_thread.join(timeout=2)
    logging.info("Proceso finalizado")

if __name__ == "__main__":
    main()