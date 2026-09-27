from dataclasses import dataclass
from typing import Optional

from mudra_sdk.models.enums import MudraModel


@dataclass
class CdcDevice:
    """CDC (USB serial) device identity for a Mudra device (Pro or Ultimate).

    Both products expose two USB CDC-ACM virtual COM ports (`CONFIG` + `DATA`)
    under one composite USB device (VID `0x2FE3` / PID `0x0001` — identical on
    both, so `model` can't be inferred from USB descriptors; CdcService
    classifies it with a "TSYNC?" protocol probe on the CONFIG port instead —
    see cdc_service.py). `CdcDevice` groups the port pair together under one
    stable address so `mudra_sdk.service.cdc_service.CdcService` can track a
    device the same way `mudra_sdk.service.ble_service.BleService` tracks a
    BLE address.
    """

    address: str
    name: str
    config_port: str
    data_port: Optional[str] = None
    serial_number: Optional[str] = None
    model: MudraModel = MudraModel.PRO
