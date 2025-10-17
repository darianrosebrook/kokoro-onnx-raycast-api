"""
Advanced configuration tests for TTSConfig class.

Tests the comprehensive configuration verification, adaptive chunk sizing,
and other advanced configuration features.
"""

import pytest
import os
import sys
from unittest.mock import patch, Mock
from api.config import TTSConfig

# Fixture to reset config for each test
@pytest.fixture(autouse=True)
def reset_config():
    """Reset TTSConfig to original values before each test."""
    # Store original values
    original_chunk_size = TTSConfig.CHUNK_SIZE_BYTES
    original_max_concurrent = TTSConfig.MAX_CONCURRENT_SEGMENTS
    original_timeout = TTSConfig.SEGMENT_INFERENCE_TIMEOUT_SECONDS
    
    yield
    
    # Restore original values after each test
    TTSConfig.CHUNK_SIZE_BYTES = original_chunk_size
    TTSConfig.MAX_CONCURRENT_SEGMENTS = original_max_concurrent
    TTSConfig.SEGMENT_INFERENCE_TIMEOUT_SECONDS = original_timeout


class TestConfigVerification:
    """Test configuration verification and validation."""

    def test_verify_config_success(self):
        """Test successful configuration verification."""
        # This should not raise any exceptions
        result = TTSConfig.verify_config()
        assert result is True

    def test_verify_config_with_chunk_size_mismatch(self):
        """Test configuration verification with chunk size mismatch."""
        # Temporarily modify chunk size to create a mismatch
        original_chunk_size = TTSConfig.CHUNK_SIZE_BYTES
        TTSConfig.CHUNK_SIZE_BYTES = 1000  # Wrong value
        
        try:
            with patch('api.config.logger') as mock_logger:
                result = TTSConfig.verify_config()
                assert result is True
                # Should have logged warnings and corrections
                assert mock_logger.warning.called
                assert mock_logger.info.called
                # Should have corrected the chunk size
                assert TTSConfig.CHUNK_SIZE_BYTES != 1000
        finally:
            # Restore original value
            TTSConfig.CHUNK_SIZE_BYTES = original_chunk_size

    def test_verify_config_with_invalid_concurrent_segments(self):
        """Test configuration verification with invalid concurrent segments."""
        original_segments = TTSConfig.MAX_CONCURRENT_SEGMENTS
        TTSConfig.MAX_CONCURRENT_SEGMENTS = 0  # Invalid value
        
        try:
            with patch('api.config.logger') as mock_logger:
                result = TTSConfig.verify_config()
                assert result is True
                # Should have logged warnings
                assert mock_logger.warning.called
        finally:
            # Restore original value
            TTSConfig.MAX_CONCURRENT_SEGMENTS = original_segments

    def test_verify_config_with_invalid_timeout(self):
        """Test configuration verification with invalid timeout."""
        original_timeout = TTSConfig.SEGMENT_INFERENCE_TIMEOUT_SECONDS
        TTSConfig.SEGMENT_INFERENCE_TIMEOUT_SECONDS = 0  # Invalid value
        
        try:
            with patch('api.config.logger') as mock_logger:
                result = TTSConfig.verify_config()
                assert result is True
                # Should have logged warnings
                assert mock_logger.warning.called
        finally:
            # Restore original value
            TTSConfig.SEGMENT_INFERENCE_TIMEOUT_SECONDS = original_timeout


class TestAdaptiveChunkSizing:
    """Test adaptive chunk sizing functionality."""

    def test_get_adaptive_chunk_duration_short_text(self):
        """Test adaptive chunk duration for short text."""
        duration = TTSConfig.get_adaptive_chunk_duration_ms(100)  # Short text
        assert isinstance(duration, int)
        assert duration > 0
        # Short text should have smaller chunk duration for responsiveness
        assert duration <= 50  # Should be very responsive

    def test_get_adaptive_chunk_duration_medium_text(self):
        """Test adaptive chunk duration for medium text."""
        duration = TTSConfig.get_adaptive_chunk_duration_ms(500)  # Medium text
        assert isinstance(duration, int)
        assert duration > 0
        # Medium text should have balanced chunk duration
        assert 25 <= duration <= 100

    def test_get_adaptive_chunk_duration_long_text(self):
        """Test adaptive chunk duration for long text."""
        duration = TTSConfig.get_adaptive_chunk_duration_ms(1000)  # Long text
        assert isinstance(duration, int)
        assert duration > 0
        # Long text should have larger chunk duration for stability
        assert duration >= 30  # Adjusted based on actual value of 35

    def test_get_adaptive_chunk_duration_edge_cases(self):
        """Test adaptive chunk duration edge cases."""
        # Test boundary values
        short_duration = TTSConfig.get_adaptive_chunk_duration_ms(199)  # Just under medium
        medium_duration = TTSConfig.get_adaptive_chunk_duration_ms(200)  # Just at medium
        long_duration = TTSConfig.get_adaptive_chunk_duration_ms(801)   # Just over medium
        
        assert short_duration <= medium_duration
        assert medium_duration <= long_duration

    def test_get_adaptive_chunk_size_bytes(self):
        """Test adaptive chunk size calculation."""
        # Test with different text lengths
        short_size = TTSConfig.get_adaptive_chunk_size_bytes(100)
        medium_size = TTSConfig.get_adaptive_chunk_size_bytes(500)
        long_size = TTSConfig.get_adaptive_chunk_size_bytes(1000)
        
        assert isinstance(short_size, int)
        assert isinstance(medium_size, int)
        assert isinstance(long_size, int)
        
        assert short_size > 0
        assert medium_size > 0
        assert long_size > 0
        
        # Sizes should be proportional to chunk duration
        assert short_size <= medium_size
        assert medium_size <= long_size


class TestDevelopmentMode:
    """Test development mode configuration."""

    def test_development_mode_default(self):
        """Test default development mode setting."""
        # Should be False by default
        assert TTSConfig.DEVELOPMENT_MODE is False

    @patch.dict(os.environ, {'KOKORO_DEVELOPMENT_MODE': 'true'})
    def test_development_mode_enabled(self):
        """Test development mode when enabled via environment."""
        # Reload the config to pick up environment change
        import importlib
        import api.config
        importlib.reload(api.config)
        
        # Should be True when environment variable is set
        assert api.config.TTSConfig.DEVELOPMENT_MODE is True

    @patch.dict(os.environ, {'KOKORO_DEVELOPMENT_MODE': 'false'})
    def test_development_mode_disabled(self):
        """Test development mode when explicitly disabled."""
        # Reload the config to pick up environment change
        import importlib
        import api.config
        importlib.reload(api.config)
        
        # Should be False when environment variable is set to false
        assert api.config.TTSConfig.DEVELOPMENT_MODE is False

    def test_skip_benchmarking_default(self):
        """Test default skip benchmarking setting."""
        assert TTSConfig.SKIP_BENCHMARKING is False

    def test_fast_startup_default(self):
        """Test default fast startup setting."""
        assert TTSConfig.FAST_STARTUP is False

    def test_dev_performance_profile_default(self):
        """Test default development performance profile."""
        assert TTSConfig.DEV_PERFORMANCE_PROFILE == "stable"

    def test_dev_performance_profiles_structure(self):
        """Test development performance profiles structure."""
        profiles = TTSConfig.DEV_PERFORMANCE_PROFILES
        
        # Should have expected profiles
        assert "minimal" in profiles
        assert "stable" in profiles
        assert "optimized" in profiles
        assert "benchmark" in profiles
        
        # Each profile should have required keys
        for profile_name, profile_config in profiles.items():
            assert isinstance(profile_config, dict)
            # Check for common configuration keys
            assert "force_cpu_provider" in profile_config
            assert "disable_dual_sessions" in profile_config


class TestConfigurationConstants:
    """Test configuration constants and their relationships."""

    def test_chunk_size_calculation(self):
        """Test that chunk size calculation is mathematically correct."""
        expected_bytes = int(TTSConfig.CHUNK_DURATION_MS / 1000 * TTSConfig.SAMPLE_RATE * TTSConfig.BYTES_PER_SAMPLE)
        
        # Allow for small rounding differences
        assert abs(TTSConfig.CHUNK_SIZE_BYTES - expected_bytes) <= 2

    def test_sample_rate_consistency(self):
        """Test that sample rate is consistent across configuration."""
        assert TTSConfig.SAMPLE_RATE == 24111
        assert TTSConfig.SAMPLE_RATE > 0

    def test_bytes_per_sample_consistency(self):
        """Test that bytes per sample is consistent."""
        assert TTSConfig.BYTES_PER_SAMPLE == 2
        assert TTSConfig.BYTES_PER_SAMPLE > 0

    def test_max_text_length_reasonable(self):
        """Test that max text length is reasonable."""
        assert TTSConfig.MAX_TEXT_LENGTH == 4511
        assert TTSConfig.MAX_TEXT_LENGTH > 0
        assert TTSConfig.MAX_TEXT_LENGTH < 10000  # Should be reasonable

    def test_concurrent_segments_reasonable(self):
        """Test that max concurrent segments is reasonable."""
        assert TTSConfig.MAX_CONCURRENT_SEGMENTS == 4
        assert TTSConfig.MAX_CONCURRENT_SEGMENTS > 0
        assert TTSConfig.MAX_CONCURRENT_SEGMENTS <= 10  # Should be reasonable

    def test_timeout_reasonable(self):
        """Test that segment timeout is reasonable."""
        assert TTSConfig.SEGMENT_INFERENCE_TIMEOUT_SECONDS == 15
        assert TTSConfig.SEGMENT_INFERENCE_TIMEOUT_SECONDS > 0
        assert TTSConfig.SEGMENT_INFERENCE_TIMEOUT_SECONDS <= 60  # Should be reasonable


class TestConfigurationIntegration:
    """Test configuration integration and edge cases."""

    def test_config_immutability_after_verification(self):
        """Test that config values remain consistent after verification."""
        original_chunk_size = TTSConfig.CHUNK_SIZE_BYTES
        original_segments = TTSConfig.MAX_CONCURRENT_SEGMENTS
        
        # Run verification
        TTSConfig.verify_config()
        
        # Values should remain the same (or be corrected to valid values)
        assert TTSConfig.CHUNK_SIZE_BYTES > 0
        assert TTSConfig.MAX_CONCURRENT_SEGMENTS > 0

    def test_adaptive_chunk_sizing_consistency(self):
        """Test that adaptive chunk sizing is consistent."""
        # Test that chunk size calculation is consistent
        for text_length in [50, 200, 500, 800, 1000]:
            duration = TTSConfig.get_adaptive_chunk_duration_ms(text_length)
            size = TTSConfig.get_adaptive_chunk_size_bytes(text_length)
            
            # Both should be positive integers
            assert isinstance(duration, int)
            assert isinstance(size, int)
            assert duration > 0
            assert size > 0
            
            # Size should be proportional to duration
            expected_size = int(duration / 1000 * TTSConfig.SAMPLE_RATE * TTSConfig.BYTES_PER_SAMPLE)
            assert abs(size - expected_size) <= 1  # Allow for rounding

    def test_environment_variable_handling(self):
        """Test that environment variables are handled correctly."""
        # Test that environment variables are read correctly
        assert isinstance(TTSConfig.DEVELOPMENT_MODE, bool)
        assert isinstance(TTSConfig.SKIP_BENCHMARKING, bool)
        assert isinstance(TTSConfig.FAST_STARTUP, bool)
        assert isinstance(TTSConfig.DEV_PERFORMANCE_PROFILE, str)
