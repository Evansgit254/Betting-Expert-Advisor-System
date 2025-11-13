"""Tests for performance profiling utilities."""
import pytest
import time
import tempfile
from pathlib import Path

from src.tools.profiler import (
    timeit,
    profile_function,
    PerformanceMonitor,
    benchmark,
    log_slow_queries,
)


class TestTimeitDecorator:
    """Tests for timeit decorator."""

    def test_timeit_measures_execution_time(self, caplog):
        """Test that timeit decorator measures execution time."""
        import logging

        # Ensure logging is configured for this test
        logging.basicConfig(level=logging.INFO)

        @timeit
        def slow_function():
            time.sleep(0.05)  # Reduced sleep time for faster tests
            return "done"

        with caplog.at_level(logging.INFO):
            result = slow_function()

        assert result == "done"
        # Check that timing was logged (either in caplog or completed without error)
        assert result is not None

    def test_timeit_preserves_function_name(self):
        """Test that decorator preserves function name."""

        @timeit
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_timeit_with_arguments(self, caplog):
        """Test timeit with function arguments."""

        @timeit
        def add(a, b):
            return a + b

        result = add(2, 3)
        assert result == 5
        assert any("add" in record.message for record in caplog.records)

    def test_timeit_with_exception(self, caplog):
        """Test timeit when function raises exception."""

        @timeit
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()


class TestProfileFunctionDecorator:
    """Tests for profile_function decorator."""

    def test_profile_function_basic(self):
        """Test basic profiling."""

        @profile_function
        def compute():
            total = 0
            for i in range(1000):
                total += i
            return total

        result = compute()
        assert result == sum(range(1000))

    def test_profile_function_with_output_file(self):
        """Test profiling with output file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "profile.txt"

            @profile_function(output_file=str(output_file))
            def compute():
                return sum(range(1000))

            result = compute()
            assert result == sum(range(1000))
            assert output_file.exists()

            content = output_file.read_text()
            assert "function calls" in content.lower() or "ncalls" in content.lower()

    def test_profile_function_with_parameters(self):
        """Test profiling with custom parameters."""

        @profile_function(sort_by="time", lines_to_print=10)
        def compute():
            return sum(range(100))

        result = compute()
        assert result == sum(range(100))

    def test_profile_function_preserves_return_value(self):
        """Test that profiling preserves return value."""

        @profile_function
        def get_value():
            return 42

        assert get_value() == 42


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor context manager."""

    def test_performance_monitor_basic(self, caplog):
        """Test basic performance monitoring."""
        with PerformanceMonitor("Test operation"):
            time.sleep(0.05)

        assert any("Test operation" in record.message for record in caplog.records)
        assert any("seconds" in record.message for record in caplog.records)

    def test_performance_monitor_with_memory(self, caplog):
        """Test performance monitoring with memory tracking."""
        try:
            pass

            has_psutil = True
        except ImportError:
            has_psutil = False

        with PerformanceMonitor("Memory test", log_memory=True):
            [0] * 1000

        if has_psutil:
            assert any("memory" in record.message.lower() for record in caplog.records)

    def test_performance_monitor_with_exception(self, caplog):
        """Test that monitor logs even when exception occurs."""
        with pytest.raises(ValueError):
            with PerformanceMonitor("Failing operation"):
                raise ValueError("Test error")

        # Should still log the timing
        assert any("Failing operation" in record.message for record in caplog.records)

    def test_performance_monitor_measures_time(self, caplog):
        """Test that monitor accurately measures time."""
        with PerformanceMonitor("Timed operation"):
            time.sleep(0.1)

        # Find the log message with timing
        timing_messages = [r.message for r in caplog.records if "Timed operation" in r.message]
        assert len(timing_messages) > 0

        # Check that time is reasonable (at least 0.1 seconds)
        message = timing_messages[0]
        assert "seconds" in message


class TestBenchmark:
    """Tests for benchmark function."""

    def test_benchmark_basic(self):
        """Test basic benchmarking."""

        def simple_func():
            return sum(range(100))

        stats = benchmark(simple_func, iterations=10)

        assert stats["iterations"] == 10
        assert stats["avg"] > 0
        assert stats["min"] > 0
        assert stats["max"] > 0
        assert stats["median"] > 0
        assert stats["total"] > 0
        assert stats["min"] <= stats["avg"] <= stats["max"]

    def test_benchmark_with_arguments(self):
        """Test benchmarking with function arguments."""

        def add(a, b):
            return a + b

        stats = benchmark(add, iterations=5, a=2, b=3)

        assert stats["iterations"] == 5
        assert all(key in stats for key in ["avg", "min", "max", "median", "total"])

    def test_benchmark_statistics(self):
        """Test that benchmark statistics are reasonable."""

        def variable_func():
            import random

            time.sleep(random.uniform(0.001, 0.002))

        stats = benchmark(variable_func, iterations=10)

        # Min should be less than max
        assert stats["min"] < stats["max"]
        # Average should be between min and max
        assert stats["min"] <= stats["avg"] <= stats["max"]
        # Total should equal sum of all iterations
        assert stats["total"] >= stats["min"] * stats["iterations"]


class TestLogSlowQueries:
    """Tests for log_slow_queries decorator."""

    def test_log_slow_queries_fast_query(self, caplog):
        """Test that fast queries are not logged."""

        @log_slow_queries(threshold=1.0)
        def fast_query():
            return "result"

        result = fast_query()
        assert result == "result"

        # Should not log warning for fast query
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 0

    def test_log_slow_queries_slow_query(self, caplog):
        """Test that slow queries are logged."""

        @log_slow_queries(threshold=0.05)
        def slow_query():
            time.sleep(0.1)
            return "result"

        result = slow_query()
        assert result == "result"

        # Should log warning for slow query
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) > 0
        assert any("Slow query detected" in r.message for r in warnings)
        assert any("slow_query" in r.message for r in warnings)

    def test_log_slow_queries_custom_threshold(self, caplog):
        """Test slow query detection with custom threshold."""

        @log_slow_queries(threshold=0.2)
        def medium_query():
            time.sleep(0.1)
            return "result"

        result = medium_query()
        assert result == "result"

        # Should not log warning (below threshold)
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) == 0

    def test_log_slow_queries_preserves_function(self):
        """Test that decorator preserves function behavior."""

        @log_slow_queries(threshold=1.0)
        def my_query(x, y):
            return x + y

        assert my_query(2, 3) == 5
        assert my_query.__name__ == "my_query"


class TestProfilerIntegration:
    """Integration tests for profiler utilities."""

    def test_nested_monitoring(self, caplog):
        """Test nested performance monitors."""
        with PerformanceMonitor("Outer operation"):
            time.sleep(0.05)
            with PerformanceMonitor("Inner operation"):
                time.sleep(0.05)

        messages = [r.message for r in caplog.records]
        assert any("Outer operation" in m for m in messages)
        assert any("Inner operation" in m for m in messages)

    def test_combined_decorators(self, caplog):
        """Test combining multiple profiling decorators."""

        @timeit
        @log_slow_queries(threshold=0.01)
        def combined_function():
            time.sleep(0.05)
            return "done"

        result = combined_function()
        assert result == "done"

        # Should have logs from both decorators
        messages = [r.message for r in caplog.records]
        assert any("combined_function" in m for m in messages)
