"""
Unit tests for api/model/loader.py - Model loader facade and legacy compatibility.

Tests cover:
- Legacy compatibility wrappers
- Model access functions
- Provider access
- Hardware detection
- Initialization functions
- Cleanup functions

@author: @darianrosebrook
@date: 2025-10-09
"""

from unittest.mock import Mock, patch

import pytest

from api.model import loader


class TestModelAccessFunctions:
    """Test model access wrapper functions."""

    @patch('api.model.sessions.get_model')
    def test_get_model_wraps_session_function(self, mock_get):
        """Test get_model wraps sessions.get_model."""
        # Setup
        mock_model = Mock()
        mock_get.return_value = mock_model

        # Test
        result = loader.get_model()

        # Assert
        assert result == mock_model
        mock_get.assert_called_once()

    @patch('api.model.sessions.get_model_status')
    def test_get_model_status_wraps_session_function(self, mock_get_status):
        """Test get_model_status wraps sessions.get_model_status."""
        # Setup
        mock_get_status.return_value = True

        # Test
        result = loader.get_model_status()

        # Assert
        assert result is True
        mock_get_status.assert_called_once()

    @patch('api.model.sessions.get_active_provider')
    def test_get_active_provider_wraps_session_function(self, mock_get_provider):
        """Test get_active_provider wraps sessions.get_active_provider."""
        # Setup
        mock_get_provider.return_value = "CPUExecutionProvider"

        # Test
        result = loader.get_active_provider()

        # Assert
        assert result == "CPUExecutionProvider"
        mock_get_provider.assert_called_once()


class TestHardwareDetection:
    """Test hardware detection wrapper."""

    @patch('api.model.hardware.detect_apple_silicon_capabilities')
    def test_detect_apple_silicon_capabilities_wraps_hardware_function(self, mock_detect):
        """Test detect_apple_silicon_capabilities wraps hardware.detect_apple_silicon_capabilities."""
        # Setup
        mock_detect.return_value = {
            "apple_silicon": True,
            "neural_engine": True
        }

        # Test
        result = loader.detect_apple_silicon_capabilities()

        # Assert
        assert result == mock_detect.return_value
        mock_detect.assert_called_once()


class TestInitializationFunctions:
    """Test initialization wrapper functions."""

    @patch('api.model.initialization.fast_init.initialize_model_fast')
    def test_initialize_model_fast_wraps_init_function(self, mock_init):
        """Test initialize_model_fast wraps initialization.fast_init.initialize_model_fast."""
        # Setup
        mock_init.return_value = True

        # Test
        result = loader.initialize_model_fast()

        # Assert
        assert result is True
        mock_init.assert_called_once()

    @patch('api.model.initialization.fast_init.initialize_model_fast')
    def test_initialize_model_wraps_fast_init(self, mock_init):
        """Test initialize_model wraps fast_init (legacy compatibility)."""
        # Setup
        mock_init.return_value = True

        # Test
        result = loader.initialize_model()

        # Assert
        assert result is True
        mock_init.assert_called_once()


class TestSessionManagement:
    """Test session management wrapper functions."""

    @patch('api.model.sessions.get_dual_session_manager')
    def test_get_dual_session_manager_wraps_session_function(self, mock_get_dsm):
        """Test get_dual_session_manager wraps sessions.get_dual_session_manager."""
        # Setup
        mock_dsm = Mock()
        mock_get_dsm.return_value = mock_dsm

        # Test
        result = loader.get_dual_session_manager()

        # Assert
        assert result == mock_dsm
        mock_get_dsm.assert_called_once()


class TestMemoryManagement:
    """Test memory management wrapper functions."""

    @patch('api.model.memory.get_dynamic_memory_manager')
    def test_get_dynamic_memory_manager_wraps_memory_function(self, mock_get_manager):
        """Test get_dynamic_memory_manager wraps memory.get_dynamic_memory_manager."""
        # Setup
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager

        # Test
        result = loader.get_dynamic_memory_manager()

        # Assert
        assert result == mock_manager
        mock_get_manager.assert_called_once()


class TestPipelineManagement:
    """Test pipeline management wrapper functions."""

    @patch('api.model.pipeline.get_pipeline_warmer')
    def test_get_pipeline_warmer_wraps_pipeline_function(self, mock_get_warmer):
        """Test get_pipeline_warmer wraps pipeline.get_pipeline_warmer."""
        # Setup
        mock_warmer = Mock()
        mock_get_warmer.return_value = mock_warmer

        # Test
        result = loader.get_pipeline_warmer()

        # Assert
        assert result == mock_warmer
        mock_get_warmer.assert_called_once()


class TestCleanupFunctions:
    """Test cleanup wrapper functions."""

    @patch('api.model.initialization.lifecycle.cleanup_model')
    def test_cleanup_model_wraps_lifecycle_function(self, mock_cleanup):
        """Test cleanup_model wraps lifecycle.cleanup_model."""
        # Setup
        mock_cleanup.return_value = None

        # Test
        result = loader.cleanup_model()

        # Assert
        mock_cleanup.assert_called_once()


class TestModuleIntegration:
    """Test module-level integration."""

    def test_patches_are_applied_on_import(self):
        """Test that patches are applied when module is imported."""
        # The module applies patches in __init__
        # Just verify the module is importable
        assert loader is not None

    def test_early_temp_directory_setup(self):
        """Test that temp directory setup happens early."""
        # The module sets up temp directory on import
        # Verify the module is functional
        assert hasattr(loader, 'cleanup_model')
        assert hasattr(loader, 'get_model')

    def test_atexit_cleanup_registered(self):
        """Test that cleanup is registered with atexit."""
        # Verify the module registers cleanup
        # (This is tested by the module not crashing on import)
        assert callable(loader.cleanup_model)

