"""
Exception classes for omni-cache.

This module defines a comprehensive hierarchy of exceptions used throughout
the omni-cache system, providing clear error categorization and helpful
error messages for debugging and monitoring.
"""

from typing import Any

from .omni_cache_error import OmniCacheError


# Health check exceptions
class HealthCheckError(OmniCacheError):
    """Raised when health checks fail."""

    def __init__(
        self,
        component: str,
        check_type: str,
        reason: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        details: dict[str, Any] = {"component": component, "check_type": check_type}
        if reason:
            details["reason"] = reason

        message = f"Health check failed for {component} ({check_type})"
        if reason:
            message += f": {reason}"

        super().__init__(message, details, cause)


# Routing exceptions
class RoutingError(OmniCacheError):
    """Base class for routing-related errors."""


class RouteNotFoundError(RoutingError):
    """Raised when no route can be found for a key."""

    def __init__(
        self,
        key: Any,
        namespace: str | None = None,
        available_routes: list[str] | None = None,
    ) -> None:
        details: dict[str, Any] = {"key": str(key)}
        if namespace:
            details["namespace"] = namespace
        if available_routes is not None:
            details["available_routes"] = available_routes

        message = f"No route found for key '{key}'"

        super().__init__(message, details)


class InvalidRouteError(RoutingError):
    """Raised when a routing rule is invalid."""

    def __init__(self, route_pattern: str, reason: str) -> None:
        details: dict[str, Any] = {"route_pattern": route_pattern, "reason": reason}
        message = f"Invalid routing rule '{route_pattern}': {reason}"
        super().__init__(message, details)
