"""
Request Interceptor for HTTP requests
Handles authentication token injection and automatic token refresh
"""

from typing import Any, Optional, Callable, Union
import requests
from requests.adapters import HTTPAdapter

# Import Retry from urllib3 (standard dependency of requests)
# urllib3 is a direct dependency of requests and should always be available
from urllib3.util.retry import Retry  # type: ignore

from .api_config import ResponseCode, BASE_URL
from ..logging_config import get_logger

logger = get_logger(__name__)


class RequestInterceptorDelegate:
    """Delegate interface for request interceptor"""
    
    def get_access_token(self) -> Optional[str]:
        """Get the current access token"""
        raise NotImplementedError
    
    def on_refresh_token_required(self) -> Optional[str]:
        """Called when token refresh is required. Should return new access token or None"""
        raise NotImplementedError


class RequestInterceptor:
    """HTTP request interceptor for handling authentication and retries"""
    
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 2
    
    def __init__(self, delegate: RequestInterceptorDelegate):
        self.delegate = delegate
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _refresh_token(self) -> Optional[str]:
        """Attempt to refresh the access token"""
        try:
            return self.delegate.on_refresh_token_required()
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return None
    
    def _is_success_status_code(self, status_code: Optional[int]) -> bool:
        """Check if status code indicates success"""
        return status_code in [
            ResponseCode.OK.value,
            ResponseCode.CREATED.value,
            ResponseCode.ACCEPTED.value
        ]
    
    def _should_skip_auth(self, url: str) -> bool:
        """Check if authentication should be skipped for this URL"""
        return f"{BASE_URL}auth" in url
    
    def request(
        self,
        method: str,
        url: str,
        data: Optional[Union[dict, bytes, str]] = None,
        json_data: Optional[dict] = None,
        files: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> requests.Response:
        """
        Make an HTTP request with automatic token injection and refresh
        
        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            url: Request URL
            data: Form data
            json_data: JSON data
            files: Files to upload
            headers: Additional headers
            timeout: Request timeout in seconds
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
        """
        if timeout is None:
            # Use longer timeout for non-rawData endpoints
            if 'rawData' not in url:
                timeout = self.DEFAULT_TIMEOUT
        
        # Prepare headers
        request_headers = headers.copy() if headers else {}
        
        # Add authentication token if needed
        if not self._should_skip_auth(url):
            token = self.delegate.get_access_token()
            if not token:
                token = self._refresh_token()
            
            if token:
                request_headers['Authorization'] = f'Bearer {token}'
            else:
                raise requests.exceptions.HTTPError(
                    "Unauthorized: No valid access token available"
                )
        
        # Make the request
        try:
            response = self.session.request(
                method=method,
                url=url,
                data=data,
                json=json_data,
                files=files,
                headers=request_headers,
                timeout=timeout,
                **kwargs
            )
            
            # Handle 401 Unauthorized - try to refresh token and retry
            if response.status_code == ResponseCode.UNAUTHORIZED.value:
                new_token = self._refresh_token()
                if new_token:
                    # Retry with new token
                    request_headers['Authorization'] = f'Bearer {new_token}'
                    response = self.session.request(
                        method=method,
                        url=url,
                        data=data,
                        json=json_data,
                        files=files,
                        headers=request_headers,
                        timeout=timeout,
                        **kwargs
                    )
                else:
                    raise requests.exceptions.HTTPError(
                        "Unauthorized: Token refresh failed"
                    )
            
            return response
            
        except requests.exceptions.RequestException as e:
            # Handle network errors
            if isinstance(e, requests.exceptions.Timeout):
                raise requests.exceptions.HTTPError(
                    f"Request timeout: {e}"
                )
            elif isinstance(e, requests.exceptions.ConnectionError):
                raise requests.exceptions.HTTPError(
                    "No internet connectivity. Please check the connection and try again"
                )
            raise
