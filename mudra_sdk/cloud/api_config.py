"""
API Configuration for Mudra Server Client
Contains base URLs, endpoints, and HTTP method definitions
"""

from enum import Enum
from typing import Optional

# Base URLs
USER_DEBUG_BASE_URL = "https://users-dev.mudra-server.com/api/v1/"
DATA_DEBUG_BASE_URL = "https://data-dev.mudra-server.com/api/v1/"

USER_PRODUCTION_BASE_URL = "https://users.mudra-server.com/api/v1/"
DATA_PRODUCTION_BASE_URL = "https://data.mudra-server.com/api/v1/"

# Recording-decrypt host (see MudraServerClient.open_recording_header) -- a
# separate deployment from users/data, dev only today. No production host
# exists yet, so unlike USER_/DATA_ above there is deliberately no
# *_PRODUCTION_BASE_URL counterpart.
DECRYPT_DEBUG_BASE_URL = "https://decrypt-dev.mudra-server.com/api/v1/"

# Default to debug
BASE_URL = USER_DEBUG_BASE_URL

_USER_TO_DATA_SERVER_URL = {
    USER_DEBUG_BASE_URL: DATA_DEBUG_BASE_URL,
    USER_PRODUCTION_BASE_URL: DATA_PRODUCTION_BASE_URL,
}

_DATA_SERVER_PATHS = frozenset([
    'data/upload/recordingDb',
    'data/preSet/download/data',
    'data/preSet/upload/data',
    'data/upload/directVideoRecording',
    'data/upload/completeVideoRecording',
    'data/upload/abortVideoRecording',
    'data/download/recordingDb',
    'data/download/directVideoRecording',
])

_DECRYPT_SERVER_PATHS = frozenset([
    'recordings/openHeader',
])


def get_data_server_url() -> Optional[str]:
    """Determine data server URL based on the current base URL"""
    return _USER_TO_DATA_SERVER_URL.get(BASE_URL)


class HttpMethod(Enum):
    """HTTP method enumeration"""
    GET = "GET"
    POST = "POST"
    PUT = "PUT"


class ResponseCode(Enum):
    """HTTP response code enumeration"""
    # Success responses
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    ALREADY_REPORTED = 208
    
    # Client error responses
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    NOT_ACCEPTABLE = 406
    REQUEST_TIMEOUT = 408
    CONFLICT = 409
    GONE = 410
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    PRECONDITION_REQUIRED = 428
    
    # Server error responses
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504
    
    # Custom timeout responses
    CONNECTION_TIMEOUT = 599
    CLIENT_TIMEOUT = -2
    NOT_CONNECTED_TO_INTERNET = -3
    UNKNOWN = -1


class Endpoint(Enum):
    """API endpoint enumeration"""
    GET_USER_INFO = ("me", HttpMethod.GET)
    SIGNIN = ("auth/signin", HttpMethod.POST)
    REFRESH_TOKENS = ("auth/refreshToken", HttpMethod.POST)
    IS_EMAIL_AVAILABLE = ("auth/isEmailAvailable", HttpMethod.POST)
    REGISTER_NEW_USER = ("auth/signup", HttpMethod.POST)
    EMAIL_VERIFICATION = ("auth/verification", HttpMethod.POST)
    GET_RESET_PASSWORD_EMAIL = ("auth/resetPassRequest", HttpMethod.POST)
    RESET_PASSWORD = ("auth/password", HttpMethod.PUT)
    UPLOAD_LOGGING = ("data/raw/uploadLogging", HttpMethod.POST)
    GOOGLE_SIGNIN = ("auth/google/signin", HttpMethod.POST)
    APPLE_SIGNIN = ("auth/apple/applesignin", HttpMethod.POST)
    GET_ACCEPT_TERMS = ("me/getAcceptedTerms", HttpMethod.GET)
    SET_ACCEPT_TERMS = ("me/setAcceptedTerms", HttpMethod.PUT)
    FIRMWARE_VERSION_DETAILS = ("firmwares/versionDetails", HttpMethod.GET)
    LATEST_FIRMWARE_VERSION_LIST = ("firmwares/latestVersionsLimited", HttpMethod.GET)
    DOWNLOAD_FIRMWARE = ("firmwares/version", HttpMethod.GET)
    UPLOAD_FUEL_GAUGE_RESET = ("me/uploadFuelGaugeReset", HttpMethod.POST)
    IS_FUEL_GAUGE_RESET_DONE = ("me/isFuelGaugeResetDone", HttpMethod.GET)
    UPLOAD_CURRENT_HAND = ("me/uploadCurrentHand", HttpMethod.POST)
    SET_USER_CHECK_POINT = ("me/setUserCheckpoint", HttpMethod.PUT)
    SET_ADVANCED_PRACTICE_FINISHED = ("me/setAdvancedGesturesComplete", HttpMethod.PUT)
    GET_ADVANCED_GESTURE_STATUS = ("me/getAdvancedGesturesStatus", HttpMethod.GET)
    SET_ADVANCED_GESTURE_STATUS = ("me/setAdvancedGesturesStatus", HttpMethod.PUT)
    SET_USER_DEVICE_INFO = ("me/setUserDevicesInfo", HttpMethod.PUT)
    SET_SERIAL_NUMBER = ("me/setUserSerialNumber", HttpMethod.PUT)
    CHANGE_NAME = ("me/changeName", HttpMethod.PUT)
    CHANGE_PASSWORD = ("me/changePassword", HttpMethod.PUT)
    CHANGE_PERMISSION_LEVEL = ("me/givePermission", HttpMethod.PUT)
    DELETE_ACCOUNT = ("auth/deleteuser", HttpMethod.POST)
    UPLOAD_RECORDING_TO_DB = ("data/upload/recordingDb", HttpMethod.POST)
    GET_MUDRA_LINK_RELEASE_VERSIONS = ("auth/getMudraLinkReleaseVersions", HttpMethod.GET)
    DOWNLOAD_PRESET = ("data/preSet/download/data", HttpMethod.POST)
    UPLOAD_PRESET = ("data/preSet/upload/data", HttpMethod.POST)
    UPLOAD_DIRECT_VIDEO_RECORDING = ("data/upload/directVideoRecording", HttpMethod.POST)
    COMPLETE_VIDEO_RECORDING = ("data/upload/completeVideoRecording", HttpMethod.POST)
    ABORT_VIDEO_RECORDING = ("data/upload/abortVideoRecording", HttpMethod.POST)
    DOWNLOAD_RECORDING = ("data/download/recordingDb", HttpMethod.POST)
    DOWNLOAD_VIDEO_RECORDING_DIRECT = ("data/download/directVideoRecording", HttpMethod.POST)
    LICENSE_SECURE_TOKEN = ("license/getLicense", HttpMethod.POST)
    OPEN_HEADER = ("recordings/openHeader", HttpMethod.POST)

    def __init__(self, path: str, method: HttpMethod):
        self.path = path
        self.method = method

    def get_url(self) -> str:
        """Get the full URL for this endpoint - uses the decrypt server for
        recording-decrypt endpoints, the data server for data endpoints,
        else the user server."""
        if self.path in _DECRYPT_SERVER_PATHS:
            return DECRYPT_DEBUG_BASE_URL + self.path
        effective_base_url = get_data_server_url() if self.path in _DATA_SERVER_PATHS else None
        base = effective_base_url if effective_base_url else BASE_URL
        return base + self.path
