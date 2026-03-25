import os

LOCK_ON_BOOT = os.getenv("LOCK_ON_BOOT", "true").lower() == "true"
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "")
ROBOT_ID = os.getenv("ROBOT_ID", "")
STATE_FILE = os.getenv("STATE_FILE", "/data/update-state.json")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")