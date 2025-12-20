"""
Custom exceptions for Tlacuilo backend.

All exceptions inherit from TlacuiloError for easy catching.
"""

from __future__ import annotations


class TlacuiloError(Exception):
    """Base exception for all Tlacuilo backend errors."""

    def __init__(self, message: str, details: str | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class FileNotFoundError(TlacuiloError):
    """Raised when a required file does not exist."""

    def __init__(self, path: str) -> None:
        super().__init__("File not found", path)
        self.path = path


class InvalidFileTypeError(TlacuiloError):
    """Raised when a file has an unsupported or invalid type."""

    def __init__(self, path: str, expected: list[str] | None = None) -> None:
        details = path
        if expected:
            details = f"{path} (expected: {', '.join(expected)})"
        super().__init__("Invalid file type", details)
        self.path = path
        self.expected = expected


class ConversionError(TlacuiloError):
    """Raised when a file conversion fails."""

    def __init__(self, source: str, target: str, reason: str | None = None) -> None:
        details = f"{source} -> {target}"
        if reason:
            details = f"{details} ({reason})"
        super().__init__("Conversion failed", details)
        self.source = source
        self.target = target
        self.reason = reason


class DependencyMissingError(TlacuiloError):
    """Raised when a required system dependency is not available."""

    def __init__(self, dependency: str, install_hint: str | None = None) -> None:
        details = dependency
        if install_hint:
            details = f"{dependency}. Install with: {install_hint}"
        super().__init__("Missing dependency", details)
        self.dependency = dependency
        self.install_hint = install_hint


class CompressionError(TlacuiloError):
    """Raised when PDF compression fails."""

    def __init__(self, path: str, reason: str | None = None) -> None:
        details = path
        if reason:
            details = f"{path} ({reason})"
        super().__init__("Compression failed", details)
        self.path = path
        self.reason = reason


class TimeoutError(TlacuiloError):
    """Raised when an operation exceeds its timeout."""

    def __init__(self, operation: str, timeout_seconds: int) -> None:
        super().__init__("Operation timed out", f"{operation} after {timeout_seconds}s")
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class CorruptedFileError(TlacuiloError):
    """Raised when a file is corrupted or malformed."""

    def __init__(self, path: str, reason: str | None = None) -> None:
        details = path
        if reason:
            details = f"{path} ({reason})"
        super().__init__("Corrupted file", details)
        self.path = path
        self.reason = reason
