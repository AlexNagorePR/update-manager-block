from dataclasses import dataclass

@dataclass
class DeviceUpdateState:
    update_pending: bool
    update_downloaded: bool

@dataclass
class ApprovalState:
    approved: bool
    approved_by: str | None = None
    approved_at: str | None = None