"""
Unit tests for dependencies.py - Dependency injection and caching.

Tests the dependency injection functions, caching mechanisms, and validation.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from api.core.dependencies import (
    get_tts_config,
    get_model_capabilities,
    get_cached_model_status,
    get_performance_tracker,
    async_lru_cache,
    get_async_model_status,
    get_async_performance_stats,
    clear_dependency_caches,
    validate_dependencies
)


class TestDependencyCaching:
    """Test dependency caching functionality."""
    
    def test_get_tts_config_caching(self):
        """Test that get_tts_config returns cached instances."""
        # Clear cache first
        get_tts_config.cache_clear()
        
        # First call should create new instance
        config1 = get_tts_config()
        assert config1 is not None
        
        # Second call should return cached instance
        config2 = get_tts_config()
        assert config1 is config2  # Same instance
    
    def test_get_model_capabilities_caching(self):
        """Test that get_model_capabilities returns cached instances."""
        # Clear cache first
        get_model_capabilities.cache_clear()
        
        with patch('api.model.loader.detect_apple_silicon_capabilities') as mock_detect:
            mock_detect.return_value = {"has_neural_engine": True}
            
            # First call should create new instance
            caps1 = get_model_capabilities()
            assert caps1 == {"has_neural_engine": True}
            
            # Second call should return cached instance
            caps2 = get_model_capabilities()
            assert caps1 is caps2  # Same instance
            
            # Function should only be called once
            assert mock_detect.call_count == 1
    
    def test_get_cached_model_status_caching(self):
        """Test that get_cached_model_status returns cached instances."""
        # Clear cache first
        get_cached_model_status.cache_clear()
        
        with patch('api.model.loader.get_model_status') as mock_status:
            mock_status.return_value = {"status": "ready"}
            
            # First call should create new instance
            status1 = get_cached_model_status()
            assert status1 == {"status": "ready"}
            
            # Second call should return cached instance
            status2 = get_cached_model_status()
            assert status1 is status2  # Same instance
            
            # Function should only be called once
            assert mock_status.call_count == 1
    
    def test_get_performance_tracker_caching(self):
        """Test that get_performance_tracker returns cached instances."""
        # Clear cache first
        get_performance_tracker.cache_clear()
        
        with patch('api.performance.stats.get_performance_stats') as mock_stats:
            mock_stats.return_value = {"requests": 100}
            
            # First call should create new instance
            tracker1 = get_performance_tracker()
            assert tracker1 is not None
            
            # Second call should return cached instance
            tracker2 = get_performance_tracker()
            assert tracker1 is tracker2  # Same instance
            
            # Function should only be called once
            assert mock_stats.call_count == 1


class TestAsyncLRUCache:
    """Test async LRU cache functionality."""
    
    def test_async_lru_cache_decorator(self):
        """Test that async_lru_cache decorator works correctly."""
        call_count = 0
        
        @async_lru_cache(maxsize=2)
        async def test_func(arg):
            nonlocal call_count
            call_count += 1
            return f"result_{arg}"
        
        async def run_test():
            # First call should execute function
            result1 = await test_func("test")
            assert result1 == "result_test"
            assert call_count == 1
            
            # Second call with same arg should return cached result
            result2 = await test_func("test")
            assert result2 == "result_test"
            assert call_count == 1  # Should not increment
            
            # Call with different arg should execute function
            result3 = await test_func("test2")
            assert result3 == "result_test2"
            assert call_count == 2
            
            return True
        
        # Run the async test
        assert asyncio.run(run_test())
    
    def test_async_lru_cache_size_limit(self):
        """Test that async_lru_cache respects size limits."""
        call_count = 0
        
        @async_lru_cache(maxsize=2)
        async def test_func(arg):
            nonlocal call_count
            call_count += 1
            return f"result_{arg}"
        
        async def run_test():
            # Fill cache to maxsize
            await test_func("arg1")
            await test_func("arg2")
            assert call_count == 2
            
            # Add third item, should evict first
            await test_func("arg3")
            assert call_count == 3
            
            # Call arg1 again, should execute function (was evicted)
            await test_func("arg1")
            assert call_count == 4
            
            return True
        
        # Run the async test
        assert asyncio.run(run_test())


class TestAsyncDependencies:
    """Test async dependency functions."""
    
    @pytest.mark.asyncio
    async def test_get_async_model_status(self):
        """Test async model status dependency."""
        with patch('api.model.loader.get_model_status') as mock_status:
            mock_status.return_value = {"status": "ready"}
            
            # First call should execute function
            status1 = await get_async_model_status()
            assert status1 == {"status": "ready"}
            
            # Second call should return cached result
            status2 = await get_async_model_status()
            assert status1 is status2  # Same instance
            
            # Function should only be called once
            assert mock_status.call_count == 1
    
    @pytest.mark.asyncio
    async def test_get_async_performance_stats(self):
        """Test async performance stats dependency."""
        with patch('api.performance.stats.get_performance_stats') as mock_stats:
            mock_stats.return_value = {"requests": 100}
            
            # First call should execute function
            stats1 = await get_async_performance_stats()
            assert stats1 == {"requests": 100}
            
            # Second call should return cached result
            stats2 = await get_async_performance_stats()
            assert stats1 is stats2  # Same instance
            
            # Function should only be called once
            assert mock_stats.call_count == 1


class TestCacheManagement:
    """Test cache management functions."""
    
    def test_clear_dependency_caches(self):
        """Test that clear_dependency_caches clears all caches."""
        # Populate caches first
        with patch('api.model.loader.detect_apple_silicon_capabilities') as mock_detect:
            mock_detect.return_value = {"test": True}
            get_model_capabilities()
        
        with patch('api.model.loader.get_model_status') as mock_status:
            mock_status.return_value = {"test": True}
            get_cached_model_status()
        
        # Verify caches are populated
        assert get_model_capabilities.cache_info().currsize > 0
        assert get_cached_model_status.cache_info().currsize > 0
        
        # Clear caches
        clear_dependency_caches()
        
        # Verify caches are cleared
        assert get_tts_config.cache_info().currsize == 0
        assert get_model_capabilities.cache_info().currsize == 0
        assert get_cached_model_status.cache_info().currsize == 0
        assert get_performance_tracker.cache_info().currsize == 0


class TestDependencyValidation:
    """Test dependency validation functions."""
    
    def test_validate_dependencies_success(self):
        """Test successful dependency validation."""
        with patch('api.core.dependencies.get_tts_config') as mock_config, \
             patch('api.core.dependencies.get_model_capabilities') as mock_caps:
            
            # Mock config with required attributes
            mock_config_instance = Mock()
            mock_config_instance.MODEL_PATH = "/path/to/model"
            mock_config.return_value = mock_config_instance
            
            # Mock capabilities as dict
            mock_caps.return_value = {"has_neural_engine": True}
            
            # Should not raise exception
            validate_dependencies()
    
    def test_validate_dependencies_missing_model_path(self):
        """Test dependency validation with missing MODEL_PATH."""
        with patch('api.core.dependencies.get_tts_config') as mock_config, \
             patch('api.core.dependencies.get_model_capabilities') as mock_caps:
            
            # Mock config without MODEL_PATH
            mock_config_instance = Mock()
            del mock_config_instance.MODEL_PATH
            mock_config.return_value = mock_config_instance
            
            # Mock capabilities as dict
            mock_caps.return_value = {"has_neural_engine": True}
            
            # Should raise ValueError
            with pytest.raises(ValueError, match="TTSConfig missing MODEL_PATH"):
                validate_dependencies()
    
    def test_validate_dependencies_invalid_capabilities(self):
        """Test dependency validation with invalid capabilities."""
        with patch('api.core.dependencies.get_tts_config') as mock_config, \
             patch('api.core.dependencies.get_model_capabilities') as mock_caps:
            
            # Mock config with required attributes
            mock_config_instance = Mock()
            mock_config_instance.MODEL_PATH = "/path/to/model"
            mock_config.return_value = mock_config_instance
            
            # Mock capabilities as non-dict
            mock_caps.return_value = "invalid"
            
            # Should raise ValueError
            with pytest.raises(ValueError, match="Hardware capabilities should be dict"):
                validate_dependencies()
    
    def test_validate_dependencies_import_error(self):
        """Test dependency validation with import error."""
        with patch('api.core.dependencies.get_tts_config') as mock_config:
            # Mock config to raise exception
            mock_config.side_effect = ImportError("Module not found")
            
            # Should raise the original exception
            with pytest.raises(ImportError, match="Module not found"):
                validate_dependencies()


class TestDependencyIntegration:
    """Test dependency integration scenarios."""
    
    def test_dependency_chain(self):
        """Test that dependencies can be chained together."""
        with patch('api.model.loader.detect_apple_silicon_capabilities') as mock_detect, \
             patch('api.model.loader.get_model_status') as mock_status, \
             patch('api.performance.stats.get_performance_stats') as mock_stats:
            
            # Setup mocks
            mock_detect.return_value = {"has_neural_engine": True}
            mock_status.return_value = {"status": "ready"}
            mock_stats.return_value = {"requests": 100}
            
            # Get all dependencies
            config = get_tts_config()
            capabilities = get_model_capabilities()
            status = get_cached_model_status()
            tracker = get_performance_tracker()
            
            # Verify all dependencies are available
            assert config is not None
            assert capabilities == {"has_neural_engine": True}
            assert status == {"status": "ready"}
            assert tracker is not None
    
    def test_cache_isolation(self):
        """Test that different dependency caches are isolated."""
        # Clear all caches
        clear_dependency_caches()
        
        with patch('api.model.loader.detect_apple_silicon_capabilities') as mock_detect, \
             patch('api.model.loader.get_model_status') as mock_status:
            
            # Setup mocks
            mock_detect.return_value = {"test": "capabilities"}
            mock_status.return_value = {"test": "status"}
            
            # Get dependencies
            capabilities = get_model_capabilities()
            status = get_cached_model_status()
            
            # Verify they return different values
            assert capabilities != status
            assert capabilities == {"test": "capabilities"}
            assert status == {"test": "status"}
    
    def test_cache_info_tracking(self):
        """Test that cache info is properly tracked."""
        # Clear all caches
        clear_dependency_caches()
        
        # Verify all caches start empty
        assert get_tts_config.cache_info().currsize == 0
        assert get_model_capabilities.cache_info().currsize == 0
        assert get_cached_model_status.cache_info().currsize == 0
        assert get_performance_tracker.cache_info().currsize == 0
        
        with patch('api.model.loader.detect_apple_silicon_capabilities') as mock_detect:
            mock_detect.return_value = {"test": True}
            
            # Use a dependency
            get_model_capabilities()
            
            # Verify cache info is updated
            assert get_model_capabilities.cache_info().currsize == 1
            assert get_model_capabilities.cache_info().hits == 0
            assert get_model_capabilities.cache_info().misses == 1
            
            # Use it again
            get_model_capabilities()
            
            # Verify cache hit
            assert get_model_capabilities.cache_info().currsize == 1
            assert get_model_capabilities.cache_info().hits == 1
            assert get_model_capabilities.cache_info().misses == 1
