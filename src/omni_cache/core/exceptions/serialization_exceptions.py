"""
Exception classes for omni-cache.

This module defines a comprehensive hierarchy of exceptions used throughout
the omni-cache system, providing clear error categorization and helpful
error messages for debugging and monitoring.
"""

from .omni_cache_error import OmniCacheError


# Serialization exceptions
class SerializationError(OmniCacheError):
    """Base class for serialization-related errors."""


class SerializationFailedError(SerializationError):
    """Raised when object serialization fails."""

    def __init__(self, object_type: str, serializer: str, cause: Exception | None = None) -> None:
        details = {"object_type": object_type, "serializer": serializer}
        message = f"Failed to serialize object of type '{object_type}' using '{serializer}'"
        super().__init__(message, details, cause)


class DeserializationFailedError(SerializationError):
    """Raised when object deserialization fails."""

    def __init__(self, data_type: str, deserializer: str, cause: Exception | None = None) -> None:
        details = {"data_type": data_type, "deserializer": deserializer}
        message = f"Failed to deserialize data of type '{data_type}' using '{deserializer}'"
        super().__init__(message, details, cause)
