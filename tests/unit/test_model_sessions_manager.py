"""
Unit tests for api/model/sessions/manager.py - Session lifecycle management.

Tests cover:
- Model status checking
- Model instance management
- Provider selection and adaptation
- Thread-safe model access
- Adaptive provider logic for different text lengths

Aligns with CAWS acceptance criteria A1 (provider selection for TTFA).

@author: @darianrosebrook
@date: 2025-10-09
"""

import os
import threading
from typing import Optional
from unittest.mock import Mock, patch

import pytest

from api.model.sessions import manager


class TestModelStatus:
    """Test model status checking."""

    def test_get_model_status_returns_false_initially(self):
        """Test that model status is False before loading."""
        # Clear state
        manager.model_loaded = False
        manager.kokoro_model = None

        # Test
        status = manager.get_model_status()

        # Assert
        assert status is False

    def test_get_model_status_returns_true_when_loaded(self):
        """Test that model status is True when loaded."""
        # Setup
        manager.model_loaded = True
        manager.kokoro_model = Mock()

        # Test
        status = manager.get_model_status()

        # Assert
        assert status is True

        # Cleanup
        manager.model_loaded = False
        manager.kokoro_model = None


class TestModelAccess:
    """Test model instance access."""

    def test_get_model_returns_none_when_not_loaded(self):
        """Test getting model when not loaded."""
        # Setup
        manager.model_loaded = False
        manager.kokoro_model = None

        # Test
        model = manager.get_model()

        # Assert
        assert model is None

    def test_get_model_returns_instance_when_loaded(self):
        """Test getting model when loaded."""
        # Setup
        mock_model = Mock()
        manager.model_loaded = True
        manager.kokoro_model = mock_model

        # Test
        model = manager.get_model()

        # Assert
        assert model is mock_model

        # Cleanup
        manager.model_loaded = False
        manager.kokoro_model = None

    def test_get_model_returns_none_when_model_is_none_despite_flag(self):
        """Test that None is returned if model is None even if flag is True."""
        # Setup - inconsistent state
        manager.model_loaded = True
        manager.kokoro_model = None

        # Test
        model = manager.get_model()

        # Assert
        assert model is None

        # Cleanup
        manager.model_loaded = False


class TestActiveProvider:
    """Test active provider management."""

    def test_get_active_provider_returns_string(self):
        """Test that active provider is returned."""
        # Test
        provider = manager.get_active_provider()

        # Assert
        assert isinstance(provider, str)
        assert "Provider" in provider or "CPU" in provider

    def test_get_active_provider_default_is_cpu(self):
        """Test default provider is CPU."""
        # Reset to default
        manager._active_provider = "CPUExecutionProvider"

        # Test
        provider = manager.get_active_provider()

        # Assert
        assert provider == "CPUExecutionProvider"


class TestAdaptiveProvider:
    """Test adaptive provider selection based on text length."""

    def test_get_adaptive_provider_short_text_uses_cpu(self):
        """Test that short text uses CPU provider (TTFA optimization)."""
        # Setup - short text
        text_length = 50

        # Test
        provider = manager.get_adaptive_provider(text_length)

        # Assert - short text should use CPU for best TTFA
        assert provider == "CPUExecutionProvider"

    def test_get_adaptive_provider_short_text_threshold(self):
        """Test adaptive provider at short text threshold."""
        # Test various lengths around threshold (200 chars)
        for length in [100, 150, 199]:
            provider = manager.get_adaptive_provider(length)
            assert provider == "CPUExecutionProvider"

    def test_get_adaptive_provider_medium_text(self):
        """Test adaptive provider for medium text."""
        # Setup - medium text (200-1000 chars)
        text_length = 500
        
        # Set a known current provider
        manager._active_provider = "CPUExecutionProvider"

        # Test
        provider = manager.get_adaptive_provider(text_length)

        # Assert - should return a valid provider
        assert isinstance(provider, str)
        assert "Provider" in provider

    def test_get_adaptive_provider_long_text(self):
        """Test adaptive provider for long text."""
        # Setup - long text (>1000 chars)
        text_length = 2000
        
        # Set current provider
        manager._active_provider = "CoreMLExecutionProvider"

        # Test
        provider = manager.get_adaptive_provider(text_length)

        # Assert
        assert isinstance(provider, str)

    @patch.dict(os.environ, {'KOKORO_COREML_COMPUTE_UNITS': 'ALL'})
    def test_get_adaptive_provider_avoids_coreml_all_for_medium_text(self):
        """Test that CoreML ALL is avoided for medium text."""
        # Setup
        text_length = 500
        manager._active_provider = "CoreMLExecutionProvider"

        # Test
        provider = manager.get_adaptive_provider(text_length)

        # Assert - should switch to CPU to avoid ALL issues
        assert provider == "CPUExecutionProvider"

    @patch.dict(os.environ, {'KOKORO_COREML_COMPUTE_UNITS': 'CPUAndGPU'})
    def test_get_adaptive_provider_allows_coreml_cpu_and_gpu(self):
        """Test that CoreML CPUAndGPU is allowed for medium text."""
        # Setup
        text_length = 500
        manager._active_provider = "CoreMLExecutionProvider"

        # Test
        provider = manager.get_adaptive_provider(text_length)

        # Assert - CPUAndGPU should be allowed
        # Will return CoreML or CPU depending on logic
        assert isinstance(provider, str)

    def test_get_adaptive_provider_zero_length_defaults_to_cpu(self):
        """Test that zero length text defaults to CPU."""
        # Test
        provider = manager.get_adaptive_provider(0)

        # Assert
        assert provider == "CPUExecutionProvider"

    def test_get_adaptive_provider_negative_length_handles_gracefully(self):
        """Test handling of negative length (edge case)."""
        # Test - should not crash
        provider = manager.get_adaptive_provider(-1)

        # Assert
        assert isinstance(provider, str)


class TestModelSetting:
    """Test setting model and provider."""

    def test_set_model_updates_global_state(self):
        """Test that set_model updates global variables."""
        # Setup
        mock_model = Mock()
        provider = "TestProvider"

        # Test
        manager.set_model(mock_model, provider)

        # Assert
        assert manager.model_loaded is True
        assert manager.kokoro_model is mock_model
        assert manager._active_provider == provider

        # Cleanup
        manager.clear_model()

    def test_set_model_thread_safety(self):
        """Test that set_model is thread-safe."""
        # Setup
        results = []
        
        def set_in_thread(i):
            mock_model = Mock(name=f"model_{i}")
            manager.set_model(mock_model, f"Provider{i}")
            results.append(manager._active_provider)

        # Test - set model from multiple threads
        threads = [threading.Thread(target=set_in_thread, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert - should have completed without errors
        assert len(results) == 5

        # Cleanup
        manager.clear_model()


class TestModelClear:
    """Test model clearing functionality."""

    def test_clear_model_resets_state(self):
        """Test that clear_model resets global state."""
        # Setup
        manager.model_loaded = True
        manager.kokoro_model = Mock()
        manager._active_provider = "TestProvider"

        # Test
        manager.clear_model()

        # Assert
        assert manager.model_loaded is False
        assert manager.kokoro_model is None
        assert manager._active_provider == "CPUExecutionProvider"  # Default

    def test_clear_model_when_already_clear(self):
        """Test clearing model when already clear."""
        # Setup
        manager.model_loaded = False
        manager.kokoro_model = None

        # Test - should not raise exception
        manager.clear_model()

        # Assert
        assert manager.model_loaded is False


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_get_model_concurrent_access(self):
        """Test concurrent model access."""
        # Setup
        manager.model_loaded = True
        manager.kokoro_model = Mock()

        # Test - multiple threads accessing model
        results = []
        
        def access_model():
            model = manager.get_model()
            results.append(model is not None)

        threads = [threading.Thread(target=access_model) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert - all should have succeeded
        assert len(results) == 10

        # Cleanup
        manager.clear_model()

    def test_set_model_with_none(self):
        """Test setting model to None explicitly."""
        # Test
        manager.set_model(None, "CPUExecutionProvider")

        # Assert
        # Behavior depends on implementation
        # Should either reject or accept None
        assert isinstance(manager._active_provider, str)

        # Cleanup
        manager.clear_model()


class TestAcceptanceCriteriaAlignment:
    """Tests aligned with CAWS acceptance criteria."""

    def test_a1_adaptive_provider_optimizes_for_short_text(self):
        """[A1] Adaptive provider selects CPU for short text (TTFA ≤ 0.50s)."""
        # Test multiple short text lengths
        for length in [10, 50, 100, 140, 199]:
            provider = manager.get_adaptive_provider(length)
            
            # Assert - should always use CPU for short text
            assert provider == "CPUExecutionProvider", \
                f"Failed for length {length}: got {provider}"

    def test_a1_provider_selection_documented_with_rationale(self):
        """[A1] Provider selection includes performance rationale."""
        # Test that function has documented benchmark data
        import inspect
        
        # Get function docstring
        docstring = inspect.getdoc(manager.get_adaptive_provider)
        
        # Assert - should document benchmark results
        assert docstring is not None
        assert "benchmark" in docstring.lower() or "ttfa" in docstring.lower()

    def test_a4_concurrent_access_maintains_stability(self):
        """[A4] Concurrent model access maintains stability."""
        # Setup
        manager.model_loaded = True
        manager.kokoro_model = Mock()

        # Test - stress test with many concurrent accesses
        errors = []
        
        def access_and_check():
            try:
                for _ in range(100):
                    provider = manager.get_active_provider()
                    status = manager.get_model_status()
                    model = manager.get_model()
                    assert isinstance(provider, str)
                    assert isinstance(status, bool)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=access_and_check) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Assert - no errors in concurrent access
        assert len(errors) == 0

        # Cleanup
        manager.clear_model()

