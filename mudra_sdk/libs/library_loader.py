"""
Platform-specific library loader for Mudra SDK
"""
import os
import sys
import platform
from pathlib import Path
from typing import Optional

try:
    import ctypes
    from ctypes import CDLL
    import ctypes.util
except ImportError:
    ctypes = None
    CDLL = None


def get_platform_info() -> tuple[str, str]:
    """
    Detect the current platform and architecture.
    
    Returns:
        tuple: (platform_name, architecture) where:
            - platform_name: 'windows', 'linux', 'darwin', or 'android'
            - architecture: 'x86', 'x64', 'x86_64', 'arm', 'arm64', 'aarch64'
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Detect Android
    if 'android' in system or hasattr(sys, 'getandroidapilevel'):
        platform_name = 'android'
    elif system == 'windows':
        platform_name = 'windows'
    elif system == 'darwin':
        platform_name = 'darwin'
    elif system == 'linux':
        platform_name = 'linux'
    else:
        platform_name = system
    
    # Normalize architecture names
    if machine in ('x86_64', 'amd64'):
        if platform_name == 'windows':
            arch = 'x64'
        elif platform_name == 'android':
            arch = 'x86_64'  # Android uses x86_64
        else:
            arch = 'x86_64'
    elif machine in ('i386', 'i686', 'x86'):
        arch = 'x86'
    elif machine in ('arm64', 'aarch64'):
        if platform_name == 'darwin':
            arch = 'arm64'
        elif platform_name == 'android':
            arch = 'aarch64'  # Android typically uses aarch64
        else:
            arch = 'aarch64'
    elif machine.startswith('arm'):
        if platform_name == 'android':
            arch = 'arm'  # Android armeabi-v7a maps to arm
        else:
            arch = 'arm'
    else:
        arch = machine
    
    return platform_name, arch


def get_library_extension(platform_name: str) -> str:
    """
    Get the library file extension for the given platform.
    
    Args:
        platform_name: Platform name ('windows', 'linux', 'darwin', 'android')
    
    Returns:
        Library file extension ('.dll', '.so', '.dylib')
    """
    extensions = {
        'windows': '.dll',
        'linux': '.so',
        'darwin': '.dylib',
        'android': '.so',
    }
    return extensions.get(platform_name, '.so')


def find_library_path(library_name: str, base_name: Optional[str] = None) -> Optional[Path]:
    """
    Find the path to the native library file.
    
    Args:
        library_name: Name of the library (e.g., 'MudraSDK')
        base_name: Optional base name if different from library_name
    
    Returns:
        Path to the library file, or None if not found
    """
    if base_name is None:
        base_name = library_name
    
    # Get platform info
    platform_name, arch = get_platform_info()
    ext = get_library_extension(platform_name)
    
    # Get the package directory
    package_dir = Path(__file__).parent.parent
    libs_dir = package_dir / 'libs'
    
    # Map platform names to directory names
    platform_dirs = {
        'windows': 'windows',
        'linux': 'linux',
        'darwin': 'darwin',
        'android': 'android',  # You may want to add android directory
    }
    
    platform_dir = platform_dirs.get(platform_name)
    if not platform_dir:
        return None
    
    # Try to find the library
    lib_path = libs_dir / platform_dir / arch / f"{base_name}{ext}"
    
    if lib_path.exists():
        return lib_path
    
    # Fallback: try without architecture subdirectory
    lib_path = libs_dir / platform_dir / f"{base_name}{ext}"
    if lib_path.exists():
        return lib_path
    
    return None


def load_library(library_name: str, base_name: Optional[str] = None) -> Optional[CDLL]:
    """
    Load the native library for the current platform.
    
    Args:
        library_name: Name of the library (e.g., 'MudraSDK')
        base_name: Optional base name if different from library_name
    
    Returns:
        CDLL object if successful, None otherwise
    
    Raises:
        OSError: If the library cannot be loaded
    """
    if ctypes is None or CDLL is None:
        raise ImportError("ctypes is not available on this platform")
    
    lib_path = find_library_path(library_name, base_name)
    
    if lib_path is None:
        platform_name, arch = get_platform_info()
        raise FileNotFoundError(
            f"Library '{library_name}' not found for platform '{platform_name}' "
            f"architecture '{arch}'. Expected path: {lib_path}"
        )
    
    try:
        # Load the library
        lib = CDLL(str(lib_path))
        return lib
    except OSError as e:
        raise OSError(
            f"Failed to load library '{library_name}' from {lib_path}: {e}"
        ) from e


# Convenience function for common use case
def get_mudra_library() -> Optional[CDLL]:
    """
    Load the Mudra core library.
    
    Returns:
        CDLL object for the Mudra core library
    """
    return load_library('MudraSDK', 'MudraSDK')

