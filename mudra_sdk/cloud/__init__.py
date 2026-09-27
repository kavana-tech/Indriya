"""
Mudra Cloud SDK Module
Provides cloud API client functionality for Mudra services
"""

from .api_config import (
    ResponseCode,
)

from .auth_storage import AuthStorage

from .data import (
    SigninRequest,
    ChangeNameRequest,
    ChangePasswordRequest,
    ChangePermissionLevelRequest,
    GoogleSigninRequest,
    AppleSigninRequest,
    UserInfoRequest,
    TokenResponse,
    RecorderData,
    RefreshTokenRequest,
    IsEmailAvailableRequest,
    SignUpRequest,
    EmailVerificationRequest,
    GetAcceptTermsRequest,
    SetAcceptTermsRequest,
    GetResetPasswordEmailRequest,
    ResetPasswordRequest,
    FirmwareVersionDetailsRequest,
    LatestFirmwareVersionListRequest,
    FirmwareVersionData,
    FuelGaugeResetRequest,
    SetUserCheckPointRequest,
    SetUserDeviceInfoRequest,
    SetSerialNumberRequest,
    LicenseSecureTokenRequest,
    DeleteAccountRequest,
    MouseConfiguration,
    KeyboardConfiguration,
    AdvancedGesturesStatus,
    UploadVideoRequest,
    VideoUploadResponse,
    PresignedUrlPart,
    UploadedPart,
    CompleteVideoRecordingRequest,
    DownloadRecordingRequest,
    DownloadRecordingResponse,
)

from .mudra_server_client import MudraServerClient

__all__ = [
    # Main Client
    'MudraServerClient',
    # API Configuration
    'ResponseCode',
    # Auth Storage
    'AuthStorage',
    # Request Data Models
    'SigninRequest',
    'GoogleSigninRequest',
    'AppleSigninRequest',
    'SignUpRequest',
    'RefreshTokenRequest',
    'IsEmailAvailableRequest',
    'EmailVerificationRequest',
    'GetResetPasswordEmailRequest',
    'ResetPasswordRequest',
    'LicenseSecureTokenRequest',
    'DeleteAccountRequest',
    # User Management Data Models
    'ChangeNameRequest',
    'ChangePasswordRequest',
    'ChangePermissionLevelRequest',
    'UserInfoRequest',
    # Device & Firmware Data Models
    'SetUserDeviceInfoRequest',
    'SetSerialNumberRequest',
    'SetUserCheckPointRequest',
    'FirmwareVersionDetailsRequest',
    'LatestFirmwareVersionListRequest',
    'FuelGaugeResetRequest',
    # Terms & Configuration Data Models
    'GetAcceptTermsRequest',
    'SetAcceptTermsRequest',
    'MouseConfiguration',
    'KeyboardConfiguration',
    'AdvancedGesturesStatus',
    # Response Data Models
    'TokenResponse',
    'RecorderData',
    'FirmwareVersionData',
    # Video upload/recording
    'UploadVideoRequest',
    'VideoUploadResponse',
    'PresignedUrlPart',
    'UploadedPart',
    'CompleteVideoRecordingRequest',
    'DownloadRecordingRequest',
    'DownloadRecordingResponse',
]
