from ctypes import (
    POINTER,
    c_float,
    c_int,
    c_void_p,
    c_char_p,
    c_uint8,
    c_uint16,
    c_uint64,
    c_int32,
    c_size_t,
    Structure,
    c_char,
)
import ctypes
from typing import Callable, List, Optional, Tuple
from mudra_sdk.models.enums import RecordingDataType
import mudra_sdk.models.mudra as mudraModule


OnChargingStateChangedCallback = Callable[[bool], None]
OnBatteryLevelChangedCallback = Callable[[int], None]
OnEmgReadyCallback = Callable[[int, List[float], int, float], None]
OnImuReadyCallback = Callable[[int, List[float], int, float], None]
OnPpgReadyCallback = Callable[[int, List[float], int, float], None]

ComputationHandle = c_void_p
OnRawDataCallback = Callable[[int, List[float], int, float], None]
OnRawDataCallbackC = ctypes.CFUNCTYPE(None, c_uint64, POINTER(c_float), c_int, c_int, c_float)


class ByteBuffer(Structure):
    _fields_ = [
        ("data", POINTER(c_uint8)),
        ("length", c_size_t),
    ]


class ComputationWrapper:
    _native_lib = None
    
    def __init__(self):
        self._ensure_native_lib_loaded()
        self._initialize_native_lib()
        self._emg_callback_ref = None
        self._imu_h_callback_ref = None
        self._imu_f_callback_ref = None
        self._ppg_callback_ref = None

        self._handle = ComputationWrapper._native_lib.create_computation()
        if not self._handle:
            raise RuntimeError("Failed to create computation")

    @classmethod
    def _ensure_native_lib_loaded(cls):
        if cls._native_lib is None:
            cls._native_lib = mudraModule.Mudra().get_native_library()
        if cls._native_lib is None:
            raise RuntimeError("Native library is not loaded")

    @classmethod
    def _initialize_native_lib(cls):
        lib = cls._native_lib
        
        lib.create_computation.argtypes = []
        lib.create_computation.restype = ComputationHandle

        lib.handle_data.argtypes = [ComputationHandle, POINTER(c_uint8), ctypes.c_size_t]
        lib.handle_data.restype = None

        lib.is_data_needed.argtypes = [ComputationHandle, c_int]
        lib.is_data_needed.restype = ctypes.c_bool

        lib.set_on_emg_ready.argtypes = [ComputationHandle, OnRawDataCallbackC]
        lib.set_on_emg_ready.restype = None

        lib.set_on_imu_h_ready.argtypes = [ComputationHandle, OnRawDataCallbackC]
        lib.set_on_imu_h_ready.restype = None

        lib.set_on_imu_f_ready.argtypes = [ComputationHandle, OnRawDataCallbackC]
        lib.set_on_imu_f_ready.restype = None

        lib.set_on_ppg_ready.argtypes = [ComputationHandle, OnRawDataCallbackC]
        lib.set_on_ppg_ready.restype = None

        lib.set_parser_emg_resolution.argtypes = [ComputationHandle, c_uint8]
        lib.set_parser_emg_resolution.restype = None

        lib.set_parser_emg_channel_count.argtypes = [ComputationHandle, c_uint8]
        lib.set_parser_emg_channel_count.restype = None

        lib.set_parser_ppg_channel_count.argtypes = [ComputationHandle, c_uint8]
        lib.set_parser_ppg_channel_count.restype = None

        lib.set_parser_imu_h_ranges.argtypes = [ComputationHandle, c_uint8, c_uint16]
        lib.set_parser_imu_h_ranges.restype = None

        lib.set_parser_imu_f_ranges.argtypes = [ComputationHandle, c_uint8, c_uint16]
        lib.set_parser_imu_f_ranges.restype = None

        lib.get_pro_firmware_command.argtypes = [c_int32]
        lib.get_pro_firmware_command.restype = ByteBuffer

        lib.get_ultimate_firmware_command.argtypes = [c_int32]
        lib.get_ultimate_firmware_command.restype = ByteBuffer

        lib.free_firmware_buffer.argtypes = [POINTER(c_uint8)]
        lib.free_firmware_buffer.restype = None

        lib.get_pro_cdc_command_token.argtypes = [c_int32, ctypes.c_bool]
        lib.get_pro_cdc_command_token.restype = ByteBuffer

        lib.get_ultimate_cdc_command_token.argtypes = [c_int32, ctypes.c_bool]
        lib.get_ultimate_cdc_command_token.restype = ByteBuffer

        lib.free_cdc_token.argtypes = [POINTER(c_uint8)]
        lib.free_cdc_token.restype = None

        ### ----------------------- Data Recorder Functions ----------------------- ###

        lib.enable_recording.argtypes = [ComputationHandle]
        lib.enable_recording.restype = None

        lib.disable_recording.argtypes = [ComputationHandle]
        lib.disable_recording.restype = None

        lib.start_recording.argtypes = [ComputationHandle, POINTER(c_int), c_int, c_int]
        lib.start_recording.restype = ctypes.c_bool

        lib.add_video.argtypes = [ComputationHandle, c_char_p, c_char_p]
        lib.add_video.restype = None

        lib.stop_recording.argtypes = [ComputationHandle]
        lib.stop_recording.restype = None

        lib.is_recording_enabled.argtypes = [ComputationHandle]
        lib.is_recording_enabled.restype = ctypes.c_bool

        lib.record_event.argtypes = [ComputationHandle, c_int, c_char_p]
        lib.record_event.restype = None

        lib.get_json_recording.argtypes = [ComputationHandle]
        lib.get_json_recording.restype = c_char_p

        lib.fill_json_buffer.argtypes = [ComputationHandle]
        lib.fill_json_buffer.restype = ctypes.c_void_p

        lib.free_shared_buffer.argtypes = [ctypes.c_void_p]
        lib.free_shared_buffer.restype = None

        ### ----------------------- Packet-Loss Stats Functions ----------------------- ###

        lib.reset_packet_loss_stats.argtypes = [ComputationHandle, c_int]
        lib.reset_packet_loss_stats.restype = None

        lib.get_packet_loss_stats.argtypes = [
            ComputationHandle, c_int, POINTER(c_uint64), POINTER(c_uint64)
        ]
        lib.get_packet_loss_stats.restype = None


    def is_data_needed(self, index: int) -> bool:
        return bool(self._native_lib.is_data_needed(self._handle, index))

    def handle_data(self, data: bytes, length: int) -> None:
        buf = (c_uint8 * length).from_buffer_copy(data)
        self._native_lib.handle_data(self._handle, buf, c_size_t(length))

    def set_parser_emg_resolution(self, bits: int) -> None:
        self._native_lib.set_parser_emg_resolution(self._handle, c_uint8(bits))

    def set_parser_emg_channel_count(self, channels: int) -> None:
        self._native_lib.set_parser_emg_channel_count(self._handle, c_uint8(channels))

    def set_parser_ppg_channel_count(self, channels: int) -> None:
        self._native_lib.set_parser_ppg_channel_count(self._handle, c_uint8(channels))

    def set_parser_imu_h_ranges(self, accel_range_g: int, gyro_range_dps: int) -> None:
        self._native_lib.set_parser_imu_h_ranges(
            self._handle, c_uint8(accel_range_g), c_uint16(gyro_range_dps)
        )

    def set_parser_imu_f_ranges(self, accel_range_g: int, gyro_range_dps: int) -> None:
        self._native_lib.set_parser_imu_f_ranges(
            self._handle, c_uint8(accel_range_g), c_uint16(gyro_range_dps)
        )

    def set_on_emg_ready(self, callback: OnEmgReadyCallback | None) -> None:
        self._emg_callback_ref = self._set_raw_callback(
            self._native_lib.set_on_emg_ready, callback
        )

    def set_on_imu_h_ready(self, callback: OnImuReadyCallback | None) -> None:
        self._imu_h_callback_ref = self._set_raw_callback(
            self._native_lib.set_on_imu_h_ready, callback
        )

    def set_on_imu_f_ready(self, callback: OnImuReadyCallback | None) -> None:
        self._imu_f_callback_ref = self._set_raw_callback(
            self._native_lib.set_on_imu_f_ready, callback
        )

    def set_on_ppg_ready(self, callback: OnPpgReadyCallback | None) -> None:
        self._ppg_callback_ref = self._set_raw_callback(
            self._native_lib.set_on_ppg_ready, callback
        )

    def _create_raw_callback_wrapper(self, callback: OnRawDataCallback):
        def _native_cb(
            timestamp: int,
            data_ptr: POINTER(c_float),
            data_len: int,
            frequency: int,
            frequency_std: float,
        ):
            # Snapshot once; avoid per-element Python loop when possible.
            if data_len <= 0 or not data_ptr:
                data: List[float] = []
            else:
                data = list(ctypes.cast(data_ptr, POINTER(c_float * data_len)).contents)
            callback(timestamp, data, frequency, frequency_std)
        return OnRawDataCallbackC(_native_cb)

    def _set_raw_callback(self, setter_func, callback: OnRawDataCallback | None):
        if callback is None:
            setter_func(self._handle, ctypes.cast(0, OnRawDataCallbackC))
            return None
        callback_ref = self._create_raw_callback_wrapper(callback)
        setter_func(self._handle, callback_ref)
        return callback_ref


    @staticmethod
    def _decode_firmware_command_buffer(buf: ByteBuffer) -> bytes:
        if buf.length == 0 or not buf.data:
            return b""
        array_ptr = ctypes.cast(buf.data, POINTER(c_uint8 * buf.length))
        result = bytes(array_ptr.contents)
        ComputationWrapper._native_lib.free_firmware_buffer(buf.data)
        return result

    @staticmethod
    def get_pro_firmware_command_bytes(command: int) -> bytes:
        """Byte template for `command` (a ProFirmwareCommand ordinal) on
        Mudra Pro — see ProFirmwareCommands.h."""
        ComputationWrapper._ensure_native_lib_loaded()
        ComputationWrapper._initialize_native_lib()
        buf = ComputationWrapper._native_lib.get_pro_firmware_command(c_int32(command))
        return ComputationWrapper._decode_firmware_command_buffer(buf)

    @staticmethod
    def get_ultimate_firmware_command_bytes(command: int) -> bytes:
        """Byte template for `command` (an UltimateFirmwareCommand ordinal)
        on Mudra Ultimate — see UltimateFirmwareCommands.h."""
        ComputationWrapper._ensure_native_lib_loaded()
        ComputationWrapper._initialize_native_lib()
        buf = ComputationWrapper._native_lib.get_ultimate_firmware_command(c_int32(command))
        return ComputationWrapper._decode_firmware_command_buffer(buf)

    @staticmethod
    def _decode_cdc_token_buffer(buf: ByteBuffer) -> str:
        if buf.length == 0 or not buf.data:
            ComputationWrapper._native_lib.free_cdc_token(buf.data)
            return ""
        array_ptr = ctypes.cast(buf.data, POINTER(c_uint8 * buf.length))
        result = bytes(array_ptr.contents).decode("ascii")
        ComputationWrapper._native_lib.free_cdc_token(buf.data)
        return result

    @staticmethod
    def get_pro_cdc_command_token(command: int, enable: bool = True) -> str:
        """ASCII CDC token for `command` (a ProFirmwareCommand ordinal, e.g.
        "EMG_ODR"), or "" if it has no CDC equivalent. `enable` only matters
        for the 5 ENABLE_* (power) commands — picks "EMG_ON" vs "EMG_OFF"
        etc.; ignored otherwise. See Computation/ProCdcCommands.h."""
        ComputationWrapper._ensure_native_lib_loaded()
        ComputationWrapper._initialize_native_lib()
        buf = ComputationWrapper._native_lib.get_pro_cdc_command_token(c_int32(command), ctypes.c_bool(enable))
        return ComputationWrapper._decode_cdc_token_buffer(buf)

    @staticmethod
    def get_ultimate_cdc_command_token(command: int, enable: bool = True) -> str:
        """ASCII CDC token for `command` (an UltimateFirmwareCommand ordinal),
        or "" if it has no CDC equivalent. `enable` only matters for the 5
        ENABLE_* (power) commands. See Computation/UltimateCdcCommands.h."""
        ComputationWrapper._ensure_native_lib_loaded()
        ComputationWrapper._initialize_native_lib()
        buf = ComputationWrapper._native_lib.get_ultimate_cdc_command_token(c_int32(command), ctypes.c_bool(enable))
        return ComputationWrapper._decode_cdc_token_buffer(buf)

    ### ----------------------- Data Recorder Functions ----------------------- ###

    def enable_recording(self) -> None:
        self._native_lib.enable_recording(self._handle)

    def disable_recording(self) -> None:
        self._native_lib.disable_recording(self._handle)

    def start_recording(self, recording_types: POINTER(c_int), recording_types_length: int, record_time: int) -> bool:
        return self._native_lib.start_recording(self._handle, recording_types, recording_types_length, record_time)

    def stop_recording(self) -> None:
        self._native_lib.stop_recording(self._handle)

    def get_json_recording(self) -> str:
        return self._native_lib.get_json_recording(self._handle).decode("utf-8")

    def is_recording_enabled(self) -> bool:
        return bool(self._native_lib.is_recording_enabled(self._handle))

    def add_video(self, video_description: str, video_path: str) -> None:
        self._native_lib.add_video(self._handle, video_description.encode(), video_path.encode())

    def record_event(self, event_type: int, event: str) -> None:
        self._native_lib.record_event(self._handle, event_type, event.encode())

    def fill_json_buffer(self):
        return self._native_lib.fill_json_buffer(self._handle)

    def free_shared_buffer(self, ptr):
        self._native_lib.free_shared_buffer(ptr)

    ### ----------------------- Packet-Loss Stats Functions ----------------------- ###

    def reset_packet_loss_stats(self, data_type: int) -> None:
        self._native_lib.reset_packet_loss_stats(self._handle, c_int(data_type))

    def get_packet_loss_stats(self, data_type: int) -> Tuple[int, int]:
        samples_seen = c_uint64(0)
        samples_lost = c_uint64(0)
        self._native_lib.get_packet_loss_stats(
            self._handle, c_int(data_type), ctypes.byref(samples_seen), ctypes.byref(samples_lost)
        )
        return samples_seen.value, samples_lost.value
