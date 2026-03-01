Testing
=======

This guide covers testing strategies, frameworks, and best practices for developing and maintaining Omni-Cache.

Testing Framework
-----------------

Test Structure
~~~~~~~~~~~~~~

Omni-Cache uses pytest with a structured test organization:

.. code-block:: text

   tests/
   ├── unit/                    # Unit tests
   │   ├── adapters/           # Adapter-specific tests
   │   │   ├── base/
   │   │   ├── memory/
   │   │   ├── redis/
   │   │   └── smartpool/
   │   ├── core/               # Core functionality tests  
   │   │   ├── test_manager.py
   │   │   ├── test_config.py
   │   │   └── test_routing.py
   │   └── utils/              # Utility tests
   ├── integration/            # Integration tests
   │   ├── test_end_to_end.py
   │   └── test_multi_adapter.py
   ├── performance/            # Performance tests
   │   ├── test_benchmarks.py
   │   └── test_load.py
   └── fixtures/               # Test fixtures and data
       ├── conftest.py
       └── test_data.py

Running Tests
~~~~~~~~~~~~~

Standard test execution commands:

.. code-block:: bash

   # Run all tests
   pytest
   
   # Run with coverage
   pytest --cov=omni_cache --cov-report=html
   
   # Run specific test categories
   pytest tests/unit/                    # Unit tests only
   pytest tests/integration/             # Integration tests only
   pytest tests/performance/             # Performance tests only
   
   # Run tests for specific adapter
   pytest tests/unit/adapters/redis/
   
   # Run with verbose output
   pytest -v
   
   # Run tests in parallel
   pytest -n auto

Unit Testing
------------

Adapter Testing
~~~~~~~~~~~~~~~

Base test class for adapter testing:

.. code-block:: python

   # tests/unit/adapters/base/test_base_adapter.py
   import pytest
   from abc import ABC
   from omni_cache.adapters.base import BaseAdapter

   class BaseAdapterTest(ABC):
       """Base test class for all adapters"""
       
       @pytest.fixture
       def adapter(self):
           """Override in subclasses to provide adapter instance"""
           raise NotImplementedError
       
       def test_basic_operations(self, adapter):
           """Test basic get/set/delete operations"""
           # Set and get
           assert adapter.set("test_key", "test_value") is True
           assert adapter.get("test_key") == "test_value"
           
           # Delete
           assert adapter.delete("test_key") is True
           assert adapter.get("test_key") is None
       
       def test_ttl_support(self, adapter):
           """Test TTL functionality"""
           adapter.set("ttl_key", "ttl_value", ttl=1)
           assert adapter.get("ttl_key") == "ttl_value"
           
           # Wait for expiration
           import time
           time.sleep(1.1)
           assert adapter.get("ttl_key") is None
       
       def test_overwrite_behavior(self, adapter):
           """Test key overwriting"""
           adapter.set("key", "value1")
           adapter.set("key", "value2")
           assert adapter.get("key") == "value2"
       
       def test_nonexistent_key(self, adapter):
           """Test behavior with non-existent keys"""
           assert adapter.get("nonexistent") is None
           assert adapter.delete("nonexistent") is False

Memory Adapter Tests
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # tests/unit/adapters/memory/test_memory_adapter.py
   import pytest
   import threading
   import time
   from omni_cache.adapters.memory import MemoryAdapter
   from tests.unit.adapters.base.test_base_adapter import BaseAdapterTest

   class TestMemoryAdapter(BaseAdapterTest):
       @pytest.fixture
       def adapter(self):
           return MemoryAdapter({
               'max_size': 1000,
               'eviction_policy': 'lru'
           })
       
       def test_max_size_enforcement(self):
           """Test that max_size is enforced"""
           adapter = MemoryAdapter({'max_size': 2})
           
           adapter.set("key1", "value1")
           adapter.set("key2", "value2")
           adapter.set("key3", "value3")  # Should evict key1
           
           assert adapter.get("key1") is None  # Evicted
           assert adapter.get("key2") == "value2"
           assert adapter.get("key3") == "value3"
       
       def test_lru_eviction(self):
           """Test LRU eviction behavior"""
           adapter = MemoryAdapter({
               'max_size': 2,
               'eviction_policy': 'lru'
           })
           
           adapter.set("key1", "value1")
           adapter.set("key2", "value2")
           
           # Access key1 to make it more recently used
           adapter.get("key1")
           
           adapter.set("key3", "value3")  # Should evict key2
           
           assert adapter.get("key1") == "value1"
           assert adapter.get("key2") is None  # Evicted
           assert adapter.get("key3") == "value3"
       
       def test_thread_safety(self):
           """Test thread safety of memory adapter"""
           adapter = MemoryAdapter({'max_size': 1000})
           results = {}
           errors = []
           
           def worker(thread_id):
               try:
                   for i in range(100):
                       key = f"thread_{thread_id}_key_{i}"
                       value = f"thread_{thread_id}_value_{i}"
                       
                       adapter.set(key, value)
                       retrieved = adapter.get(key)
                       
                       if retrieved != value:
                           errors.append(f"Mismatch in {key}: {retrieved} != {value}")
                   
                   results[thread_id] = "completed"
               except Exception as e:
                   errors.append(f"Thread {thread_id} failed: {e}")
           
           # Start multiple threads
           threads = []
           for i in range(10):
               thread = threading.Thread(target=worker, args=(i,))
               threads.append(thread)
               thread.start()
           
           # Wait for completion
           for thread in threads:
               thread.join()
           
           assert len(errors) == 0, f"Thread safety errors: {errors}"
           assert len(results) == 10

Redis Adapter Tests
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # tests/unit/adapters/redis/test_redis_adapter.py
   import pytest
   import redis
   from unittest.mock import Mock, patch
   from omni_cache.adapters.redis import RedisAdapter
   from omni_cache.core.exceptions import ConnectionError, CacheError
   from tests.unit.adapters.base.test_base_adapter import BaseAdapterTest

   class TestRedisAdapter(BaseAdapterTest):
       @pytest.fixture
       def adapter(self):
           with patch('redis.Redis') as mock_redis:
               mock_instance = Mock()
               mock_redis.return_value = mock_instance
               
               adapter = RedisAdapter({
                   'host': 'localhost',
                   'port': 6379,
                   'db': 0
               })
               adapter._redis = mock_instance
               return adapter
       
       def test_connection_error_handling(self):
           """Test handling of Redis connection errors"""
           with patch('redis.Redis') as mock_redis:
               mock_redis.side_effect = redis.ConnectionError("Connection failed")
               
               with pytest.raises(ConnectionError):
                   RedisAdapter({'host': 'unreachable'})
       
       def test_get_with_redis_error(self, adapter):
           """Test get operation with Redis error"""
           adapter._redis.get.side_effect = redis.RedisError("Redis error")
           
           with pytest.raises(CacheError):
               adapter.get("test_key")
       
       def test_set_with_redis_error(self, adapter):
           """Test set operation with Redis error"""
           adapter._redis.set.side_effect = redis.RedisError("Redis error")
           
           with pytest.raises(CacheError):
               adapter.set("test_key", "test_value")
       
       def test_serialization_integration(self, adapter):
           """Test serialization with complex objects"""
           complex_obj = {
               'list': [1, 2, 3],
               'dict': {'nested': True},
               'string': 'test'
           }
           
           # Mock Redis to return serialized data
           import pickle
           serialized = pickle.dumps(complex_obj)
           adapter._redis.get.return_value = serialized
           adapter._redis.set.return_value = True
           
           adapter.set("complex_key", complex_obj)
           result = adapter.get("complex_key")
           
           assert result == complex_obj

Configuration Testing
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # tests/unit/core/test_config.py
   import pytest
   import os
   import threading
   from unittest.mock import patch
   from omni_cache.core.config import ConfigManager, get_global_config_manager

   class TestConfigManager:
       def test_basic_config_operations(self):
           """Test basic configuration operations"""
           config = ConfigManager()
           
           config.set('test_key', 'test_value')
           assert config.get('test_key') == 'test_value'
           
           config.update({
               'key1': 'value1',
               'key2': 'value2'
           })
           
           assert config.get('key1') == 'value1'
           assert config.get('key2') == 'value2'
       
       def test_environment_variable_override(self):
           """Test environment variable precedence"""
           config = ConfigManager()
           
           # Set config value
           config.set('redis_host', 'localhost')
           
           # Override with environment variable
           with patch.dict(os.environ, {'OMNI_CACHE_REDIS_HOST': 'redis.example.com'}):
               assert config.get('redis_host') == 'redis.example.com'
       
       def test_thread_safety(self):
           """Test thread safety of config manager"""
           config = ConfigManager()
           results = []
           errors = []
           
           def config_worker(thread_id):
               try:
                   for i in range(100):
                       key = f'thread_{thread_id}_key_{i}'
                       value = f'thread_{thread_id}_value_{i}'
                       
                       config.set(key, value)
                       retrieved = config.get(key)
                       
                       if retrieved != value:
                           errors.append(f"Config mismatch: {retrieved} != {value}")
                   
                   results.append(thread_id)
               except Exception as e:
                   errors.append(f"Thread {thread_id} error: {e}")
           
           threads = []
           for i in range(10):
               thread = threading.Thread(target=config_worker, args=(i,))
               threads.append(thread)
               thread.start()
           
           for thread in threads:
               thread.join()
           
           assert len(errors) == 0
           assert len(results) == 10
       
       def test_global_config_manager_singleton(self):
           """Test that global config manager is a singleton"""
           manager1 = get_global_config_manager()
           manager2 = get_global_config_manager()
           
           assert manager1 is manager2

Mock Testing
------------

Mock Strategies
~~~~~~~~~~~~~~~

Effective mocking for external dependencies:

.. code-block:: python

   # tests/unit/adapters/redis/test_redis_mocking.py
   import pytest
   from unittest.mock import Mock, patch, MagicMock
   from omni_cache.adapters.redis import RedisAdapter

   class TestRedisMocking:
       @pytest.fixture
       def mock_redis(self):
           """Create a comprehensive Redis mock"""
           mock = MagicMock()
           
           # Storage for mock data
           mock._data = {}
           
           # Mock get method
           def mock_get(key):
               return mock._data.get(key)
           mock.get.side_effect = mock_get
           
           # Mock set method
           def mock_set(key, value):
               mock._data[key] = value
               return True
           mock.set.side_effect = mock_set
           
           # Mock setex method (set with expiry)
           def mock_setex(key, ttl, value):
               mock._data[key] = value
               # Note: TTL handling omitted for simplicity
               return True
           mock.setex.side_effect = mock_setex
           
           # Mock delete method
           def mock_delete(key):
               if key in mock._data:
                   del mock._data[key]
                   return 1
               return 0
           mock.delete.side_effect = mock_delete
           
           # Mock exists method
           def mock_exists(key):
               return 1 if key in mock._data else 0
           mock.exists.side_effect = mock_exists
           
           return mock
       
       def test_adapter_with_comprehensive_mock(self, mock_redis):
           """Test adapter with comprehensive Redis mock"""
           with patch('redis.Redis', return_value=mock_redis):
               adapter = RedisAdapter({'host': 'localhost'})
               
               # Test operations
               adapter.set("test_key", "test_value")
               assert adapter.get("test_key") == "test_value"
               
               adapter.delete("test_key")
               assert adapter.get("test_key") is None

Fixture Management
~~~~~~~~~~~~~~~~~~

Reusable test fixtures:

.. code-block:: python

   # tests/fixtures/conftest.py
   import pytest
   import tempfile
   import shutil
   from omni_cache.adapters.memory import MemoryAdapter
   from omni_cache.adapters.redis import RedisAdapter
   from unittest.mock import Mock

   @pytest.fixture
   def temp_dir():
       """Create temporary directory for tests"""
       temp_dir = tempfile.mkdtemp()
       yield temp_dir
       shutil.rmtree(temp_dir)

   @pytest.fixture
   def memory_adapter():
       """Memory adapter for testing"""
       return MemoryAdapter({
           'max_size': 1000,
           'eviction_policy': 'lru'
       })

   @pytest.fixture
   def mock_redis_adapter():
       """Mock Redis adapter for testing"""
       mock_redis = Mock()
       mock_redis._data = {}
       
       def mock_get(key):
           return mock_redis._data.get(key)
       mock_redis.get.side_effect = mock_get
       
       def mock_set(key, value):
           mock_redis._data[key] = value
           return True
       mock_redis.set.side_effect = mock_set
       
       with patch('redis.Redis', return_value=mock_redis):
           return RedisAdapter({'host': 'localhost'})

   @pytest.fixture(params=['memory', 'mock_redis'])
   def any_adapter(request, memory_adapter, mock_redis_adapter):
       """Parametrized fixture for testing with any adapter"""
       adapters = {
           'memory': memory_adapter,
           'mock_redis': mock_redis_adapter
       }
       return adapters[request.param]

Integration Testing
-------------------

End-to-End Tests
~~~~~~~~~~~~~~~~

Test complete workflows:

.. code-block:: python

   # tests/integration/test_end_to_end.py
   import pytest
   from omni_cache import OmniCache
   from omni_cache.core.routing import NamespaceRouter

   class TestEndToEnd:
       def test_multi_adapter_workflow(self):
           """Test complete workflow with multiple adapters"""
           
           # Create cache with routing
           router = NamespaceRouter({
               'user:*': 'memory_cache',
               'session:*': 'redis_cache',
               'default': 'memory_cache'
           })
           
           cache = OmniCache.create_cache(
               adapters={
                   'memory_cache': {
                       'adapter': 'memory',
                       'config': {'max_size': 1000}
                   },
                   'redis_cache': {
                       'adapter': 'redis', 
                       'config': {'host': 'localhost'}
                   }
               },
               router=router
           )
           
           # Test user data goes to memory
           cache.set('user:123', {'name': 'Alice', 'age': 30})
           user_data = cache.get('user:123')
           assert user_data['name'] == 'Alice'
           
           # Test session data goes to Redis
           cache.set('session:abc', {'user_id': 123, 'expires': '2024-12-31'})
           session_data = cache.get('session:abc')
           assert session_data['user_id'] == 123
           
           # Test fallback behavior
           cache.set('other:key', 'fallback_value')
           assert cache.get('other:key') == 'fallback_value'
       
       def test_decorator_integration(self):
           """Test decorator integration with caching"""
           from omni_cache import cached
           
           call_count = 0
           
           @cached(ttl=300, adapter='memory')
           def expensive_function(x, y):
               nonlocal call_count
               call_count += 1
               return x * y + call_count  # Include call_count to verify caching
           
           # First call
           result1 = expensive_function(5, 10)
           assert call_count == 1
           
           # Second call (should be cached)
           result2 = expensive_function(5, 10)
           assert call_count == 1  # Should not increment
           assert result1 == result2
           
           # Different parameters (should call function)
           result3 = expensive_function(3, 7)
           assert call_count == 2

Multi-Process Tests
~~~~~~~~~~~~~~~~~~~

Test behavior across processes:

.. code-block:: python

   # tests/integration/test_multi_process.py
   import pytest
   import multiprocessing
   import time
   from omni_cache import OmniCache

   def worker_function(worker_id, shared_results):
       """Worker function for multi-process test"""
       cache = OmniCache.create_cache(
           adapter='redis',
           config={'host': 'localhost', 'db': 1}  # Use test database
       )
       
       # Each worker sets and gets data
       for i in range(10):
           key = f'worker_{worker_id}_key_{i}'
           value = f'worker_{worker_id}_value_{i}'
           
           cache.set(key, value)
           retrieved = cache.get(key)
           
           if retrieved != value:
               shared_results.append(f'Mismatch: {retrieved} != {value}')
       
       shared_results.append(f'Worker {worker_id} completed')

   class TestMultiProcess:
       @pytest.mark.skipif(
           not pytest.redis_available,
           reason="Redis not available"
       )
       def test_multi_process_access(self):
           """Test cache access from multiple processes"""
           
           manager = multiprocessing.Manager()
           shared_results = manager.list()
           
           # Start multiple worker processes
           processes = []
           for i in range(4):
               process = multiprocessing.Process(
                   target=worker_function,
                   args=(i, shared_results)
               )
               processes.append(process)
               process.start()
           
           # Wait for completion
           for process in processes:
               process.join(timeout=30)
               assert not process.is_alive(), "Process did not complete"
           
           # Check results
           results = list(shared_results)
           completion_messages = [r for r in results if 'completed' in r]
           error_messages = [r for r in results if 'Mismatch' in r]
           
           assert len(completion_messages) == 4, "Not all workers completed"
           assert len(error_messages) == 0, f"Errors occurred: {error_messages}"

Performance Testing
-------------------

Benchmark Tests
~~~~~~~~~~~~~~~

Performance regression testing:

.. code-block:: python

   # tests/performance/test_benchmarks.py
   import pytest
   import time
   import statistics
   from omni_cache.adapters.memory import MemoryAdapter

   class TestPerformanceBenchmarks:
       def benchmark_operation(self, adapter, operation, iterations=1000):
           """Benchmark a specific operation"""
           times = []
           
           for i in range(iterations):
               start = time.perf_counter()
               operation(i)
               end = time.perf_counter()
               times.append((end - start) * 1000)  # Convert to milliseconds
           
           return {
               'mean': statistics.mean(times),
               'median': statistics.median(times),
               'p95': statistics.quantiles(times, n=20)[18],  # 95th percentile
               'min': min(times),
               'max': max(times)
           }
       
       def test_memory_adapter_performance(self):
           """Test memory adapter performance benchmarks"""
           adapter = MemoryAdapter({'max_size': 10000})
           
           # Benchmark set operations
           def set_operation(i):
               adapter.set(f'key_{i}', f'value_{i}')
           
           set_stats = self.benchmark_operation(adapter, set_operation)
           
           # Assert performance thresholds
           assert set_stats['mean'] < 0.1, f"SET too slow: {set_stats['mean']:.3f}ms"
           assert set_stats['p95'] < 0.5, f"SET P95 too slow: {set_stats['p95']:.3f}ms"
           
           # Benchmark get operations  
           def get_operation(i):
               adapter.get(f'key_{i % 1000}')  # Get existing keys
           
           get_stats = self.benchmark_operation(adapter, get_operation)
           
           assert get_stats['mean'] < 0.05, f"GET too slow: {get_stats['mean']:.3f}ms"
           assert get_stats['p95'] < 0.2, f"GET P95 too slow: {get_stats['p95']:.3f}ms"
       
       def test_memory_vs_redis_performance(self):
           """Compare memory and Redis adapter performance"""
           memory_adapter = MemoryAdapter({'max_size': 1000})
           
           # Mock Redis for consistent testing
           from unittest.mock import Mock, patch
           with patch('redis.Redis') as mock_redis:
               mock_redis.return_value = Mock()
               redis_adapter = RedisAdapter({'host': 'localhost'})
           
           def memory_set(i):
               memory_adapter.set(f'key_{i}', f'value_{i}')
           
           def redis_set(i):
               redis_adapter.set(f'key_{i}', f'value_{i}')
           
           memory_stats = self.benchmark_operation(memory_adapter, memory_set, 100)
           redis_stats = self.benchmark_operation(redis_adapter, redis_set, 100)
           
           # Memory should be significantly faster
           assert memory_stats['mean'] < redis_stats['mean']
           
           print(f"Memory SET: {memory_stats['mean']:.3f}ms")
           print(f"Redis SET: {redis_stats['mean']:.3f}ms")

Load Testing
~~~~~~~~~~~~

High-load scenario testing:

.. code-block:: python

   # tests/performance/test_load.py
   import pytest
   import threading
   import time
   from concurrent.futures import ThreadPoolExecutor
   from omni_cache.adapters.memory import MemoryAdapter

   class TestLoadTesting:
       def test_concurrent_access_load(self):
           """Test adapter under concurrent load"""
           adapter = MemoryAdapter({'max_size': 10000})
           
           # Statistics tracking
           stats = {
               'operations_completed': 0,
               'errors': [],
               'start_time': None,
               'end_time': None
           }
           
           stats_lock = threading.Lock()
           
           def worker(worker_id, operations_per_worker):
               """Worker thread for load testing"""
               local_ops = 0
               local_errors = []
               
               try:
                   for i in range(operations_per_worker):
                       key = f'worker_{worker_id}_key_{i}'
                       value = f'worker_{worker_id}_value_{i}'
                       
                       # Mix of operations
                       if i % 3 == 0:
                           adapter.set(key, value)
                           local_ops += 1
                       else:
                           result = adapter.get(key)
                           local_ops += 1
                       
                       if i % 100 == 0:  # Periodic delete
                           adapter.delete(f'worker_{worker_id}_key_{i-50}')
                           local_ops += 1
               
               except Exception as e:
                   local_errors.append(f'Worker {worker_id}: {e}')
               
               # Update global stats
               with stats_lock:
                   stats['operations_completed'] += local_ops
                   stats['errors'].extend(local_errors)
           
           # Run load test
           num_workers = 20
           operations_per_worker = 500
           
           stats['start_time'] = time.time()
           
           with ThreadPoolExecutor(max_workers=num_workers) as executor:
               futures = [
                   executor.submit(worker, i, operations_per_worker)
                   for i in range(num_workers)
               ]
               
               for future in futures:
                   future.result(timeout=60)  # 60 second timeout
           
           stats['end_time'] = time.time()
           
           # Analyze results
           total_time = stats['end_time'] - stats['start_time']
           throughput = stats['operations_completed'] / total_time
           
           print(f"Load test results:")
           print(f"  Total operations: {stats['operations_completed']}")
           print(f"  Total time: {total_time:.2f} seconds")
           print(f"  Throughput: {throughput:.2f} ops/sec")
           print(f"  Errors: {len(stats['errors'])}")
           
           # Assertions
           assert len(stats['errors']) == 0, f"Errors during load test: {stats['errors']}"
           assert throughput > 1000, f"Throughput too low: {throughput:.2f} ops/sec"
           
           # Verify cache is still functional
           adapter.set('post_test_key', 'post_test_value')
           assert adapter.get('post_test_key') == 'post_test_value'

Test Configuration
------------------

Pytest Configuration
~~~~~~~~~~~~~~~~~~~~

.. code-block:: ini

   # pytest.ini
   [tool:pytest]
   minversion = 6.0
   addopts = 
       -ra
       --strict-markers
       --strict-config
       --cov=omni_cache
       --cov-report=term-missing:skip-covered
       --cov-report=html:htmlcov
       --cov-report=xml
   testpaths = tests
   markers =
       slow: marks tests as slow (deselect with '-m "not slow"')
       integration: marks tests as integration tests
       performance: marks tests as performance tests
       redis_required: marks tests that require Redis
   filterwarnings =
       error
       ignore::UserWarning
       ignore::DeprecationWarning

GitHub Actions CI
~~~~~~~~~~~~~~~~~

.. code-block:: yaml

   # .github/workflows/test.yml
   name: Tests
   
   on:
     push:
       branches: [ main ]
     pull_request:
       branches: [ main ]
   
   jobs:
     test:
       runs-on: ubuntu-latest
       strategy:
         matrix:
           python-version: [3.8, 3.9, "3.10", "3.11"]
       
       services:
         redis:
           image: redis:7
           options: >-
             --health-cmd "redis-cli ping"
             --health-interval 10s
             --health-timeout 5s
             --health-retries 5
           ports:
             - 6379:6379
       
       steps:
       - uses: actions/checkout@v3
       
       - name: Set up Python ${{ matrix.python-version }}
         uses: actions/setup-python@v3
         with:
           python-version: ${{ matrix.python-version }}
       
       - name: Install dependencies
         run: |
           python -m pip install --upgrade pip
           pip install -e ".[dev]"
       
       - name: Run tests
         run: |
           pytest --cov=omni_cache --cov-report=xml
       
       - name: Upload coverage to Codecov
         uses: codecov/codecov-action@v3
         with:
           file: ./coverage.xml

Best Practices
--------------

Test Organization
~~~~~~~~~~~~~~~~~

1. **Separate Unit and Integration Tests**
   - Unit tests: Fast, isolated, mocked dependencies
   - Integration tests: Real components, slower execution

2. **Use Descriptive Test Names**
   - ``test_memory_adapter_enforces_max_size_limit``
   - ``test_redis_adapter_handles_connection_failures``

3. **Test Both Happy and Error Paths**
   - Normal operation scenarios
   - Error conditions and edge cases

4. **Parameterized Tests for Multiple Scenarios**
   - Test same logic with different inputs
   - Test adapter compatibility

Mock Guidelines
~~~~~~~~~~~~~~~

1. **Mock External Dependencies**
   - Redis connections
   - File system operations
   - Network calls

2. **Avoid Over-Mocking**
   - Don't mock the system under test
   - Mock at appropriate boundaries

3. **Use Realistic Mock Behavior**
   - Match actual API behavior
   - Include error scenarios

Performance Testing
~~~~~~~~~~~~~~~~~~~

1. **Set Performance Baselines**
   - Define acceptable thresholds
   - Track performance over time

2. **Test Under Load**
   - Concurrent access patterns
   - High-volume scenarios

3. **Memory and Resource Testing**
   - Memory leak detection
   - Resource cleanup verification

Next Steps
----------

* Follow this testing guide for local development workflow
* Review :doc:`architecture` for understanding system design
* Check existing tests for examples and patterns
