import os
import requests
from .models import DeviceUpdateState

SUPERVISOR_ADDRESS = os.getenv("BALENA_SUPERVISOR_ADDRESS", "http://127.0.0.1:48484")
SUPERVISOR_API_KEY = os.getenv("BALENA_SUPERVISOR_API_KEY", "")

def _headers() -> dict:
    return {
        "Authorization": f"Bearer {SUPERVISOR_API_KEY}",
        "Content-Type": "application/json",
    }

def get_device_state() -> DeviceUpdateState:
    url = f"{SUPERVISOR_ADDRESS}/v1/device"
    response = requests.get(url, headers=_headers(), timeout=5)
    response.raise_for_status()
    data = response.json()
    return DeviceUpdateState(
        update_pending=bool(data.get("update_pending", False)),
        update_downloaded=bool(data.get("update_downloaded", False)),
    )