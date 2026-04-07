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
from lockfile import LockFile, AlreadyLocked

BALENA_SUPERVISOR_ADDRESS = os.getenv("BALENA_SUPERVISOR_ADDRESS")
BALENA_SUPERVISOR_API_KEY = os.getenv("BALENA_SUPERVISOR_API_KEY")

POLL_INTERVAL = 10.0

LOCK_PATH = "/tmp/balena/updates"
UNLOCK_TOKEN = os.getenv("UNLOCK_TOKEN")

SAVE_UPDATE_STATES = {
    int(x) for x in os.getenv("SAVE_UPDATE_STATES", "").split(",") if x
    }

if not BALENA_SUPERVISOR_ADDRESS or not BALENA_SUPERVISOR_API_KEY:
    raise RuntimeError(
        "Error: Missing environment variables. Please set BALENA_SUPERVISOR_ADDRESS and BALENA_SUPERVISOR_API_KEY."
    )

if not UNLOCK_TOKEN:
    raise RuntimeError("UNLOCK_TOKEN no está definido")

os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)

lock = LockFile(LOCK_PATH)
state_lock = threading.Lock()
running = threading.Event()
running.set()

waiting_for_update = False
update_allowed = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
    force=True
)

logger = logging.getLogger(__name__)

class UpdateManagerNode(Node):
    def __init__(self):
        super().__init__("update_manager")
        
        self.update_allow_sub = self.create_subscription(
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
            qos_profile,
        )

    def update_allowed_callback(self, msg: UInt16):
        global update_allowed

        with state_lock:
            previous_allowed = update_allowed
            update_allowed = msg.data
            current_allowed = update_allowed

        if current_allowed != previous_allowed:
            logger.info("update_allowed cambiado: %s -> %s", previous_allowed, current_allowed)
            if current_allowed == 1:
                release_lock()
                update_allowed = False

        else:
            logger.info("update_allowed recibido sin cambio: %s", current_allowed)

    def publish_update_pending(self, pending: bool):
        msg = UInt16()
        msg.data = 1 if pending else 0
        self.update_pending_pub.publish(msg)


def acquire_lock() -> bool:
    with state_lock:
        try:
            lock.acquire(timeout=0)
            logger.info("Lock adquirido en %s", LOCK_PATH)
            return True
        except AlreadyLocked:
            logger.info("Lock ya existe")
            return False
        
def release_lock():
    with state_lock:
        try:
            lock.release()
            logger.info("Lock liberado en %s", LOCK_PATH)
        except Exception as e:
            logger.warning("Error al liberar lock: %s", e)

def fetch_device_state():
    url = (
        f"{BALENA_SUPERVISOR_ADDRESS}/v1/device"
        f"?apikey={BALENA_SUPERVISOR_API_KEY}"
    )

    req = request.Request(
        url,
        method="GET",
        headers={"Content-Type": "application/json"}
    )
    
    with request.urlopen(req, timeout=5) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)
    
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
            logger.error(f"Error en ROS2 spin thread: {e}")

    ros_thread = threading.Thread(target=spin, daemon=True)
    ros_thread.start()
    logger.info("ROS2 iniciado")
    return node, ros_thread
    
def main():
    global waiting_for_update

    node, ros_thread = start_ros2()

    acquire_lock()

    previous_waiting = None

    try:
        while True:
            try:
                data = fetch_device_state()

                waiting = (
                    bool(data.get("update_pending", False))
                    and bool(data.get("update_failed", False))
                )

                with state_lock:
                    waiting_for_update = waiting

                if waiting != previous_waiting:
                    logger.info("Waiting cambiado: %s -> %s", previous_waiting, waiting)
                    previous_waiting = waiting
                    if waiting == False and not lock.is_locked():
                        acquire_lock()
                    
                if running.is_set():
                    try:
                        node.publish_update_pending(waiting)
                    except Exception as e:
                        logger.warning(f"No se pudo publicar update_pending: {e}")
        
            except Exception as e:
                logger.error(f"Error fetching device state: {e}")
            
            time.sleep(POLL_INTERVAL)
    finally:
        # release_lock()
        running.clear()
        ros_thread.join(timeout=2)
        try:
            node.destroy_node()
            rclpy.shutdown()
        except Exception as e:
            logger.warning(f"Error durante shutdown de ROS2: {e}")
        logger.info("ROS2 detenido")

if __name__ == "__main__":
    main()