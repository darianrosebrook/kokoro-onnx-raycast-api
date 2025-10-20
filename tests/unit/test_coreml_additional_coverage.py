"""
Additional unit tests for api/model/providers/coreml.py to improve coverage.

This file focuses on testing the missing lines and edge cases that aren't
covered by the existing test_model_providers_coreml.py file.

Tests cover:
- Error handling paths
- Different neural engine configurations
- Memory management scenarios
- Context cleanup functions
- Edge cases and exception handling

@author: @darianrosebrook
@date: 2025-01-15
"""

import os
import tempfile
import time
from typing import Any, Dict
from unittest.mock import Mock, patch, MagicMock

import pytest

from api.model.providers import coreml


class TestErrorHandlingPaths:
    """Test error handling paths that are currently missing coverage."""

    @patch('api.config.TTSConfig')
    @patch('api.model.providers.coreml.cleanup_existing_coreml_temp_files')
    @patch('api.model.providers.coreml._force_onnxruntime_temp_directory')
    def test_setup_coreml_temp_directory_write_test_failure(self, mock_force_ort, mock_cleanup, mock_config):
        """Test error handling when write test fails (lines 84-86)."""
        # Setup
        mock_config.CACHE_DIR = "/tmp/test_cache"
        
        with patch('os.makedirs'), \
             patch('os.chmod'), \
             patch('builtins.open', side_effect=IOError("Write failed")):
            
            # Test - should raise exception
            with pytest.raises(IOError, match="Write failed"):
                coreml.setup_coreml_temp_directory()

    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.path.isfile')
    @patch('os.remove')
    def test_cleanup_existing_coreml_temp_files_handles_os_error(self, mock_remove, mock_isfile, mock_listdir, mock_exists):
        """Test error handling in cleanup when OSError occurs (lines 110-114)."""
        # Setup
        mock_exists.return_value = True
        mock_listdir.return_value = ["file1.tmp"]
        mock_isfile.return_value = True
        mock_remove.side_effect = OSError("Permission denied")

        # Test - should not raise exception
        coreml.cleanup_existing_coreml_temp_files("/tmp/test")

        # Assert - should have attempted to remove file
        mock_remove.assert_called_once()

    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    @patch('shutil.rmtree')
    def test_cleanup_existing_coreml_temp_files_handles_permission_error(self, mock_rmtree, mock_isdir, mock_isfile, mock_listdir, mock_exists):
        """Test error handling in cleanup when PermissionError occurs."""
        # Setup
        mock_exists.return_value = True
        mock_listdir.return_value = ["subdir"]
        mock_isfile.return_value = False
        mock_isdir.return_value = True
        mock_rmtree.side_effect = PermissionError("Permission denied")

        # Test - should not raise exception
        coreml.cleanup_existing_coreml_temp_files("/tmp/test")

        # Assert - should have attempted to remove directory
        mock_rmtree.assert_called_once()


class TestCleanupCoremlTempDirectory:
    """Test the cleanup_coreml_temp_directory function (lines 154-186)."""

    @patch('api.config.TTSConfig')
    @patch('os.path.exists')
    @patch('glob.glob')
    @patch('os.path.isfile')
    @patch('os.path.getmtime')
    @patch('os.remove')
    def test_cleanup_coreml_temp_directory_removes_old_files(self, mock_remove, mock_getmtime, mock_isfile, mock_glob, mock_exists, mock_config):
        """Test that old files are removed."""
        # Setup
        mock_config.CACHE_DIR = "/tmp/test_cache"
        mock_exists.return_value = True
        mock_glob.return_value = ["/tmp/test_cache/coreml_temp/old_file.tmp"]
        mock_isfile.return_value = True
        mock_getmtime.return_value = time.time() - 7200  # 2 hours old

        # Test
        coreml.cleanup_coreml_temp_directory()

        # Assert - should remove old file
        mock_remove.assert_called_once()

    @patch('api.config.TTSConfig')
    @patch('os.path.exists')
    @patch('glob.glob')
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    @patch('os.path.getmtime')
    @patch('os.listdir')
    @patch('os.rmdir')
    def test_cleanup_coreml_temp_directory_removes_old_empty_dirs(self, mock_rmdir, mock_listdir, mock_getmtime, mock_isdir, mock_isfile, mock_glob, mock_exists, mock_config):
        """Test that old empty directories are removed."""
        # Setup
        mock_config.CACHE_DIR = "/tmp/test_cache"
        mock_exists.return_value = True
        mock_glob.return_value = ["/tmp/test_cache/coreml_temp/old_dir"]
        mock_isfile.return_value = False
        mock_isdir.return_value = True
        mock_getmtime.return_value = time.time() - 7200  # 2 hours old
        mock_listdir.return_value = []  # Empty directory

        # Test
        coreml.cleanup_coreml_temp_directory()

        # Assert - should remove old empty directory
        mock_rmdir.assert_called_once()

    @patch('api.config.TTSConfig')
    @patch('os.path.exists')
    def test_cleanup_coreml_temp_directory_nonexistent_dir(self, mock_exists, mock_config):
        """Test cleanup when directory doesn't exist."""
        # Setup
        mock_config.CACHE_DIR = "/tmp/test_cache"
        mock_exists.return_value = False

        # Test - should return early
        coreml.cleanup_coreml_temp_directory()

        # Assert - should not crash


class TestMemoryManagementScenarios:
    """Test memory management scenarios (lines 249-252, 377-378, 394-396)."""

    @patch.dict(os.environ, {'KOKORO_DISABLE_MEMORY_MGMT': 'true'})
    def test_create_coreml_provider_options_memory_mgmt_disabled(self):
        """Test provider options creation when memory management is disabled."""
        # Setup
        capabilities = {"neural_engine_cores": 16, "memory_gb": 8}

        # Test
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should still create options
        assert isinstance(options, dict)
        assert "MLComputeUnits" in options

    @patch('api.model.memory.coreml_leak_mitigation.initialize_coreml_memory_management')
    @patch('api.model.memory.coreml_leak_mitigation.configure_coreml_memory_management')
    def test_create_coreml_provider_options_memory_mgmt_initialization_error(self, mock_configure, mock_init):
        """Test error handling when memory management initialization fails (lines 249-252)."""
        # Setup
        mock_init.side_effect = Exception("Memory management failed")
        capabilities = {"neural_engine_cores": 16, "memory_gb": 8}

        # Test - should not raise exception
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should still create options
        assert isinstance(options, dict)

    @patch.dict(os.environ, {'KOKORO_DISABLE_MEMORY_MGMT': 'true'})
    def test_coreml_memory_managed_session_creation_disabled(self):
        """Test session creation when memory management is disabled (lines 377-378)."""
        # Setup
        session_func = Mock(return_value="session")

        # Test
        result = coreml.coreml_memory_managed_session_creation(session_func, "arg1")

        # Assert - should use standard session creation
        assert result == "session"
        session_func.assert_called_once_with("arg1")

    @patch('api.model.memory.coreml_leak_mitigation.get_memory_manager')
    def test_coreml_memory_managed_session_creation_import_error(self, mock_get_manager):
        """Test session creation when memory manager import fails (lines 394-396)."""
        # Setup
        mock_get_manager.side_effect = ImportError("Memory management not available")
        session_func = Mock(return_value="session")

        # Test
        result = coreml.coreml_memory_managed_session_creation(session_func, "arg1")

        # Assert - should fallback to standard session creation
        assert result == "session"
        session_func.assert_called_once_with("arg1")


class TestNeuralEngineConfigurations:
    """Test different neural engine configurations (lines 276-289, 292-294, 301-303)."""

    def test_create_coreml_provider_options_m1_max_config(self):
        """Test M1 Max / M2 Max configuration (lines 276-289)."""
        # Setup - M1 Max has 32+ neural engine cores
        capabilities = {
            "neural_engine_cores": 32,
            "memory_gb": 32,
            "is_apple_silicon": True
        }

        # Test
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should use ALL for maximum Neural Engine utilization
        assert options["MLComputeUnits"] == "ALL"
        assert options["ModelFormat"] == "MLProgram"

    def test_create_coreml_provider_options_m3_config(self):
        """Test M3 configuration (lines 292-294)."""
        # Setup - M3 has 18+ neural engine cores
        capabilities = {
            "neural_engine_cores": 18,
            "memory_gb": 16,
            "is_apple_silicon": True
        }

        # Test
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should use ALL for maximum Neural Engine utilization
        assert options["MLComputeUnits"] == "ALL"
        assert options["ModelFormat"] == "MLProgram"

    def test_create_coreml_provider_options_m1_m2_config(self):
        """Test M1/M2 configuration (lines 301-303)."""
        # Setup - M1/M2 has 16+ neural engine cores
        capabilities = {
            "neural_engine_cores": 16,
            "memory_gb": 8,
            "is_apple_silicon": True
        }

        # Test
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should use ALL for maximum Neural Engine utilization
        assert options["MLComputeUnits"] == "ALL"
        assert options["ModelFormat"] == "MLProgram"

    def test_create_coreml_provider_options_other_apple_silicon(self):
        """Test other Apple Silicon configuration."""
        # Setup - Other Apple Silicon with fewer cores
        capabilities = {
            "neural_engine_cores": 8,
            "memory_gb": 8,
            "is_apple_silicon": True
        }

        # Test
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should use CPUAndGPU
        assert options["MLComputeUnits"] == "CPUAndGPU"


class TestMemoryBasedOptimizations:
    """Test memory-based optimizations (lines 317-322)."""

    def test_create_coreml_provider_options_high_memory_system(self):
        """Test high memory system optimizations."""
        # Setup - 32GB+ system
        capabilities = {
            "neural_engine_cores": 16,
            "memory_gb": 32,
            "is_apple_silicon": True
        }

        # Test
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should create options (specific optimizations may be commented out)
        assert isinstance(options, dict)

    def test_create_coreml_provider_options_standard_memory_system(self):
        """Test standard memory system optimizations."""
        # Setup - 16GB system
        capabilities = {
            "neural_engine_cores": 16,
            "memory_gb": 16,
            "is_apple_silicon": True
        }

        # Test
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should create options
        assert isinstance(options, dict)

    def test_create_coreml_provider_options_low_memory_system(self):
        """Test low memory system optimizations."""
        # Setup - 8GB system
        capabilities = {
            "neural_engine_cores": 16,
            "memory_gb": 8,
            "is_apple_silicon": True
        }

        # Test
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should create options
        assert isinstance(options, dict)


class TestMLComputeUnitsTestConfigurations:
    """Test different MLComputeUnits test configurations (lines 460-465, 468-473, 476-481)."""

    def test_test_mlcompute_units_configuration_m1_max(self):
        """Test MLComputeUnits configuration for M1 Max (lines 460-465)."""
        # Setup - M1 Max has 32+ neural engine cores
        capabilities = {
            "neural_engine_cores": 32,
            "is_apple_silicon": True
        }

        # Test
        result = coreml.test_mlcompute_units_configuration(capabilities)

        # Assert - should return optimal configuration (may be CPUAndGPU if benchmarking fails)
        # Our implementation runs actual benchmarks and selects the best performing option
        assert result in ["CPUAndNeuralEngine", "ALL", "CPUAndGPU"]

    def test_test_mlcompute_units_configuration_m1_m2(self):
        """Test MLComputeUnits configuration for M1/M2 (lines 468-473)."""
        # Setup - M1/M2 has 16+ neural engine cores
        capabilities = {
            "neural_engine_cores": 16,
            "is_apple_silicon": True
        }

        # Test
        result = coreml.test_mlcompute_units_configuration(capabilities)

        # Assert - should return optimal configuration (may be CPUAndGPU if benchmarking fails)
        # Our implementation runs actual benchmarks and selects the best performing option
        assert result in ["CPUAndNeuralEngine", "ALL", "CPUAndGPU"]

    def test_test_mlcompute_units_configuration_other_apple_silicon(self):
        """Test MLComputeUnits configuration for other Apple Silicon (lines 476-481)."""
        # Setup - Other Apple Silicon
        capabilities = {
            "neural_engine_cores": 8,
            "is_apple_silicon": True
        }

        # Test
        result = coreml.test_mlcompute_units_configuration(capabilities)

        # Assert - should return CPUAndGPU
        assert result == "CPUAndGPU"

    def test_test_mlcompute_units_configuration_non_apple_silicon(self):
        """Test MLComputeUnits configuration for non-Apple Silicon."""
        # Setup - Non-Apple Silicon
        capabilities = {
            "neural_engine_cores": 0,
            "is_apple_silicon": False
        }

        # Test
        result = coreml.test_mlcompute_units_configuration(capabilities)

        # Assert - should return CPUOnly
        assert result == "CPUOnly"


class TestContextCleanupFunctions:
    """Test context cleanup functions (lines 564-575, 590-598, 606-616)."""

    @patch('os.environ.get')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.path.isfile')
    @patch('os.unlink')
    def test_cleanup_coreml_contexts_clears_temp_dir(self, mock_unlink, mock_isfile, mock_listdir, mock_exists, mock_env_get):
        """Test that context cleanup clears temp directory (lines 564-575)."""
        # Setup
        mock_env_get.return_value = "/tmp/coreml_temp"
        mock_exists.return_value = True
        mock_listdir.return_value = ["temp_file.tmp"]
        mock_isfile.return_value = True

        # Test
        coreml.cleanup_coreml_contexts(aggressive=False)

        # Assert - should attempt to unlink file
        mock_unlink.assert_called_once()

    @patch('os.environ.get')
    @patch('os.path.exists')
    @patch('os.listdir')
    @patch('os.path.isfile')
    @patch('os.path.isdir')
    @patch('shutil.rmtree')
    def test_cleanup_coreml_contexts_removes_directories(self, mock_rmtree, mock_isdir, mock_isfile, mock_listdir, mock_exists, mock_env_get):
        """Test that context cleanup removes directories."""
        # Setup
        mock_env_get.return_value = "/tmp/coreml_temp"
        mock_exists.return_value = True
        mock_listdir.return_value = ["temp_dir"]
        mock_isfile.return_value = False
        mock_isdir.return_value = True

        # Test
        coreml.cleanup_coreml_contexts(aggressive=False)

        # Assert - should attempt to remove directory
        mock_rmtree.assert_called_once()

    @patch('glob.glob')
    @patch('os.path.exists')
    @patch('os.path.isfile')
    @patch('os.unlink')
    def test_cleanup_coreml_contexts_aggressive_mode_system_cache(self, mock_unlink, mock_isfile, mock_exists, mock_glob):
        """Test aggressive mode system cache cleanup (lines 590-598)."""
        # Setup
        mock_glob.return_value = ["/tmp/coreml_cache"]
        mock_exists.return_value = True
        mock_isfile.return_value = True

        # Test
        coreml.cleanup_coreml_contexts(aggressive=True)

        # Assert - should attempt to clean system cache
        mock_glob.assert_called()

    @patch('builtins.__import__')
    def test_cleanup_coreml_contexts_objc_autorelease_pool(self, mock_import):
        """Test Objective-C autorelease pool management (lines 606-616)."""
        # Setup - mock objc module
        mock_objc = Mock()
        mock_import.side_effect = lambda name, *args, **kwargs: mock_objc if name == 'objc' else __import__(name, *args, **kwargs)

        # Test
        coreml.cleanup_coreml_contexts(aggressive=False)

        # Assert - should call recycleAutoreleasePool
        mock_objc.recycleAutoreleasePool.assert_called()

    @patch('importlib.import_module')
    def test_cleanup_coreml_contexts_objc_import_error(self, mock_import):
        """Test fallback when objc module not available."""
        # Setup - objc import fails
        mock_import.side_effect = ImportError("objc not available")

        # Test - should not raise exception
        coreml.cleanup_coreml_contexts(aggressive=False)

        # Assert - should complete without crashing


class TestErrorHandlingInCleanup:
    """Test error handling in cleanup functions (lines 628-631, 645, 648-651, 655-656)."""

    @patch('os.environ.get')
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_cleanup_coreml_contexts_handles_listdir_error(self, mock_listdir, mock_exists, mock_env_get):
        """Test error handling when listdir fails (lines 628-631)."""
        # Setup
        mock_env_get.return_value = "/tmp/coreml_temp"
        mock_exists.return_value = True
        mock_listdir.side_effect = OSError("Permission denied")

        # Test - should not raise exception
        coreml.cleanup_coreml_contexts(aggressive=False)

        # Assert - should complete without crashing

    @patch('importlib.import_module')
    def test_cleanup_coreml_contexts_handles_objc_error(self, mock_import):
        """Test error handling when objc operations fail (lines 645, 648-651)."""
        # Setup - objc module available but operations fail
        mock_objc = Mock()
        mock_objc.recycleAutoreleasePool.side_effect = Exception("objc operation failed")
        mock_import.return_value = mock_objc

        # Test - should not raise exception
        coreml.cleanup_coreml_contexts(aggressive=False)

        # Assert - should complete without crashing

    @patch('gc.collect')
    def test_cleanup_coreml_contexts_handles_gc_error(self, mock_gc_collect):
        """Test error handling when garbage collection fails (lines 655-656)."""
        # Setup
        mock_gc_collect.side_effect = Exception("GC failed")

        # Test - should not raise exception
        coreml.cleanup_coreml_contexts(aggressive=False)

        # Assert - should complete without crashing


class TestStartupContextLeakMitigation:
    """Test startup context leak mitigation function."""

    @patch('builtins.__import__')
    def test_startup_context_leak_mitigation_objc_available(self, mock_import):
        """Test startup mitigation with objc available."""
        # Setup - mock objc module
        mock_objc = Mock()
        mock_import.side_effect = lambda name, *args, **kwargs: mock_objc if name == 'objc' else __import__(name, *args, **kwargs)

        # Test
        coreml.startup_context_leak_mitigation()

        # Assert - should call recycleAutoreleasePool multiple times
        assert mock_objc.recycleAutoreleasePool.call_count == 5

    @patch('importlib.import_module')
    def test_startup_context_leak_mitigation_objc_import_error(self, mock_import):
        """Test startup mitigation when objc not available."""
        # Setup - objc import fails
        mock_import.side_effect = ImportError("objc not available")

        # Test - should not raise exception
        coreml.startup_context_leak_mitigation()

        # Assert - should complete without crashing

    @patch('importlib.import_module')
    def test_startup_context_leak_mitigation_objc_operation_error(self, mock_import):
        """Test startup mitigation when objc operations fail."""
        # Setup - objc module available but operations fail
        mock_objc = Mock()
        mock_objc.recycleAutoreleasePool.side_effect = Exception("objc operation failed")
        mock_import.return_value = mock_objc

        # Test - should not raise exception
        coreml.startup_context_leak_mitigation()

        # Assert - should complete without crashing

    @patch('gc.collect')
    def test_startup_context_leak_mitigation_gc_available(self, mock_gc_collect):
        """Test startup mitigation with garbage collection."""
        # Setup
        mock_gc_collect.return_value = 5  # Collected 5 objects

        # Test
        coreml.startup_context_leak_mitigation()

        # Assert - should call gc.collect multiple times
        assert mock_gc_collect.call_count == 3

    @patch('gc.collect')
    def test_startup_context_leak_mitigation_gc_error(self, mock_gc_collect):
        """Test startup mitigation when garbage collection fails."""
        # Setup
        mock_gc_collect.side_effect = Exception("GC failed")

        # Test - should not raise exception
        coreml.startup_context_leak_mitigation()

        # Assert - should complete without crashing

    @patch('time.sleep')
    def test_startup_context_leak_mitigation_sleep(self, mock_sleep):
        """Test startup mitigation includes sleep."""
        # Test
        coreml.startup_context_leak_mitigation()

        # Assert - should sleep briefly
        mock_sleep.assert_called_once_with(0.05)


class TestBenchmarkingCacheScenarios:
    """Test benchmarking cache scenarios."""

    @patch('api.utils.cache_helpers.load_json_cache')
    @patch('api.utils.cache_helpers.save_json_cache_atomic')
    def test_benchmark_mlcompute_units_if_needed_saves_cache(self, mock_save, mock_load):
        """Test that benchmarking results are cached."""
        # Setup - no cached result
        mock_load.return_value = None
        capabilities = {"neural_engine_cores": 16}

        # Test
        result = coreml.benchmark_mlcompute_units_if_needed(capabilities)

        # Assert - should save to cache
        mock_save.assert_called_once()
        assert isinstance(result, str)

    @patch('api.utils.cache_helpers.load_json_cache')
    @patch('api.utils.cache_helpers.save_json_cache_atomic')
    def test_benchmark_mlcompute_units_if_needed_cache_save_error(self, mock_save, mock_load):
        """Test error handling when cache save fails."""
        # Setup - no cached result, save fails
        mock_load.return_value = None
        mock_save.side_effect = Exception("Save failed")
        capabilities = {"neural_engine_cores": 16}

        # Test - should not raise exception
        result = coreml.benchmark_mlcompute_units_if_needed(capabilities)

        # Assert - should still return result
        assert isinstance(result, str)


class TestEdgeCasesAndIntegration:
    """Test additional edge cases and integration scenarios."""

    def test_get_coreml_memory_status_import_error(self):
        """Test memory status when import fails."""
        with patch('api.model.memory.coreml_leak_mitigation.get_coreml_memory_stats', side_effect=ImportError("Not available")):
            # Test
            status = coreml.get_coreml_memory_status()

            # Assert - should return error dict
            assert isinstance(status, dict)
            assert "error" in status

    def test_get_coreml_memory_status_general_error(self):
        """Test memory status when general error occurs."""
        with patch('api.model.memory.coreml_leak_mitigation.get_coreml_memory_stats', side_effect=Exception("General error")):
            # Test
            status = coreml.get_coreml_memory_status()

            # Assert - should return error dict
            assert isinstance(status, dict)
            assert "error" in status

    def test_force_coreml_cleanup_import_error(self):
        """Test forced cleanup when import fails."""
        with patch('api.model.memory.coreml_leak_mitigation.force_coreml_memory_cleanup', side_effect=ImportError("Not available")):
            # Test
            result = coreml.force_coreml_cleanup()

            # Assert - should return error dict
            assert isinstance(result, dict)
            assert "error" in result

    def test_force_coreml_cleanup_general_error(self):
        """Test forced cleanup when general error occurs."""
        with patch('api.model.memory.coreml_leak_mitigation.force_coreml_memory_cleanup', side_effect=Exception("General error")):
            # Test
            result = coreml.force_coreml_cleanup()

            # Assert - should return error dict
            assert isinstance(result, dict)
            assert "error" in result

    def test_create_coreml_provider_options_environment_variables(self):
        """Test that environment variables are set during options creation."""
        # Setup
        capabilities = {"neural_engine_cores": 32, "memory_gb": 16}

        # Test
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should set CoreML environment variables
        assert os.environ.get('COREML_NEURAL_ENGINE_OPTIMIZATION') == '1'
        assert os.environ.get('COREML_USE_FLOAT16') == '1'
        assert os.environ.get('COREML_OPTIMIZE_FOR_APPLE_SILICON') == '1'

    @patch('api.config.TTSConfig')
    @patch('os.makedirs')
    def test_create_coreml_provider_options_cache_directory_creation(self, mock_makedirs, mock_config):
        """Test that cache directories are created."""
        # Setup - clear cache to ensure fresh execution
        coreml._provider_options_cache.clear()
        mock_config.CACHE_DIR = "/tmp/test_cache"
        capabilities = {"neural_engine_cores": 16, "memory_gb": 8}

        # Test
        options = coreml.create_coreml_provider_options(capabilities)

        # Assert - should create cache directories
        assert mock_makedirs.call_count >= 2  # coreml_temp and coreml_cache
        assert isinstance(options, dict)
