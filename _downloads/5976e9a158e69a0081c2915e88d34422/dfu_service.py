"""Standalone firmware-update (DFU) service.

Kept as an independent sibling of `BleService`/`CdcService` (not behind a
shared transport interface) — see the standalone-services-first preference
recorded for this codebase. DFU speaks the industry-standard MCUmgr/SMP
protocol (via the `smpclient` library) over a USB-CDC serial port that is
completely separate from the `CONFIG`/`DATA` ports `CdcService` already owns,
so there's no protocol overlap with it to unify.

Firmware side: stock Zephyr MCUboot + MCUmgr, dual-bank overwrite-only, one
signed image covering both the app core and the FLPR sensor core, exposed
over a third USB-CDC-ACM port labeled "SMP" (alongside the existing CONFIG
and DATA ports). This is the same design on both Mudra Pro and Mudra
Ultimate — see `docs/dfu.md`/`docs/dfu_process.md` in the firmware repos.

IMPORTANT: as of writing, DFU firmware only exists on the `develop` branch of
each firmware repo — the `dfu` branch of mudra_pro has no DFU support yet,
and the `dfu` branch of mudra_ultimate ships with DFU explicitly compiled
out. A device must be running a `develop`-built image (with the SMP port
present) for this service to find anything. There is also no BLE DFU
transport wired up on either product yet, so this is USB (CDC) only.
"""

from typing import Callable, List, Optional

import serial
import serial.tools.list_ports
from smpclient import SMPClient
from smpclient.generics import error, success
from smpclient.requests.image_management import ImageStatesRead, ImageStatesWrite
from smpclient.requests.os_management import EchoWrite, ResetWrite
from smpclient.transport.serial import SMPSerialTransport

MUDRA_USB_VID = 0x2FE3
MUDRA_USB_PID = 0x0001

# Matches firmware's CONFIG_UART_MCUMGR_RX_BUF_SIZE=4096 / RX_BUF_COUNT=4 (see
# docs/dfu.md) -- Zephyr's stock UART-mcumgr default (128B / 2 buffers) is
# ~7x slower over USB-CDC.
_LINE_LENGTH = 2048
_LINE_BUFFERS = 2
_MAX_FRAME_SIZE = _LINE_LENGTH * _LINE_BUFFERS
_SERIAL_TIMEOUT = 15.0
_FIRST_CHUNK_TIMEOUT = 40.0
_PORT_PROBE_TIMEOUT = 3.0


class DfuStage:
    CONNECT = "connect"
    UPLOAD = "upload"
    MARK = "mark"
    RESET = "reset"
    DONE = "done"


class DfuError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(f"[{stage}] {message}")
        self.stage = stage
        self.message = message


OnProgressCallback = Callable[[int, int], None]
OnStageCallback = Callable[[str], None]


def _make_transport() -> SMPSerialTransport:
    return SMPSerialTransport(
        max_smp_encoded_frame_size=_MAX_FRAME_SIZE,
        line_length=_LINE_LENGTH,
        line_buffers=_LINE_BUFFERS,
        timeout=_SERIAL_TIMEOUT,
    )


async def _is_smp_port(port: str) -> bool:
    """Confirm `port` answers MCUmgr's OS-group echo request."""
    client = SMPClient(_make_transport(), port, timeout_s=_PORT_PROBE_TIMEOUT)
    try:
        await client.connect(connect_timeout_s=_PORT_PROBE_TIMEOUT)
        response = await client.request(EchoWrite(d="mudra_sdk"), timeout_s=_PORT_PROBE_TIMEOUT)
        return success(response)
    except Exception:
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


class DfuService:
    """Finds a device's SMP port and drives one firmware-update session."""

    async def find_port(
        self, serial_number: Optional[str], exclude_ports: List[str]
    ) -> Optional[str]:
        """Find the device's SMP serial port: a Mudra-VID/PID port sharing
        `serial_number` that isn't one of the already-known CONFIG/DATA
        ports (`exclude_ports`), confirmed by an MCUmgr echo round-trip."""
        candidates = [
            p.device
            for p in serial.tools.list_ports.comports()
            if p.vid == MUDRA_USB_VID
            and p.pid == MUDRA_USB_PID
            and p.device not in exclude_ports
            and (serial_number is None or p.serial_number == serial_number)
        ]
        for port in candidates:
            if await _is_smp_port(port):
                return port
        return None

    async def update(
        self,
        port: str,
        image: bytes,
        *,
        on_progress: Optional[OnProgressCallback] = None,
        on_stage: Optional[OnStageCallback] = None,
    ) -> str:
        """Upload `image` to the device at `port` and stage it for boot.

        Flow: connect -> upload to slot 1 -> read back the staged image's
        hash -> mark it pending (test-swap, not confirmed) -> reset. MCUboot
        then swaps slot1 into slot0 and boots the new image on its own; there
        is no device-side "update complete" push, so the caller should
        reconnect afterward to verify the new version landed. Returns the
        staged image's version string.
        """

        def _stage(stage: str) -> None:
            if on_stage is not None:
                on_stage(stage)

        client = SMPClient(_make_transport(), port)

        _stage(DfuStage.CONNECT)
        try:
            await client.connect()
        except Exception as e:
            raise DfuError(DfuStage.CONNECT, str(e)) from e

        try:
            _stage(DfuStage.UPLOAD)
            total = len(image)
            if on_progress is not None:
                on_progress(0, total)
            try:
                async for offset in client.upload(
                    image, slot=0, first_timeout_s=_FIRST_CHUNK_TIMEOUT
                ):
                    if on_progress is not None:
                        on_progress(offset, total)
            except Exception as e:
                raise DfuError(DfuStage.UPLOAD, str(e)) from e

            _stage(DfuStage.MARK)
            states_response = await client.request(ImageStatesRead())
            if error(states_response):
                raise DfuError(DfuStage.MARK, f"could not read image state: {states_response}")
            target = next(
                (im for im in states_response.images if not im.active and im.hash), None
            )
            if target is None:
                raise DfuError(DfuStage.MARK, "no staged image found after upload")
            mark_response = await client.request(ImageStatesWrite(hash=target.hash, confirm=False))
            if error(mark_response):
                raise DfuError(DfuStage.MARK, f"device rejected the staged image: {mark_response}")

            _stage(DfuStage.RESET)
            await client.request(ResetWrite())

            _stage(DfuStage.DONE)
            return target.version
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
