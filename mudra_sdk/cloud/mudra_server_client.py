"""
Mudra Server Client
Main API client for interacting with Mudra cloud services
"""

import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List, Union
from threading import Lock
import requests
from requests.exceptions import HTTPError, RequestException

from .api_config import Endpoint, HttpMethod, ResponseCode
from .auth_storage import AuthStorage
from .data import (
    RefreshTokenRequest,
    TokenResponse,
    LicenseSecureTokenRequest,
    UploadVideoRequest,
    VideoUploadResponse,
    PresignedUrlPart,
    UploadedPart,
    CompleteVideoRecordingRequest,
)
from .request_interceptor import RequestInterceptor, RequestInterceptorDelegate
from ..logging_config import get_logger

logger = get_logger(__name__)


_MULTIPART_CHUNK_SIZE = 10 * 1024 * 1024  # 10 MB
_MULTIPART_CONCURRENCY = 5


class MudraServerClient(RequestInterceptorDelegate):
    """Singleton client for Mudra server API calls"""
    
    _instance: Optional['MudraServerClient'] = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
        
        self._auth_storage = AuthStorage()
        self._interceptor = RequestInterceptor(delegate=self)
        self._initialized = True
    
    def get_access_token(self) -> Optional[str]:
        """Get the current access token"""
        token = self._auth_storage.access_token
        return token if token else None
    
    def on_refresh_token_required(self) -> Optional[str]:
        """Handle token refresh when required"""
        data = RefreshTokenRequest(
            email=self._auth_storage.email,
            refresh_token=self._auth_storage.refresh_token
        ).to_json()
        
        try:
            response = self.refresh_token_api_call(data)
            if response is True:
                logger.info(f"Token refreshed successfully")
                return self._auth_storage.access_token
            return None
        except Exception as e:
            logger.error(f"Error occurred for refreshToken: {e}")
            return None
    
    def _is_success_status_code(self, status_code: Optional[int]) -> bool:
        """Check if status code indicates success"""
        return status_code in [
            ResponseCode.OK.value,
            ResponseCode.CREATED.value,
            ResponseCode.ACCEPTED.value
        ]
    
    def _requires_token_storage(self, endpoint: Endpoint) -> bool:
        """Check if endpoint requires token storage after response"""
        return endpoint in [
            Endpoint.SIGNIN,
            Endpoint.REFRESH_TOKENS,
            Endpoint.GOOGLE_SIGNIN,
            Endpoint.APPLE_SIGNIN,
        ]
    
    def _store_tokens_from_response(self, data: Dict[str, Any], request_data: Optional[Dict[str, Any]]):
        """Store tokens from response data"""
        email_value = request_data.get('email') if request_data else None
        if email_value is not None and email_value != '':
            self._auth_storage.email = email_value
        
        token_response = TokenResponse.from_json(data)
        self._auth_storage.access_token = token_response.access_token
        self._auth_storage.refresh_token = token_response.refresh_token
    
    def _handle_api_error(self, error_code: int, custom_error_messages: Dict[ResponseCode, str] = None) -> str:
        """Handle API errors and return appropriate error message"""
        if custom_error_messages is None:
            custom_error_messages = {}
        
        try:
            response_code = ResponseCode(error_code)
        except ValueError:
            response_code = ResponseCode.UNKNOWN
        
        # Check for custom error messages
        if response_code in custom_error_messages:
            return custom_error_messages[response_code]
        
        # Handle common error cases
        error_messages = {
            ResponseCode.CLIENT_TIMEOUT: "Low internet connectivity. Please check the connection and try again",
            ResponseCode.NOT_CONNECTED_TO_INTERNET: "No internet connectivity. Please check the connection and try again",
            ResponseCode.INTERNAL_SERVER_ERROR: "Something went wrong. Contact support@mudra-band.com",
            ResponseCode.UNAUTHORIZED: "Failed : Unauthorized",
            ResponseCode.FORBIDDEN: "Access forbidden. You don't have permission to access this resource",
            ResponseCode.NOT_ACCEPTABLE: "Failed : notAcceptable",
            ResponseCode.NOT_FOUND: "Resource not found",
            ResponseCode.METHOD_NOT_ALLOWED: "Method not allowed for this resource",
            ResponseCode.REQUEST_TIMEOUT: "Request timed out. Please try again",
            ResponseCode.BAD_REQUEST: "Bad request",
            ResponseCode.CONFLICT: "Conflict with existing resource",
            ResponseCode.GONE: "The requested resource is no longer available",
            ResponseCode.UNPROCESSABLE_ENTITY: "Invalid request data. Please check your input",
            ResponseCode.TOO_MANY_REQUESTS: "Too many requests. Please wait before trying again",
            ResponseCode.PRECONDITION_REQUIRED: "Precondition required for this operation",
            ResponseCode.NOT_IMPLEMENTED: "This feature is not implemented yet",
            ResponseCode.BAD_GATEWAY: "Bad gateway error. Please try again later",
            ResponseCode.SERVICE_UNAVAILABLE: "Service temporarily unavailable. Please try again later",
            ResponseCode.GATEWAY_TIMEOUT: "Gateway timeout. Please try again later",
            ResponseCode.ALREADY_REPORTED: "Resource already exists",
        }
        
        return error_messages.get(response_code, "Unrecognized problem.")
    
    def _make_api_call(
        self,
        endpoint: Endpoint,
        data: Optional[Dict[str, Any]] = None,
        custom_error_messages: Optional[Dict[ResponseCode, str]] = None,
        response_transformer: Optional[Callable] = None
    ) -> Any:
        """Generic API call wrapper"""
        url = endpoint.get_url()
        method = endpoint.method.value
        
        # Handle query parameters for GET requests
        if method == HttpMethod.GET.value and data:
            url = self._get_parameterized_url(endpoint, data)
        
        try:
            if method == HttpMethod.GET.value:
                response = self._interceptor.request(method=method, url=url, headers={'Content-Type': 'application/json'})
            elif method == HttpMethod.POST.value:
                response = self._interceptor.request(method=method, url=url, json_data=data)
            elif method == HttpMethod.PUT.value:
                response = self._interceptor.request(method=method, url=url, json_data=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if self._is_success_status_code(response.status_code):
                # Handle token storage for authentication endpoints
                if self._requires_token_storage(endpoint):
                    self._store_tokens_from_response(response.json(), data)
                
                response_data = response.json()
                if response_transformer:
                    return response_transformer(response_data)
                return response_data
            else:
                error_msg = self._handle_api_error(response.status_code, custom_error_messages)
                raise HTTPError(error_msg)
                
        except HTTPError:
            raise
        except RequestException as e:
            if isinstance(e, requests.exceptions.Timeout):
                error_msg = self._handle_api_error(ResponseCode.CLIENT_TIMEOUT.value, custom_error_messages)
            elif isinstance(e, requests.exceptions.ConnectionError):
                error_msg = self._handle_api_error(ResponseCode.NOT_CONNECTED_TO_INTERNET.value, custom_error_messages)
            else:
                error_msg = self._handle_api_error(ResponseCode.UNKNOWN.value, custom_error_messages)
            raise HTTPError(error_msg) from e
        except Exception as e:
            error_msg = self._handle_api_error(ResponseCode.UNKNOWN.value, custom_error_messages)
            raise HTTPError(error_msg) from e
    
    def _get_parameterized_url(self, endpoint: Endpoint, data: Optional[Dict[str, Any]]) -> str:
        """Build URL with query parameters"""
        url = endpoint.get_url()
        
        query_param_map = {
            Endpoint.FIRMWARE_VERSION_DETAILS: [{'key': 'version', 'value': data.get('version') if data else None}],
            Endpoint.GET_USER_INFO: [{'key': 'application', 'value': data.get('application') if data else None}],
            Endpoint.LATEST_FIRMWARE_VERSION_LIST: [
                {'key': 'ProdOrDev', 'value': data.get('ProdorDev') if data else None},
                {'key': 'limit', 'value': data.get('limit') if data else None}
            ],
            Endpoint.GET_ACCEPT_TERMS: [{'key': 'signInType', 'value': data.get('signInType') if data else None}],
            Endpoint.SET_ACCEPT_TERMS: [{'key': 'signInType', 'value': data.get('signInType') if data else None}],
        }
        
        params = query_param_map.get(endpoint)
        if params:
            query_params = []
            for param in params:
                value = param['value']
                if value is not None and value != '':
                    query_params.append(f"{param['key']}={value}")
            if query_params:
                url = f"{url}?{'&'.join(query_params)}"
        
        return url
    
    # API Call Methods
    
    def sign_in_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Sign in API call"""
        return self._make_api_call(
            endpoint=Endpoint.SIGNIN,
            data=data,
            custom_error_messages={
                ResponseCode.PRECONDITION_REQUIRED: "account not activated",
                ResponseCode.FORBIDDEN: "Invalid email address or password",
            }
        )
    
    def refresh_token_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Refresh token API call"""
        return self._make_api_call(
            endpoint=Endpoint.REFRESH_TOKENS,
            data=data,
            response_transformer=lambda _: True
        )
    
    def get_video_upload_urls_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Get video upload presigned URLs for multipart upload"""
        return self._make_api_call(
            endpoint=Endpoint.UPLOAD_DIRECT_VIDEO_RECORDING,
            data=data
        )
    
    def is_email_available_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Check if email is available"""
        return self._make_api_call(
            endpoint=Endpoint.IS_EMAIL_AVAILABLE,
            data=data,
            custom_error_messages={
                ResponseCode.PRECONDITION_REQUIRED: "account not activated",
                ResponseCode.CONFLICT: "This email address is already in use.",
                ResponseCode.FORBIDDEN: "Invalid email address or password",
            }
        )
    
    def sign_up_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Sign up API call"""
        return self._make_api_call(
            endpoint=Endpoint.REGISTER_NEW_USER,
            data=data,
            custom_error_messages={
                ResponseCode.PRECONDITION_REQUIRED: "account not activated",
            }
        )
    
    def email_verification_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Email verification API call"""
        return self._make_api_call(
            endpoint=Endpoint.EMAIL_VERIFICATION,
            data=data,
            custom_error_messages={
                ResponseCode.PRECONDITION_REQUIRED: "account not activated",
                ResponseCode.FORBIDDEN: "Invalid email address or password",
                ResponseCode.ALREADY_REPORTED: "User already verified.",
            }
        )
    
    def get_reset_password_email_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Get reset password email API call"""
        return self._make_api_call(
            endpoint=Endpoint.GET_RESET_PASSWORD_EMAIL,
            data=data,
            custom_error_messages={
                ResponseCode.NOT_FOUND: "We couldn't find an account for this email",
            }
        )
    
    def reset_password_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Reset password API call"""
        return self._make_api_call(
            endpoint=Endpoint.RESET_PASSWORD,
            data=data,
            custom_error_messages={
                ResponseCode.NOT_FOUND: "The temporary password you entered is incorrect",
                ResponseCode.NOT_ACCEPTABLE: "The temporary password you entered is incorrect",
            }
        )
    
    def google_signin_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Google sign in API call"""
        return self._make_api_call(
            endpoint=Endpoint.GOOGLE_SIGNIN,
            data=data,
            custom_error_messages={
                ResponseCode.PRECONDITION_REQUIRED: "account not activated",
                ResponseCode.FORBIDDEN: "Invalid email address or password",
            }
        )

    def apple_signin_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Apple sign in API call"""
        return self._make_api_call(
            endpoint=Endpoint.APPLE_SIGNIN,
            data=data,
            custom_error_messages={
                ResponseCode.PRECONDITION_REQUIRED: "account not activated",
                ResponseCode.FORBIDDEN: "Invalid email address or password",
            }
        )

    def get_accept_terms_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Get accept terms API call"""
        return self._make_api_call(
            endpoint=Endpoint.GET_ACCEPT_TERMS,
            data=data
        )
    
    def set_accept_terms_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Set accept terms API call"""
        return self._make_api_call(
            endpoint=Endpoint.SET_ACCEPT_TERMS,
            data=data,
            response_transformer=lambda _: True
        )
    
    def get_user_info_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Get user info API call"""
        return self._make_api_call(
            endpoint=Endpoint.GET_USER_INFO,
            data=data
        )
    
    def upload_logging(self, file_name: str, log_file_path: Optional[str] = None) -> str:
        """Upload logging file"""
        if log_file_path is None:
            # Default log file location
            home_dir = Path.home()
            log_file_path = home_dir / '.mudra_sdk' / 'mudra_logger.txt'
        
        log_file = Path(log_file_path)
        if not log_file.exists():
            raise FileNotFoundError(f"Log file does not exist at path: {log_file_path}")
        
        with open(log_file, 'rb') as f:
            file_data = f.read()
        
        url = Endpoint.UPLOAD_LOGGING.get_url()
        
        try:
            files = {'file': (file_name, file_data, 'text/plain')}
            response = self._interceptor.request(
                method=HttpMethod.POST.value,
                url=url,
                files=files
            )
            
            if self._is_success_status_code(response.status_code):
                logger.info("Log file uploaded successfully")
                return "Log file uploaded successfully"
            else:
                error_msg = self._handle_api_error(response.status_code, {})
                raise HTTPError(error_msg)
        except Exception as e:
            raise HTTPError(f"Failed to upload log file: {e}") from e
    
    def upload_data_recorder(self, presigned_url: str, file_path: str) -> Any:
        """Upload data recorder file using presigned URL"""
        file = Path(file_path)
        if not file.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        try:
            with open(file, 'rb') as f:
                file_data = f.read()
            
            response = requests.put(
                presigned_url,
                data=file_data,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': str(len(file_data))
                }
            )
            
            if self._is_success_status_code(response.status_code):
                return response.json() if response.content else {}
            else:
                raise HTTPError(f"Upload failed with status {response.status_code}")
        except Exception as e:
            raise HTTPError(f"Failed to upload file: {e}") from e
    
    def download_preset(self, data: str) -> Any:
        """Download preset"""
        url = Endpoint.DOWNLOAD_PRESET.get_url()
        try:
            response = self._interceptor.request(
                method=HttpMethod.POST.value,
                url=url,
                json_data=json.loads(data) if isinstance(data, str) else data,
                headers={'Content-Type': 'application/json'}
            )
            
            if self._is_success_status_code(response.status_code):
                return response.json()
            else:
                error_msg = self._handle_api_error(response.status_code, {})
                raise HTTPError(error_msg)
        except Exception as e:
            raise HTTPError(f"Failed to download preset: {e}") from e
    
    def upload_preset(self, data: str) -> Any:
        """Upload preset"""
        url = Endpoint.UPLOAD_PRESET.get_url()
        try:
            response = self._interceptor.request(
                method=HttpMethod.POST.value,
                url=url,
                json_data=json.loads(data) if isinstance(data, str) else data,
                headers={'Content-Type': 'application/json'}
            )
            
            if self._is_success_status_code(response.status_code):
                return response.json()
            else:
                error_msg = self._handle_api_error(response.status_code, {})
                raise HTTPError(error_msg)
        except Exception as e:
            raise HTTPError(f"Failed to upload preset: {e}") from e
    
    def complete_video_recording_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Complete video recording after multipart upload"""
        return self._make_api_call(
            endpoint=Endpoint.COMPLETE_VIDEO_RECORDING,
            data=data
        )

    def abort_video_recording_api_call(self, upload_id: str, object_key: str) -> Any:
        """Abort video recording upload"""
        return self._make_api_call(
            endpoint=Endpoint.ABORT_VIDEO_RECORDING,
            data={'uploadId': upload_id, 'objectKey': object_key}
        )

    def _upload_video_multipart_part(self, part: PresignedUrlPart, data: bytes) -> UploadedPart:
        """PUT one chunk to S3 presigned URL (no auth interceptor)."""
        response = requests.put(
            part.url,
            data=data,
            headers={
                'Content-Type': 'video/mp4',
                'Content-Length': str(len(data)),
            },
            allow_redirects=False,
            timeout=600,
        )
        if not self._is_success_status_code(response.status_code):
            raise HTTPError(
                f'Multipart upload failed for part {part.part_number}: {response.status_code}'
            )
        etag = response.headers.get('ETag') or response.headers.get('etag') or ''
        return UploadedPart(part_number=part.part_number, etag=etag)

    def upload_video_file_multipart_api_call(
        self,
        file_path: str,
        presigned_url_parts: List[PresignedUrlPart],
        *,
        upload_id: str,
        object_key: str,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ) -> List[UploadedPart]:
        """
        Upload file in 10 MB parts to presigned URLs, up to 5 parallel uploads per batch.
        On failure, calls abort before re-raising.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f'File not found: {file_path}')

        file_size = path.stat().st_size
        sorted_parts = sorted(presigned_url_parts, key=lambda p: p.part_number)
        required_parts = (file_size + _MULTIPART_CHUNK_SIZE - 1) // _MULTIPART_CHUNK_SIZE
        if len(sorted_parts) < required_parts:
            raise HTTPError(
                f'Not enough presigned URLs: {len(sorted_parts)} for {required_parts} parts'
            )

        results: List[UploadedPart] = []
        try:
            with open(path, 'rb') as f:
                for batch_start in range(0, len(sorted_parts), _MULTIPART_CONCURRENCY):
                    batch_end = min(batch_start + _MULTIPART_CONCURRENCY, len(sorted_parts))
                    batch_parts = sorted_parts[batch_start:batch_end]
                    batch_bytes: List[bytes] = []
                    for i in range(batch_start, batch_end):
                        offset = i * _MULTIPART_CHUNK_SIZE
                        remaining = file_size - offset
                        length = min(_MULTIPART_CHUNK_SIZE, remaining)
                        f.seek(offset)
                        batch_bytes.append(f.read(length))

                    with ThreadPoolExecutor(max_workers=len(batch_parts)) as executor:
                        future_map = {
                            executor.submit(self._upload_video_multipart_part, p, b): p
                            for p, b in zip(batch_parts, batch_bytes)
                        }
                        for fut in as_completed(future_map):
                            results.append(fut.result())
                    if on_progress:
                        on_progress(len(results), len(sorted_parts))
        except Exception:
            try:
                self.abort_video_recording_api_call(upload_id, object_key)
            except Exception as abort_err:
                logger.error(f'Abort video recording failed: {abort_err}')
            raise

        results.sort(key=lambda p: p.part_number)
        return results

    @staticmethod
    def _update_recorder_json_with_video(
        recorder_json: Dict[str, Any], server_video_file_paths: List[str]
    ) -> str:
        videos: Dict[str, Any] = {}
        for index, server_path in enumerate(server_video_file_paths):
            videos[str(index + 1)] = server_path
        recorder_json['videos'] = videos
        return json.dumps(recorder_json)

    def upload_recording_with_video(
        self,
        video_paths: List[str],
        recorder_json: Dict[str, Any],
        on_progress: Optional[Callable[[int, int, float, str], None]] = None,
    ) -> None:
        """
        Upload each local video via multipart presigned URLs, then POST recording JSON to MongoDB.
        on_progress: (video_index 1-based, total_videos, percent 0-100 or -1 when N/A, status_message).
        """
        server_video_file_paths: List[str] = []
        total_videos = len(video_paths)

        for i, video_path in enumerate(video_paths):
            video_index = i + 1
            file_name = os.path.basename(video_path)
            file_size = Path(video_path).stat().st_size

            part_count = 1
            if file_size > _MULTIPART_CHUNK_SIZE:
                part_count = (file_size + _MULTIPART_CHUNK_SIZE - 1) // _MULTIPART_CHUNK_SIZE

            response = self.get_video_upload_urls_api_call(
                UploadVideoRequest(file_name=file_name, part_count=part_count).to_json()
            )
            if not isinstance(response, dict):
                raise HTTPError('Invalid presigned URL response')
            direct = VideoUploadResponse.from_json(response)

            video_file_path = f'{direct.folder_name}/{direct.file_name}'
            server_video_file_paths.append(video_file_path)

            def _part_progress(completed: int, total: int) -> None:
                if on_progress and total > 0:
                    pct = (completed / total) * 100.0
                    on_progress(
                        video_index,
                        total_videos,
                        pct,
                        f'Uploading video {video_index} of {total_videos}',
                    )

            uploaded_parts = self.upload_video_file_multipart_api_call(
                video_path,
                direct.presigned_urls,
                upload_id=direct.upload_id,
                object_key=direct.object_key,
                on_progress=_part_progress,
            )

            if on_progress:
                on_progress(
                    video_index,
                    total_videos,
                    100.0,
                    f'Uploading video {video_index} of {total_videos}',
                )

            self.complete_video_recording_api_call(
                CompleteVideoRecordingRequest(
                    upload_id=direct.upload_id,
                    object_key=direct.object_key,
                    parts=uploaded_parts,
                ).to_json()
            )

        if on_progress:
            on_progress(
                total_videos,
                total_videos,
                -1.0,
                'Uploading recording...',
            )

        updated_json = self._update_recorder_json_with_video(
            recorder_json, server_video_file_paths
        )
        mongo_response = self.upload_data_recorder_to_mongodb(updated_json)
        logger.debug(f'upload data recorder to mongo db response: {mongo_response}')

    def upload_data_recorder_to_mongodb(self, data: Union[str, Dict[str, Any]]) -> Any:
        """Upload data recorder to MongoDB"""
        url = Endpoint.UPLOAD_RECORDING_TO_DB.get_url()
        try:
            if isinstance(data, str):
                body_bytes = data.encode('utf-8')
            else:
                body_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
            response = self._interceptor.request(
                method=HttpMethod.POST.value,
                url=url,
                data=body_bytes,
                headers={'Content-Type': 'application/json'},
            )

            if self._is_success_status_code(response.status_code):
                if not response.content:
                    return None
                try:
                    return response.json()
                except ValueError:
                    return response.text
            else:
                error_msg = self._handle_api_error(response.status_code, {})
                body_preview = (response.text or '')[:2000]
                if body_preview:
                    raise HTTPError(f'{error_msg} — server: {body_preview}')
                raise HTTPError(error_msg)
        except HTTPError:
            raise
        except Exception as e:
            raise HTTPError(f'Failed to upload to MongoDB: {e}') from e
    
    def get_firmware_version_details_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Get firmware version details API call"""
        return self._make_api_call(
            endpoint=Endpoint.FIRMWARE_VERSION_DETAILS,
            data=data
        )
    
    def get_latest_firmware_version_list_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Get latest firmware version list API call"""
        return self._make_api_call(
            endpoint=Endpoint.LATEST_FIRMWARE_VERSION_LIST,
            data=data
        )

    def download_recording_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Download recording API call"""
        return self._make_api_call(
            endpoint=Endpoint.DOWNLOAD_RECORDING,
            data=data
        )

    def get_download_video_url(self, data: Optional[Dict[str, Any]]) -> Any:
        """Get download video URL"""
        return self._make_api_call(
            endpoint=Endpoint.DOWNLOAD_VIDEO_RECORDING_DIRECT,
            data=data
        )

    def upload_fuel_gauge_reset(self, data: Optional[Dict[str, Any]]) -> Any:
        """Upload fuel gauge reset API call"""
        return self._make_api_call(
            endpoint=Endpoint.UPLOAD_FUEL_GAUGE_RESET,
            data=data
        )
    
    def is_fuel_gauge_reset_done_api_call(self) -> Any:
        """Check if fuel gauge reset is done"""
        return self._make_api_call(
            endpoint=Endpoint.IS_FUEL_GAUGE_RESET_DONE,
            data=None,
            custom_error_messages={
                ResponseCode.UNAUTHORIZED: "Failed : Unauthorized",
                ResponseCode.NOT_ACCEPTABLE: "Failed : notAcceptable",
                ResponseCode.CLIENT_TIMEOUT: "Low internet connectivity. Please check the connection and try again",
                ResponseCode.NOT_CONNECTED_TO_INTERNET: "No internet connectivity. Please check the connection and try again",
            }
        )
    
    def upload_current_hand(self, data: Optional[str]) -> Any:
        """Upload current hand API call"""
        return self._make_api_call(
            endpoint=Endpoint.UPLOAD_CURRENT_HAND,
            data=data
        )
    
    def set_user_check_point_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Set user checkpoint API call"""
        return self._make_api_call(
            endpoint=Endpoint.SET_USER_CHECK_POINT,
            data=data,
            custom_error_messages={
                ResponseCode.UNAUTHORIZED: "Failed : Unauthorized",
                ResponseCode.NOT_ACCEPTABLE: "Failed : notAcceptable",
            }
        )
    
    def set_advanced_practice_finished_api_call(self) -> Any:
        """Set advanced practice finished API call"""
        return self._make_api_call(
            endpoint=Endpoint.SET_ADVANCED_PRACTICE_FINISHED,
            data=None,
            custom_error_messages={
                ResponseCode.UNAUTHORIZED: "Failed : Unauthorized",
                ResponseCode.NOT_ACCEPTABLE: "Failed : notAcceptable",
            }
        )
    
    def get_advanced_gesture_status_api_call(self) -> Any:
        """Get advanced gesture status API call"""
        return self._make_api_call(
            endpoint=Endpoint.GET_ADVANCED_GESTURE_STATUS,
            data=None
        )
    
    def set_advanced_gesture_status_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Set advanced gesture status API call"""
        return self._make_api_call(
            endpoint=Endpoint.SET_ADVANCED_GESTURE_STATUS,
            data=data,
            custom_error_messages={
                ResponseCode.UNAUTHORIZED: "Failed : Unauthorized",
                ResponseCode.NOT_ACCEPTABLE: "Failed : notAcceptable",
            }
        )
    
    def set_user_device_info_api_call(self, data: Optional[Dict[str, str]]) -> Any:
        """Set user device info API call"""
        return self._make_api_call(
            endpoint=Endpoint.SET_USER_DEVICE_INFO,
            data=data,
            custom_error_messages={
                ResponseCode.UNAUTHORIZED: "Failed : Unauthorized",
                ResponseCode.NOT_ACCEPTABLE: "Failed : notAcceptable",
            }
        )
    
    def set_serial_number_api_call(self, data: Optional[Dict[str, str]]) -> Any:
        """Set serial number API call"""
        return self._make_api_call(
            endpoint=Endpoint.SET_SERIAL_NUMBER,
            data=data,
            custom_error_messages={
                ResponseCode.UNAUTHORIZED: "Failed : Unauthorized",
                ResponseCode.NOT_ACCEPTABLE: "Failed : notAcceptable",
            }
        )
    
    def change_name_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Change name API call"""
        return self._make_api_call(
            endpoint=Endpoint.CHANGE_NAME,
            data=data,
            custom_error_messages={
                ResponseCode.UNAUTHORIZED: "Failed : Unauthorized",
            }
        )
    
    def change_password_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Change password API call"""
        return self._make_api_call(
            endpoint=Endpoint.CHANGE_PASSWORD,
            data=data,
            custom_error_messages={
                ResponseCode.BAD_REQUEST: "The current password you entered is incorrect",
            }
        )
    
    def delete_account_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Delete account API call"""
        return self._make_api_call(
            endpoint=Endpoint.DELETE_ACCOUNT,
            data=data
        )
    
    def change_permission_level_api_call(self, data: Optional[Dict[str, Any]]) -> Any:
        """Change permission level API call"""
        return self._make_api_call(
            endpoint=Endpoint.CHANGE_PERMISSION_LEVEL,
            data=data,
            custom_error_messages={
                ResponseCode.BAD_REQUEST: "Failed : Bad Request",
            }
        )

    def get_pro_license(self, serial: Optional[str] = None) -> Optional[bytes]:
        """Fetch the server-issued device-license token (POST license/getLicense).
        The server returns a device-bound token for the account's tier; pass
        ``serial`` to bind it to this device (omit for a wildcard/dev token —
        used when the serial can't be read, e.g. over BLE). Returns the opaque
        token bytes to relay to the device, or None if the server returned no
        token."""
        body: Dict[str, Any] = {"encryptionMethod": "PRO"}
        if serial:
            body["serial"] = serial
        resp = self._make_api_call(endpoint=Endpoint.LICENSE_SECURE_TOKEN, data=body)
        tok = resp.get("token") if isinstance(resp, dict) else None
        return bytes(tok) if tok else None

    def open_recording_header(self, header: bytes) -> bytes:
        """POST recordings/openHeader on the recording-decrypt host (dev
        only). Given the crypto header sliced from an encrypted SD
        recording (141 or 157 bytes),
        the server resolves it into the 32-byte file_key needed to decrypt
        the recording's body, after checking it against the caller's own
        signed `uref`. This SDK holds no key material of its own and does
        no unsealing itself -- that's the whole point of this call.

        Raises ValueError for a malformed header (wrong length), or
        HTTPError with the server's error code/message on failure --
        notably 400 bad_header/invalid_point, 403 no_recording_ref (caller
        never signed in) / user_id_mismatch (wrong account, or a recording
        tied to someone else's uref), 503 no_decrypt_key (server-side
        deployment gap, not a bad file), 401 (no/expired session -- sign in
        again). The exact JSON error-body field names below (``code``/
        ``message``) are this SDK's best-effort parsing -- verify against
        the live service and adjust if it differs."""
        if len(header) not in (141, 157):
            raise ValueError(f"header must be 141 or 157 bytes, got {len(header)}")

        url = Endpoint.OPEN_HEADER.get_url()
        try:
            response = self._interceptor.request(
                method=HttpMethod.POST.value,
                url=url,
                json_data={"header": base64.b64encode(header).decode("ascii")},
            )
        except RequestException as e:
            if isinstance(e, requests.exceptions.Timeout):
                raise HTTPError(self._handle_api_error(ResponseCode.CLIENT_TIMEOUT.value)) from e
            if isinstance(e, requests.exceptions.ConnectionError):
                raise HTTPError(self._handle_api_error(ResponseCode.NOT_CONNECTED_TO_INTERNET.value)) from e
            raise HTTPError(self._handle_api_error(ResponseCode.UNKNOWN.value)) from e

        if self._is_success_status_code(response.status_code):
            data = response.json()
            file_key_b64 = data.get("fileKey") if isinstance(data, dict) else None
            if not file_key_b64:
                raise HTTPError("openHeader response missing fileKey")
            return base64.b64decode(file_key_b64)

        try:
            body = response.json()
        except ValueError:
            body = {}
        code = body.get("code") if isinstance(body, dict) else None
        message = body.get("message") if isinstance(body, dict) else None
        detail = f"{code}: {message}" if code or message else (response.text or "").strip()[:500]
        raise HTTPError(f"openHeader failed ({response.status_code}) {detail}".strip())

    def send_security_number_api_call(self, securityNumber: int) -> Optional[bytes]:
        """Call license secure token API with value. Returns token as bytes or None."""
        try:
            request = LicenseSecureTokenRequest(securityNumber=securityNumber)
            response = self._make_api_call(
                endpoint=Endpoint.LICENSE_SECURE_TOKEN,
                data=request.to_json(),
            )
            if isinstance(response, dict) and 'token' in response:
                token_list = response.get('token')
                if token_list is not None:
                    return bytes(int(x) for x in token_list)
            return None
        except Exception as e:
            logger.error(f"Failed to call license secure token API: {e}")
            return None

    def download_firmware(self, version: str) -> str:
        """Download firmware file"""
        url = Endpoint.DOWNLOAD_FIRMWARE.get_url().replace("version", version).strip()
        
        home_dir = Path.home()
        temp_dir = home_dir / '.mudra_sdk' / 'temp'
        temp_dir.mkdir(parents=True, exist_ok=True)
        file_path = temp_dir / 'firmware.zip'
        
        try:
            response = self._interceptor.request(
                method=HttpMethod.GET.value,
                url=url,
                timeout=60  # Longer timeout for downloads
            )
            
            if self._is_success_status_code(response.status_code):
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                logger.info(f'Download completed: {file_path}')
                return str(file_path)
            else:
                error_msg = self._handle_api_error(response.status_code, {})
                raise HTTPError(error_msg)
        except Exception as e:
            raise HTTPError(f"Failed to download firmware: {e}") from e
    
    def fetch_version_data(self) -> Optional[Dict[str, Any]]:
        """Fetch version data"""
        try:
            return self._make_api_call(
                endpoint=Endpoint.GET_MUDRA_LINK_RELEASE_VERSIONS,
                data=None,
                response_transformer=lambda data: json.loads(data) if isinstance(data, str) else data
            )
        except Exception as e:
            logger.error(f"Error occurred getting version info: {e}")
            return None
