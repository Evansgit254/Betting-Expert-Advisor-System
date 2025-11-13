"""Performance profiling utilities for the betting system.

This module provides decorators and utilities for profiling code performance,
memory usage, and identifying bottlenecks.
"""
import cProfile
import functools
import io
import pstats
import time
from pathlib import Path
from typing import Any, Callable, Optional

from src.logging_config import get_logger

logger = get_logger(__name__)


def timeit(func: Callable) -> Callable:
    """Decorator to measure function execution time.

    Args:
        func: Function to profile

    Returns:
        Wrapped function that logs execution time

    Example:
        @timeit
        def my_function():
            # Your code here
            pass
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        elapsed = end_time - start_time

        logger.info(f"Function '{func.__name__}' took {elapsed:.4f} seconds to execute")
        return result

    return wrapper


def profile_function(
    func: Optional[Callable] = None,
    *,
    output_file: Optional[str] = None,
    sort_by: str = "cumulative",
    lines_to_print: int = 20,
) -> Callable:
    """Decorator to profile a function using cProfile.

    Args:
        func: Function to profile
        output_file: Optional file to save profile results
        sort_by: Sorting criterion for profile stats
        lines_to_print: Number of lines to print in the report

    Returns:
        Wrapped function that profiles execution

    Example:
        @profile_function(output_file='profile_results.txt')
        def my_function():
            # Your code here
            pass
    """

    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            profiler = cProfile.Profile()
            profiler.enable()
            result = None

            try:
                result = f(*args, **kwargs)
                return result
            finally:
                profiler.disable()

                # Create stats
                s = io.StringIO()
                ps = pstats.Stats(profiler, stream=s).sort_stats(sort_by)
                ps.print_stats(lines_to_print)

                profile_output = s.getvalue()

                # Log or save results
                if output_file:
                    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
                    with open(output_file, "w") as file_handle:
                        file_handle.write(profile_output)
                    logger.info(f"Profile results saved to {output_file}")
                else:
                    func_name = getattr(f, "__name__", "unknown")
                    logger.info(f"Profile results for '{func_name}':\n{profile_output}")

        return wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


class PerformanceMonitor:
    """Context manager for monitoring performance of code blocks.

    Example:
        with PerformanceMonitor("Database query"):
            # Your code here
            result = expensive_operation()
    """

    def __init__(self, name: str, log_memory: bool = False):
        """Initialize the performance monitor.

        Args:
            name: Name of the code block being monitored
            log_memory: If True, also log memory usage
        """
        self.name = name
        self.log_memory = log_memory
        self.start_time = None
        self.start_memory = None

    def __enter__(self):
        """Start monitoring."""
        self.start_time = time.perf_counter()

        if self.log_memory:
            try:
                import psutil

                process = psutil.Process()
                self.start_memory = process.memory_info().rss / 1024 / 1024  # MB
            except ImportError:
                logger.warning("psutil not installed, memory monitoring disabled")
                self.log_memory = False

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop monitoring and log results."""
        elapsed = time.perf_counter() - self.start_time

        log_msg = f"'{self.name}' took {elapsed:.4f} seconds"

        if self.log_memory:
            try:
                import psutil

                process = psutil.Process()
                end_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_delta = end_memory - self.start_memory
                log_msg += f", memory delta: {memory_delta:+.2f} MB"
            except Exception as e:
                logger.warning(f"Error measuring memory: {e}")

        logger.info(log_msg)


def benchmark(func: Callable, iterations: int = 100, *args: Any, **kwargs: Any) -> dict:
    """Benchmark a function by running it multiple times.

    Args:
        func: Function to benchmark
        iterations: Number of times to run the function
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Dictionary with benchmark statistics

    Example:
        stats = benchmark(my_function, iterations=1000, arg1=value1)
        print(f"Average time: {stats['avg']:.4f}s")
    """
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        func(*args, **kwargs)
        end = time.perf_counter()
        times.append(end - start)

    return {
        "iterations": iterations,
        "total": sum(times),
        "avg": sum(times) / len(times),
        "min": min(times),
        "max": max(times),
        "median": sorted(times)[len(times) // 2],
    }


def log_slow_queries(threshold: float = 1.0) -> Callable:
    """Decorator to log database queries that take longer than threshold.

    Args:
        threshold: Time threshold in seconds

    Returns:
        Decorator function

    Example:
        @log_slow_queries(threshold=0.5)
        def get_user_data(user_id):
            # Database query here
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start_time

            if elapsed > threshold:
                logger.warning(
                    f"Slow query detected: '{func.__name__}' took {elapsed:.4f}s "
                    f"(threshold: {threshold}s)"
                )

            return result

        return wrapper

    return decorator
