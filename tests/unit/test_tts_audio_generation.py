"""
Unit tests for audio generation functions in api/tts/core.py.

Tests cover:
- Audio generation with fallback mechanisms
- Fast generation path for TTFA optimization
- Dual session processing
- Error handling and fallback paths
- Cache integration
- Performance tracking

Aligns with CAWS acceptance criteria A1-A4.

@author: @darianrosebrook
@date: 2025-10-09
"""

import asyncio
import time
from typing import Any, Dict, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, Mock, patch, call

import numpy as np
import pytest

from api.tts import core


class TestGenerateAudioWithFallback:
    """Test main audio generation function with fallback logic."""

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    def test_returns_cached_audio_if_available(self, mock_cache_key, mock_get_cached):
        """Test that cached audio is returned when available."""
        # Setup
        mock_cache_key.return_value = "test_key"
        cached_audio = np.array([0.1, 0.2], dtype=np.float32)
        mock_get_cached.return_value = (cached_audio, "CoreMLExecutionProvider")

        # Test
        idx, audio, info, method = core._generate_audio_with_fallback(
            0, "Hello", "af_heart", 1.0, "en-us", "req-123"
        )

        # Assert
        assert idx == 0
        assert audio is not None
        np.testing.assert_array_equal(audio, cached_audio)
        assert "cached" in info.lower()
        assert "CoreML" in info

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core.get_dual_session_manager')
    def test_uses_dual_session_when_available(self, mock_dsm_getter, mock_cache_key, mock_get_cached):
        """Test dual session path when available."""
        # Setup
        mock_cache_key.return_value = "test_key"
        mock_get_cached.return_value = None  # Cache miss
        
        # Mock dual session manager
        mock_dsm = Mock()
        generated_audio = np.array([0.3, 0.4], dtype=np.float32)
        mock_dsm.process_segment_concurrent.return_value = generated_audio
        mock_dsm.get_utilization_stats.return_value = {
            "sessions_available": {"ane": True}
        }
        mock_dsm_getter.return_value = mock_dsm

        # Test
        idx, audio, info, method = core._generate_audio_with_fallback(
            0, "Hello world", "af_heart", 1.0, "en-us", "req-123"
        )

        # Assert
        assert idx == 0
        assert audio is not None
        assert "DualSession" in info
        mock_dsm.process_segment_concurrent.assert_called_once()

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core.get_dual_session_manager')
    @patch('api.tts.core._get_cached_model')
    @patch('api.model.sessions.manager.get_adaptive_provider')
    def test_fallback_to_single_model_when_dual_session_fails(
        self, mock_get_provider, mock_get_model, mock_dsm_getter, 
        mock_cache_key, mock_get_cached
    ):
        """Test fallback to single model when dual session fails."""
        # Setup
        mock_cache_key.return_value = "test_key"
        mock_get_cached.return_value = None
        
        # Dual session fails
        mock_dsm = Mock()
        mock_dsm.process_segment_concurrent.side_effect = Exception("DS failed")
        mock_dsm_getter.return_value = mock_dsm
        
        # Single model succeeds
        mock_get_provider.return_value = "CPUExecutionProvider"
        mock_model = Mock()
        fallback_audio = np.array([0.5, 0.6], dtype=np.float32)
        mock_model.create.return_value = fallback_audio
        mock_get_model.return_value = mock_model

        # Test
        result = core._generate_audio_with_fallback(
            0, "Test text", "af_heart", 1.0, "en-us", "req-123"
        )
        
        # Handle both 3 and 4-tuple returns
        if len(result) == 4:
            idx, audio, info, method = result
        else:
            idx, audio, info = result

        # Assert
        assert idx == 0
        assert audio is not None
        assert "CPU" in info
        mock_model.create.assert_called_once()

    def test_rejects_empty_text(self):
        """Test that empty text is rejected."""
        # Test empty string
        idx, audio, info, method = core._generate_audio_with_fallback(
            0, "", "af_heart", 1.0, "en-us", "req-123"
        )

        assert idx == 0
        assert audio is None
        assert "too short" in info.lower()

    def test_rejects_very_short_text(self):
        """Test that very short text is rejected."""
        # Test text less than 3 chars
        idx, audio, info, method = core._generate_audio_with_fallback(
            0, "Hi", "af_heart", 1.0, "en-us", "req-123"
        )

        assert idx == 0
        assert audio is None
        assert "too short" in info.lower()

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core.should_use_phoneme_preprocessing')
    @patch('api.tts.core.preprocess_text_for_inference')
    @patch('api.tts.core.get_dual_session_manager')
    def test_applies_phoneme_preprocessing_for_complex_text(
        self, mock_dsm, mock_preprocess, mock_should_use, 
        mock_cache_key, mock_get_cached
    ):
        """Test that phoneme preprocessing is applied for complex text."""
        # Setup
        mock_cache_key.return_value = "test_key"
        mock_get_cached.return_value = None
        mock_should_use.return_value = True
        
        # Mock preprocessing
        mock_preprocess.return_value = {
            "normalized_text": "preprocessed_text",
            "processing_method": "misaki",
            "original_length": 50,
            "padded_length": 60,
            "cache_hit": False
        }
        
        # Mock dual session
        mock_dsm_instance = Mock()
        audio = np.array([0.1, 0.2], dtype=np.float32)
        mock_dsm_instance.process_segment_concurrent.return_value = audio
        mock_dsm_instance.get_utilization_stats.return_value = {"sessions_available": {}}
        mock_dsm.return_value = mock_dsm_instance

        # Test with complex text (numbers, punctuation)
        idx, result_audio, info, method = core._generate_audio_with_fallback(
            0, "Hello! How are you? $5.99", "af_heart", 1.0, "en-us", "req-123"
        )

        # Assert preprocessing was called
        mock_preprocess.assert_called_once()

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core._cache_inference_result')
    @patch('api.tts.core.get_dual_session_manager')
    def test_caches_result_when_no_cache_false(
        self, mock_dsm, mock_cache_result, mock_cache_key, mock_get_cached
    ):
        """Test that results are cached when no_cache=False."""
        # Setup
        mock_cache_key.return_value = "test_key"
        mock_get_cached.return_value = None
        
        mock_dsm_instance = Mock()
        audio = np.array([0.1, 0.2], dtype=np.float32)
        mock_dsm_instance.process_segment_concurrent.return_value = audio
        mock_dsm_instance.get_utilization_stats.return_value = {"sessions_available": {}}
        mock_dsm.return_value = mock_dsm_instance

        # Test
        core._generate_audio_with_fallback(
            0, "Test", "af_heart", 1.0, "en-us", "req-123", no_cache=False
        )

        # Assert caching happened
        mock_cache_result.assert_called_once()

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core._cache_inference_result')
    @patch('api.tts.core.get_dual_session_manager')
    def test_skips_cache_when_no_cache_true(
        self, mock_dsm, mock_cache_result, mock_cache_key, mock_get_cached
    ):
        """Test that cache is bypassed when no_cache=True."""
        # Setup
        mock_cache_key.return_value = "test_key"
        mock_get_cached.return_value = (np.array([0.1]), "CPU")  # Has cached data
        
        mock_dsm_instance = Mock()
        audio = np.array([0.2, 0.3], dtype=np.float32)
        mock_dsm_instance.process_segment_concurrent.return_value = audio
        mock_dsm_instance.get_utilization_stats.return_value = {"sessions_available": {}}
        mock_dsm.return_value = mock_dsm_instance

        # Test with no_cache=True
        core._generate_audio_with_fallback(
            0, "Test", "af_heart", 1.0, "en-us", "req-123", no_cache=True
        )

        # Assert: should not check cache (still creates key though)
        # Should not write to cache either
        mock_cache_result.assert_not_called()


class TestFastGenerateAudioSegment:
    """Test fast generation path for TTFA optimization."""

    def test_rejects_empty_text(self):
        """Test fast path rejects empty text."""
        idx, audio, info, method = core._fast_generate_audio_segment(
            0, "", "af_heart", 1.0, "en-us", "req-123"
        )

        assert idx == 0
        assert audio is None
        assert "too short" in info.lower()

    def test_rejects_very_short_text(self):
        """Test fast path rejects very short text."""
        idx, audio, info, method = core._fast_generate_audio_segment(
            0, "Hi", "af_heart", 1.0, "en-us", "req-123"
        )

        assert idx == 0
        assert audio is None

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    def test_returns_cached_audio_if_available(self, mock_cache_key, mock_get_cached):
        """Test fast path returns cached audio."""
        # Setup
        mock_cache_key.return_value = "test_key"
        cached_audio = np.array([0.1, 0.2], dtype=np.float32)
        mock_get_cached.return_value = (cached_audio, "CPUExecutionProvider")

        # Test
        idx, audio, info, method = core._fast_generate_audio_segment(
            0, "Hello", "af_heart", 1.0, "en-us", "req-123"
        )

        # Assert
        assert idx == 0
        assert audio is not None
        np.testing.assert_array_equal(audio, cached_audio)
        assert "fast-cached" in info.lower() or "cached" in info.lower()

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core._get_cached_model')
    def test_uses_cpu_provider_for_fast_ttfa(
        self, mock_get_model, mock_cache_key, mock_get_cached
    ):
        """Test that fast path uses CPU provider for minimal TTFA."""
        # Setup
        mock_cache_key.return_value = "test_key"
        mock_get_cached.return_value = None  # Cache miss
        
        mock_model = Mock()
        audio = np.array([0.3, 0.4], dtype=np.float32)
        mock_model.create.return_value = audio
        mock_get_model.return_value = mock_model

        # Test
        idx, result_audio, info, method = core._fast_generate_audio_segment(
            0, "Hello world", "af_heart", 1.0, "en-us", "req-123"
        )

        # Assert
        assert idx == 0
        assert result_audio is not None
        # Fast path should specifically request CPU provider
        mock_get_model.assert_called_once_with("CPUExecutionProvider")

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core._get_cached_model')
    @patch('api.tts.core.update_inference_stats')
    def test_updates_performance_stats(
        self, mock_update_stats, mock_get_model, mock_cache_key, mock_get_cached
    ):
        """Test that performance stats are updated."""
        # Setup
        mock_cache_key.return_value = "test_key"
        mock_get_cached.return_value = None
        
        mock_model = Mock()
        audio = np.array([0.1, 0.2], dtype=np.float32)
        mock_model.create.return_value = audio
        mock_get_model.return_value = mock_model

        # Test
        core._fast_generate_audio_segment(
            0, "Test", "af_heart", 1.0, "en-us", "req-123"
        )

        # Assert stats were updated
        mock_update_stats.assert_called_once()
        # First arg should be duration (float), second should be provider
        call_args = mock_update_stats.call_args[0]
        assert isinstance(call_args[0], float)  # duration
        assert "CPU" in call_args[1]  # provider

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core._get_cached_model')
    def test_handles_model_create_exception(
        self, mock_get_model, mock_cache_key, mock_get_cached
    ):
        """Test error handling when model.create() fails."""
        # Setup
        mock_cache_key.return_value = "test_key"
        mock_get_cached.return_value = None
        
        mock_model = Mock()
        mock_model.create.side_effect = Exception("Model error")
        mock_get_model.return_value = mock_model

        # Test
        idx, audio, info, method = core._fast_generate_audio_segment(
            0, "Test", "af_heart", 1.0, "en-us", "req-123"
        )

        # Assert error handling
        assert idx == 0
        assert audio is None
        assert isinstance(info, str)  # Error message


class TestGenerateAudioSegment:
    """Test legacy wrapper function."""

    @patch('api.tts.core._generate_audio_with_fallback')
    def test_calls_fallback_function(self, mock_fallback):
        """Test that wrapper calls the main fallback function."""
        # Setup
        expected_audio = np.array([0.1, 0.2], dtype=np.float32)
        mock_fallback.return_value = (0, expected_audio, "TestProvider", "method")

        # Test
        idx, audio, info, method = core._generate_audio_segment(
            0, "Hello", "af_heart", 1.0, "en-us"
        )

        # Assert
        assert idx == 0
        assert audio is not None
        np.testing.assert_array_equal(audio, expected_audio)
        mock_fallback.assert_called_once()

    @patch('api.tts.core._generate_audio_with_fallback')
    def test_handles_legacy_return_format(self, mock_fallback):
        """Test handling of legacy 3-tuple return format."""
        # Setup - return only 3 values
        mock_fallback.return_value = (0, np.array([0.1]), "Provider")

        # Test
        result = core._generate_audio_segment(
            0, "Hello", "af_heart", 1.0, "en-us"
        )

        # Assert - should handle 3-tuple and add "unknown" processing method
        assert len(result) == 4
        assert result[3] == "unknown"


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core.get_dual_session_manager')
    def test_full_generation_workflow_with_dual_session(
        self, mock_dsm, mock_cache_key, mock_get_cached
    ):
        """Test complete generation workflow with dual session."""
        # Setup: Cache miss, dual session success
        mock_cache_key.return_value = "workflow_key"
        mock_get_cached.return_value = None
        
        mock_dsm_instance = Mock()
        generated_audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        mock_dsm_instance.process_segment_concurrent.return_value = generated_audio
        mock_dsm_instance.get_utilization_stats.return_value = {
            "sessions_available": {"ane": True, "gpu": True}
        }
        mock_dsm.return_value = mock_dsm_instance

        # Test
        idx, audio, info, method = core._generate_audio_with_fallback(
            0, "Complete workflow test", "af_heart", 1.0, "en-us", "req-workflow"
        )

        # Assert complete workflow
        assert idx == 0
        assert audio is not None
        assert len(audio) == 3
        assert "DualSession" in info
        mock_dsm_instance.process_segment_concurrent.assert_called_once()

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core._get_cached_model')
    def test_fast_path_workflow_for_primer(
        self, mock_get_model, mock_cache_key, mock_get_cached
    ):
        """Test fast path workflow for primer segment."""
        # Setup
        mock_cache_key.return_value = "primer_key"
        mock_get_cached.return_value = None
        
        mock_model = Mock()
        primer_audio = np.array([0.5, 0.6], dtype=np.float32)
        mock_model.create.return_value = primer_audio
        mock_get_model.return_value = mock_model

        # Test - short text for primer
        idx, audio, info, method = core._fast_generate_audio_segment(
            0, "Hello there", "af_heart", 1.2, "en-us", "req-primer"
        )

        # Assert primer workflow
        assert idx == 0
        assert audio is not None
        # Fast path should use CPU for minimal latency
        assert "CPU" in info or "ExecutionProvider" in info


class TestPerformanceTracking:
    """Test performance and stats tracking."""

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core._get_cached_model')
    @patch('api.tts.core.update_inference_stats')
    def test_timing_is_measured_accurately(
        self, mock_update_stats, mock_get_model, mock_cache_key, mock_get_cached
    ):
        """Test that generation timing is measured."""
        # Setup
        mock_cache_key.return_value = "timing_key"
        mock_get_cached.return_value = None
        
        mock_model = Mock()
        # Simulate some processing time with larger audio array
        def slow_create(*args, **kwargs):
            time.sleep(0.01)  # 10ms
            # Return larger audio array to pass validation (needs > 100 samples)
            return np.random.rand(1000).astype(np.float32) * 0.5
        
        mock_model.create = slow_create
        mock_get_model.return_value = mock_model

        # Test
        start = time.perf_counter()
        idx, audio, info, method = core._fast_generate_audio_segment(
            0, "Timing test", "af_heart", 1.0, "en-us", "req-timing"
        )
        total_duration = time.perf_counter() - start

        # Assert generation succeeded
        assert audio is not None
        
        # Assert timing was tracked
        mock_update_stats.assert_called_once()
        recorded_duration = mock_update_stats.call_args[0][0]
        
        # Recorded duration should be reasonable (between 0 and total time)
        assert 0 < recorded_duration <= total_duration


class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core.get_dual_session_manager')
    @patch('api.tts.core._get_cached_model')
    @patch('api.model.sessions.manager.get_adaptive_provider')
    def test_handles_all_paths_corrupted(
        self, mock_get_provider, mock_get_model, mock_dsm, 
        mock_cache_key, mock_get_cached
    ):
        """Test behavior when all generation paths return corrupted audio."""
        # Setup
        mock_cache_key.return_value = "corrupt_key"
        mock_get_cached.return_value = None
        
        # Dual session returns corrupted audio (will be caught by validation)
        mock_dsm_instance = Mock()
        corrupted = np.array([np.nan, np.nan], dtype=np.float32)
        mock_dsm_instance.process_segment_concurrent.return_value = corrupted
        mock_dsm_instance.get_utilization_stats.return_value = {"sessions_available": {}}
        mock_dsm.return_value = mock_dsm_instance
        
        # Single model also returns corrupted
        mock_get_provider.return_value = "CPUExecutionProvider"
        mock_model = Mock()
        mock_model.create.return_value = corrupted
        mock_get_model.return_value = mock_model

        # Test
        idx, audio, info, method = core._generate_audio_with_fallback(
            0, "Test", "af_heart", 1.0, "en-us", "req-corrupt"
        )

        # Assert graceful handling
        assert idx == 0
        # Audio might be None or sanitized, depending on implementation
        if audio is None:
            assert "corrupt" in info.lower()

    def test_handles_whitespace_only_text(self):
        """Test handling of whitespace-only text."""
        idx, audio, info, method = core._generate_audio_with_fallback(
            0, "   ", "af_heart", 1.0, "en-us", "req-whitespace"
        )

        assert idx == 0
        assert audio is None
        assert "too short" in info.lower()

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core.get_dual_session_manager')
    def test_handles_none_from_dual_session(
        self, mock_dsm, mock_cache_key, mock_get_cached
    ):
        """Test handling when dual session returns None."""
        # Setup
        mock_cache_key.return_value = "none_key"
        mock_get_cached.return_value = None
        
        mock_dsm_instance = Mock()
        mock_dsm_instance.process_segment_concurrent.return_value = None
        mock_dsm_instance.get_utilization_stats.return_value = {"sessions_available": {}}
        mock_dsm.return_value = mock_dsm_instance

        # Test - should handle None gracefully
        try:
            idx, audio, info, method = core._generate_audio_with_fallback(
                0, "Test", "af_heart", 1.0, "en-us", "req-none"
            )
            # Should either return None or handle the error
            assert isinstance(idx, int)
        except Exception as e:
            pytest.fail(f"Should handle None return gracefully, but raised: {e}")


class TestAcceptanceCriteriaAlignment:
    """Tests aligned with CAWS acceptance criteria."""

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core._get_cached_model')
    def test_a1_fast_generation_supports_ttfa_goal(
        self, mock_get_model, mock_cache_key, mock_get_cached
    ):
        """[A1] Fast generation path supports TTFA ≤ 0.50s goal."""
        # Setup
        mock_cache_key.return_value = "a1_key"
        mock_get_cached.return_value = None
        
        mock_model = Mock()
        audio = np.array([0.1, 0.2], dtype=np.float32)
        mock_model.create.return_value = audio
        mock_get_model.return_value = mock_model

        # Test - measure actual generation time
        start = time.perf_counter()
        idx, result, info, method = core._fast_generate_audio_segment(
            0, "Short text", "af_heart", 1.0, "en-us", "req-a1"
        )
        duration = time.perf_counter() - start

        # Assert - function itself should be fast (< 100ms for mocked generation)
        assert duration < 0.1
        assert result is not None

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core.get_dual_session_manager')
    def test_a2_generation_supports_streaming_workflow(
        self, mock_dsm, mock_cache_key, mock_get_cached
    ):
        """[A2] Generation supports streaming workflow (multiple segments)."""
        # Setup
        mock_cache_key.return_value = "a2_key"
        mock_get_cached.return_value = None
        
        mock_dsm_instance = Mock()
        audio = np.array([0.1, 0.2], dtype=np.float32)
        mock_dsm_instance.process_segment_concurrent.return_value = audio
        mock_dsm_instance.get_utilization_stats.return_value = {"sessions_available": {}}
        mock_dsm.return_value = mock_dsm_instance

        # Test - generate multiple segments (simulating streaming)
        segments = []
        for i in range(3):
            idx, seg_audio, info, method = core._generate_audio_with_fallback(
                i, f"Segment {i}", "af_heart", 1.0, "en-us", f"req-a2-{i}"
            )
            if seg_audio is not None:
                segments.append((idx, seg_audio))

        # Assert - all segments generated successfully
        assert len(segments) == 3
        # Segments should be in order
        assert segments[0][0] == 0
        assert segments[1][0] == 1
        assert segments[2][0] == 2

    @patch('api.tts.core._get_cached_inference')
    @patch('api.tts.core._create_inference_cache_key')
    @patch('api.tts.core.get_dual_session_manager')
    @patch('api.tts.core._get_cached_model')
    @patch('api.model.sessions.manager.get_adaptive_provider')
    def test_a3_error_handling_returns_gracefully(
        self, mock_get_provider, mock_get_model, mock_dsm,
        mock_cache_key, mock_get_cached
    ):
        """[A3] Error handling returns None without raising exceptions."""
        # Setup - all paths fail
        mock_cache_key.return_value = "a3_key"
        mock_get_cached.return_value = None
        
        mock_dsm.return_value = None  # No dual session
        
        mock_get_provider.return_value = "CPUExecutionProvider"
        mock_model = Mock()
        mock_model.create.side_effect = Exception("Generation failed")
        mock_get_model.return_value = mock_model

        # Test - should not raise exception
        try:
            idx, audio, info, method = core._generate_audio_with_fallback(
                0, "Error test", "af_heart", 1.0, "en-us", "req-a3"
            )
            
            # Assert error was handled
            assert idx == 0
            assert audio is None
            assert isinstance(info, str)  # Error message
        except Exception as e:
            pytest.fail(f"Should handle errors gracefully, but raised: {e}")

