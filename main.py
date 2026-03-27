import json
import logging
import os
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from lockfile import LockFile, AlreadyLocked, NotLocked, NotMyLock
from std_msgs.msg import UInt16
import rclpy
from rclpy.node import Node

LOCK_PATH = "/tmp/balena/updates"
PORT = int(os.getenv("PORT", "8080"))
UNLOCK_TOKEN = os.getenv("UNLOCK_TOKEN")

if not UNLOCK_TOKEN:
    raise RuntimeError("UNLOCK_TOKEN no está definido")

os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)

lock = LockFile(LOCK_PATH)
state_lock = threading.Lock()
running = threading.Event()
running.set()
robot_state = -1

class StateListener(Node):
    def __init__(self):
        super().__init__("state_listener")
        self.subscription = self.create_subscription(
            UInt16,
            "/state",
            self.listener_callback,
            10,
        )

    def listener_callback(self, msg: UInt16):
        global robot_state
        robot_state = msg.data
        logging.info("Estado del robot actualizado: %s", robot_state)

def start_ros2_listener():
    rclpy.init()
    node = StateListener()

    def spin_ros2():
        while running.is_set():
            rclpy.spin_once(node, timeout_sec=0.5)

    ros_thread = threading.Thread(target=spin_ros2, daemon=True)
    ros_thread.start()
    logging.info("ROS2 listener iniciado")
    return node

def acquire_lock() -> bool:
    with state_lock:
        try:
            lock.acquire(timeout=0)
            logging.info("Lock adquirido en %s", LOCK_PATH)
            return True
        except AlreadyLocked:
            logging.info("El lock ya está adquirido")
            return False

def release_lock() -> None:
    with state_lock:
        try:
            lock.break_lock()
            logging.info("Lock liberado")
        except NotLocked:
            logging.warning("El lock ya estaba liberado")
        except NotMyLock:
            logging.warning("El lock no fue adquirido por este proceso")

def is_locked() -> bool:
    with state_lock:
        return lock.is_locked()

def is_manual_mode() -> bool:
    with state_lock:
        return robot_state == 5
        
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
                    "running": running.is_set(),
                    "robot_state": robot_state,
                    "manual_mode": is_manual_mode(),
                },
            )
            return
        self._send_json(404, { "error": "not_found"})

    def do_POST(self):
        if not check_token(self):
            self._send_json(401, { "error": "unauthorized" })
            return
        
        if self.path == "/unlock":
            if not is_manual_mode():
                self._send_json(403, { "ok": False, "error": "forbidden", "reason": "robot_not_in_manual_mode" })
                return
            release_lock()
            self._send_json(200, { "ok": True, "locked": is_locked() })
            return
        
        if self.path == "/lock":
            try:
                acquire = acquire_lock()
                if not acquire:
                    self._send_json(409, { "ok": False, "error": "already_locked", "locked": True })
                    return
                self._send_json(200, { "ok": True, "locked": True })
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
        while running.is_set():
            server.handle_request()
    finally:
        server.server_close()

def handle_signal(signum, frame) -> None:
    logging.info("Señal recibida, cerrando update-manager")
    running.clear()

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    logging.info("Arrancando update-manager")

    ros2_node = start_ros2_listener()

    acquire_lock()
    logging.info("Sistema bloqueado al arrancar")
    
    try:
        serve_http()
    finally:
        release_lock()
        rclpy.shutdown()
        logging.info("Proceso finalizado")

if __name__ == "__main__":
    main()