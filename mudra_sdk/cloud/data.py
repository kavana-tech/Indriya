"""
Data models for API requests and responses
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
import json


@dataclass
class SigninRequest:
    """Sign in request data model"""
    email: str
    password: str
    platform: str
    application: str

    def to_json(self) -> Dict[str, str]:
        return {
            'application': self.application,
            'email': self.email,
            'password': self.password,
            'platform': self.platform,
        }


@dataclass
class ChangeNameRequest:
    """Change name request data model"""
    first_name: str
    last_name: str

    def to_json(self) -> Dict[str, str]:
        return {
            'firstName': self.first_name,
            'lastName': self.last_name,
        }


# ==================== Video Upload (Multipart)  ====================


@dataclass
class UploadVideoRequest:
    """Request for data/upload/directVideoRecording API - presigned URLs for multipart upload"""
    file_name: str
    part_count: int

    def to_json(self) -> Dict[str, Any]:
        return {'fileName': self.file_name, 'partCount': self.part_count}


@dataclass
class PresignedUrlPart:
    """Single presigned URL entry in VideoUploadResponse.presignedUrls"""
    part_number: int
    url: str

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'PresignedUrlPart':
        return cls(
            part_number=data.get('partNumber', 0),
            url=data.get('url', ''),
        )


@dataclass
class VideoUploadResponse:
    """Response from data/upload/directVideoRecording API"""
    file_name: str
    folder_name: str
    upload_id: str
    object_key: str
    presigned_urls: list

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'VideoUploadResponse':
        presigned_urls_list = data.get('presignedUrls', []) or []
        parts = [PresignedUrlPart.from_json(p) for p in presigned_urls_list]
        parts.sort(key=lambda p: p.part_number)
        return cls(
            file_name=data.get('fileName', ''),
            folder_name=data.get('folderName', ''),
            upload_id=data.get('uploadId', ''),
            object_key=data.get('objectKey', ''),
            presigned_urls=parts,
        )


@dataclass
class UploadedPart:
    """Single part result from multipart upload (partNumber + etag from S3 response)"""
    part_number: int
    etag: str

    def to_json(self) -> Dict[str, Any]:
        return {'partNumber': self.part_number, 'etag': self.etag}

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'UploadedPart':
        return cls(
            part_number=data.get('partNumber', 0),
            etag=data.get('etag', ''),
        )


@dataclass
class CompleteVideoRecordingRequest:
    """Request body for data/upload/completeVideoRecording API"""
    upload_id: str
    object_key: str
    parts: list  # List[UploadedPart]

    def to_json(self) -> Dict[str, Any]:
        return {
            'uploadId': self.upload_id,
            'objectKey': self.object_key,
            'parts': [p.to_json() if hasattr(p, 'to_json') else p for p in self.parts],
        }


@dataclass
class DownloadRecordingRequest:
    """Request for download recording API"""
    filters: Optional[Dict[str, Any]] = None
    page: Optional[int] = None
    size: Optional[int] = None

    def to_json(self) -> Dict[str, Any]:
        return {
            'filters': self.filters or {},
            'page': self.page,
            'size': self.size,
        }


@dataclass
class DownloadRecordingResponse:
    """Paginated response from download recording API"""
    content: list
    page: int
    size: int
    total_elements: int
    total_pages: int

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'DownloadRecordingResponse':
        content_list = data.get('content', []) or []
        return cls(
            content=content_list,
            page=data.get('page', 0),
            size=data.get('size', 10),
            total_elements=data.get('totalElements', 0),
            total_pages=data.get('totalPages', 0),
        )


@dataclass
class ChangePasswordRequest:
    """Change password request data model"""
    old_password: str
    new_password: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'oldPassword': self.old_password,
            'newPassword': self.new_password,
        }


@dataclass
class ChangePermissionLevelRequest:
    """Change permission level request data model"""
    email: str
    permission_level: int
    
    def to_json(self) -> Dict[str, Any]:
        return {
            'email': self.email,
            'permissionLevel': self.permission_level,
        }


@dataclass
class GoogleSigninRequest:
    """Google sign in request data model"""
    google_id_token: str
    os_type: str
    platform: str

    def to_json(self) -> Dict[str, str]:
        return {
            'application': 'MUDRA_LINK',
            'idToken': self.google_id_token,
            'osType': self.os_type,
            'platform': self.platform,
        }


@dataclass
class AppleSigninRequest:
    """Apple sign in request data model"""
    apple_user_id: str
    first_name: str
    last_name: str
    user_auth_token: str

    def to_json(self) -> Dict[str, str]:
        return {
            'appleUserId': self.apple_user_id,
            'firstName': self.first_name,
            'lastName': self.last_name,
            'userAuthToken': self.user_auth_token,
        }


@dataclass
class UserInfoRequest:
    """User info request data model"""
    
    def to_json(self) -> Dict[str, str]:
        return {
            'application': 'MUDRA_LINK',
        }


@dataclass
class TokenResponse:
    """Token response data model"""
    access_token: str
    refresh_token: str
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'TokenResponse':
        return cls(
            access_token=data['accessToken'],
            refresh_token=data['refreshToken']
        )


@dataclass
class RecorderData:
    """Recorder data model"""
    file_name: str
    url: str
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'RecorderData':
        return cls(
            file_name=data['fileName'],
            url=data['url']
        )
    
    def to_json(self) -> Dict[str, str]:
        return {
            'fileName': self.file_name,
            'url': self.url,
        }


@dataclass
class RefreshTokenRequest:
    """Refresh token request data model"""
    email: str
    refresh_token: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'application': 'MUDRA_LINK',
            'email': self.email,
            'refreshToken': self.refresh_token,
        }


@dataclass
class IsEmailAvailableRequest:
    """Is email available request data model"""
    email: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'email': self.email,
        }


@dataclass
class SignUpRequest:
    """Sign up request data model"""
    email: str
    first_name: str
    last_name: str
    password: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'email': self.email,
            'firstName': self.first_name,
            'lastName': self.last_name,
            'password': self.password,
        }


@dataclass
class EmailVerificationRequest:
    """Email verification request data model"""
    email: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'email': self.email,
        }


@dataclass
class GetAcceptTermsRequest:
    """Get accept terms request data model - signInType as parameter"""
    sign_in_type: str = 'google'

    def to_json(self) -> Dict[str, str]:
        return {
            'signInType': self.sign_in_type,
        }


@dataclass
class SetAcceptTermsRequest:
    """Set accept terms request data model - signInType as parameter"""
    sign_in_type: str = 'google'

    def to_json(self) -> Dict[str, str]:
        return {
            'signInType': self.sign_in_type,
        }


@dataclass
class GetResetPasswordEmailRequest:
    """Get reset password email request data model"""
    email: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'email': self.email,
        }


@dataclass
class ResetPasswordRequest:
    """Reset password request data model"""
    email: str
    password: str
    reset_code: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'email': self.email,
            'password': self.password,
            'resetCode': self.reset_code,
        }


@dataclass
class FirmwareVersionDetailsRequest:
    """Firmware version details request data model"""
    version: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'version': self.version,
        }


@dataclass
class LatestFirmwareVersionListRequest:
    """Latest firmware version list request data model"""
    prod_or_dev: str
    limit: int
    
    def to_json(self) -> Dict[str, Any]:
        return {
            'ProdorDev': self.prod_or_dev,
            'limit': self.limit,
        }


@dataclass
class FirmwareVersionData:
    """Firmware version data model"""
    id: int
    version: str
    details: str
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'FirmwareVersionData':
        return cls(
            id=data['id'],
            version=data['version'],
            details=data['details']
        )


@dataclass
class FuelGaugeResetRequest:
    """Fuel gauge reset request data model"""
    app_version: str
    firmware_version: str
    reset_date: str
    reset_successful: str
    serial_number: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'appVersion': self.app_version,
            'firmWareVersion': self.firmware_version,
            'resetDate': self.reset_date,
            'resetSuccessful': self.reset_successful,
            'serialNumber': self.serial_number,
        }


@dataclass
class SetUserCheckPointRequest:
    """Set user checkpoint request data model"""
    check_point: int
    
    def to_json(self) -> Dict[str, Any]:
        return {
            'application': 'MUDRA_LINK',
            'userCheckpoint': self.check_point,
        }


@dataclass
class SetUserDeviceInfoRequest:
    """Set user device info request data model"""
    app_version: str
    firmware_version: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'application': 'MUDRA_LINK',
            'appVersion': self.app_version,
            'firmwareVersion': self.firmware_version,
        }


@dataclass
class SetSerialNumberRequest:
    """Set serial number request data model"""
    serial_number: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'userSerialNumber': self.serial_number,
        }


@dataclass
class LicenseSecureTokenRequest:
    """Request for license/secure-token API"""
    securityNumber: int

    def to_json(self) -> Dict[str, Any]:
        return {
            'encryptionMethod': 'ADVANCED',
            'securityNumber': self.securityNumber,
        }


@dataclass
class DeleteAccountRequest:
    """Delete account request data model"""
    email: str
    
    def to_json(self) -> Dict[str, str]:
        return {
            'email': self.email,
        }


@dataclass
class MouseConfiguration:
    """Mouse configuration data model"""
    reversed_tap: bool
    reverse_pinch_and_slide: bool
    twist: bool
    double_twist: bool
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'MouseConfiguration':
        return cls(
            reversed_tap=data.get('reversedTap', False),
            reverse_pinch_and_slide=data.get('reversePinchAndSlide', False),
            twist=data.get('twist', False),
            double_twist=data.get('doubleTwist', False),
        )
    
    def to_json(self) -> Dict[str, bool]:
        return {
            'reversedTap': self.reversed_tap,
            'reversePinchAndSlide': self.reverse_pinch_and_slide,
            'twist': self.twist,
            'doubleTwist': self.double_twist,
        }


@dataclass
class KeyboardConfiguration:
    """Keyboard configuration data model"""
    twist: bool
    double_twist: bool
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'KeyboardConfiguration':
        return cls(
            twist=data.get('twist', False),
            double_twist=data.get('doubleTwist', False),
        )
    
    def to_json(self) -> Dict[str, bool]:
        return {
            'twist': self.twist,
            'doubleTwist': self.double_twist,
        }


@dataclass
class AdvancedGesturesStatus:
    """Advanced gestures status data model"""
    mouse: MouseConfiguration
    keyboard: KeyboardConfiguration
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'AdvancedGesturesStatus':
        return cls(
            mouse=MouseConfiguration.from_json(data.get('mouse', {})),
            keyboard=KeyboardConfiguration.from_json(data.get('keyboard', {})),
        )
    
    @classmethod
    def from_json_string(cls, json_string: str) -> 'AdvancedGesturesStatus':
        data = json.loads(json_string)
        return cls.from_json(data)
    
    def to_json(self) -> Dict[str, Any]:
        return {
            'mouse': self.mouse.to_json(),
            'keyboard': self.keyboard.to_json(),
        }
    
    def to_json_string(self) -> str:
        return json.dumps(self.to_json())
