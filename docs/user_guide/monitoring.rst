Monitoring
==========

Omni-Cache provides comprehensive monitoring and metrics capabilities to help you track performance, identify bottlenecks, and optimize your caching strategy.

Built-in Metrics
----------------

Cache Statistics
~~~~~~~~~~~~~~~~

Get detailed cache performance metrics:

.. code-block:: python

   from omni_cache import OmniCache

   cache = OmniCache.create_cache(adapter="memory")
   
   # Perform some operations
   cache.set("key1", "value1")
   cache.get("key1")  # Hit
   cache.get("key2")  # Miss
   
   # Get statistics
   stats = cache.get_stats()
   print(f"Hits: {stats['hits']}")
   print(f"Misses: {stats['misses']}")
   print(f"Hit Rate: {stats['hit_rate']:.2%}")
   print(f"Total Operations: {stats['total_operations']}")

**Available Metrics:**

* **hits**: Number of cache hits
* **misses**: Number of cache misses  
* **hit_rate**: Hit rate percentage
* **total_operations**: Total cache operations
* **memory_usage**: Current memory usage (bytes)
* **item_count**: Number of cached items
* **evictions**: Number of evicted items

Performance Metrics
~~~~~~~~~~~~~~~~~~~

Track operation performance:

.. code-block:: python

   # Get performance metrics
   perf = cache.get_performance_metrics()
   
   print(f"Average GET time: {perf['avg_get_time']:.3f}ms")
   print(f"Average SET time: {perf['avg_set_time']:.3f}ms")
   print(f"95th percentile: {perf['p95_response_time']:.3f}ms")

Monitoring Setup
----------------

Metrics Collection
~~~~~~~~~~~~~~~~~~

Enable detailed metrics collection:

.. code-block:: python

   cache = OmniCache.create_cache(
       adapter="redis",
       config={
           "enable_metrics": True,
           "metrics_interval": 60,  # seconds
           "detailed_metrics": True
       }
   )

Custom Metrics
~~~~~~~~~~~~~~

Add custom metrics to your cache operations:

.. code-block:: python

   from omni_cache.monitoring import MetricsCollector

   collector = MetricsCollector()
   
   # Track custom events
   @collector.track_time("business_logic")
   def expensive_operation():
       return complex_computation()
   
   # Manual metrics
   collector.increment("custom_counter")
   collector.gauge("queue_size", 42)
   collector.histogram("request_size", len(data))

Logging Integration
-------------------

Structured Logging
~~~~~~~~~~~~~~~~~~

Configure structured logging for cache operations:

.. code-block:: python

   import logging
   from omni_cache.monitoring import CacheLogger

   # Configure cache logger
   logger = CacheLogger(
       level=logging.INFO,
       format="json",
       include_metrics=True
   )

   cache = OmniCache.create_cache(
       adapter="redis",
       logger=logger
   )

   # Operations are automatically logged
   cache.set("user:123", user_data)  # Logs: {"level": "INFO", "operation": "SET", "key": "user:123", "duration": 0.002}

Operation Tracing
~~~~~~~~~~~~~~~~~

Trace cache operations for debugging:

.. code-block:: python

   # Enable operation tracing
   cache.enable_tracing()
   
   # Perform operations
   result = cache.get("key")
   
   # Get trace information
   traces = cache.get_traces()
   for trace in traces:
       print(f"Operation: {trace['operation']}")
       print(f"Key: {trace['key']}")
       print(f"Duration: {trace['duration']}")
       print(f"Result: {trace['result']}")

Alerting and Notifications
--------------------------

Threshold Alerts
~~~~~~~~~~~~~~~~

Set up alerts based on metrics thresholds:

.. code-block:: python

   from omni_cache.monitoring import AlertManager

   alert_manager = AlertManager()
   
   # Configure alerts
   alert_manager.add_alert(
       name="low_hit_rate",
       condition=lambda stats: stats['hit_rate'] < 0.8,
       action=lambda: send_notification("Cache hit rate is low")
   )
   
   alert_manager.add_alert(
       name="high_memory_usage",
       condition=lambda stats: stats['memory_usage'] > 1000000000,  # 1GB
       action=lambda: logging.warning("High memory usage detected")
   )
   
   # Attach to cache
   cache.set_alert_manager(alert_manager)

Health Checks
~~~~~~~~~~~~~

Implement health check endpoints:

.. code-block:: python

   from omni_cache.monitoring import HealthChecker

   health_checker = HealthChecker(cache)
   
   # Check cache health
   health = health_checker.check_health()
   
   print(f"Status: {health['status']}")          # "healthy" or "unhealthy"
   print(f"Response Time: {health['latency']}")  # Response time in ms
   print(f"Errors: {health['error_count']}")     # Number of recent errors

Integration with Monitoring Systems
-----------------------------------

Prometheus Integration
~~~~~~~~~~~~~~~~~~~~~~

Export metrics to Prometheus:

.. code-block:: python

   from omni_cache.monitoring.exporters import PrometheusExporter
   from prometheus_client import start_http_server

   # Create Prometheus exporter
   exporter = PrometheusExporter(cache)
   
   # Start metrics server
   start_http_server(8000)
   
   # Metrics available at http://localhost:8000/metrics

StatsD Integration
~~~~~~~~~~~~~~~~~~

Send metrics to StatsD:

.. code-block:: python

   from omni_cache.monitoring.exporters import StatsDExporter

   exporter = StatsDExporter(
       host="statsd.example.com",
       port=8125,
       prefix="omni_cache"
   )
   
   cache.add_exporter(exporter)

Grafana Dashboard
~~~~~~~~~~~~~~~~~

Create Grafana dashboard for visualization:

.. code-block:: json

   {
     "dashboard": {
       "title": "Omni-Cache Metrics",
       "panels": [
         {
           "title": "Hit Rate",
           "type": "stat",
           "targets": [
             {
               "expr": "omni_cache_hit_rate"
             }
           ]
         },
         {
           "title": "Operations per Second",
           "type": "graph", 
           "targets": [
             {
               "expr": "rate(omni_cache_operations_total[5m])"
             }
           ]
         }
       ]
     }
   }

Performance Monitoring
----------------------

Latency Tracking
~~~~~~~~~~~~~~~~

Monitor operation latencies:

.. code-block:: python

   # Get latency percentiles
   latency_stats = cache.get_latency_stats()
   
   print(f"P50: {latency_stats['p50']:.3f}ms")
   print(f"P95: {latency_stats['p95']:.3f}ms")
   print(f"P99: {latency_stats['p99']:.3f}ms")
   print(f"Max: {latency_stats['max']:.3f}ms")

Throughput Monitoring
~~~~~~~~~~~~~~~~~~~~~

Track cache throughput:

.. code-block:: python

   throughput = cache.get_throughput_stats()
   
   print(f"Operations/sec: {throughput['ops_per_second']}")
   print(f"Bytes/sec: {throughput['bytes_per_second']}")
   print(f"Peak throughput: {throughput['peak_ops_per_second']}")

Memory Monitoring
~~~~~~~~~~~~~~~~~

Monitor memory usage patterns:

.. code-block:: python

   memory_stats = cache.get_memory_stats()
   
   print(f"Used memory: {memory_stats['used_bytes']:,} bytes")
   print(f"Peak memory: {memory_stats['peak_bytes']:,} bytes")
   print(f"Memory fragmentation: {memory_stats['fragmentation']:.2%}")

Error Monitoring
----------------

Error Tracking
~~~~~~~~~~~~~~

Monitor and categorize errors:

.. code-block:: python

   error_stats = cache.get_error_stats()
   
   print(f"Total errors: {error_stats['total_errors']}")
   print(f"Connection errors: {error_stats['connection_errors']}")
   print(f"Timeout errors: {error_stats['timeout_errors']}")
   print(f"Serialization errors: {error_stats['serialization_errors']}")

Error Rate Alerts
~~~~~~~~~~~~~~~~~

Set up error rate monitoring:

.. code-block:: python

   from omni_cache.monitoring import ErrorRateMonitor

   error_monitor = ErrorRateMonitor(
       threshold=0.05,  # 5% error rate
       window_size=300,  # 5 minutes
       action=lambda rate: logging.critical(f"High error rate: {rate:.2%}")
   )
   
   cache.add_monitor(error_monitor)

Custom Monitoring
-----------------

Custom Collectors
~~~~~~~~~~~~~~~~~

Create custom metrics collectors:

.. code-block:: python

   from omni_cache.monitoring import BaseCollector

   class BusinessMetricsCollector(BaseCollector):
       def collect_metrics(self, cache):
           return {
               "user_cache_hits": cache.namespace_stats("users")["hits"],
               "session_cache_size": cache.namespace_stats("sessions")["size"],
               "api_cache_miss_rate": cache.namespace_stats("api")["miss_rate"]
           }

   collector = BusinessMetricsCollector()
   cache.add_collector(collector)

Event Hooks
~~~~~~~~~~~

Hook into cache events for custom monitoring:

.. code-block:: python

   def on_cache_miss(key, namespace=None):
       # Custom logic for cache misses
       if namespace == "critical":
           logging.warning(f"Critical cache miss: {key}")
   
   def on_eviction(key, reason):
       # Track evictions by reason
       metrics.increment(f"evictions.{reason}")
   
   cache.on("cache_miss", on_cache_miss)
   cache.on("eviction", on_eviction)

Monitoring Best Practices
-------------------------

1. **Set Appropriate Thresholds**
   - Monitor hit rates (aim for >80%)
   - Track error rates (keep <5%)
   - Watch memory usage trends

2. **Use Sampling for High-Volume Systems**
   - Sample traces to reduce overhead
   - Aggregate metrics efficiently
   - Focus on key performance indicators

3. **Implement Gradual Degradation**
   - Disable expensive monitoring during peak load
   - Use circuit breakers for monitoring systems
   - Prioritize application performance over metrics

4. **Regular Monitoring Review**
   - Review thresholds regularly
   - Update alerts based on usage patterns
   - Archive old metrics data

Configuration Example
---------------------

Complete monitoring configuration:

.. code-block:: python

   monitoring_config = {
       "metrics": {
           "enabled": True,
           "collection_interval": 60,
           "retention_period": 86400,  # 24 hours
           "detailed_metrics": True
       },
       "alerts": {
           "hit_rate_threshold": 0.8,
           "error_rate_threshold": 0.05,
           "memory_threshold": 0.9
       },
       "exporters": [
           {
               "type": "prometheus",
               "port": 8000
           },
           {
               "type": "statsd", 
               "host": "statsd.example.com",
               "port": 8125
           }
       ],
       "logging": {
           "level": "INFO",
           "format": "json",
           "include_metrics": True
       }
   }

   cache = OmniCache.create_cache(
       adapter="redis",
       monitoring=monitoring_config
   )

Next Steps
----------

* Learn about :doc:`performance` for optimization techniques
* Explore :doc:`troubleshooting` for debugging monitoring issues
* Check :doc:`../examples/index` for monitoring examples
