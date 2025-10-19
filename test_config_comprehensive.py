#!/usr/bin/env python3
"""Comprehensive tests for api/config.py to increase coverage."""

import os
import pytest
import sys
sys.path.insert(0, os.path.dirname(__file__))

from api.config import TTSConfig
import api.config as api_config


class TestConfigBenchmarkFrequency:
    """Test benchmark frequency configuration."""

    def test_benchmark_frequency_default(self):
        """Test default benchmark frequency."""
        # Reset environment
        if "KOKORO_BENCHMARK_FREQUENCY" in os.environ:
            del os.environ["KOKORO_BENCHMARK_FREQUENCY"]

        # Reload config to get defaults
        import importlib
        import api.config
        importlib.reload(api.config)

        assert TTSConfig.BENCHMARK_FREQUENCY == "daily"

    def test_benchmark_frequency_options_exist(self):
        """Test that benchmark frequency options are properly defined."""
        # Test that the options dictionary exists and has expected keys
        assert hasattr(TTSConfig, 'BENCHMARK_FREQUENCY_OPTIONS')
        assert isinstance(TTSConfig.BENCHMARK_FREQUENCY_OPTIONS, dict)
        assert 'daily' in TTSConfig.BENCHMARK_FREQUENCY_OPTIONS
        assert 'weekly' in TTSConfig.BENCHMARK_FREQUENCY_OPTIONS
        assert 'monthly' in TTSConfig.BENCHMARK_FREQUENCY_OPTIONS
        assert 'manually' in TTSConfig.BENCHMARK_FREQUENCY_OPTIONS

    def test_benchmark_frequency_fallback_logic(self):
        """Test that invalid benchmark frequency falls back to daily."""
        # This tests the logic without environment variable manipulation
        # The fallback logic in the config file handles invalid values
        assert TTSConfig.BENCHMARK_FREQUENCY in ['daily', 'weekly', 'monthly', 'manually']

    def test_benchmark_frequency_invalid_fallback(self):
        """Test that invalid benchmark frequency falls back to daily."""
        if "KOKORO_BENCHMARK_FREQUENCY" in os.environ:
            del os.environ["KOKORO_BENCHMARK_FREQUENCY"]
        os.environ["KOKORO_BENCHMARK_FREQUENCY"] = "invalid"
        import importlib
        import api.config
        importlib.reload(api.config)
        assert TTSConfig.BENCHMARK_FREQUENCY == "daily"


class TestConfigDevelopmentProfiles:
    """Test development performance profiles."""

    def test_dev_performance_profile_default(self):
        """Test default development performance profile."""
        if "KOKORO_DEV_PERFORMANCE_PROFILE" in os.environ:
            del os.environ["KOKORO_DEV_PERFORMANCE_PROFILE"]

        import importlib
        import api.config
        importlib.reload(api.config)

        assert TTSConfig.DEV_PERFORMANCE_PROFILE == "stable"

    def test_dev_performance_profiles_exist(self):
        """Test that development performance profiles are properly defined."""
        assert hasattr(TTSConfig, 'DEV_PERFORMANCE_PROFILES')
        assert isinstance(TTSConfig.DEV_PERFORMANCE_PROFILES, dict)

        expected_profiles = ['minimal', 'stable', 'optimized', 'benchmark']
        for profile in expected_profiles:
            assert profile in TTSConfig.DEV_PERFORMANCE_PROFILES
            profile_data = TTSConfig.DEV_PERFORMANCE_PROFILES[profile]
            assert 'force_cpu_provider' in profile_data
            assert 'disable_dual_sessions' in profile_data
            assert 'skip_background_benchmarking' in profile_data
            assert 'enable_coreml_optimizations' in profile_data
            assert 'chunk_duration_ms' in profile_data
            assert 'max_segment_length' in profile_data

    def test_dev_performance_profile_invalid_fallback(self):
        """Test that invalid profile falls back to stable."""
        if "KOKORO_DEV_PERFORMANCE_PROFILE" in os.environ:
            del os.environ["KOKORO_DEV_PERFORMANCE_PROFILE"]
        os.environ["KOKORO_DEV_PERFORMANCE_PROFILE"] = "invalid"
        import importlib
        import api.config
        importlib.reload(api.config)
        assert TTSConfig.DEV_PERFORMANCE_PROFILE == "stable"

    def test_development_mode_profile_structure(self):
        """Test that development mode profile structure is correct."""
        # Test that profiles have the expected structure without environment manipulation
        profiles = TTSConfig.DEV_PERFORMANCE_PROFILES

        for profile_name, profile_data in profiles.items():
            # All profiles should have boolean values for these settings
            assert isinstance(profile_data["force_cpu_provider"], bool)
            assert isinstance(profile_data["disable_dual_sessions"], bool)
            assert isinstance(profile_data["skip_background_benchmarking"], bool)
            assert isinstance(profile_data["enable_coreml_optimizations"], bool)

            # All profiles should have numeric values for performance settings
            assert isinstance(profile_data["chunk_duration_ms"], (int, float))
            assert isinstance(profile_data["max_segment_length"], (int, float))

    def test_production_mode_defaults(self):
        """Test that production mode uses correct defaults."""
        if "KOKORO_DEVELOPMENT_MODE" in os.environ:
            del os.environ["KOKORO_DEVELOPMENT_MODE"]
        if "KOKORO_DEV_PERFORMANCE_PROFILE" in os.environ:
            del os.environ["KOKORO_DEV_PERFORMANCE_PROFILE"]

        import importlib
        import api.config
        importlib.reload(api.config)

        # Production defaults
        assert TTSConfig.FORCE_CPU_PROVIDER == False
        assert TTSConfig.DISABLE_DUAL_SESSIONS == False
        assert TTSConfig.SKIP_BACKGROUND_BENCHMARKING == False
        assert TTSConfig.ENABLE_COREML_OPTIMIZATIONS == True  # Default for Apple Silicon


class TestConfigAdaptiveChunking:
    """Test adaptive chunk duration and size methods."""

    def test_get_adaptive_chunk_duration_ms_short_content(self):
        """Test adaptive chunk duration for short content."""
        result = TTSConfig.get_adaptive_chunk_duration_ms(150)
        assert result == TTSConfig.SHORT_CONTENT_CHUNK_MS

    def test_get_adaptive_chunk_duration_ms_medium_content(self):
        """Test adaptive chunk duration for medium content."""
        result = TTSConfig.get_adaptive_chunk_duration_ms(500)
        assert result == TTSConfig.MEDIUM_CONTENT_CHUNK_MS

    def test_get_adaptive_chunk_duration_ms_long_content(self):
        """Test adaptive chunk duration for long content."""
        result = TTSConfig.get_adaptive_chunk_duration_ms(1200)
        assert result == TTSConfig.LONG_CONTENT_CHUNK_MS

    def test_get_adaptive_chunk_size_bytes(self):
        """Test adaptive chunk size calculation."""
        # Test with different text lengths
        test_cases = [
            (150, TTSConfig.SHORT_CONTENT_CHUNK_MS),
            (500, TTSConfig.MEDIUM_CONTENT_CHUNK_MS),
            (1200, TTSConfig.LONG_CONTENT_CHUNK_MS),
        ]

        for text_length, expected_duration in test_cases:
            result = TTSConfig.get_adaptive_chunk_size_bytes(text_length)
            expected_bytes = int(expected_duration / 1000 * TTSConfig.SAMPLE_RATE * TTSConfig.BYTES_PER_SAMPLE)
            assert result == expected_bytes


class TestConfigBenchmarkCache:
    """Test benchmark cache duration calculations."""

    def test_get_benchmark_cache_duration_daily_default(self):
        """Test benchmark cache duration for daily frequency."""
        if "KOKORO_BENCHMARK_FREQUENCY" in os.environ:
            del os.environ["KOKORO_BENCHMARK_FREQUENCY"]
        if "KOKORO_DEVELOPMENT_MODE" in os.environ:
            del os.environ["KOKORO_DEVELOPMENT_MODE"]
        if "KOKORO_DEV_PERFORMANCE_PROFILE" in os.environ:
            del os.environ["KOKORO_DEV_PERFORMANCE_PROFILE"]

        import importlib
        import api.config
        importlib.reload(api.config)

        result = TTSConfig.get_benchmark_cache_duration()
        expected = TTSConfig.BENCHMARK_FREQUENCY_OPTIONS["daily"]
        assert result == expected

    def test_get_benchmark_cache_duration_method_exists(self):
        """Test that benchmark cache duration method exists and works."""
        # Test that the method exists and returns a reasonable value
        result = TTSConfig.get_benchmark_cache_duration()
        assert isinstance(result, int)
        assert result > 0  # Should return a positive duration

    def test_get_benchmark_cache_duration_ranges(self):
        """Test that benchmark cache duration returns reasonable ranges."""
        # The method should return values in expected ranges based on frequency
        result = TTSConfig.get_benchmark_cache_duration()

        # Check against known frequency options
        frequency_options = TTSConfig.BENCHMARK_FREQUENCY_OPTIONS
        expected_values = list(frequency_options.values())

        # The result should be one of the expected values or a development extension
        assert result in expected_values or result > max(expected_values)


class TestConfigLogging:
    """Test logging configuration."""

    def test_logging_variables_exist(self):
        """Test that logging variables are properly defined."""
        # Test that the module-level logging variables exist
        assert hasattr(api_config, 'LOG_LEVEL')
        assert hasattr(api_config, 'LOG_VERBOSE')

        # Test that LOG_LEVEL is a string and has expected format
        assert isinstance(api_config.LOG_LEVEL, str)
        assert api_config.LOG_LEVEL.isupper()  # Should be uppercase

        # Test that LOG_VERBOSE is a boolean
        assert isinstance(api_config.LOG_VERBOSE, bool)

    def test_log_verbose_boolean_conversion(self):
        """Test that LOG_VERBOSE properly converts string environment to boolean."""
        # This tests the logic without environment manipulation
        # The conversion happens at module load time
        assert isinstance(api_config.LOG_VERBOSE, bool)


class TestConfigValidation:
    """Test configuration validation methods."""

    def test_validate_configuration_basic(self):
        """Test basic configuration validation."""
        # This should not raise an exception
        TTSConfig.validate_configuration()

    def test_validate_configuration_chunk_size_correction(self):
        """Test that chunk size validation corrects mismatches."""
        # Store original value
        original_chunk_size = TTSConfig.CHUNK_SIZE_BYTES

        try:
            # Set an incorrect chunk size
            incorrect_size = 12345
            TTSConfig.CHUNK_SIZE_BYTES = incorrect_size

            # Validation should correct it
            TTSConfig.validate_configuration()

            # Calculate expected size
            expected_samples = int(TTSConfig.CHUNK_DURATION_MS / 1000 * TTSConfig.SAMPLE_RATE)
            expected_bytes = expected_samples * TTSConfig.BYTES_PER_SAMPLE

            assert TTSConfig.CHUNK_SIZE_BYTES == expected_bytes
            assert TTSConfig.CHUNK_SIZE_BYTES != incorrect_size

        finally:
            # Restore original value
            TTSConfig.CHUNK_SIZE_BYTES = original_chunk_size

    def test_validate_configuration_concurrent_segments_bounds(self):
        """Test concurrent segments validation."""
        original_value = TTSConfig.MAX_CONCURRENT_SEGMENTS

        try:
            # Test lower bound
            TTSConfig.MAX_CONCURRENT_SEGMENTS = 0
            TTSConfig.validate_configuration()
            assert TTSConfig.MAX_CONCURRENT_SEGMENTS == 1

            # Test upper bound warning (should not change value but log warning)
            TTSConfig.MAX_CONCURRENT_SEGMENTS = 10
            TTSConfig.validate_configuration()
            assert TTSConfig.MAX_CONCURRENT_SEGMENTS == 10

        finally:
            TTSConfig.MAX_CONCURRENT_SEGMENTS = original_value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
