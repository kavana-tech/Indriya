"""Tab panels for the connect app."""

from .auth import build_auth_bar
from .command import build_command_ui
from .config import build_sensor_config_ui
from .dfu import build_dfu_ui
from .packet_loss import build_packet_loss_ui
from .pc_recording import build_pc_recording_ui
from .ping import build_ping_ui
from .recording import build_sd_recording_ui

__all__ = [
    "build_auth_bar",
    "build_command_ui",
    "build_sensor_config_ui",
    "build_dfu_ui",
    "build_packet_loss_ui",
    "build_pc_recording_ui",
    "build_ping_ui",
    "build_sd_recording_ui",
]
