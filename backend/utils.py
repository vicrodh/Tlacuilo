"""
Shared utility functions for Tlacuilo backend.

Provides common operations like path validation, temp file management,
and system command detection.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Sequence

try:
    from exceptions import FileNotFoundError as TlacuiloFileNotFoundError
    from exceptions import InvalidFileTypeError, DependencyMissingError
except ImportError:
    from .exceptions import FileNotFoundError as TlacuiloFileNotFoundError
    from .exceptions import InvalidFileTypeError, DependencyMissingError

# Use our custom FileNotFoundError (shadowing builtin intentionally)
FileNotFoundError = TlacuiloFileNotFoundError


def which_command(name: str) -> Path | None:
    """
    Find an executable in PATH.

    Args:
        name: Command name to find (e.g., "libreoffice", "gs", "pandoc")

    Returns:
        Path to executable if found, None otherwise.
    """
    path = shutil.which(name)
    return Path(path) if path else None


def check_dependency(
    name: str,
    alternatives: Sequence[str] | None = None,
    install_hint: str | None = None,
) -> Path:
    """
    Check if a system dependency is available.

    Args:
        name: Primary command name to check
        alternatives: Alternative command names (e.g., ["libreoffice", "soffice"])
        install_hint: Installation instructions for error message

    Returns:
        Path to the found executable.

    Raises:
        DependencyMissingError: If dependency is not found.
    """
    candidates = [name] + list(alternatives or [])

    for cmd in candidates:
        path = which_command(cmd)
        if path:
            return path

    raise DependencyMissingError(name, install_hint)


def validate_file_exists(
    path: Path | str,
    extensions: Sequence[str] | None = None,
) -> Path:
    """
    Validate that a file exists and optionally check its extension.

    Args:
        path: File path to validate
        extensions: Allowed extensions (without dot, e.g., ["pdf", "jpg"])

    Returns:
        Resolved Path object.

    Raises:
        FileNotFoundError: If file doesn't exist.
        InvalidFileTypeError: If extension doesn't match.
    """
    p = Path(path).resolve()

    if not p.exists():
        raise FileNotFoundError(str(p))

    if not p.is_file():
        raise FileNotFoundError(str(p))

    if extensions:
        ext = p.suffix.lower().lstrip(".")
        if ext not in [e.lower().lstrip(".") for e in extensions]:
            raise InvalidFileTypeError(str(p), list(extensions))

    return p


def validate_files_exist(
    paths: Sequence[Path | str],
    extensions: Sequence[str] | None = None,
) -> list[Path]:
    """
    Validate multiple files exist.

    Args:
        paths: File paths to validate
        extensions: Allowed extensions

    Returns:
        List of resolved Path objects.

    Raises:
        FileNotFoundError: If any file doesn't exist.
        InvalidFileTypeError: If any extension doesn't match.
    """
    return [validate_file_exists(p, extensions) for p in paths]


def ensure_output_dir(path: Path | str) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        Resolved Path object.
    """
    p = Path(path).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_temp_path(prefix: str = "tlacuilo", suffix: str = "") -> Path:
    """
    Generate a unique temporary file path.

    Args:
        prefix: Filename prefix
        suffix: Filename suffix (e.g., ".pdf")

    Returns:
        Path to a non-existent temp file.
    """
    temp_dir = Path(tempfile.gettempdir())
    unique_id = uuid.uuid4().hex[:8]
    filename = f"{prefix}_{unique_id}{suffix}"
    return temp_dir / filename


def get_temp_dir(prefix: str = "tlacuilo") -> Path:
    """
    Create a unique temporary directory.

    Args:
        prefix: Directory name prefix

    Returns:
        Path to the created temp directory.
    """
    temp_base = Path(tempfile.gettempdir())
    unique_id = uuid.uuid4().hex[:8]
    dirname = f"{prefix}_{unique_id}"
    temp_dir = temp_base / dirname
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


def get_file_size_mb(path: Path | str) -> float:
    """
    Get file size in megabytes.

    Args:
        path: File path

    Returns:
        File size in MB (rounded to 2 decimals).
    """
    size_bytes = Path(path).stat().st_size
    return round(size_bytes / (1024 * 1024), 2)


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable form.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "12.5 MB", "340 KB")
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_extension(path: Path | str) -> str:
    """
    Get file extension without dot, lowercase.

    Args:
        path: File path

    Returns:
        Extension string (e.g., "pdf", "jpg")
    """
    return Path(path).suffix.lower().lstrip(".")


def safe_filename(name: str, max_length: int = 200) -> str:
    """
    Sanitize a string to be safe for use as a filename.

    Args:
        name: Original name
        max_length: Maximum length

    Returns:
        Safe filename string.
    """
    # Remove/replace unsafe characters
    unsafe = '<>:"/\\|?*\x00'
    for char in unsafe:
        name = name.replace(char, "_")

    # Replace multiple underscores with single
    while "__" in name:
        name = name.replace("__", "_")

    # Trim and limit length
    name = name.strip("_ ")
    if len(name) > max_length:
        # Preserve extension if present
        ext = get_extension(name)
        if ext:
            base_max = max_length - len(ext) - 1
            name = name[:base_max] + "." + ext
        else:
            name = name[:max_length]

    return name or "unnamed"


def cleanup_temp_files(*paths: Path | str) -> None:
    """
    Safely delete temporary files/directories.

    Args:
        paths: Paths to delete (files or directories)
    """
    for p in paths:
        try:
            path = Path(p)
            if path.exists():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        except OSError:
            pass  # Best effort cleanup
