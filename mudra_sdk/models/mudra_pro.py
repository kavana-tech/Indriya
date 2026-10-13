"""MudraPro — Mudra Pro device (3-channel EMG).

See mudra_device.py's MudraDevice for shared transport/status-parsing
plumbing common to both hardware models; this file only adds what's
Pro-specific.
"""

from mudra_sdk.models.enums import MudraModel, ProFirmwareCommand, ProEMGODR
from mudra_sdk.models.mudra_device import MudraDevice


class MudraPro(MudraDevice):
    """Mudra Pro (3-channel EMG). The packet-loss test-mode commands
    (set_*_test_mode) are shared with Mudra Ultimate and live on MudraDevice."""

    MODEL = MudraModel.PRO
    EMG_CHANNEL_COUNT = 3
    EMG_ODR_ENUM = ProEMGODR
    CMD = ProFirmwareCommand
