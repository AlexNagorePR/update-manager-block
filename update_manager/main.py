import json
import logging
import os
import sys
import threading
import time
from urllib import request

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, DurabilityPolicy, ReliabilityPolicy
from rclpy.executors import ExternalShutdownException
from std_msgs.msg import UInt16, Bool
from std_srvs.srv import Trigger
from lockfile import LockFile, AlreadyLocked, NotLocked, NotMyLock

BALENA_SUPERVISOR_ADDRESS = os.getenv("BALENA_SUPERVISOR_ADDRESS")
BALENA_SUPERVISOR_API_KEY = os.getenv("BALENA_SUPERVISOR_API_KEY")

POLL_INTERVAL = 10
LOCK_PATH = "/tmp/balena/updates"

SAFE_UPDATE_STATES = {
    int(x) for x in os.getenv("FLE_SAFE_UPDATE_STATES", "").split(",") if x
}

if not BALENA_SUPERVISOR_ADDRESS or not BALENA_SUPERVISOR_API_KEY:
    raise RuntimeError(
        "Error: Missing environment variables. Please set "
        "BALENA_SUPERVISOR_ADDRESS and BALENA_SUPERVISOR_API_KEY."
    )

os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)

lock = LockFile(LOCK_PATH)
state_lock = threading.RLock()  # RLock para permitir múltiples adquisiciones del mismo thread
running = threading.Event()
running.set()

waiting_for_update = False
update_allowed = False
robot_state = -1
lock_released_for_update = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)


class UpdateManagerNode(Node):
    def __init__(self):
        super().__init__("update_manager")
        logger.info("UpdateManagerNode inicializado")

        logger.info("Creando subscriber /state (UInt16)")
        self.state_sub = self.create_subscription(
            UInt16,
            "/state",
            self.state_callback,
            10,
        )
        logger.info("Subscriber /state creado exitosamente")

        logger.info("Creando subscriber /update_allowed (Bool)")
        self.update_allow_sub = self.create_subscription(
            Bool,
            "/update_allowed",
            self.update_allowed_callback,
            10,
        )
        logger.info("Subscriber /update_allowed creado exitosamente")

        logger.info("Configurando QoS profile")
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
        )
        logger.info("QoS profile configurado")

        logger.info("Creando publisher /update_pending (Bool)")
        self.update_pending_pub = self.create_publisher(
            Bool,
            "/update_pending",
            qos_profile,
        )
        logger.info("Publisher /update_pending creado exitosamente")

        logger.info("Creando servicio /get_update_state (std_srvs/Trigger)")
        self.get_update_state_srv = self.create_service(
            Trigger,
            "/get_update_state",
            self.get_update_state_callback,
        )
        logger.info("Servicio /get_update_state disponible (std_srvs/Trigger)")

    def state_callback(self, msg: UInt16):
        global robot_state
        try:
            with state_lock:
                robot_state = int(msg.data)
                current_state = robot_state

            logger.info("Estado del robot actualizado: %s", current_state)
        except Exception as e:
            logger.error("Error en state_callback: %s", e)

    def update_allowed_callback(self, msg: Bool):
        global update_allowed
        try:
            with state_lock:
                previous_allowed = update_allowed
                update_allowed = bool(msg.data)
                current_allowed = update_allowed

            if current_allowed != previous_allowed:
                logger.info(
                    "update_allowed cambiado: %s -> %s",
                    previous_allowed,
                    current_allowed,
                )
            else:
                logger.info("update_allowed recibido sin cambio: %s", current_allowed)

        except Exception as e:
            logger.error("Error en update_allowed_callback: %s", e)

    def publish_update_pending(self, pending: bool):
        if not rclpy.ok():
            return

        try:
            msg = Bool()
            msg.data = pending
            self.update_pending_pub.publish(msg)
        except Exception as e:
            logger.warning("Error al publicar update_pending: %s", e)

    def get_update_state_callback(self, request, response):
        """Service callback to query the current update pending state using std_srvs/Trigger."""
        logger.info("Llamada al servicio /get_update_state recibida")
        try:
            with state_lock:
                pending = waiting_for_update
            
            response.success = pending
            response.message = "Update pending" if pending else "No update pending"
            logger.info(
                "Servicio /get_update_state respondido: pending=%s", 
                pending
            )
        except Exception as e:
            logger.error("Error en get_update_state_callback: %s", e)
            response.success = False
            response.message = "Error retrieving update state"
        
        return response

def acquire_lock() -> bool:
    logger.info("Intentando adquirir lock en %s", LOCK_PATH)
    with state_lock:
        try:
            lock.acquire(timeout=0)
            logger.info("Lock adquirido en %s", LOCK_PATH)
            return True
        except AlreadyLocked:
            logger.info("Lock ya existente")
            return False


def release_lock() -> bool:
    global lock_released_for_update

    with state_lock:
        try:
            lock.release()
            lock_released_for_update = True
            logger.info("Lock liberado en %s", LOCK_PATH)
            return True
        except NotLocked:
            logger.info("El lock ya estaba liberado")
            return False
        except NotMyLock:
            logger.warning("El lock no pertenece a este proceso")
            return False
        except Exception as e:
            logger.warning("Error al liberar lock: %s", e)
            return False


def is_locked() -> bool:
    try:
        return lock.is_locked()
    except Exception:
        return False


def evaluate_unlock_condition():
    with state_lock:
        current_state = robot_state
        current_allowed = update_allowed
        current_waiting = waiting_for_update
        current_locked = lock.is_locked()

    if (
        current_allowed
        and current_state in SAFE_UPDATE_STATES
        and current_waiting
        and current_locked
    ):
        logger.info("Condicion de desbloqueo cumplida, liberando lock")
        if release_lock():
            notify_supervisor_update_allowed()

def fetch_device_state():
    url = (
        f"{BALENA_SUPERVISOR_ADDRESS}/v1/device"
        f"?apikey={BALENA_SUPERVISOR_API_KEY}"
    )

    req = request.Request(
        url,
        method="GET",
        headers={"Content-Type": "application/json"},
    )

    try:
        with request.urlopen(req, timeout=5) as response:
            body = response.read().decode("utf-8")
            
            if not body:
                logger.warning("Respuesta vacía del supervisor en /v1/device")
                return {}
            
            logger.debug("Respuesta del supervisor: %s", body)
            return json.loads(body)
    except json.JSONDecodeError as e:
        logger.error("Error parsing JSON de respuesta del supervisor: %s (contenido: %s)", e, body if body else "vacío")
        raise
    except Exception as e:
        logger.error("Error fetching device state: %s", e)
        raise

def ensure_lock_owned():
    logger.info("Asegurando propiedad del lock en %s", LOCK_PATH)
    with state_lock:
        if lock.is_locked():
            logger.info("Existe lock previo; reclamandolo para esta instancia")
            try:
                lock.break_lock()
            except Exception as e:
                logger.warning("No se pudo romper lock previo: %s", e)

        return acquire_lock()
    
def notify_supervisor_update_allowed():
    logger.info("Solicitando actualizacion a traves del supervisor")
    url = (
        f"{BALENA_SUPERVISOR_ADDRESS}/v1/update"
        f"?apikey={BALENA_SUPERVISOR_API_KEY}"
    )

    body = json.dumps({"force": False, "cancel": True}).encode("utf-8")
    
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with request.urlopen(req, timeout=5) as response:
            response_body = response.read().decode("utf-8")
            result = json.loads(response_body)
            logger.info("Respuesta del supervisor: %s", result)
            return result
    except Exception as e:
        logger.error("Error al notificar al supervisor: %s", e)
        raise
    
def start_ros2():
    logger.info("Inicializando ROS2...")
    try:
        rclpy.init()
        logger.info("rclpy.init() completado")
    except Exception as e:
        logger.error("Error en rclpy.init(): %s", e)
        raise
    
    logger.info("Creando nodo UpdateManagerNode...")
    try:
        node = UpdateManagerNode()
        logger.info("UpdateManagerNode creado exitosamente")
    except Exception as e:
        logger.error("Error al crear UpdateManagerNode: %s", e)
        raise

    def spin():
        try:
            while running.is_set():
                try:
                    rclpy.spin_once(node, timeout_sec=0.1)
                except ExternalShutdownException:
                    logger.debug("ROS2 external shutdown detectado en spin thread")
                    break
        except Exception as e:
            logger.error("Error en ROS2 spin thread: %s", e)

    logger.info("Iniciando thread de spin de ROS2...")
    ros_thread = threading.Thread(target=spin, daemon=True)
    ros_thread.start()
    logger.info("ROS2 iniciado exitosamente")
    return node, ros_thread

def is_waiting_for_update(device_state: dict) -> bool:
    """
    Consideramos que hay una actualización pendiente de aplicación cuando
    el supervisor reporta simultáneamente update_pending y update_failed.
    Esta interpretación está basada en el comportamiento observado del
    supervisor en este sistema.
    """
    return (
        bool(device_state.get("update_pending", False))
        and bool(device_state.get("update_failed", False))
    )

def main():
    global waiting_for_update, lock_released_for_update, update_allowed

    logger.info("=== INICIANDO UPDATE MANAGER ===")
    
    logger.info("Paso 1: Iniciando ROS2")
    node, ros_thread = start_ros2()
    logger.info("Paso 1: ROS2 iniciado exitosamente")
    
    logger.info("Paso 2: Asegurando propiedad del lock")
    ensure_lock_owned()
    logger.info("Paso 2: Lock asegurado")

    previous_waiting = None

    try:
        logger.info("Paso 3: Iniciando loop principal")
        while running.is_set():
            try:
                data = fetch_device_state()

                waiting = is_waiting_for_update(data)

                with state_lock:
                    waiting_for_update = waiting
                    current_lock_released = lock_released_for_update

                if waiting != previous_waiting:
                    logger.info("Waiting cambiado: %s -> %s", previous_waiting, waiting)

                    if (
                        previous_waiting == True
                        and waiting == False
                        and current_lock_released
                        and not is_locked()
                    ):
                        logger.info("Update terminada; reintentando adquirir lock")
                        acquired = acquire_lock()
                        if acquired:
                            with state_lock:
                                lock_released_for_update = False
                                update_allowed = False
                            logger.info("update_allowed reseteado a %s", update_allowed)

                    previous_waiting = waiting

                if running.is_set():
                    try:
                        node.publish_update_pending(waiting)
                    except Exception as e:
                        logger.warning("No se pudo publicar update_pending: %s", e)

                evaluate_unlock_condition()

            except Exception as e:
                logger.error("Error fetching device state: %s", e)

            time.sleep(POLL_INTERVAL)

    finally:
        logger.info("Shutdown iniciado")
        running.clear()
        ros_thread.join(timeout=2)
        try:
            node.destroy_node()
            rclpy.shutdown()
        except Exception as e:
            logger.warning("Error durante shutdown de ROS2: %s", e)
        logger.info("ROS2 detenido")


if __name__ == "__main__":
    main()