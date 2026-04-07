import json
import logging
import os
import signal
import threading
import time
from urllib import error, request

from lockfile import LockFile, AlreadyLocked, NotLocked, NotMyLock
from std_msgs.msg import UInt16
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile

LOCK_PATH = "/tmp/balena/updates"
POLL_INTERVAL = 10
BALENA_SUPERVISOR_ADDRESS = os.getenv("BALENA_SUPERVISOR_ADDRESS")
BALENA_SUPERVISOR_API_KEY = os.getenv("BALENA_SUPERVISOR_API_KEY")

UNLOCK_TOKEN = os.getenv("UNLOCK_TOKEN")
SAVE_UPDATE_STATES = {
    int(x) for x in os.getenv("SAVE_UPDATE_STATES", "").split(",") if x
    }

if not BALENA_SUPERVISOR_ADDRESS or not BALENA_SUPERVISOR_API_KEY:
    raise RuntimeError(
        "Faltan BALENA_SUPERVISOR_ADDRESS o BALENA_SUPERVISOR_API_KEY. "
        "Asegúrate de añadir la label io.balena.features.supervisor-api al servicio."
    )

if not UNLOCK_TOKEN:
    raise RuntimeError("UNLOCK_TOKEN no está definido")

os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)

lock = LockFile(LOCK_PATH)
state_lock = threading.Lock()
running = threading.Event()
running.set()
robot_state = -1
update_allowed = 0
last_update_pending = 0

logger = logging.getLogger(__name__)

class UpdateManagerNode(Node):
    def __init__(self):
        super().__init__("update_manager")
        self.state_sub = self.create_subscription(
            UInt16,
            "/state",
            self.state_callback,
            10,
        )

        self.update_allowed_sub = self.create_subscription(
            UInt16,
            "/update_allowed",
            self.update_allowed_callback,
            10,
        )

        qos_profile = QoSProfile(
            depth=10,
            durability=DurabilityPolicy.TRANSIENT_LOCAL
        )

        self.update_pending_pub = self.create_publisher(
            UInt16,
            "/update_pending",
            qos_profile
        )

    def state_callback(self, msg: UInt16):
        global robot_state
        with state_lock:
            robot_state = int(msg.data)
        logging.info("Estado del robot actualizado: %s", robot_state)
        evaluate_unlock_condition()

    def update_allowed_callback(self, msg: UInt16):
        global update_allowed
        with state_lock:
            update_allowed = int(msg.data)
        logging.info("Update allowed actualizado: %s", update_allowed)
        evaluate_unlock_condition()

    def publish_update_pending(self, pending: int):
        msg = UInt16()
        msg.data = pending
        self.update_pending_pub.publish(msg)
        logger.info("Publicado update_pending: %s", pending)

def acquire_lock() -> bool:
    with state_lock:
        try:
            lock.acquire(timeout=0)
            logging.info("Lock adquirido en %s", LOCK_PATH)
            return True
        except AlreadyLocked:
            logging.info("Lock ya adquirido por otro proceso")
            return False
        
def release_lock() -> bool:
    with state_lock:
        try:
            lock.break_lock()
            logging.info("Lock liberado")
            return True
        except NotLocked:
            logging.warning("El lock ya estaba liberado")
            return False
        except NotMyLock:
            logging.warning("El lock no fue adquirido por este proceso")
            try:
                lock.break_lock()
                logging.info("Lock liberado de forma forzada")
                return True
            except Exception:
                logger.exception("No se pudo liberar el lock de forma forzada")
                return False
            
def is_locked() -> bool:
    with state_lock:
        return lock.is_locked()
    
def evaluate_unlock_condition():
    with state_lock:
        current_state = robot_state
        current_allowed = update_allowed
        current_pending = last_update_pending
        current_locked = lock.is_locked()

        if current_allowed == 1 and current_state in SAVE_UPDATE_STATES and current_locked:
            logger.info("Condición de desbloqueo cumplida, liberando lock")
            release_lock()

def fetch_supervisor_device_state():
    url = (
        f"{BALENA_SUPERVISOR_ADDRESS}/v1/device"
        f"?apikey={BALENA_SUPERVISOR_API_KEY}"
    )
    
    req = request.Request(
        url,
        method="GET",
        headers={"Content-Type": "application/json"},
    )

    with request.urlopen(req, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"Respuesta inesperada del supervisor: HTTP {response.status}")
        body = response.read().decode("utf-8")
        return json.loads(body)
    
def supervisor_poll_loop(node: UpdateManagerNode) -> None:
    global last_update_pending

    logger.info("Polling del Supervisor iniciado, consultando cada %s segundos", POLL_INTERVAL)

    while running.is_set():
        try:
            device_state = fetch_supervisor_device_state()

            pending = 1 if bool(device_state.get("update_downloaded", False)) else 0

            with state_lock:
                previous_pending = last_update_pending
                last_update_pending = pending

            if pending != previous_pending:
                logger.info(
                    "Cambio detectado en update_downloaded: %s -> %s | device_state: %s",
                    previous_pending,
                    pending,
                    device_state
                )
                node.publish_update_pending(pending)
                evaluate_unlock_condition()

        except error.URLError as e:
            logger.error("Error de conexión al supervisor: %s", e)
        except Exception as e:
            logger.exception("Error inesperado durante la consulta al supervisor: %s", e)
        
        time.sleep(POLL_INTERVAL)

def start_ros2() -> tuple[UpdateManagerNode, threading.Thread]:
    rclpy.init()
    node = UpdateManagerNode()
    
    def spin():
        while running.is_set():
            rclpy.spin_once(node, timeout_sec=0.5)
            
    ros_thread = threading.Thread(target=spin, daemon=True)
    ros_thread.start()
    logger.info("ROS2 iniciado")
    return node, ros_thread

def handle_signal(signum, frame) -> None:
    logger.info("Señal recibida: %s, iniciando shutdown", signum)
    running.clear()

def main():
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info("Iniciando Update Manager")

    node, ros_thread = start_ros2()

    acquire_lock()
    logger.info("Sistema bloqueado al iniciar")

    poll_thread = threading.Thread(
        target=supervisor_poll_loop,
        args=(node,),
        daemon=True
    )
    poll_thread.start()

    try:
        while running.is_set():
            time.sleep(0.5)
    finally:
        running.clear()

        try:
            poll_thread.join(timeout=5)
        except Exception:
            logger.exception("Error al esperar el hilo de polling")

        try:
            ros_thread.join(timeout=5)
        except Exception:
            logger.exception("Error al esperar el hilo de ROS2")

        try:
            node.destroy_node()
        except Exception:
            logger.exception("Error al destruir el nodo ROS2")

        try:
            rclpy.shutdown()
        except Exception:
            logger.exception("Error al apagar ROS2")

        logger.info("Update Manager finalizado")

if __name__ == "__main__":
    main()