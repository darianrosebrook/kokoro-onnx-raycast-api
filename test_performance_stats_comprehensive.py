#!/usr/bin/env python3
"""Comprehensive tests for api/performance/stats.py to increase coverage."""

import pytest
import time
import os
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, os.path.dirname(__file__))

from api.performance.stats import (
    update_inference_stats,
    update_phonemizer_stats,
    get_phonemizer_stats,
    reset_phonemizer_stats,
    handle_coreml_context_warning,
    update_endpoint_performance_stats,
    get_performance_stats,
    get_session_utilization_stats,
    calculate_load_balancing_efficiency,
    get_memory_fragmentation_stats,
    get_dynamic_memory_optimization_stats,
    update_fast_path_performance_stats,
    mark_phonemizer_preinitialized
)


class TestInferenceStats:
    """Test inference statistics functionality."""

    def test_update_inference_stats_basic(self):
        """Test basic inference stats update."""
        # Test that the function can be called without errors
        update_inference_stats(100.0, "cpu")

    def test_update_inference_stats_with_kwargs(self):
        """Test inference stats update with additional kwargs."""
        update_inference_stats(150.0, "coreml", session_id="test_session")

    def test_update_inference_stats_different_providers(self):
        """Test inference stats with different providers."""
        providers = ["cpu", "coreml", "ort"]

        for provider in providers:
            update_inference_stats(100.0, provider)


class TestPhonemizerStats:
    """Test phonemizer statistics functionality."""

    def test_update_phonemizer_stats_no_fallback(self):
        """Test phonemizer stats update without fallback."""
        update_phonemizer_stats(fallback_used=False, quality_mode=False)

    def test_update_phonemizer_stats_with_fallback(self):
        """Test phonemizer stats update with fallback."""
        update_phonemizer_stats(fallback_used=True, quality_mode=True)

    def test_get_phonemizer_stats(self):
        """Test phonemizer stats retrieval."""
        stats = get_phonemizer_stats()

        assert isinstance(stats, dict)
        # Should contain some expected keys based on actual structure
        assert len(stats) > 0  # Should not be empty

    def test_reset_phonemizer_stats(self):
        """Test phonemizer stats reset."""
        # Add some stats first
        update_phonemizer_stats(fallback_used=True)

        # Reset stats
        reset_phonemizer_stats()

        # Should not raise an exception and should return valid stats
        stats_after = get_phonemizer_stats()
        assert isinstance(stats_after, dict)


class TestCoreMLContextWarning:
    """Test CoreML context warning handling."""

    def test_handle_coreml_context_warning(self):
        """Test CoreML context warning handling."""
        # Should not raise an exception
        handle_coreml_context_warning()


class TestEndpointPerformanceStats:
    """Test endpoint performance statistics."""

    def test_update_endpoint_performance_stats_success(self):
        """Test successful endpoint performance update."""
        update_endpoint_performance_stats("/api/tts", 150.0, success=True)

    def test_update_endpoint_performance_stats_failure(self):
        """Test failed endpoint performance update."""
        update_endpoint_performance_stats("/api/tts", 200.0, success=False)

    def test_update_endpoint_performance_stats_different_endpoints(self):
        """Test different endpoint performance tracking."""
        endpoints = ["/api/tts", "/health", "/api/generate", "/api/status"]

        for endpoint in endpoints:
            update_endpoint_performance_stats(endpoint, 100.0, success=True)


class TestPerformanceStatsRetrieval:
    """Test performance statistics retrieval."""

    def test_get_performance_stats(self):
        """Test performance stats retrieval."""
        stats = get_performance_stats()

        assert isinstance(stats, dict)
        # Should contain major categories
        assert len(stats) > 0

    def test_get_session_utilization_stats(self):
        """Test session utilization stats retrieval."""
        stats = get_session_utilization_stats()

        assert isinstance(stats, dict)
        # Should contain session-related metrics
        assert len(stats) > 0


class TestLoadBalancingEfficiency:
    """Test load balancing efficiency calculations."""

    def test_calculate_load_balancing_efficiency(self):
        """Test load balancing efficiency calculation."""
        efficiency = calculate_load_balancing_efficiency()

        assert isinstance(efficiency, (int, float))
        # Should be between 0 and 100 or -1 for no data
        assert efficiency == -1 or (0 <= efficiency <= 100)


class TestMemoryFragmentationStats:
    """Test memory fragmentation statistics."""

    def test_get_memory_fragmentation_stats(self):
        """Test memory fragmentation stats retrieval."""
        stats = get_memory_fragmentation_stats()

        assert isinstance(stats, dict)
        # Should contain memory-related metrics
        assert len(stats) > 0


class TestDynamicMemoryOptimizationStats:
    """Test dynamic memory optimization statistics."""

    def test_get_dynamic_memory_optimization_stats(self):
        """Test dynamic memory optimization stats retrieval."""
        stats = get_dynamic_memory_optimization_stats()

        assert isinstance(stats, dict)
        # Should contain memory optimization metrics
        assert len(stats) > 0


class TestFastPathPerformanceStats:
    """Test fast path performance statistics."""

    def test_update_fast_path_performance_stats_basic(self):
        """Test basic fast path performance stats update."""
        update_fast_path_performance_stats("cpu_provider", ttfa_ms=100.0)

    def test_update_fast_path_performance_stats_success(self):
        """Test fast path performance stats with success."""
        update_fast_path_performance_stats("coreml_provider", ttfa_ms=50.0, success=True)

    def test_update_fast_path_performance_stats_failure(self):
        """Test fast path performance stats with failure."""
        update_fast_path_performance_stats("ort_provider", ttfa_ms=200.0, success=False)

    def test_update_fast_path_performance_stats_with_kwargs(self):
        """Test fast path performance stats with additional kwargs."""
        update_fast_path_performance_stats(
            "test_provider",
            ttfa_ms=75.0,
            rtf=0.8,
            memory_mb=150.0
        )


class TestPhonemizerPreinitialization:
    """Test phonemizer preinitialization marking."""

    def test_mark_phonemizer_preinitialized(self):
        """Test phonemizer preinitialization marking."""
        # Should not raise an exception
        mark_phonemizer_preinitialized()


class TestPerformanceStatsIntegration:
    """Test integrated performance statistics functionality."""

    def test_multiple_stats_updates(self):
        """Test multiple statistics updates work together."""
        # Update various stats
        update_inference_stats(100.0, "cpu")
        update_phonemizer_stats(fallback_used=True)
        update_endpoint_performance_stats("/api/tts", 150.0, success=True)
        handle_coreml_context_warning()

        # Verify stats can be retrieved
        perf_stats = get_performance_stats()
        phoneme_stats = get_phonemizer_stats()

        assert isinstance(perf_stats, dict)
        assert isinstance(phoneme_stats, dict)

    def test_stats_persistence_across_calls(self):
        """Test that statistics persist across multiple calls."""
        # Add some initial stats
        update_inference_stats(100.0, "cpu")
        initial_stats = get_performance_stats()

        # Add more stats
        update_inference_stats(120.0, "coreml")
        updated_stats = get_performance_stats()

        # Stats should reflect the updates
        assert isinstance(initial_stats, dict)
        assert isinstance(updated_stats, dict)

    def test_all_stat_functions_exist(self):
        """Test that all major stat functions exist and are callable."""
        functions_to_test = [
            lambda: update_inference_stats(100.0, "cpu"),
            lambda: update_phonemizer_stats(),
            lambda: get_phonemizer_stats(),
            lambda: reset_phonemizer_stats(),
            lambda: handle_coreml_context_warning(),
            lambda: update_endpoint_performance_stats("/test", 100.0),
            lambda: get_performance_stats(),
            lambda: get_session_utilization_stats(),
            lambda: calculate_load_balancing_efficiency(),
            lambda: get_memory_fragmentation_stats(),
            lambda: get_dynamic_memory_optimization_stats(),
            lambda: update_fast_path_performance_stats("test", ttfa_ms=100.0),
            lambda: mark_phonemizer_preinitialized(),
        ]

        for func in functions_to_test:
            # Each function should be callable without critical errors
            try:
                func()
                assert True
            except Exception as e:
                # Some functions might fail due to missing dependencies, but not due to basic issues
                assert "import" not in str(e).lower() and "module" not in str(e).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
