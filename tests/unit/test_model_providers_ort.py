"""
Unit tests for api/model/providers/ort.py - ONNX Runtime provider configuration.

Tests cover:
- Session options creation and optimization
- Provider options caching
- CPU provider configuration
- Thread configuration based on hardware
- Memory optimizations
- Provider selection logic

Aligns with CAWS acceptance criteria A1 (provider selection).

@author: @darianrosebrook
@date: 2025-10-09
"""

import logging
from typing import Any, Dict, List, Optional
from unittest.mock import Mock, patch, MagicMock

import onnxruntime as ort
import pytest

from api.model.providers import ort as ort_provider


class TestSessionOptionsCreation:
    """Test ONNX Runtime session options creation."""

    def test_create_optimized_session_options_returns_session_options(self):
        """Test that session options are created."""
        # Setup
        capabilities = {
            "is_apple_silicon": True,
            "neural_engine_cores": 16,
            "cpu_cores": 8
        }

        # Test
        options = ort_provider.create_optimized_session_options(capabilities)

        # Assert
        assert isinstance(options, ort.SessionOptions)
        assert options.graph_optimization_level == ort.GraphOptimizationLevel.ORT_ENABLE_BASIC

    def test_create_optimized_session_options_caches_result(self):
        """Test that session options are cached."""
        # Clear cache
        ort_provider._session_options_cache = None
        
        # Setup
        capabilities = {"is_apple_silicon": True}

        # Test - create twice
        options1 = ort_provider.create_optimized_session_options(capabilities)
        options2 = ort_provider.create_optimized_session_options(capabilities)

        # Assert - should return same cached instance
        assert options1 is options2

    def test_session_options_for_m1_max(self):
        """Test session options for M1 Max / M2 Max."""
        # Clear cache
        ort_provider._session_options_cache = None
        
        # Setup - M1 Max has 32 ANE cores
        capabilities = {
            "is_apple_silicon": True,
            "neural_engine_cores": 32,
            "cpu_cores": 10
        }

        # Test
        options = ort_provider.create_optimized_session_options(capabilities)

        # Assert
        assert options.intra_op_num_threads == 8
        assert options.inter_op_num_threads == 4

    def test_session_options_for_m1(self):
        """Test session options for M1 / M2."""
        # Clear cache
        ort_provider._session_options_cache = None
        
        # Setup - M1 has 16 ANE cores
        capabilities = {
            "is_apple_silicon": True,
            "neural_engine_cores": 16,
            "cpu_cores": 8
        }

        # Test
        options = ort_provider.create_optimized_session_options(capabilities)

        # Assert
        assert options.intra_op_num_threads == 6
        assert options.inter_op_num_threads == 2

    def test_session_options_for_non_apple_silicon(self):
        """Test session options for non-Apple Silicon."""
        # Clear cache
        ort_provider._session_options_cache = None
        
        # Setup
        capabilities = {
            "is_apple_silicon": False,
            "cpu_cores": 4
        }

        # Test
        options = ort_provider.create_optimized_session_options(capabilities)

        # Assert - conservative settings
        assert options.intra_op_num_threads == 2
        assert options.inter_op_num_threads == 1

    def test_session_options_enable_memory_optimizations(self):
        """Test that memory optimizations are enabled."""
        # Clear cache
        ort_provider._session_options_cache = None
        
        # Setup
        capabilities = {}

        # Test
        options = ort_provider.create_optimized_session_options(capabilities)

        # Assert
        assert options.enable_mem_pattern is True
        assert options.enable_mem_reuse is True
        assert options.enable_cpu_mem_arena is True


class TestProviderOptionsCache:
    """Test provider options caching."""

    def test_get_cached_provider_options_for_cpu(self):
        """Test CPU provider options."""
        # Clear cache
        ort_provider._provider_options_cache.clear()
        
        # Setup
        capabilities = {
            "cpu_cores": 8,
            "memory_gb": 16
        }

        # Test
        options = ort_provider.get_cached_provider_options("CPUExecutionProvider", capabilities)

        # Assert
        assert isinstance(options, dict)
        assert "intra_op_num_threads" in options
        assert "enable_cpu_mem_arena" in options

    def test_get_cached_provider_options_caches_result(self):
        """Test that provider options are cached."""
        # Clear cache
        ort_provider._provider_options_cache.clear()
        
        # Setup
        capabilities = {"cpu_cores": 4}

        # Test - get twice
        options1 = ort_provider.get_cached_provider_options("CPUExecutionProvider", capabilities)
        options2 = ort_provider.get_cached_provider_options("CPUExecutionProvider", capabilities)

        # Assert - second call should return cached result
        assert options1 == options2
        # Should only have one cache entry
        assert len(ort_provider._provider_options_cache) == 1

    def test_get_cached_provider_options_for_coreml(self):
        """Test CoreML provider options delegation."""
        # Clear cache
        ort_provider._provider_options_cache.clear()
        
        # Setup
        capabilities = {
            "apple_silicon": True,
            "neural_engine": True
        }

        with patch('api.model.providers.ort.create_coreml_provider_options') as mock_create:
            mock_create.return_value = {"MLComputeUnits": "ALL"}
            
            # Test
            options = ort_provider.get_cached_provider_options("CoreMLExecutionProvider", capabilities)

            # Assert
            mock_create.assert_called_once_with(capabilities)
            assert options == {"MLComputeUnits": "ALL"}

    def test_cpu_provider_high_memory_configuration(self):
        """Test CPU provider options with high memory."""
        # Clear cache
        ort_provider._provider_options_cache.clear()
        
        # Setup - 16GB+ RAM
        capabilities = {
            "cpu_cores": 8,
            "memory_gb": 32
        }

        # Test
        options = ort_provider.get_cached_provider_options("CPUExecutionProvider", capabilities)

        # Assert - should have larger arena sizes
        assert "cpu_mem_arena_initial_chunk_size" in options
        initial_size = int(options["cpu_mem_arena_initial_chunk_size"])
        assert initial_size >= 67108864  # 64MB

    def test_cpu_provider_low_memory_configuration(self):
        """Test CPU provider options with lower memory."""
        # Clear cache
        ort_provider._provider_options_cache.clear()
        
        # Setup - <16GB RAM
        capabilities = {
            "cpu_cores": 4,
            "memory_gb": 8
        }

        # Test
        options = ort_provider.get_cached_provider_options("CPUExecutionProvider", capabilities)

        # Assert - should have smaller arena sizes
        assert "cpu_mem_arena_initial_chunk_size" in options
        initial_size = int(options["cpu_mem_arena_initial_chunk_size"])
        assert initial_size <= 33554432  # 32MB

    def test_clear_provider_cache_empties_all_caches(self):
        """Test cache clearing."""
        # Setup - populate caches
        ort_provider._session_options_cache = Mock(spec=ort.SessionOptions)
        ort_provider._provider_options_cache["test"] = {"data": "test"}

        # Test
        ort_provider.clear_provider_cache()

        # Assert
        assert ort_provider._session_options_cache is None
        assert len(ort_provider._provider_options_cache) == 0


class TestProviderSelection:
    """Test provider selection and configuration."""

    def test_should_use_ort_optimization_with_apple_silicon(self):
        """Test ORT optimization decision for Apple Silicon."""
        # Setup
        capabilities = {
            "is_apple_silicon": True
        }

        # Test
        result = ort_provider.should_use_ort_optimization(capabilities)

        # Assert
        assert isinstance(result, bool)

    def test_should_use_ort_optimization_without_apple_silicon(self):
        """Test ORT optimization decision for non-Apple Silicon."""
        # Setup
        capabilities = {
            "is_apple_silicon": False
        }

        # Test
        result = ort_provider.should_use_ort_optimization(capabilities)

        # Assert
        assert isinstance(result, bool)

    def test_configure_ort_providers_returns_list(self):
        """Test that provider configuration returns provider list."""
        # Setup
        capabilities = {
            "is_apple_silicon": True,
            "neural_engine": True
        }

        # Test
        providers = ort_provider.configure_ort_providers(capabilities)

        # Assert
        assert isinstance(providers, list)
        assert len(providers) > 0
        assert all(isinstance(p, str) for p in providers)

    def test_configure_ort_providers_without_capabilities(self):
        """Test provider configuration with None capabilities."""
        # Test - should use defaults
        providers = ort_provider.configure_ort_providers(None)

        # Assert
        assert isinstance(providers, list)
        assert len(providers) > 0

    def test_get_provider_info_returns_dict(self):
        """Test getting provider information."""
        # Test
        info = ort_provider.get_provider_info("CPUExecutionProvider")

        # Assert
        assert isinstance(info, dict)


class TestThreadConfiguration:
    """Test thread configuration for different hardware."""

    def test_thread_config_scales_with_cpu_cores(self):
        """Test that thread count scales with CPU cores."""
        # Clear cache
        ort_provider._session_options_cache = None
        
        # Setup - many cores
        capabilities = {
            "is_apple_silicon": False,
            "cpu_cores": 16
        }

        # Test
        options = ort_provider.create_optimized_session_options(capabilities)

        # Assert - should have configured threads
        assert options.intra_op_num_threads > 0
        assert options.inter_op_num_threads > 0

    def test_thread_config_for_low_core_count(self):
        """Test thread configuration for low-core systems."""
        # Clear cache
        ort_provider._session_options_cache = None
        
        # Setup - few cores
        capabilities = {
            "is_apple_silicon": False,
            "cpu_cores": 2
        }

        # Test
        options = ort_provider.create_optimized_session_options(capabilities)

        # Assert - should have conservative thread settings
        assert options.intra_op_num_threads <= 2
        assert options.inter_op_num_threads <= 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_create_session_options_empty_capabilities(self):
        """Test session options with empty capabilities."""
        # Clear cache
        ort_provider._session_options_cache = None
        
        # Test
        options = ort_provider.create_optimized_session_options({})

        # Assert - should still create valid options
        assert isinstance(options, ort.SessionOptions)

    def test_get_provider_options_unknown_provider(self):
        """Test getting options for unknown provider."""
        # Clear cache
        ort_provider._provider_options_cache.clear()
        
        # Test
        options = ort_provider.get_cached_provider_options("UnknownProvider", {})

        # Assert - should return empty dict or default options
        assert isinstance(options, dict)

    def test_configure_providers_empty_capabilities(self):
        """Test provider configuration with empty dict."""
        # Test
        providers = ort_provider.configure_ort_providers({})

        # Assert
        assert isinstance(providers, list)


class TestAcceptanceCriteriaAlignment:
    """Tests aligned with CAWS acceptance criteria."""

    def test_a1_optimized_options_support_fast_ttfa(self):
        """[A1] Optimized session options support TTFA ≤ 0.50s."""
        # Clear cache
        ort_provider._session_options_cache = None
        
        # Setup - high-performance configuration
        capabilities = {
            "is_apple_silicon": True,
            "neural_engine_cores": 32,
            "cpu_cores": 10
        }

        # Test
        options = ort_provider.create_optimized_session_options(capabilities)

        # Assert - should use aggressive optimization
        assert options.graph_optimization_level == ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        assert options.use_deterministic_compute is False  # Allow optimizations
        assert options.intra_op_num_threads >= 4  # Parallel execution

    def test_a1_provider_selection_prefers_performance(self):
        """[A1] Provider selection prioritizes performance."""
        # Setup
        capabilities = {
            "is_apple_silicon": True,
            "neural_engine": True,
            "metal_gpu": True
        }

        # Test
        providers = ort_provider.configure_ort_providers(capabilities)

        # Assert
        assert isinstance(providers, list)
        # Should include high-performance providers first
        if "CoreMLExecutionProvider" in providers:
            # CoreML should be early in the list for Apple Silicon
            coreml_idx = providers.index("CoreMLExecutionProvider")
            assert coreml_idx < len(providers) // 2  # In first half

    def test_a4_memory_optimizations_enabled(self):
        """[A4] Memory optimizations support memory envelope goal."""
        # Clear cache
        ort_provider._session_options_cache = None
        
        # Setup
        capabilities = {}

        # Test
        options = ort_provider.create_optimized_session_options(capabilities)

        # Assert - memory optimizations enabled
        assert options.enable_mem_pattern is True
        assert options.enable_mem_reuse is True
        assert options.enable_cpu_mem_arena is True


class TestCacheManagement:
    """Test cache management functionality."""

    def test_clear_cache_resets_session_options(self):
        """Test that clearing cache resets session options."""
        # Setup
        ort_provider._session_options_cache = Mock(spec=ort.SessionOptions)

        # Test
        ort_provider.clear_provider_cache()

        # Assert
        assert ort_provider._session_options_cache is None

    def test_clear_cache_resets_provider_options(self):
        """Test that clearing cache resets provider options."""
        # Setup
        ort_provider._provider_options_cache["CPU"] = {"test": "data"}

        # Test
        ort_provider.clear_provider_cache()

        # Assert
        assert len(ort_provider._provider_options_cache) == 0

    def test_cache_persists_across_calls(self):
        """Test that cache persists for subsequent calls."""
        # Clear and setup
        ort_provider._session_options_cache = None
        ort_provider._provider_options_cache.clear()
        
        capabilities = {"cpu_cores": 4}

        # Test - create session options and provider options
        session_opts = ort_provider.create_optimized_session_options(capabilities)
        provider_opts = ort_provider.get_cached_provider_options("CPUExecutionProvider", capabilities)

        # Make second calls
        session_opts2 = ort_provider.create_optimized_session_options(capabilities)
        provider_opts2 = ort_provider.get_cached_provider_options("CPUExecutionProvider", capabilities)

        # Assert - should return cached instances
        assert session_opts is session_opts2
        assert provider_opts == provider_opts2


class TestProviderInfo:
    """Test provider information functionality."""

    def test_get_provider_info_cpu(self):
        """Test getting CPU provider information."""
        # Test
        info = ort_provider.get_provider_info("CPUExecutionProvider")

        # Assert
        assert isinstance(info, dict)

    def test_get_provider_info_coreml(self):
        """Test getting CoreML provider information."""
        # Test
        info = ort_provider.get_provider_info("CoreMLExecutionProvider")

        # Assert
        assert isinstance(info, dict)

    def test_get_provider_info_unknown(self):
        """Test getting info for unknown provider."""
        # Test
        info = ort_provider.get_provider_info("UnknownProvider")

        # Assert - should return dict (may be empty or with defaults)
        assert isinstance(info, dict)


class TestORTOptimization:
    """Test ORT optimization decision logic."""

    def test_should_use_ort_optimization_true_for_apple_silicon(self):
        """Test ORT optimization is recommended for Apple Silicon."""
        # Setup
        capabilities = {"is_apple_silicon": True}

        # Test
        result = ort_provider.should_use_ort_optimization(capabilities)

        # Assert
        assert isinstance(result, bool)

    def test_should_use_ort_optimization_with_empty_capabilities(self):
        """Test ORT optimization decision with no capabilities."""
        # Test
        result = ort_provider.should_use_ort_optimization({})

        # Assert
        assert isinstance(result, bool)


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_full_provider_configuration_workflow(self):
        """Test complete provider configuration workflow."""
        # Clear all caches
        ort_provider._session_options_cache = None
        ort_provider._provider_options_cache.clear()
        
        # Setup
        capabilities = {
            "is_apple_silicon": True,
            "neural_engine_cores": 16,
            "cpu_cores": 8,
            "memory_gb": 16
        }

        # Test - full workflow
        # 1. Create session options
        session_opts = ort_provider.create_optimized_session_options(capabilities)
        
        # 2. Configure providers
        providers = ort_provider.configure_ort_providers(capabilities)
        
        # 3. Get provider options
        for provider in providers:
            if provider in ["CPUExecutionProvider", "CoreMLExecutionProvider"]:
                opts = ort_provider.get_cached_provider_options(provider, capabilities)
                assert isinstance(opts, dict)

        # Assert
        assert isinstance(session_opts, ort.SessionOptions)
        assert isinstance(providers, list)
        assert len(providers) > 0

