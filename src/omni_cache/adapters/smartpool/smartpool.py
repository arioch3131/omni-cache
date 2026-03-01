"""
SmartPool Adapter for omni-cache - Complete implementation with performance metrics.

Features:
1. Full BasePoolAdapter compatibility
2. Complete performance metrics integration
3. Standard get()/put() interface with SmartPool compatibility
4. All abstract methods implemented
5. English documentation and messages
6. Performance monitoring and health reporting
"""

# pylint: disable=too-many-lines

import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import (
    Any,
    Generic,
    TypeVar,
    cast,
)

from omni_cache.adapters.base import BasePoolAdapter
from omni_cache.adapters.smartpool.config import SmartPoolAdapterConfig
from omni_cache.adapters.smartpool.factory_smartpool import SimpleSmartPoolFactory
from omni_cache.adapters.smartpool.wrapper import AutoWeakRefWrapper
from omni_cache.core.exceptions import (
    AdapterNotConnectedError,
    ConfigurationError,
    PoolEmptyError,
)
from omni_cache.core.interfaces.enum_dataclasses import CacheBackend

T = TypeVar("T")

try:
    from smartpool import (
        MemoryConfig,
        MemoryPressure,
        ObjectCreationCost,
        PoolConfiguration,
        SmartObjectManager,
    )

    SMARTPOOL_ADAPTER_AVAILABLE = True
except ImportError:
    SMARTPOOL_ADAPTER_AVAILABLE = False
    MemoryConfig = None  # type: ignore
    PoolConfiguration = None  # type: ignore
    SmartObjectManager = None  # type: ignore


# pylint: disable=too-many-ancestors
class SmartPoolAdapter(BasePoolAdapter, Generic[T]):
    """
    SmartPool adapter for omni-cache.

    This adapter provides advanced object pooling capabilities using the SmartPool library.
    It supports automatic tuning, performance metrics, and sophisticated memory management.
    """

    _config: SmartPoolAdapterConfig  # Add this line

    def __init__(self, config: dict[str, Any] | SmartPoolAdapterConfig):
        if not SMARTPOOL_ADAPTER_AVAILABLE:
            raise ImportError(
                "smartpool is not available. Please install it to use SmartPoolAdapter."
            )
        if config is None:
            raise ConfigurationError("Configuration cannot be None for SmartPoolAdapter.")
        # Handle different config types
        parsed_config: SmartPoolAdapterConfig | None = None
        if isinstance(config, dict):
            parsed_config = SmartPoolAdapterConfig(**config)
        elif isinstance(config, SmartPoolAdapterConfig):
            parsed_config = config
        else:
            raise ConfigurationError(
                "Invalid configuration type: "
                f"{type(config)}. Expected dict or SmartPoolAdapterConfig."
            )

        super().__init__(parsed_config)

        self._pool: SmartObjectManager[T] | None = None
        self._factory: SimpleSmartPoolFactory | None = None
        self._lock = threading.RLock()
        self._borrowed_objects: dict[int, tuple] = {}  # Track objects for standard interface
        self._manual_obj_id = -1

    def _wrap_object(self, obj: T) -> T | AutoWeakRefWrapper[T]:
        """Wrap object if auto_wrap_objects is enabled."""
        if self.config.auto_wrap_objects and not isinstance(obj, AutoWeakRefWrapper):
            return cast(T | AutoWeakRefWrapper[T], AutoWeakRefWrapper(obj))
        return cast(T | AutoWeakRefWrapper[T], obj)

    def _next_manual_obj_id(self) -> int:
        """Generate a unique negative object id for manual pool insertions."""
        obj_id = self._manual_obj_id
        self._manual_obj_id -= 1
        return obj_id

    # pylint: disable=protected-access
    def _unwrap_object(self, obj: T | AutoWeakRefWrapper[T]) -> T:
        """Unwrap object if it's wrapped."""
        if isinstance(obj, AutoWeakRefWrapper):
            return cast(T, obj._obj)
        return obj

    def _create_factory(self) -> SimpleSmartPoolFactory:
        """Create the factory with proper configuration."""
        # Extract functions from extra_config
        extra_config = self.config.extra_config or {}
        reset_func = extra_config.get("reset_func")
        validate_func = self.config.factory_validate_function or extra_config.get("validate_func")
        destroy_func = extra_config.get("destroy_func")
        self._logger.info("Creation of the factory")

        factory_func = self.config.factory_function
        if factory_func is None:  # Added check
            raise ValueError("Factory function cannot be None.")  # Or provide a default

        return SimpleSmartPoolFactory(
            factory_func=factory_func,  # Use the non-None factory_func
            validate_func=validate_func,
            factory_args=self.config.factory_args,
            factory_kwargs=self.config.factory_kwargs,
            auto_wrap=self.config.auto_wrap_objects,  # Allow factory to wrap if configured
            reset_func=reset_func,
            destroy_func=destroy_func,
        )

    @property
    def config(self) -> SmartPoolAdapterConfig:
        """Expose config as public property (for backward compatibility)."""
        return self._config

    def _create_memory_config(self) -> MemoryConfig:
        """Create memory configuration for SmartPool."""
        max_objects_per_key = (
            self.config.max_size_per_key
            if self.config.max_size_per_key is not None
            else self.config.max_size
        )
        return MemoryConfig(
            max_objects_per_key=max_objects_per_key,
            ttl_seconds=self.config.max_age_seconds,
            cleanup_interval_seconds=self.config.cleanup_interval,
            enable_background_cleanup=self.config.enable_background_cleanup,
            enable_performance_metrics=self.config.enable_performance_metrics,
            enable_logging=False,  # DISABLE verbose SmartPool logs
            max_validation_attempts=1,
            max_corrupted_objects=3,
            enable_acquisition_tracking=True,  # Enable for metrics
            enable_lock_contention_tracking=True,  # Enable for metrics
            max_performance_history_size=100,
            max_expected_concurrency=10,
            object_creation_cost=ObjectCreationCost.LOW,
            memory_pressure=MemoryPressure.LOW,
        )

    def _create_pool_config(self) -> PoolConfiguration:
        """Create pool configuration for SmartPool."""
        return PoolConfiguration(
            max_total_objects=self.config.max_size,
            enable_monitoring=self.config.enable_performance_metrics,
            register_atexit=False,
        )

    def _do_connect(self) -> bool:
        """Connect to SmartPool backend."""
        try:
            with self._lock:
                if self._pool is not None:
                    return True

                # Create factory
                self._factory = self._create_factory()

                # Create memory and pool configurations
                memory_config = self._create_memory_config()
                pool_config = self._create_pool_config()

                # Create the SmartObjectManager
                self._pool = SmartObjectManager(
                    factory=self._factory, default_config=memory_config, pool_config=pool_config
                )

                # Enable auto-tuning if requested
                if self.config.enable_auto_tuning:
                    self._pool.enable_auto_tuning(self.config.auto_tuning_interval)

                self._logger.info("SmartPool adapter '%s' connected", self.config.name)

                # Pre-populate pool
                self._prepopulate_pool()

                return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("SmartPool adapter connection failed: %s", e)
            return False

    def _prepopulate_pool(self) -> None:
        """Pre-populate the pool with initial objects."""
        self._logger.info(
            "Attempting to pre-populate pool with %d objects.", self.config.initial_size
        )  # Added debug
        try:
            if self._factory is None:  # Added check
                self._logger.error("Factory not initialized for pre-population.")
                return
            if self._pool is None:  # Added check
                self._logger.error("Pool not initialized for pre-population.")
                return

            # Assign to local variables for mypy's flow analysis
            factory = self._factory
            pool = self._pool

            pool_key = factory.get_key(*self.config.factory_args, **self.config.factory_kwargs)

            for _ in range(self.config.initial_size):
                new_obj = factory.create_object(
                    *self.config.factory_args, **self.config.factory_kwargs
                )
                # SmartPool expects unique object IDs for managed entries.
                obj_id = self._next_manual_obj_id()
                pool.release(obj_id, pool_key, new_obj)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.warning("Pool pre-population failed: %s", e)

    def _ensure_pool_replenished(self) -> None:
        """Replenish pool up to initial_size after object destruction/attrition."""
        if self._pool is None or self._factory is None or self.config.initial_size <= 0:
            return

        try:
            stats = self._pool.get_basic_stats()
            total_managed = int(stats.get("total_managed_objects", 0))
            missing = self.config.initial_size - total_managed
            if missing <= 0:
                return

            pool_key = self._factory.get_key(
                *self.config.factory_args, **self.config.factory_kwargs
            )
            for _ in range(missing):
                new_obj = self._factory.create_object(
                    *self.config.factory_args, **self.config.factory_kwargs
                )
                self._pool.release(self._next_manual_obj_id(), pool_key, new_obj)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.debug("Pool replenishment skipped due to error: %s", e)

    def _do_disconnect(self) -> bool:
        """Disconnect from SmartPool backend."""
        try:
            with self._lock:
                if self._pool is not None:
                    self._pool.shutdown()
                    self._pool = None
                    self._factory = None
                    self._borrowed_objects.clear()
                    self._logger.info("SmartPool adapter '%s' disconnected", self.config.name)
                return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("SmartPool adapter disconnection failed: %s", e)
            return False

    def _do_health_check(self) -> bool:
        """Perform the actual health check logic."""
        if not self._pool:
            return False
        try:
            health_status = self._pool.get_health_status()
            return health_status.get("status") == "healthy"
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("SmartPool health check failed: %s", e)
            return False

    # Abstract methods implementation with omni-cache patterns
    def size(self) -> int:
        """Get the current number of objects in the pool."""
        return self._safe_operation(self._size_internal, "size", default=0)

    def _size_internal(self) -> int:
        """Internal implementation of size operation."""
        if self._pool is None:
            return 0
        try:
            stats = self._pool.get_basic_stats()
            return cast(int, stats.get("total_pooled_objects", stats.get("pooled_objects", 0)))
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error getting pool size: %s", e)
            return 0

    def is_empty(self) -> bool:
        """Check if the pool is empty."""
        return self._safe_operation(self._is_empty_internal, "is_empty", default=True)

    def _is_empty_internal(self) -> bool:
        """Internal implementation of is_empty check."""
        if self._pool is None:
            return True
        try:
            stats = self._pool.get_basic_stats()
            pooled = stats.get("total_pooled_objects", stats.get("pooled_objects", 0))
            active = stats.get("active_objects_count", stats.get("active_objects", 0))
            is_empty = (pooled + active) == 0
            self._update_pool_stats("is_empty", active=active, idle=pooled)
            return cast(bool, is_empty)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error checking if pool is empty: %s", e)
            return True

    def clear(self) -> bool:
        """Clear all objects from the pool."""
        return self._safe_operation(self._clear_internal, "clear", default=False)

    def _clear_internal(self) -> bool:
        """Internal implementation of clear operation."""
        if self._pool is None:
            return False
        if self._factory is None:  # Added check
            self._logger.error("Factory not initialized for clear operation.")
            return False

        # Assign to local variables for mypy's flow analysis
        pool_manager = self._pool
        factory_manager = self._factory

        try:
            # Get stats before clearing
            old_stats = pool_manager.get_basic_stats()
            active_before = old_stats.get("active_objects", 0)
            idle_before = old_stats.get("pooled_objects", 0)

            # SmartPool doesn't have direct clear, so shutdown and recreate
            pool_manager.shutdown()

            # Recreate pool with same configuration
            memory_config = self._create_memory_config()
            pool_config = self._create_pool_config()
            self._pool = SmartObjectManager(
                factory=factory_manager, default_config=memory_config, pool_config=pool_config
            )

            # Clear borrowed objects tracking
            self._borrowed_objects.clear()

            self._update_pool_stats("clear", active=-active_before, idle=-idle_before)
            return True
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error clearing pool: %s", e)
            self._update_pool_stats("clear", success=False)
            return False

    # Standard pool interface (overridden for SmartPool compatibility)
    # pylint: disable=unused-argument
    def get(self, *args: Any, timeout: float | None = None, **kwargs: Any) -> T | None:
        """Get an object from the pool (standard interface)."""
        return self._safe_operation(
            lambda: self._get_internal(*args, **kwargs), "get", default=None
        )

    # pylint: disable=unused-argument
    def put(self, obj: T, timeout: float | None = None) -> bool:
        """Return an object to the pool (standard interface)."""
        return self._safe_operation(lambda: self._put_internal(obj), "put", default=False)

    def _get_internal(self, *args: Any, **kwargs: Any) -> T | None:
        """Internal implementation of get operation."""
        if self._pool is None:
            raise AdapterNotConnectedError(f"Adapter {self.config.name} not connected")
        pool_manager: SmartObjectManager[T] = self._pool
        try:
            final_args = args if args else self.config.factory_args
            final_kwargs = {**self.config.factory_kwargs, **kwargs}

            acquired_result = pool_manager.acquire(*final_args, **final_kwargs)

            # SmartPool returns always a tuple (obj_id, key, actual_obj) or raises an exception
            obj_id, key, actual_obj = acquired_result

            # Determine the object that will be returned to the user
            object_to_return: T | AutoWeakRefWrapper[T]
            if self.config.auto_wrap_objects:
                object_to_return = self._wrap_object(actual_obj)
            else:
                object_to_return = actual_obj

            # Track for later release using the ID of the object returned to the user
            self._borrowed_objects[id(object_to_return)] = (obj_id, key, actual_obj)

            self._update_pool_stats("get", active=1, idle=-1)
            return cast(T, object_to_return)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error getting object from pool: %s", e)
            self._update_pool_stats("get", success=False)
            return None  # Returns None if catching an Exception

    def _put_internal(self, obj: T) -> bool:
        """Internal implementation of put operation."""
        if self._pool is None:
            return False
        pool_manager: SmartObjectManager[T] = self._pool
        try:
            # Find the object in our tracking
            obj_key: int = id(obj)
            if obj_key in self._borrowed_objects:
                obj_id, key, actual_obj = self._borrowed_objects.pop(obj_key)
                pool_manager.release(obj_id, key, actual_obj)
                self._ensure_pool_replenished()
                self._update_pool_stats("put", active=-1, idle=1)
                return True

            self._logger.warning("Cannot return object to pool: object not tracked")
            return False
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error returning object to pool: %s", e)
            self._update_pool_stats("put", success=False)
            return False

    @contextmanager
    def borrow(self, *args: Any, **kwargs: Any) -> Iterator[T]:
        """
        Context manager for borrowing objects from the pool.

        Usage:
            with adapter.borrow() as obj:
                # Use obj._obj to access the wrapped object
                pass
        """
        if not self.is_connected():
            raise AdapterNotConnectedError(f"Adapter {self.config.name} not connected")
        pool_manager: SmartObjectManager[T] = cast(SmartObjectManager[T], self._pool)

        acquired_obj_data = None
        try:
            # Use provided args/kwargs or defaults from config
            final_args = args or self.config.factory_args
            final_kwargs = {**self.config.factory_kwargs, **kwargs}
            acquired_result = pool_manager.acquire(*final_args, **final_kwargs)
            if cast(int, acquired_result) == 0:
                raise PoolEmptyError("SmartPool returned 0, indicating an empty pool.")

            obj_id, key, actual_obj = acquired_result

            # If auto_wrap_objects is enabled, yield the wrapped object
            if self.config.auto_wrap_objects:
                wrapped_obj: T | AutoWeakRefWrapper[T] = self._wrap_object(actual_obj)
                acquired_obj_data = (obj_id, key, actual_obj)  # Track original for release
                yield cast(T, wrapped_obj)  # Yield the wrapped object
            else:
                acquired_obj_data = (obj_id, key, actual_obj)  # Track original for release
                yield actual_obj  # Yield the actual object

            self._update_pool_stats("borrow", active=1, idle=-1)  # Unwrap before yielding

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error in borrow context: %s", e)
            self._update_pool_stats("borrow", success=False)
            raise PoolEmptyError(f"Unable to borrow object: {e}") from e
        finally:
            if acquired_obj_data is not None:
                obj_id, key, actual_obj = acquired_obj_data
                try:
                    pool_manager.release(obj_id, key, actual_obj)
                    self._update_pool_stats("return", active=-1, idle=1)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self._logger.error("Error releasing object: %s", e)

    # Performance metrics methods
    def get_performance_metrics(self) -> dict[str, Any]:
        """Get detailed performance metrics from SmartPool."""
        if self._pool is None:
            return {"error": "Pool not initialized"}
        pool_manager: Any = self._pool
        try:
            # Check if performance metrics are enabled
            if (
                not hasattr(pool_manager, "performance_metrics")
                or pool_manager.performance_metrics is None
            ):
                return {"error": "Performance metrics not enabled"}
            perf_metrics_obj: Any = (
                pool_manager.performance_metrics
            )  # Use local variable for type narrowing
            # Get current performance snapshot
            perf_snapshot = perf_metrics_obj.create_snapshot()

            # Get comprehensive performance report
            perf_report = perf_metrics_obj.get_performance_report()

            # Format metrics
            metrics = {
                "current_snapshot": {
                    "timestamp": perf_snapshot.timestamp.isoformat(),
                    "total_acquisitions": perf_snapshot.total_acquisitions,
                    "hit_rate": perf_snapshot.hit_rate,
                    # Timing metrics
                    "timing_metrics": {
                        "avg_acquisition_time_ms": perf_snapshot.avg_acquisition_time_ms,
                        "min_acquisition_time_ms": perf_snapshot.min_acquisition_time_ms,
                        "max_acquisition_time_ms": perf_snapshot.max_acquisition_time_ms,
                        "p50_acquisition_time_ms": perf_snapshot.p50_acquisition_time_ms,
                        "p95_acquisition_time_ms": perf_snapshot.p95_acquisition_time_ms,
                        "p99_acquisition_time_ms": perf_snapshot.p99_acquisition_time_ms,
                    },
                    # Contention metrics
                    "contention_metrics": {
                        "avg_lock_wait_time_ms": perf_snapshot.avg_lock_wait_time_ms,
                        "max_lock_wait_time_ms": perf_snapshot.max_lock_wait_time_ms,
                        "lock_contention_rate": perf_snapshot.lock_contention_rate,
                    },
                    # Throughput metrics
                    "throughput_metrics": {
                        "acquisitions_per_second": perf_snapshot.acquisitions_per_second,
                        "peak_concurrent_acquisitions": perf_snapshot.peak_concurrent_acquisitions,
                    },
                    # Key-based metrics
                    "key_metrics": {
                        "top_keys_by_usage": perf_snapshot.top_keys_by_usage,
                        "slowest_keys": perf_snapshot.slowest_keys,
                    },
                },
                # Historical trends
                "trends": perf_report.get("trends", {}),
                # Alerts and recommendations
                "alerts": perf_report.get("alerts", []),
                "recommendations": perf_report.get("recommendations", []),
            }

            return metrics

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error getting performance metrics: %s", e)
            return {"error": str(e)}

    def get_dashboard_summary(self) -> dict[str, Any]:
        """Get formatted summary for dashboard display."""
        if self._pool is None:
            return {"error": "Pool not initialized", "status": "disconnected"}

        try:
            backend_info = self.get_backend_info()
            status = backend_info.get("smartpool_health", {}).get("status", "unknown")

            # Main metrics
            dashboard = {
                "status": status,
                "preset": backend_info.get("memory_preset", "unknown"),
                "auto_tuning": backend_info.get("auto_tuning_enabled", False),
                # Main metrics
                "metrics": {
                    "hit_rate": backend_info.get("hit_rate", 0),
                    "pooled_objects": backend_info.get("current_size", 0),
                    "active_objects": backend_info.get("active_objects", 0),
                    "total_objects": backend_info.get("total_objects", 0),
                    "pool_utilization": backend_info.get("computed_metrics", {}).get(
                        "pool_utilization", 0
                    ),
                    "reuse_efficiency": backend_info.get("computed_metrics", {}).get(
                        "reuse_efficiency", 0
                    ),
                },
                # Performance metrics if available
                "performance": {
                    "avg_response_time_ms": 0,
                    "p95_response_time_ms": 0,
                    "throughput_ops_sec": 0,
                    "lock_contention_rate": 0,
                    "peak_concurrent": 0,
                },
                # Alerts
                "alerts": {
                    "active_count": 0,
                    "has_warnings": False,
                    "has_errors": False,
                },
                # Configuration
                "config": {
                    "max_size": backend_info.get("max_size", 0),
                    "initial_size": backend_info.get("initial_size", 0),
                    "min_size": backend_info.get("min_size", 0),
                },
            }

            # If backend_info itself has an error, update dashboard status and alerts
            if "error" in backend_info or "performance_enrichment_error" in backend_info:
                dashboard["status"] = "error"
                dashboard["alerts"]["has_errors"] = True

            # Add performance metrics if available
            perf_metrics = self.get_performance_metrics()
            if "error" not in perf_metrics:
                current = perf_metrics.get("current_snapshot", {})
                timing = current.get("timing_metrics", {})
                throughput = current.get("throughput_metrics", {})
                contention = current.get("contention_metrics", {})

                dashboard["performance"].update(
                    {
                        "avg_response_time_ms": timing.get("avg_acquisition_time_ms", 0),
                        "p95_response_time_ms": timing.get("p95_acquisition_time_ms", 0),
                        "throughput_ops_sec": throughput.get("acquisitions_per_second", 0),
                        "lock_contention_rate": contention.get("lock_contention_rate", 0),
                        "peak_concurrent": throughput.get("peak_concurrent_acquisitions", 0),
                    }
                )

                # Add alert status
                alerts = perf_metrics.get("alerts", [])
                dashboard["alerts"].update(
                    {
                        "active_count": len(alerts),
                        "has_warnings": any(alert.get("level") == "warning" for alert in alerts),
                    }
                )
                if not dashboard["alerts"]["has_errors"]:
                    dashboard["alerts"].update(
                        {
                            "has_errors": any(alert.get("level") == "error" for alert in alerts),
                        }
                    )

                # Add recommendations
                if "recommendations" in perf_metrics:
                    dashboard["recommendations"] = perf_metrics["recommendations"]
            else:
                dashboard["status"] = (
                    "error"  # Set status to error if performance metrics retrieval fails
                )
                dashboard["alerts"].update(
                    {
                        "active_count": 0,
                        "has_warnings": False,
                        "has_errors": True,
                    }
                )

            return dashboard

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error getting dashboard summary: %s", e)
            return {
                "error": str(e),
                "status": "error",
                "metrics": {},
                "performance": {},
                "alerts": {"active_count": 0, "has_warnings": False, "has_errors": True},
            }

    # pylint: disable=too-many-locals,too-many-branches
    def get_health_report(self) -> dict[str, Any]:
        """Generate comprehensive health report for monitoring."""
        if self._pool is None:
            return {"status": "disconnected", "issues": ["Pool not initialized"]}

        try:
            # Get comprehensive metrics
            detailed_stats = self.get_detailed_smartpool_stats()

            # If detailed_stats itself indicates an error, return early with critical status
            if "error" in detailed_stats:
                return {
                    "status": "critical",
                    "issues": [f"Failed to retrieve detailed stats: {detailed_stats['error']}"],
                    "warnings": [],
                    "recommendations": [],
                }

            issues: list[str] = []
            warnings: list[str] = []
            recommendations: list[str] = []

            # Analyze metrics to detect problems
            hit_rate = detailed_stats.get("computed_metrics", {}).get("hit_rate_calculated", 0)
            if hit_rate < 0.5:
                issues.append(f"Low hit rate: {hit_rate:.1%}")
                recommendations.append(
                    "Consider increasing pool size or reviewing object reuse patterns"
                )

            # Get performance metrics for additional analysis
            perf_metrics = self.get_performance_metrics()
            if "error" not in perf_metrics:
                current = perf_metrics.get("current_snapshot", {})
                timing = current.get("timing_metrics", {})
                contention = current.get("contention_metrics", {})

                avg_response = timing.get("avg_acquisition_time_ms", 0)
                if avg_response > 50:
                    warnings.append(f"High average response time: {avg_response:.2f}ms")
                    recommendations.append("Investigate object creation time or pool contention")

                contention_rate = contention.get("lock_contention_rate", 0)
                if contention_rate > 0.1:
                    warnings.append(f"High lock contention: {contention_rate:.1%}")
                    recommendations.append("Consider optimizing concurrent access patterns")

                # Add performance metric alerts
                alerts = perf_metrics.get("alerts", [])
                for alert in alerts:
                    level = alert.get("level", "info")
                    message = alert.get("message", "Unknown alert")
                    if level == "error":
                        issues.append(f"Performance alert: {message}")
                    elif level == "warning":
                        warnings.append(f"Performance warning: {message}")

                # Add performance metric recommendations
                if "recommendations" in perf_metrics:
                    recommendations.extend(perf_metrics["recommendations"])

            # Check pool utilization
            utilization = detailed_stats.get("computed_metrics", {}).get("pool_utilization", 0)
            if utilization > 0.9:
                warnings.append(f"High pool utilization: {utilization:.1%}")
                recommendations.append("Consider increasing max_size")
            elif utilization < 0.1:
                warnings.append(f"Low pool utilization: {utilization:.1%}")
                recommendations.append("Consider decreasing initial_size or max_size")

            # Determine overall status
            if issues:
                status = "critical"
            elif warnings:
                status = "warning"
            else:
                status = "healthy"

            return {
                "status": status,
                "timestamp": time.time(),
                "issues": issues,
                "warnings": warnings,
                "recommendations": list(set(recommendations)),  # Deduplicate
                "summary": {
                    "total_issues": len(issues),
                    "total_warnings": len(warnings),
                    "total_recommendations": len(recommendations),
                },
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error generating health report: %s", e)
            return {
                "status": "error",
                "issues": [f"Failed to generate health report: {str(e)}"],
                "warnings": [],
                "recommendations": [],
            }

    def enable_performance_monitoring(self) -> bool:
        """Enable performance monitoring if not already active."""
        if self._pool is None:
            self._logger.error("Cannot enable performance monitoring: pool not initialized")
            return False

        try:
            # Check if metrics are already enabled
            if (
                hasattr(self._pool, "performance_metrics")
                and self._pool.performance_metrics is not None
            ):
                self._logger.info("Performance monitoring already enabled")
                return True

            # If pool supports dynamic metrics activation
            if hasattr(self._pool, "enable_performance_metrics"):
                self._pool.enable_performance_metrics()
                self._logger.info("Performance monitoring enabled successfully")
                return True

            self._logger.warning("Pool does not support dynamic performance metrics activation")
            return False

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error enabling performance monitoring: %s", e)
            return False

    # Backend info methods (renamed legacy method)
    def _get_backend_info(self) -> dict[str, Any]:
        """Get basic information about the SmartPool backend (legacy method)."""
        base_info = {
            "adapter_class": self.__class__.__name__,
            "backend": CacheBackend.SMARTPOOL.value,
            "is_connected": self.is_connected(),
            "initial_size": self.config.initial_size,
            "max_size": self.config.max_size,
            "min_size": self.config.min_size,
            "memory_preset": self.config.memory_preset,
            "auto_tuning_enabled": self.config.enable_auto_tuning,
        }

        if not self.is_connected():
            return base_info
        pool_manager: Any = self._pool
        try:
            # Get SmartPool stats
            pool_stats = pool_manager.get_basic_stats()
            health_status = pool_manager.get_health_status()

            # Map SmartPool stats to expected format
            smartpool_stats = {
                "creates": pool_stats["counters"].get("creates", 0),
                "hits": pool_stats["counters"].get("hits", 0),
                "misses": pool_stats["counters"].get("misses", 0),
                "reuses": pool_stats["counters"].get("reuses", 0),
                "destroys": pool_stats["counters"].get("destroys", 0),
                "acquires": pool_stats["counters"].get("borrows", 0),
                "borrows": pool_stats["counters"].get("borrows", 0),
                "releases": pool_stats["counters"].get("releases", 0),
            }

            current_size = pool_stats.get(
                "total_pooled_objects",
                pool_stats.get(
                    "pooled_objects", pool_stats.get("gauges", {}).get("total_pooled_objects", 0)
                ),
            )
            active_objects = pool_stats.get(
                "active_objects_count",
                pool_stats.get(
                    "active_objects", pool_stats.get("gauges", {}).get("active_objects_count", 0)
                ),
            )
            total_objects = pool_stats.get(
                "total_managed_objects",
                int(current_size) + int(active_objects),
            )
            reuse_efficiency = smartpool_stats["reuses"] / max(
                smartpool_stats["reuses"] + smartpool_stats["creates"],
                1,
            )
            pool_utilization = (
                int(active_objects) / self.config.max_size if self.config.max_size > 0 else 0.0
            )

            base_info.update(
                {
                    "current_size": current_size,
                    "active_objects": active_objects,
                    "total_objects": total_objects,
                    "hit_rate": pool_stats["counters"].get("hits", 0)
                    / max(
                        pool_stats["counters"].get("hits", 0)
                        + pool_stats["counters"].get("misses", 0),
                        1,
                    ),
                    "computed_metrics": {
                        "pool_utilization": pool_utilization,
                        "reuse_efficiency": reuse_efficiency,
                    },
                    "pool_health_status": health_status.get("status", "unknown"),
                    "smartpool_stats": smartpool_stats,
                    "smartpool_health": health_status,
                }
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error getting backend info: %s", e)
            base_info["error"] = str(e)

        return base_info

    def get_backend_info(self) -> dict[str, Any]:
        """Get comprehensive information about the SmartPool backend with performance metrics."""
        # Get base info from legacy method
        base_info = self._get_backend_info()

        if not self.is_connected():
            return base_info

        try:
            # Add performance metrics if available
            performance_metrics = self.get_performance_metrics()
            if "error" not in performance_metrics:
                current = performance_metrics.get("current_snapshot", {})
                timing = current.get("timing_metrics", {})
                throughput = current.get("throughput_metrics", {})
                contention = current.get("contention_metrics", {})

                # Add key performance indicators to base info
                base_info.update(
                    {
                        "avg_response_time_ms": timing.get("avg_acquisition_time_ms", 0),
                        "p95_response_time_ms": timing.get("p95_acquisition_time_ms", 0),
                        "throughput_ops_sec": throughput.get("acquisitions_per_second", 0),
                        "lock_contention_rate": contention.get("lock_contention_rate", 0),
                        "peak_concurrent": throughput.get("peak_concurrent_acquisitions", 0),
                    }
                )

                # Add alert status
                alerts = performance_metrics.get("alerts", [])
                base_info["active_alerts"] = len(alerts)
                base_info["has_warnings"] = any(alert.get("level") == "warning" for alert in alerts)
                base_info["has_errors"] = any(alert.get("level") == "error" for alert in alerts)

                # Include full performance metrics
                base_info["performance_metrics"] = performance_metrics

            # Get memory manager metrics if available
            if self._pool is not None and hasattr(self._pool, "manager") and self._pool.manager:
                try:
                    memory_report = self._pool.manager.get_performance_report(detailed=True)
                    base_info["memory_manager_report"] = memory_report
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self._logger.debug("Memory manager report not available: %s", e)

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error enriching backend info with performance metrics: %s", e)
            base_info["performance_enrichment_error"] = str(e)

        return base_info

    def get_detailed_smartpool_stats(self) -> dict[str, Any]:
        """Get detailed SmartPool statistics with performance metrics."""
        if self._pool is None:
            return {"error": "Pool not initialized"}
        pool_manager: Any = self._pool
        try:
            basic_stats = pool_manager.get_basic_stats()
            health_status = pool_manager.get_health_status()

            # Map stats to include 'borrows' for compatibility
            # mapped_stats = dict(basic_stats)
            # print(mapped_stats)
            # if "borrows" not in mapped_stats["counters"]:
            #     mapped_stats["counters"]["borrows"] = basic_stats["counters"].get("acquires", 0)

            # Calculate derived metrics
            total_requests = basic_stats["counters"].get("hits", 0) + basic_stats["counters"].get(
                "misses", 0
            )
            hit_rate = (
                basic_stats["counters"].get("hits", 0) / total_requests
                if total_requests > 0
                else 0.0
            )

            reuse_count = basic_stats["counters"].get("reuses", 0)
            create_count = basic_stats["counters"].get("creates", 0)
            reuse_efficiency = (
                reuse_count / (reuse_count + create_count)
                if (reuse_count + create_count) > 0
                else 0.0
            )

            active_objects = basic_stats.get(
                "active_objects_count",
                basic_stats.get("active_objects", 0),
            )
            total_objects = basic_stats.get(
                "total_managed_objects",
                basic_stats.get("total_pooled_objects", 0) + active_objects,
            )
            pool_utilization = (
                active_objects / self.config.max_size if self.config.max_size > 0 else 0.0
            )

            # Get performance metrics
            performance_metrics = self.get_performance_metrics()

            # Get memory manager report if available
            memory_report = {}
            if hasattr(pool_manager, "manager") and pool_manager.manager:
                try:
                    memory_report = pool_manager.manager.get_performance_report(detailed=True)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    self._logger.debug("Memory manager report not available: %s", e)

            return {
                "basic_stats": basic_stats,
                "health_status": health_status,
                "computed_metrics": {
                    "total_objects": total_objects,
                    "total_requests": total_requests,
                    "hit_rate_calculated": hit_rate,
                    "reuse_efficiency": reuse_efficiency,
                    "pool_utilization": pool_utilization,
                },
                "configuration": {
                    "initial_size": self.config.initial_size,
                    "max_size": self.config.max_size,
                    "min_size": self.config.min_size,
                    "memory_preset": self.config.memory_preset,
                    "auto_tuning_enabled": self.config.enable_auto_tuning,
                    "performance_metrics_enabled": self.config.enable_performance_metrics,
                },
                "performance_metrics": performance_metrics,
                "memory_manager_report": memory_report,
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Error getting detailed SmartPool stats: %s", e)
            return {"error": str(e)}
