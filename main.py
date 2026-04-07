import json
import logging
import os
import sys
import threading
import time
from urllib import request

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from rclpy.executors import ExternalShutdownException
from std_msgs.msg import UInt16
from lockfile import LockFile, AlreadyLocked, NotLocked, NotMyLock

BALENA_SUPERVISOR_ADDRESS = os.getenv("BALENA_SUPERVISOR_ADDRESS")
BALENA_SUPERVISOR_API_KEY = os.getenv("BALENA_SUPERVISOR_API_KEY")

POLL_INTERVAL = 10.0
LOCK_PATH = "/tmp/balena/updates"

SAVE_UPDATE_STATES = {
    int(x) for x in os.getenv("SAVE_UPDATE_STATES", "").split(",") if x
}

if not BALENA_SUPERVISOR_ADDRESS or not BALENA_SUPERVISOR_API_KEY:
    raise RuntimeError(
        "Error: Missing environment variables. Please set "
        "BALENA_SUPERVISOR_ADDRESS and BALENA_SUPERVISOR_API_KEY."
    )

os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)

lock = LockFile(LOCK_PATH)
state_lock = threading.Lock()
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

        self.state_sub = self.create_subscription(
            UInt16,
            "/state",
            self.state_callback,
            10,
        )

        self.update_allow_sub = self.create_subscription(
            UInt16,
            "/update_allowed",
            self.update_allowed_callback,
            10,
        )

        qos_profile = QoSProfile(
            depth=10,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )

        self.update_pending_pub = self.create_publisher(
            UInt16,
            "/update_pending",
            qos_profile,
        )

    def state_callback(self, msg: UInt16):
        global robot_state
        try:
            with state_lock:
                robot_state = int(msg.data)
                current_state = robot_state

            logger.info("Estado del robot actualizado: %s", current_state)
            evaluate_unlock_condition()
        except Exception as e:
            logger.error("Error en state_callback: %s", e)

    def update_allowed_callback(self, msg: UInt16):
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

            evaluate_unlock_condition()
        except Exception as e:
            logger.error("Error en update_allowed_callback: %s", e)

    def publish_update_pending(self, pending: bool):
        if not rclpy.ok():
            return

        try:
            msg = UInt16()
            msg.data = 1 if pending else 0
            self.update_pending_pub.publish(msg)
        except Exception as e:
            logger.warning("Error al publicar update_pending: %s", e)


def acquire_lock() -> bool:
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
        and current_state in SAVE_UPDATE_STATES
        and current_waiting
        and current_locked
    ):
        logger.info("Condición de desbloqueo cumplida, liberando lock")
        release_lock()


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

    with request.urlopen(req, timeout=5) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)

def ensure_lock_owned():
    with state_lock:
        if lock.is_locked():
            logger.info("Existe lock previo; reclamándolo para esta instancia")
            try:
                lock.break_lock()
            except Exception as e:
                logger.warning("No se pudo romper lock previo: %s", e)

        try:
            lock.acquire(timeout=0)
            logger.info("Lock adquirido por esta instancia")
            return True
        except AlreadyLocked:
            logger.info("No se pudo adquirir lock; sigue existiendo")
            return False

def start_ros2():
    rclpy.init()
    node = UpdateManagerNode()

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

    ros_thread = threading.Thread(target=spin, daemon=True)
    ros_thread.start()
    logger.info("ROS2 iniciado")
    return node, ros_thread


def main():
    global waiting_for_update, lock_released_for_update

    node, ros_thread = start_ros2()
    ensure_lock_owned()

    previous_waiting = None

    try:
        while running.is_set():
            try:
                data = fetch_device_state()

                waiting = (
                    bool(data.get("update_pending", False))
                    and bool(data.get("update_failed", False))
                )

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