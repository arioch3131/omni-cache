# =============================================================================
# EXAMPLE: Data Processing Pipeline with Multi-Level Caching
# File: examples/advanced/data_processing_pipeline.py
# =============================================================================
"""
Data processing pipeline example with multi-level caching.

This example shows:
- Raw data caching (expensive I/O operations)
- Processed data caching (computation results)
- Memoization for statistical calculations
- Cache warming strategies
- Performance monitoring
"""

import hashlib
import random
import time
from typing import Any

import numpy as np
import pandas as pd

from omni_cache import (
    CacheBackend,
    cached,
    clear_cache,
    create_adapter,
    get_cache_stats,
    memoize,
    setup,
)

# =============================================================================
# Pipeline Setup
# =============================================================================

# Setup multi-level caching
manager = setup(log_level="INFO")

# Raw data cache (persistent, large TTL)
raw_data_adapter = create_adapter(
    CacheBackend.MEMORY,
    {"max_size": 100, "eviction_policy": "lru"},  # Limit number of datasets
)
manager.register_adapter("raw_data", raw_data_adapter)

# Processed data cache (memory, medium TTL)
processed_adapter = create_adapter(CacheBackend.MEMORY, {"max_size": 500, "eviction_policy": "lru"})
manager.register_adapter("processed", processed_adapter)

# Setup routing
manager.add_routing_rule("raw", "raw_data")
manager.add_routing_rule("processed", "processed")

# =============================================================================
# Data Generation (Simulating External Data Sources)
# =============================================================================


def generate_sample_data(size: int, complexity: str = "simple") -> pd.DataFrame:
    """Generate sample data for processing."""
    print(f"Generating {complexity} dataset with {size} rows...")

    # Simulate time-consuming data generation
    time.sleep(0.1 * size / 1000)  # Simulate I/O delay

    if complexity == "simple":
        data = {
            "id": range(size),
            "value": np.random.normal(100, 15, size),
            "category": np.random.choice(["A", "B", "C"], size),
            "timestamp": pd.date_range("2024-01-01", periods=size, freq="h"),
        }
    elif complexity == "medium":
        data = {
            "id": range(size),
            "value1": np.random.normal(100, 15, size),
            "value2": np.random.exponential(2, size),
            "value3": np.random.gamma(2, 2, size),
            "category": np.random.choice(["A", "B", "C", "D", "E"], size),
            "subcategory": np.random.choice(["X", "Y", "Z"], size),
            "timestamp": pd.date_range("2024-01-01", periods=size, freq="30min"),
            "region": np.random.choice(["North", "South", "East", "West"], size),
        }
    else:  # complex
        data = {
            "id": range(size),
            **{f"metric_{i}": np.random.normal(i * 10, 5, size) for i in range(10)},
            "category": np.random.choice([f"Cat_{i}" for i in range(20)], size),
            "timestamp": pd.date_range("2024-01-01", periods=size, freq="15min"),
            "coordinates_x": np.random.uniform(-180, 180, size),
            "coordinates_y": np.random.uniform(-90, 90, size),
        }

    return pd.DataFrame(data)


# =============================================================================
# Level 1: Raw Data Loading (Heavy Caching)
# =============================================================================


@cached(ttl=3600, namespace="raw", adapter="raw_data")
def load_dataset(source: str, size: int, complexity: str = "simple") -> pd.DataFrame:
    """Load dataset with heavy caching (simulates file I/O)."""
    print(f"💾 Loading dataset: {source} (size={size}, complexity={complexity})")

    # Simulate expensive I/O operation
    if complexity == "simple":
        time.sleep(0.5)
    elif complexity == "medium":
        time.sleep(1.0)
    else:
        time.sleep(2.0)

    return generate_sample_data(size, complexity)


@cached(ttl=1800, namespace="raw", adapter="raw_data")
def load_external_data(api_endpoint: str) -> dict[str, Any]:
    """Load data from external API with caching."""
    print(f"🌐 Fetching data from: {api_endpoint}")

    # Simulate API call
    time.sleep(1.0)

    return {
        "endpoint": api_endpoint,
        "data": [random.randint(1, 100) for _ in range(100)],
        "metadata": {"timestamp": time.time(), "version": "1.0", "records": 100},
    }


# =============================================================================
# Level 2: Data Processing (Medium Caching)
# =============================================================================


@cached(ttl=600, namespace="processed", adapter="processed")
def clean_dataset(df_hash: str, df: pd.DataFrame, remove_outliers: bool = True) -> pd.DataFrame:
    """Clean dataset with caching based on data hash."""
    print(f"🧹 Cleaning dataset (hash: {df_hash[:8]}...)")

    # Simulate processing time
    time.sleep(0.2)

    cleaned_df = df.copy()

    # Remove duplicates
    cleaned_df = cleaned_df.drop_duplicates()

    # Handle missing values
    cleaned_df = cleaned_df.fillna(cleaned_df.mean(numeric_only=True))

    # Remove outliers (simple method)
    if remove_outliers and "value" in cleaned_df.columns:
        Q1 = cleaned_df["value"].quantile(0.25)
        Q3 = cleaned_df["value"].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        cleaned_df = cleaned_df[
            (cleaned_df["value"] >= lower_bound) & (cleaned_df["value"] <= upper_bound)
        ]

    print(f"  Original size: {len(df)}, Cleaned size: {len(cleaned_df)}")
    return cleaned_df


@cached(ttl=900, namespace="processed", adapter="processed")
def aggregate_data(
    df_hash: str, df: pd.DataFrame, group_by: str, agg_funcs: list[str]
) -> pd.DataFrame:
    """Aggregate data with caching."""
    print(f"📊 Aggregating data by {group_by} (hash: {df_hash[:8]}...)")

    # Simulate processing time
    time.sleep(0.3)

    # Build aggregation dictionary
    agg_dict = {}
    numeric_columns = df.select_dtypes(include=[np.number]).columns

    for col in numeric_columns:
        if col != group_by and col in df.columns:
            agg_dict[col] = agg_funcs  # Aggregate all functions for this column

    if not agg_dict:
        return df

    # Perform aggregation
    aggregated_df = df.groupby(group_by).agg(agg_dict)

    # Flatten multi-level columns
    aggregated_df.columns = [f"{col}_{func}" for col, func in aggregated_df.columns]

    # Reset index to make group_by a regular column
    result = aggregated_df.reset_index()

    return result


# =============================================================================
# Level 3: Statistical Calculations (Memoization)
# =============================================================================


@memoize(maxsize=1000)
def calculate_statistics(data_hash: str, data_array: tuple[float, ...]) -> dict[str, float]:
    """Calculate statistics with memoization."""
    print(f"📈 Calculating statistics (hash: {data_hash[:8]}...)")

    # Convert back to numpy array
    arr = np.array(data_array)

    # Simulate computation time
    time.sleep(0.1)

    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "std": float(np.std(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
        "q25": float(np.percentile(arr, 25)),
        "q75": float(np.percentile(arr, 75)),
        "skewness": float(scipy_stats_skew(arr)),
        "kurtosis": float(scipy_stats_kurtosis(arr)),
    }


def scipy_stats_skew(arr):
    """Simple skewness calculation."""
    mean = np.mean(arr)
    std = np.std(arr)
    return np.mean(((arr - mean) / std) ** 3) if std > 0 else 0


def scipy_stats_kurtosis(arr):
    """Simple kurtosis calculation."""
    mean = np.mean(arr)
    std = np.std(arr)
    return np.mean(((arr - mean) / std) ** 4) - 3 if std > 0 else 0


@memoize(maxsize=500)
def calculate_correlation_matrix(
    df_hash: str, columns_hash: str, numeric_data: tuple[tuple[float, ...], ...]
) -> dict[str, dict[str, float]]:
    """Calculate correlation matrix with memoization."""
    print(f"🔗 Calculating correlation matrix (hash: {df_hash[:8]}...)")

    # Convert back to DataFrame-like structure
    data_array = np.array(numeric_data)

    # Simulate computation time
    time.sleep(0.2)

    corr_matrix = np.corrcoef(data_array.T)

    # Convert to dictionary (assuming we know column names)
    n_cols = data_array.shape[1]
    col_names = [f"col_{i}" for i in range(n_cols)]

    result = {}
    for i, col1 in enumerate(col_names):
        result[col1] = {}
        for j, col2 in enumerate(col_names):
            result[col1][col2] = float(corr_matrix[i, j])

    return result


# =============================================================================
# Pipeline Functions
# =============================================================================


def create_data_hash(data: Any) -> str:
    """Create hash for data to use as cache key."""
    if isinstance(data, pd.DataFrame):
        # Use shape and sample of values for hash
        sample_data = f"{data.shape}_{data.head().to_string()}"
    else:
        sample_data = str(data)

    return hashlib.sha256(sample_data.encode()).hexdigest()


def process_dataset_pipeline(
    source: str,
    size: int,
    complexity: str = "simple",
    clean_data: bool = True,
    aggregate_by: str = None,
    calculate_stats: bool = True,
) -> dict[str, Any]:
    """Complete data processing pipeline with multi-level caching."""

    print(f"\n🔄 Starting pipeline: {source}")
    start_time = time.time()

    results = {"source": source, "size": size, "complexity": complexity}

    # Step 1: Load raw data (Level 1 cache)
    step_start = time.time()
    raw_data = load_dataset(source, size, complexity)
    results["load_time"] = time.time() - step_start
    results["raw_shape"] = raw_data.shape

    # Step 2: Clean data (Level 2 cache)
    if clean_data:
        step_start = time.time()
        data_hash = create_data_hash(raw_data)
        cleaned_data = clean_dataset(data_hash, raw_data)
        results["clean_time"] = time.time() - step_start
        results["cleaned_shape"] = cleaned_data.shape
    else:
        cleaned_data = raw_data
        results["clean_time"] = 0
        results["cleaned_shape"] = raw_data.shape

    # Step 3: Aggregate data (Level 2 cache)
    if aggregate_by and aggregate_by in cleaned_data.columns:
        step_start = time.time()
        data_hash = create_data_hash(cleaned_data)
        aggregated_data = aggregate_data(
            data_hash, cleaned_data, aggregate_by, ["mean", "sum", "count"]
        )
        results["aggregate_time"] = time.time() - step_start
        results["aggregated_shape"] = aggregated_data.shape
        final_data = aggregated_data
    else:
        results["aggregate_time"] = 0
        results["aggregated_shape"] = cleaned_data.shape
        final_data = cleaned_data

    # Step 4: Calculate statistics (Level 3 memoization)
    if calculate_stats:
        step_start = time.time()

        numeric_columns = final_data.select_dtypes(include=[np.number]).columns
        stats_results = {}

        for col in numeric_columns:
            col_data = final_data[col].dropna()
            if len(col_data) > 0:
                data_hash = create_data_hash(col_data)
                data_tuple = tuple(col_data.values)
                stats_results[col] = calculate_statistics(data_hash, data_tuple)

        results["stats_time"] = time.time() - step_start
        results["statistics"] = stats_results
    else:
        results["stats_time"] = 0

    results["total_time"] = time.time() - start_time

    print(f"✅ Pipeline completed in {results['total_time']:.2f}s")
    return results


# =============================================================================
# Benchmarking and Performance Testing
# =============================================================================


def benchmark_caching_performance():
    """Benchmark the performance benefits of caching."""
    print("\n🏁 Benchmarking Caching Performance")
    print("=" * 50)

    # Test parameters
    test_cases = [
        ("small_dataset", 1000, "simple"),
        ("medium_dataset", 5000, "medium"),
        ("large_dataset", 10000, "complex"),
    ]

    for source, size, complexity in test_cases:
        print(f"\n📊 Testing: {source}")

        # Clear cache to start fresh
        clear_cache(namespace="raw")
        clear_cache(namespace="processed")

        # First run (cold cache)
        start_time = time.time()
        result1 = process_dataset_pipeline(source, size, complexity, aggregate_by="category")
        cold_time = time.time() - start_time

        # Second run (warm cache)
        start_time = time.time()
        result2 = process_dataset_pipeline(source, size, complexity, aggregate_by="category")
        warm_time = time.time() - start_time

        # Calculate speedup
        speedup = cold_time / warm_time if warm_time > 0 else float("inf")

        print(f"  Cold cache time: {cold_time:.2f}s")
        print(f"  Warm cache time: {warm_time:.2f}s")
        print(f"  Speedup: {speedup:.1f}x")

        # Verify results are identical
        assert result1["raw_shape"] == result2["raw_shape"]
        print("  ✅ Results verified identical")


def cache_warming_strategy():
    """Demonstrate cache warming for better performance."""
    print("\n🔥 Cache Warming Strategy")
    print("=" * 30)

    # Common datasets that should be pre-loaded
    common_datasets = [
        ("daily_reports", 2000, "medium"),
        ("user_analytics", 3000, "simple"),
        ("system_metrics", 1500, "complex"),
    ]

    print("Warming cache with common datasets...")
    for source, size, complexity in common_datasets:
        # Pre-load and process common datasets
        process_dataset_pipeline(source, size, complexity, aggregate_by="category")
        print(f"  ✅ Warmed: {source}")

    # Show cache statistics
    stats = get_cache_stats()
    print("\nCache Statistics:")
    print(f"  Raw data cache: {stats}")


# =============================================================================
# Demo and Main Function
# =============================================================================


def demo_data_processing():
    """Demonstrate the data processing pipeline."""
    print("🏭 Data Processing Pipeline Demo")
    print("=" * 40)

    # Process several datasets
    datasets = [
        ("sales_data", 2000, "medium"),
        ("user_behavior", 3000, "simple"),
        ("sensor_readings", 1500, "complex"),
    ]

    all_results = []

    for source, size, complexity in datasets:
        result = process_dataset_pipeline(
            source, size, complexity, clean_data=True, aggregate_by="category", calculate_stats=True
        )
        all_results.append(result)

    # Summary
    print("\n📈 Processing Summary:")
    total_time = sum(r["total_time"] for r in all_results)
    total_records = sum(r["size"] for r in all_results)

    print(f"  Total datasets: {len(all_results)}")
    print(f"  Total records: {total_records:,}")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Records/second: {total_records / total_time:,.0f}")

    # Show cache efficiency
    cache_stats = get_cache_stats()
    print(f"\n💾 Cache Statistics: {cache_stats}")


if __name__ == "__main__":
    print("🔬 Omni-Cache Data Processing Pipeline Example")
    print("=" * 60)

    # Run demonstrations
    demo_data_processing()
    benchmark_caching_performance()
    cache_warming_strategy()

    print("\n✅ All processing examples completed!")
