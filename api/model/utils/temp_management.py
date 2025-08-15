"""
Temporary Directory Management Utilities

This module handles temporary directory setup and management for CoreML and ONNX Runtime.
"""
import os
import tempfile
import shutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def setup_early_temp_directory() -> Optional[str]:
    """
    Set up temp directory immediately for CoreML and ONNX Runtime operations.
    
    This function creates a local cache directory and sets up environment variables
    to ensure all temporary files are created in a controlled location.
    
    @returns: Path to the created temp directory or None if setup failed
    """
    try:
        cache_dir = os.path.abspath(".cache")
        local_temp_dir = os.path.join(cache_dir, "coreml_temp")
        os.makedirs(local_temp_dir, exist_ok=True)
        os.chmod(local_temp_dir, 0o755)
        
        # Clean any existing files first
        try:
            for item in os.listdir(local_temp_dir):
                item_path = os.path.join(local_temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                except (OSError, PermissionError):
                    pass  # Ignore permission errors during early cleanup
        except Exception:
            pass  # Directory might not exist yet
        
        # Set environment variables early - these must be set before any ONNX Runtime operations
        os.environ['TMPDIR'] = local_temp_dir
        os.environ['TMP'] = local_temp_dir 
        os.environ['TEMP'] = local_temp_dir
        os.environ['COREML_TEMP_DIR'] = local_temp_dir
        os.environ['ONNXRUNTIME_TEMP_DIR'] = local_temp_dir
        
        # Also set Python's tempfile default directory
        tempfile.tempdir = local_temp_dir
        
        # Override tempfile.gettempdir() early - avoid infinite recursion
        if not hasattr(tempfile, '_original_gettempdir'):
            tempfile._original_gettempdir = tempfile.gettempdir
            def patched_gettempdir():
                return local_temp_dir
            tempfile.gettempdir = patched_gettempdir
        
        # Verify the environment variables are set correctly
        if os.environ.get('TMPDIR') != local_temp_dir:
            logger.warning(f"TMPDIR environment variable not set correctly. Expected: {local_temp_dir}, Got: {os.environ.get('TMPDIR')}")
        
        logger.info(f"Early temp directory setup completed: {local_temp_dir}")
        return local_temp_dir
        
    except Exception as e:
        logger.error(f"Early temp directory setup failed: {e}")
        return None


def verify_temp_directory_configuration() -> bool:
    """
    Verify that temp directory configuration is correct and warn if not.
    
    This function checks that the environment variables are properly set
    and warns if ONNX Runtime might still use the system temp directory.
    
    @returns: True if configuration is correct, False otherwise
    """
    expected_temp_dir = os.path.join(os.getcwd(), ".cache", "coreml_temp")
    actual_tmpdir = os.environ.get('TMPDIR')
    
    if actual_tmpdir != expected_temp_dir:
        logger.critical("Temp directory misconfiguration detected!")
        logger.critical(f"Expected TMPDIR: {expected_temp_dir}")
        logger.critical(f"Actual TMPDIR: {actual_tmpdir}")
        logger.critical("This will cause CoreML cleanup failures on work-provisioned machines!")
        logger.critical("Please restart the application to fix this issue.")
        return False
    else:
        logger.info(f"Temp directory configuration verified: {actual_tmpdir}")
        return True


def cleanup_temp_directory(temp_dir: Optional[str] = None) -> bool:
    """
    Clean up temporary directory and files.
    
    @param temp_dir: Directory to clean up. If None, uses default cache location
    @returns: True if cleanup was successful, False otherwise
    """
    if temp_dir is None:
        temp_dir = os.path.join(os.getcwd(), ".cache", "coreml_temp")
    
    try:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temp directory: {temp_dir}")
        return True
    except Exception as e:
        logger.error(f"Failed to cleanup temp directory {temp_dir}: {e}")
        return False


def get_temp_directory() -> str:
    """Get the current temporary directory path."""
    return os.environ.get('TMPDIR', tempfile.gettempdir())
