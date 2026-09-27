"""
Authentication Storage Manager
Handles persistent storage of authentication tokens and user data
"""

import json
import os
from pathlib import Path
from typing import Optional
from threading import Lock

from ..logging_config import get_logger

logger = get_logger(__name__)


class AuthStorage:
    """Singleton class for managing authentication storage"""
    
    _instance: Optional['AuthStorage'] = None
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
        
        # Get user's home directory and create .mudra_sdk folder
        home_dir = Path.home()
        self._storage_dir = home_dir / '.mudra_sdk'
        self._storage_dir.mkdir(exist_ok=True)
        
        self._storage_file = self._storage_dir / 'auth_storage.json'
        self._data: dict = {}
        self._load()
        self._initialized = True
    
    def _load(self):
        """Load data from storage file"""
        if self._storage_file.exists():
            try:
                with open(self._storage_file, 'r') as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}
        else:
            self._data = {}
    
    def _save(self):
        """Save data to storage file"""
        try:
            with open(self._storage_file, 'w') as f:
                json.dump(self._data, f)
        except IOError as e:
            logger.error(f"Error saving auth storage: {e}")
    
    def clear(self) -> bool:
        """Clear all stored authentication data"""
        try:
            self._data = {}
            self._save()
            return True
        except Exception as e:
            logger.error(f"Error clearing auth storage: {e}")
            return False
    
    @property
    def access_token(self) -> str:
        """Get access token"""
        return self._data.get('accessToken', '')
    
    @access_token.setter
    def access_token(self, value: Optional[str]):
        """Set access token"""
        self._data['accessToken'] = value or ''
        self._save()
    
    @property
    def refresh_token(self) -> str:
        """Get refresh token"""
        return self._data.get('refreshToken', '')
    
    @refresh_token.setter
    def refresh_token(self, value: Optional[str]):
        """Set refresh token"""
        self._data['refreshToken'] = value or ''
        self._save()
    
    @property
    def email(self) -> str:
        """Get email"""
        return self._data.get('email', '')
    
    @email.setter
    def email(self, value: Optional[str]):
        """Set email"""
        self._data['email'] = value or ''
        self._save()
    
    @property
    def google_id_token(self) -> str:
        """Get Google ID token"""
        return self._data.get('googleIdToken', '')
    
    @google_id_token.setter
    def google_id_token(self, value: Optional[str]):
        """Set Google ID token"""
        self._data['googleIdToken'] = value or ''
        self._save()
    
    @property
    def google_access_token(self) -> str:
        """Get Google access token"""
        return self._data.get('googleAccessToken', '')
    
    @google_access_token.setter
    def google_access_token(self, value: Optional[str]):
        """Set Google access token"""
        self._data['googleAccessToken'] = value or ''
        self._save()
    
    @property
    def google_refresh_token(self) -> str:
        """Get Google refresh token"""
        return self._data.get('googleRefreshToken', '')
    
    @google_refresh_token.setter
    def google_refresh_token(self, value: Optional[str]):
        """Set Google refresh token"""
        self._data['googleRefreshToken'] = value or ''
        self._save()
    
    @property
    def google_user_name(self) -> str:
        """Get Google user name"""
        return self._data.get('googleUserName', '')
    
    @google_user_name.setter
    def google_user_name(self, value: Optional[str]):
        """Set Google user name"""
        self._data['googleUserName'] = value or ''
        self._save()
    
    @property
    def google_user_email(self) -> str:
        """Get Google user email"""
        return self._data.get('googleUserEmail', '')
    
    @google_user_email.setter
    def google_user_email(self, value: Optional[str]):
        """Set Google user email"""
        self._data['googleUserEmail'] = value or ''
        self._save()
