import json
from ctypes import POINTER, c_int, cast, string_at
from typing import Any, Callable, Dict, List, Optional

from ..cloud.mudra_server_client import MudraServerClient
from .computation_wrapper import ComputationWrapper
from .enums import EventType, RecordingDataType
from ..logging_config import get_logger

logger = get_logger(__name__)


class DataRecorder:
    max_record_time = 60

    def __init__(self):
        pass

    def enable_recording(self, computation_wrapper: ComputationWrapper) -> None:
        computation_wrapper.enable_recording()

    def disable_recording(self, computation_wrapper: ComputationWrapper) -> None:
        computation_wrapper.disable_recording()

    def start_recording(
        self,
        computation_wrapper: ComputationWrapper,
        recording_types: List[RecordingDataType],
    ) -> None:
        int_array = (c_int * len(recording_types))()
        for i in range(len(recording_types)):
            int_array[i] = recording_types[i].value

        recording_types_ptr = cast(int_array, POINTER(c_int))
        computation_wrapper.start_recording(
            recording_types_ptr,
            len(recording_types),
            self.max_record_time,
        )

    def stop_recording(self, computation_wrapper: ComputationWrapper) -> None:
        computation_wrapper.stop_recording()

    def get_json_recording(self, computation_wrapper: ComputationWrapper) -> str:
        buffer = computation_wrapper.fill_json_buffer()
        if not buffer:
            logger.error("Failed to allocate buffer")
            return ""
        # buffer is a void pointer (memory address) - read the UTF-8 string from it
        result = string_at(buffer).decode("utf-8")
        computation_wrapper.free_shared_buffer(buffer)
        return result

    def is_recording_enabled(self, computation_wrapper: ComputationWrapper) -> bool:
        return computation_wrapper.is_recording_enabled()

    def record_event(self, computation_wrapper: ComputationWrapper, event_type: EventType, event: str) -> None:
        computation_wrapper.record_event(event_type, event)

    def add_video(self, computation_wrapper: ComputationWrapper, video_description: str, video_path: str) -> None:
        computation_wrapper.add_video(video_description, video_path)

    @staticmethod
    def _extract_video_files(
        recording: Dict[str, Any], *, is_server_json: bool = False
    ) -> List[str]:
        try:
            source = recording.get('recordings') if is_server_json else recording
            if not isinstance(source, dict):
                return []
            videos = source.get('videos')
            if not isinstance(videos, dict):
                return []
            return [v for v in videos.values() if isinstance(v, str)]
        except Exception as e:
            logger.error(f'Error extracting video file: {e}')
            return []

    def upload_recording(
        self,
        computation_wrapper: ComputationWrapper,
        on_progress: Optional[Callable[[int, int, float, str], None]] = None,
    ) -> None:
        recorder_json_string = self.get_json_recording(computation_wrapper)
        if not recorder_json_string:
            return
        try:
            recorder_json = json.loads(recorder_json_string)
            logger.debug(json.dumps(recorder_json, indent=2, ensure_ascii=False))
            video_paths = self._extract_video_files(recorder_json)
            if video_paths:
                MudraServerClient().upload_recording_with_video(
                    video_paths, recorder_json, on_progress=on_progress
                )
            else:
                response = MudraServerClient().upload_data_recorder_to_mongodb(
                    recorder_json_string
                )
                logger.debug(f'upload data recorder to mongo db response: {response}')
        except Exception as e:
            logger.error(f'Error occurred for upload/uploadRecordingDb: {e}')
            raise

