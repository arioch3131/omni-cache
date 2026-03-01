# =============================================================================
# EXAMPLE: Microservices with Async Caching and Circuit Breakers
# File: examples/advanced/microservices_async_caching.py
# =============================================================================
"""
Microservices example with async caching and resilience patterns.

This example shows:
- Async function caching with aiohttp
- Service-to-service communication caching
- Circuit breaker pattern with cached fallbacks
- Distributed caching for session management
- Health checking and monitoring
"""

import asyncio
import random
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp

from omni_cache import (
    async_cached,
    cached,
    get_global_manager,
    invalidate_cache,
    retry_with_cache,
    setup,
)

# =============================================================================
# Service Configuration
# =============================================================================


@dataclass
class ServiceConfig:
    name: str
    host: str
    port: int
    timeout: float = 0.1
    max_retries: int = 3

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


# Service registry
SERVICES = {
    "user_service": ServiceConfig("user_service", "localhost", 8001),
    "product_service": ServiceConfig("product_service", "localhost", 8002),
    "order_service": ServiceConfig("order_service", "localhost", 8003),
    "notification_service": ServiceConfig("notification_service", "localhost", 8004),
}

# Setup omni-cache for microservices
manager = setup(log_level="INFO")

# =============================================================================
# Circuit Breaker Implementation
# =============================================================================


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3

    def __post_init__(self):
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED


circuit_breakers = {service: CircuitBreaker() for service in SERVICES}


def get_circuit_breaker(service_name: str) -> CircuitBreaker:
    """Get circuit breaker for service."""
    return circuit_breakers.get(service_name, CircuitBreaker())


# =============================================================================
# Async HTTP Client with Caching
# =============================================================================


class CachedHttpClient:
    """HTTP client with built-in caching and circuit breakers."""

    def __init__(self):
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    @async_cached(ttl=300, namespace="http_cache")
    async def get(self, url: str, **kwargs) -> dict[str, Any]:
        """Cached HTTP GET request."""
        if not self.session:
            raise RuntimeError("Client not initialized")

        print(f"🌐 HTTP GET: {url}")

        async with self.session.get(url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    @async_cached(ttl=180, namespace="http_cache")
    async def post(self, url: str, data: dict[str, Any], **kwargs) -> dict[str, Any]:
        """Cached HTTP POST request (be careful with caching POST!)."""
        if not self.session:
            raise RuntimeError("Client not initialized")

        print(f"🌐 HTTP POST: {url}")

        async with self.session.post(url, json=data, **kwargs) as response:
            response.raise_for_status()
            return await response.json()


# =============================================================================
# Service Client with Circuit Breaker
# =============================================================================


async def call_service_with_circuit_breaker(
    service_name: str,
    endpoint: str,
    method: str = "GET",
    data: dict[str, Any] | None = None,
    fallback_data: Any | None = None,
) -> Any:
    """Call service with circuit breaker pattern."""

    circuit = get_circuit_breaker(service_name)
    service_config = SERVICES.get(service_name)

    if not service_config:
        raise ValueError(f"Unknown service: {service_name}")

    # Check circuit breaker state
    current_time = time.time()

    if circuit.state == CircuitState.OPEN:
        if current_time - circuit.last_failure_time > circuit.recovery_timeout:
            circuit.state = CircuitState.HALF_OPEN
            circuit.success_count = 0
        else:
            print(f"⚡ Circuit breaker OPEN for {service_name}, using fallback")
            return fallback_data

    try:
        async with CachedHttpClient() as client:
            url = f"{service_config.base_url}/{endpoint}"

            if method == "GET":
                result = await client.get(url, timeout=service_config.timeout)
            elif method == "POST":
                result = await client.post(url, data or {}, timeout=service_config.timeout)
            else:
                raise ValueError(f"Unsupported method: {method}")

        # Success - update circuit breaker
        if circuit.state == CircuitState.HALF_OPEN:
            circuit.success_count += 1
            if circuit.success_count >= circuit.success_threshold:
                circuit.state = CircuitState.CLOSED
                circuit.failure_count = 0
                print(f"✅ Circuit breaker CLOSED for {service_name}")

        return result

    except Exception as e:
        # Failure - update circuit breaker
        circuit.failure_count += 1
        circuit.last_failure_time = current_time

        if circuit.failure_count >= circuit.failure_threshold:
            circuit.state = CircuitState.OPEN
            print(
                f"🔴 Circuit breaker OPEN for {service_name} after {circuit.failure_count} failures"
            )

        print(f"❌ Service call failed: {service_name}/{endpoint} - {e}")

        if fallback_data is not None:
            print(f"🔄 Using fallback data for {service_name}")
            return fallback_data

        raise


# =============================================================================
# Cached Service Clients
# =============================================================================


class UserService:
    """User service client with caching."""

    @async_cached(ttl=600, namespace="user_service")
    async def get_user(self, user_id: int) -> dict[str, Any]:
        """Get user by ID with caching."""
        fallback = {"id": user_id, "name": "Unknown User", "status": "cached_fallback"}

        return await call_service_with_circuit_breaker(
            "user_service", f"users/{user_id}", fallback_data=fallback
        )

    @async_cached(ttl=300, namespace="user_service")
    async def get_user_preferences(self, user_id: int) -> dict[str, Any]:
        """Get user preferences with caching."""
        fallback = {"user_id": user_id, "preferences": {}, "status": "cached_fallback"}

        return await call_service_with_circuit_breaker(
            "user_service", f"users/{user_id}/preferences", fallback_data=fallback
        )

    @cached(ttl=1800, namespace="user_service")  # Sync version for batch operations
    def get_user_roles(self, user_id: int) -> list[str]:
        """Get user roles (simulated sync call)."""
        # Simulate database lookup
        time.sleep(0.1)
        return ["user", "customer"] if user_id % 2 == 0 else ["user", "admin"]


class ProductService:
    """Product service client with caching."""

    @async_cached(ttl=900, namespace="product_service")
    async def get_product(self, product_id: int) -> dict[str, Any]:
        """Get product by ID with caching."""
        fallback = {
            "id": product_id,
            "name": "Unknown Product",
            "price": 0.0,
            "status": "cached_fallback",
        }

        return await call_service_with_circuit_breaker(
            "product_service", f"products/{product_id}", fallback_data=fallback
        )

    @async_cached(ttl=600, namespace="product_service")
    async def get_product_recommendations(
        self, user_id: int, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Get product recommendations with caching."""
        fallback = [
            {"id": i, "name": f"Recommended Product {i}", "score": 0.5} for i in range(1, limit + 1)
        ]

        return await call_service_with_circuit_breaker(
            "product_service",
            f"recommendations?user_id={user_id}&limit={limit}",
            fallback_data=fallback,
        )


class OrderService:
    """Order service client with caching."""

    @async_cached(ttl=120, namespace="order_service")  # Shorter TTL for order data
    async def get_user_orders(self, user_id: int) -> list[dict[str, Any]]:
        """Get user orders with caching."""
        fallback = []

        return await call_service_with_circuit_breaker(
            "order_service", f"users/{user_id}/orders", fallback_data=fallback
        )

    @retry_with_cache(max_retries=3, cache_failures=True, failure_ttl=60)
    async def create_order(self, order_data: dict[str, Any]) -> dict[str, Any]:
        """Create order with retry logic."""
        return await call_service_with_circuit_breaker(
            "order_service", "orders", method="POST", data=order_data
        )


# =============================================================================
# Aggregated Service Layer
# =============================================================================


class UserProfileAggregator:
    """Aggregates data from multiple services to build user profiles."""

    def __init__(self):
        self.user_service = UserService()
        self.product_service = ProductService()
        self.order_service = OrderService()

    @async_cached(ttl=300, namespace="aggregated_profiles")
    async def get_complete_user_profile(self, user_id: int) -> dict[str, Any]:
        """Get complete user profile from multiple services."""
        print(f"👤 Building complete profile for user {user_id}")

        # Gather data from multiple services concurrently
        user_data, preferences, orders, recommendations = await asyncio.gather(
            self.user_service.get_user(user_id),
            self.user_service.get_user_preferences(user_id),
            self.order_service.get_user_orders(user_id),
            self.product_service.get_product_recommendations(user_id),
            return_exceptions=True,
        )

        # Handle exceptions gracefully
        profile = {"user_id": user_id, "timestamp": time.time()}

        if not isinstance(user_data, Exception):
            profile["user"] = user_data

        if not isinstance(preferences, Exception):
            profile["preferences"] = preferences

        if not isinstance(orders, Exception):
            profile["orders"] = orders
            profile["order_count"] = len(orders)

        if not isinstance(recommendations, Exception):
            profile["recommendations"] = recommendations

        # Add computed fields
        profile["roles"] = self.user_service.get_user_roles(user_id)

        return profile


# =============================================================================
# Session Management with Distributed Caching
# =============================================================================


class SessionManager:
    """Distributed session management with caching."""

    @cached(ttl=1800, namespace="sessions")  # 30 minutes
    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get session data."""
        # In real implementation, this might query a database
        print(f"🗝️ Fetching session: {session_id[:8]}...")
        time.sleep(0.1)  # Simulate database query

        return {
            "session_id": session_id,
            "user_id": hash(session_id) % 1000,
            "created_at": time.time() - 3600,
            "last_activity": time.time(),
            "data": {"cart": [], "preferences": {}},
        }

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate session cache."""
        return self.get_session.invalidate(session_id)

    @cached(ttl=3600, namespace="session_stats")
    def get_session_stats(self) -> dict[str, Any]:
        """Get session statistics."""
        print("📊 Calculating session statistics...")
        time.sleep(0.2)

        return {
            "active_sessions": random.randint(100, 500),
            "avg_session_duration": random.randint(10, 60),
            "peak_concurrent": random.randint(50, 200),
        }


# =============================================================================
# Health Monitoring and Circuit Breaker Status
# =============================================================================


class HealthMonitor:
    """Monitor service health and circuit breaker status."""

    @cached(ttl=30, namespace="health")  # Short TTL for health data
    def get_service_health(self) -> dict[str, Any]:
        """Get health status of all services."""
        health_status = {}

        for service_name, config in SERVICES.items():
            circuit = get_circuit_breaker(service_name)
            health_status[service_name] = {
                "state": circuit.state.value,
                "failure_count": circuit.failure_count,
                "success_count": circuit.success_count,
                "last_failure": circuit.last_failure_time,
                "url": config.base_url,
            }

        return health_status

    def get_cache_health(self) -> dict[str, Any]:
        """Get cache health and statistics."""
        manager = get_global_manager()

        return {
            "global_stats": manager.get_global_stats(),
            "adapter_stats": manager.get_adapter_stats(),
            "adapters": manager.list_adapters(),
        }


# =============================================================================
# Demo Microservices Application
# =============================================================================


class MicroservicesApp:
    """Demo application using microservices with caching."""

    def __init__(self):
        self.profile_aggregator = UserProfileAggregator()
        self.session_manager = SessionManager()
        self.health_monitor = HealthMonitor()

    async def handle_user_request(self, session_id: str) -> dict[str, Any]:
        """Handle a user request with session management."""
        print(f"\n🚀 Handling request for session: {session_id[:8]}...")

        # Get session
        session = self.session_manager.get_session(session_id)
        if not session:
            return {"error": "Invalid session"}

        user_id = session["user_id"]

        # Get complete user profile (aggregated from multiple services)
        profile = await self.profile_aggregator.get_complete_user_profile(user_id)

        return {"session": session, "profile": profile, "request_time": time.time()}

    async def simulate_load(self, num_requests: int = 10):
        """Simulate application load."""
        print(f"\n🏋️ Simulating load with {num_requests} requests...")

        # Generate random session IDs
        session_ids = [f"session_{random.randint(1000, 9999)}" for _ in range(num_requests)]

        start_time = time.time()

        # Process requests concurrently
        tasks = [self.handle_user_request(sid) for sid in session_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time
        successful_requests = sum(1 for r in results if not isinstance(r, Exception))

        print(f"✅ Processed {successful_requests}/{num_requests} requests in {total_time:.2f}s")
        print(f"📈 Throughput: {successful_requests / total_time:.1f} requests/second")

        return results

    def print_health_status(self):
        """Print service and cache health status."""
        print("\n🏥 Health Status")
        print("=" * 30)

        # Service health
        service_health = self.health_monitor.get_service_health()
        print("Services:")
        for service, status in service_health.items():
            state_emoji = {"closed": "✅", "open": "🔴", "half_open": "🟡"}
            emoji = state_emoji.get(status["state"], "❓")
            print(f"  {emoji} {service}: {status['state']} (failures: {status['failure_count']})")

        # Cache health
        cache_health = self.health_monitor.get_cache_health()
        print("\nCache:")
        global_stats = cache_health["global_stats"]
        if "cache" in global_stats:
            cache_stats = global_stats["cache"]
            hit_rate = getattr(cache_stats, "hit_rate", 0) * 100
            print(f"  📊 Hit rate: {hit_rate:.1f}%")
            print(f"  🎯 Hits: {getattr(cache_stats, 'hits', 0)}")
            print(f"  ❌ Misses: {getattr(cache_stats, 'misses', 0)}")


# =============================================================================
# Main Demo
# =============================================================================


async def main():
    """Main demo function."""
    print("🏗️ Microservices with Omni-Cache Demo")
    print("=" * 50)

    app = MicroservicesApp()

    # Simulate normal load
    await app.simulate_load(5)
    app.print_health_status()

    # Simulate service failures (circuit breaker demo)
    print("\n⚠️ Simulating service failures...")
    for service_name in ["user_service", "product_service"]:
        circuit = get_circuit_breaker(service_name)
        circuit.failure_count = circuit.failure_threshold  # Force circuit open
        circuit.state = CircuitState.OPEN
        circuit.last_failure_time = time.time()

    # Load with failures (should use fallback data)
    await app.simulate_load(3)
    app.print_health_status()

    # Clear cache and show performance difference
    print("\n🧹 Clearing cache to show performance difference...")
    invalidate_cache(pattern="*")

    # Cold cache run
    print("Cold cache run:")
    start_time = time.time()
    await app.simulate_load(3)
    cold_time = time.time() - start_time

    # Warm cache run
    print("Warm cache run:")
    start_time = time.time()
    await app.simulate_load(3)
    warm_time = time.time() - start_time

    speedup = cold_time / warm_time if warm_time > 0 else float("inf")
    print("\n📈 Performance comparison:")
    print(f"  Cold cache: {cold_time:.2f}s")
    print(f"  Warm cache: {warm_time:.2f}s")
    print(f"  Speedup: {speedup:.1f}x")

    app.print_health_status()


if __name__ == "__main__":
    print("🌐 Starting Microservices Demo...")
    print("Note: This demo simulates service calls without actual services running")
    print("In a real environment, you would have actual microservices at the configured URLs")
    print()

    asyncio.run(main())

    print("\n✅ Microservices demo completed!")
