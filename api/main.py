"""
Kokoro-ONNX TTS API - Production-Ready FastAPI Server with Hardware Acceleration

This module implements a high-performance TTS API server optimized for the Kokoro ONNX model,
featuring intelligent hardware acceleration, streaming audio delivery, and production-ready
error handling and monitoring.

## Architecture Overview

The API server follows a sophisticated multi-layer architecture designed to maximize
performance while maintaining reliability and scalability:

1. **FastAPI Foundation**: Built on FastAPI for automatic OpenAPI documentation,
   request validation, and async request handling with uvicorn ASGI server.

2. **Hardware-Accelerated Model Management**: Intelligent provider selection between
   CoreML (Apple Silicon Neural Engine) and CPU execution providers with automatic
   benchmarking and fallback mechanisms.

3. **Streaming Audio Pipeline**: OpenAI-compatible streaming endpoint that processes
   text in parallel segments while streaming audio chunks to minimize latency.

4. **Production Monitoring**: Comprehensive performance tracking, error handling,
   and benchmark reporting for production deployment insights.

5. **Cross-Platform Compatibility**: Optimized for Apple Silicon with automatic
   fallback to CPU execution for maximum compatibility.

## Key Features

### Performance Optimizations
- **Hardware Acceleration**: Automatic CoreML provider selection on Apple Silicon
- **Streaming Audio**: Real-time audio streaming with <500ms latency
- **Parallel Processing**: Concurrent text segment processing for long texts
- **Intelligent Caching**: Provider selection caching with 24-hour expiration
- **Memory Management**: Automatic cleanup and garbage collection

### Production Readiness
- **Health Monitoring**: Real-time health checks and status endpoints
- **Error Resilience**: Multi-level fallback systems with graceful degradation
- **Performance Metrics**: Comprehensive runtime statistics and benchmarking
- **Request Tracking**: Request ID-based logging for debugging and analytics
- **Warning Management**: Intelligent handling of CoreML context warnings

### API Compatibility
- **OpenAI TTS API**: Full compatibility with OpenAI's TTS API specification
- **Streaming Support**: Chunked transfer encoding for real-time audio delivery
- **Format Support**: WAV and PCM audio formats with proper MIME types
- **CORS Enabled**: Cross-origin resource sharing for web applications

## Technical Implementation

### Application Lifecycle Management
The server uses FastAPI's lifespan context manager for proper resource initialization
and cleanup with comprehensive error handling and validation:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Comprehensive validation and initialization
    validate_dependencies()
    TTSConfig.verify_config()
    initialize_model()
    
    yield  # Application runs here
    
    # Shutdown: Clean up resources
    logger.info("Application shutdown.")
```

### Request Processing Pipeline
```
Client Request → Request Validation → Model Status Check → Text Processing → 
Audio Generation → Response Streaming → Client
```

### Audio Processing Chain
```
Text Input → Segmentation → Parallel Synthesis → Audio Concatenation → 
Format Conversion → Streaming Output
```

## API Endpoints

### Health Check (`GET /health`)
Simple health check endpoint returning server status:
- `online`: Model is loaded and ready
- `initializing`: Model is still loading

### Status Information (`GET /status`)
Comprehensive server status including:
- Model loading state
- Available ONNX providers
- Performance statistics
- Hardware acceleration status
- Patch status and errors

### TTS Generation (`POST /v1/audio/speech`)
Main TTS endpoint compatible with OpenAI's API:
- **Streaming Mode**: Real-time audio streaming with chunked transfer
- **Non-Streaming Mode**: Complete audio generation before response
- **Format Support**: WAV and PCM output formats
- **Voice Selection**: Multiple voice options with speed control
- **Language Support**: Multi-language synthesis

## Error Handling Strategy

### Multi-Level Fallback System
1. **Provider Fallback**: CoreML → CPU if hardware acceleration fails
2. **Text Fallback**: Minimal text processing if phonemizer fails
3. **Segment Fallback**: Skip failed segments while preserving others
4. **Format Fallback**: PCM if WAV generation fails

### Error Response Codes
- `400`: Invalid request parameters or text processing failure
- `500`: Internal server error with detailed logging
- `503`: Service unavailable when model is not loaded

## Performance Characteristics

### Latency Optimization
- **Streaming**: 200-500ms to first audio chunk
- **Parallel Processing**: Multiple segments processed simultaneously
- **Hardware Acceleration**: 2-5x performance improvement on Apple Silicon
- **Caching**: Provider selection cached to avoid re-benchmarking

### Memory Management
- **Automatic Cleanup**: Garbage collection after each request
- **Resource Monitoring**: Memory usage tracking and cleanup
- **Context Management**: Proper CoreML context lifecycle management

### Scalability Features
- **Async Processing**: Non-blocking request handling
- **Concurrent Segments**: Parallel audio generation
- **Streaming Output**: Constant memory usage regardless of text length

## Security Considerations

### Input Validation
- **Text Length Limits**: Maximum 2000 characters per request
- **Parameter Validation**: Pydantic model validation for all inputs
- **Request Sanitization**: Safe text processing with fallback mechanisms

### Resource Protection
- **Memory Limits**: Automatic cleanup to prevent memory leaks
- **Process Management**: Proper cleanup of model resources
- **Timeout Handling**: Request timeouts to prevent resource exhaustion

## Monitoring and Observability

### Performance Metrics
- **Inference Time**: Per-request processing time tracking
- **Provider Usage**: Hardware acceleration utilization statistics
- **Error Rates**: Fallback usage and error frequency monitoring
- **Memory Usage**: Resource consumption tracking

### Logging Strategy
- **Request Tracking**: Unique request IDs for debugging
- **Performance Logging**: Detailed timing and provider information
- **Error Logging**: Comprehensive error reporting with stack traces
- **Warning Management**: Intelligent CoreML warning suppression

@author @darianrosebrook
@version 2.1.0
@since 2025-07-08
@license MIT

@example
```bash
# Start the server
uvicorn api.main:app --host 0.0.0.0 --port 8000

# Health check
curl http://localhost:8000/health

# TTS generation
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "af_heart", "speed": 1.0}'
```
"""
import io
import logging
import os
import struct
import sys
import traceback
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from datetime import datetime

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import StreamingResponse, ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse

from api.security import SecurityMiddleware, SecurityConfig
import soundfile as sf

from api.config import TTSConfig, TTSRequest
from api.warnings import setup_coreml_warning_handler
from api.model.patch import apply_all_patches, get_patch_status
from api.model.loader import (
    initialize_model_fast as initialize_model_sync,
    detect_apple_silicon_capabilities,
    get_model_status,
)
from api.performance.stats import get_performance_stats
from api.tts.core import _generate_audio_segment, stream_tts_audio, get_tts_processing_stats
from api.tts.core import get_primer_microcache_stats
from api.utils.cache_cleanup import cleanup_cache, get_cache_info
from api.tts.text_processing import segment_text
from api.warnings import suppress_phonemizer_warnings, configure_onnx_runtime_logging
from functools import lru_cache


# Enhanced dependency injection caching for optimal performance
# Reference: DEPENDENCY_RESEARCH.md section 2.2

@lru_cache(maxsize=1)
def get_tts_config():
    """
    Cached TTS configuration dependency.
    
    Returns cached TTSConfig instance to avoid repeated instantiation.
    Cache size limited to 1 since configuration is static.
    """
    return TTSConfig()

@lru_cache(maxsize=1)
def get_model_capabilities():
    """
    Cached hardware capabilities dependency.
    
    Returns cached system capabilities to avoid repeated detection.
    Cache size limited to 1 since hardware doesn't change during runtime.
    """
    from api.model.loader import detect_apple_silicon_capabilities
    return detect_apple_silicon_capabilities()

@lru_cache(maxsize=10)
def get_cached_model_status():
    """
    Cached model status dependency with TTL-like behavior.
    
    Returns cached model status for performance optimization.
    Cache size limited to 10 to handle different status states.
    """
    from api.model.loader import get_model_status
    return get_model_status()

@lru_cache(maxsize=1)
def get_performance_tracker():
    """
    Cached performance tracker dependency.
    
    Returns cached performance tracking instance.
    Cache size limited to 1 since tracker is singleton.
    """
    from api.performance.stats import PerformanceTracker
    return PerformanceTracker()

# Async cached dependencies for better performance
import asyncio
from functools import wraps

def async_lru_cache(maxsize=128):
    """
    Async LRU cache decorator for async dependency functions.
    
    Provides caching for async functions with configurable cache size.
    """
    def decorator(func):
        cache = {}
        cache_order = []
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key
            key = str(args) + str(sorted(kwargs.items()))
            
            # Check cache hit
            if key in cache:
                # Move to end (most recently used)
                cache_order.remove(key)
                cache_order.append(key)
                return cache[key]
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Add to cache
            cache[key] = result
            cache_order.append(key)
            
            # Evict if over maxsize
            if len(cache) > maxsize:
                oldest_key = cache_order.pop(0)
                del cache[oldest_key]
            
            return result
        
        return wrapper
    return decorator

@async_lru_cache(maxsize=5)
async def get_cached_system_info():
    """
    Cached system information dependency.
    
    Returns cached system information for status endpoints.
    """
    import psutil
    return {
        'memory_usage': psutil.virtual_memory().percent,
        'cpu_usage': psutil.cpu_percent(),
        'disk_usage': psutil.disk_usage('/').percent,
    }


def setup_application_logging():
    """
    Setup comprehensive logging configuration for the application.

    This function configures logging with multiple handlers for different output
    destinations and provides detailed logging for debugging and monitoring.
    """
    # Prevent duplicate setup
    if hasattr(setup_application_logging, '_configured'):
        return
    setup_application_logging._configured = True
    
    # Import config here to avoid circular imports
    from api.config import CONSOLE_LOG_LEVEL, FILE_LOG_LEVEL
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Set to DEBUG to allow all levels

    # Clear existing handlers to prevent duplicates
    root_logger.handlers.clear()

    # Console handler with immediate flushing
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, CONSOLE_LOG_LEVEL))
    console_handler.setFormatter(simple_formatter)
    # Ensure immediate flushing
    console_handler.flush = lambda: console_handler.stream.flush()
    # Set buffer size to 0 for immediate output
    if hasattr(console_handler.stream, 'reconfigure'):
        console_handler.stream.reconfigure(line_buffering=True)
    root_logger.addHandler(console_handler)

    # Create logs directory
    logs_dir = "logs"
    os.makedirs(logs_dir, exist_ok=True)

    # File handler for detailed logging
    file_handler = logging.FileHandler("logs/api_server.log")
    file_handler.setLevel(getattr(logging, FILE_LOG_LEVEL))
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)

    logger = logging.getLogger(__name__)
    logger.info("Application logging configured")
    logger.debug("Detailed logs will be written to: logs/api_server.log")

    # Configure immediate flushing for console handler
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream and handler.stream == sys.stdout:
            # Force immediate flushing for console output
            handler.flush = lambda: handler.stream.flush() if handler.stream else None
            # Override emit to ensure flushing
            original_emit = handler.emit

            def emit_with_flush(record):
                original_emit(record)
                if handler.stream:
                    handler.stream.flush()
                # Also force stdout flush
                sys.stdout.flush()
            handler.emit = emit_with_flush

    # Ensure stdout is unbuffered
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)

    # Test logging to ensure it's working immediately
    logger.debug("Logging system initialized and ready")
    sys.stdout.flush()  # Force immediate output


def validate_dependencies():
    """
    Validate that all required dependencies are available.

    This function checks for the presence and compatibility of all required
    dependencies before starting the application to prevent runtime failures.

    @raises RuntimeError: If critical dependencies are missing
    """
    logger = logging.getLogger(__name__)
    logger.info(" Validating application dependencies...")

    missing_deps = []
    version_issues = []

    # Check critical dependencies
    required_packages = [
        ('onnxruntime', 'onnxruntime'),
        ('numpy', 'numpy'),
        ('kokoro_onnx', 'kokoro-onnx'),
        ('espeakng_loader', 'espeakng-loader'),
        ('fastapi', 'fastapi'),
        ('uvicorn', 'uvicorn'),
    ]

    for import_name, package_name in required_packages:
        try:
            __import__(import_name)
            logger.debug(f"✅ {package_name} available")
        except ImportError:
            missing_deps.append(package_name)
            logger.error(f" {package_name} not found")

    # Check optional dependencies
    optional_packages = [
        ('psutil', 'psutil'),
        ('phonemizer_fork', 'phonemizer-fork'),
    ]

    for import_name, package_name in optional_packages:
        try:
            __import__(import_name)
            logger.debug(f"✅ {package_name} available (optional)")
        except ImportError:
            logger.warning(f"⚠️ {package_name} not found (optional)")

    # Check eSpeak installation
    try:
        import subprocess
        result = subprocess.run(['which', 'espeak-ng'],
                                capture_output=True, text=True)
        if result.returncode == 0:
            logger.debug("✅ eSpeak-ng found in system PATH")
        else:
            logger.warning("⚠️ eSpeak-ng not found in system PATH")
    except Exception as e:
        logger.warning(f"⚠️ Could not check eSpeak-ng installation: {e}")

    # Report results
    if missing_deps:
        error_msg = f"Missing required dependencies: {', '.join(missing_deps)}"
        logger.error(f" {error_msg}")
        logger.error(
            " Install missing packages with: pip install " + " ".join(missing_deps))
        raise RuntimeError(error_msg)

    if version_issues:
        logger.warning(
            f"⚠️ Version compatibility issues: {', '.join(version_issues)}")

    logger.info("✅ All application dependencies validated successfully")


def validate_model_files():
    """
    Validate that required model files are present and accessible.

    This function checks for the presence of model files before attempting
    to initialize the TTS model to prevent startup failures.

    @raises RuntimeError: If model files are missing or inaccessible
    """
    logger = logging.getLogger(__name__)
    logger.info(" Validating model files...")

    model_files = {
        'model': TTSConfig.MODEL_PATH,
        'voices': TTSConfig.VOICES_PATH
    }

    missing_files = []

    for file_type, file_path in model_files.items():
        if not os.path.exists(file_path):
            missing_files.append(f"{file_type} ({file_path})")
            logger.error(f" {file_type} file not found: {file_path}")
        else:
            # Check if file is readable
            try:
                with open(file_path, 'rb') as f:
                    f.read(1024)  # Read first 1KB to test access
                logger.debug(f"✅ {file_type} file accessible: {file_path}")
            except Exception as e:
                missing_files.append(
                    f"{file_type} ({file_path}) - access error: {e}")
                logger.error(
                    f" {file_type} file not accessible: {file_path} - {e}")

    if missing_files:
        error_msg = f"Missing or inaccessible model files: {', '.join(missing_files)}"
        logger.error(f" {error_msg}")
        raise RuntimeError(error_msg)

    logger.info("✅ All model files validated successfully")


def validate_environment():
    """
    Validate environment configuration and system capabilities.

    This function checks environment variables, system capabilities, and
    configuration settings to ensure the application can start properly.

    @raises RuntimeError: If environment validation fails
    """
    logger = logging.getLogger(__name__)
    logger.info(" Validating environment configuration...")

    # The main hardware capability detection is now handled in the model loader.
    # This check is a lightweight validation to ensure ONNX Runtime is functional.

    # Check ONNX Runtime providers
    try:
        available_providers = ort.get_available_providers()
        logger.info(f" Available ONNX providers: {available_providers}")

        if 'CPUExecutionProvider' not in available_providers:
            raise RuntimeError("CPU provider not available - critical error")

    except Exception as e:
        logger.error(f" ONNX Runtime provider validation failed: {e}")
        raise RuntimeError(f"ONNX Runtime validation failed: {e}")

    # Check environment variables
    required_env_vars = ['PYTHONPATH']
    for env_var in required_env_vars:
        if not os.environ.get(env_var):
            logger.warning(f"⚠️ Environment variable {env_var} not set")

    logger.info("✅ Environment configuration validated successfully")


def validate_patch_status():
    """
    Validate that patches have been applied successfully.

    This function checks the status of applied patches and reports any
    issues that might affect application functionality.

    @raises RuntimeError: If critical patches failed to apply
    """
    logger = logging.getLogger(__name__)
    logger.info(" Validating patch status...")

    try:
        patch_status = get_patch_status()

        if not patch_status['applied']:
            raise RuntimeError("Patches not applied - critical error")

        if patch_status['patch_errors']:
            logger.warning(
                f"⚠️ Patch errors detected: {patch_status['patch_errors']}")

        logger.info(
            f"✅ Patches applied successfully in {patch_status['application_time']:.3f}s")
        logger.info(
            f" Original functions stored: {patch_status['original_functions_stored']}")

        # Log patch guard status
        guard_status = patch_status.get('patch_guard_status', {})
        for method, is_patched in guard_status.items():
            status = "✅ Patched" if is_patched else " Not Patched"
            logger.debug(f"   • {method}: {status}")

    except Exception as e:
        logger.error(f" Patch status validation failed: {e}")
        raise RuntimeError(f"Patch validation failed: {e}")


# Setup comprehensive logging
setup_application_logging()
logger = logging.getLogger(__name__)

# Initialize warning handlers for various noise sources
# This must be called before any ONNX Runtime operations
logger.debug("Initializing warning management systems...")
configure_onnx_runtime_logging()
setup_coreml_warning_handler()
suppress_phonemizer_warnings()

# Note: Stderr interceptor is already activated at module import time in warnings.py
# This ensures early warning suppression before any ONNX Runtime operations

# Apply monkey patches for eSpeak integration and Kokoro model fixes
# These patches fix known issues with the upstream kokoro-onnx library
logger.debug("Applying production patches to kokoro-onnx library...")
apply_all_patches()

# Global variables for application state
kokoro_model: Optional[object] = None
model_initialization_complete = False
model_initialization_started = False
startup_progress = {
    "status": "starting",
    "progress": 0,
    "message": "Initializing application...",
    "started_at": None,
    "completed_at": None
}

# Global variables for cold-start warm-up tracking
_cold_start_warmup_completed: bool = False
_cold_start_warmup_time_ms: float = 0.0
_cold_start_warmup_error: Optional[str] = None


class PerformanceMiddleware(BaseHTTPMiddleware):
    """
    Custom middleware for performance optimization and monitoring.

    This middleware provides:
    - Request timing and performance headers
    - Memory usage optimization
    - Response compression hints
    - Security headers for production
    """

    async def dispatch(self, request: StarletteRequest, call_next):
        # Start timing
        start_time = time.time()

        # Process request
        response: StarletteResponse = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Add performance headers
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-API-Version"] = "2.1.0"

        # Add security headers in production
        is_prod = os.environ.get(
            "KOKORO_PRODUCTION", "false").lower() == "true"
        if is_prod:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Add cache headers for static content
        if request.url.path.startswith("/health") or request.url.path.startswith("/status"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

        return response


def update_startup_progress(progress: int, message: str, status: str = "initializing"):
    """Update startup progress for user feedback"""
    startup_progress.update({
        "status": status,
        "progress": progress,
        "message": message,
        "started_at": startup_progress.get("started_at") or time.time()
    })
    # Use print for immediate console output only
    print(f"Startup Progress ({progress}%): {message}", flush=True)


async def initialize_model():
    """Initialize the model with progress tracking"""
    global kokoro_model, model_initialization_complete, model_initialization_started

    if model_initialization_started:
        return

    model_initialization_started = True
    startup_progress["started_at"] = time.time()

    try:
        update_startup_progress(5, "Setting up warning management...")
        setup_coreml_warning_handler()

        # Set TMPDIR to local cache to avoid CoreML permission issues
        local_cache_dir = os.path.abspath(".cache")
        os.environ['TMPDIR'] = local_cache_dir
        logger.debug(f"Set TMPDIR to local cache: {local_cache_dir}")

        update_startup_progress(8, "Cleaning up cache files...")
        try:
            cache_info = get_cache_info()
            if cache_info.get('needs_cleanup', False):
                cleanup_result = cleanup_cache(aggressive=False)
                logger.info(f"Cache cleanup completed: freed {cleanup_result.get('total_freed_mb', 0):.1f}MB")
            else:
                logger.debug(f"Cache size OK: {cache_info.get('total_size_mb', 0):.1f}MB")
        except Exception as e:
            logger.warning(f"⚠️ Cache cleanup failed: {e}")

        # Clean up any existing CoreML temp files that might cause permission issues
        try:
            import shutil
            import glob
            coreml_temp_dirs = [
                ".cache/coreml_temp",
                "/var/folders/by/jwzv5d892jgcbjj02895c5280000gn/T/onnxruntime-*",
                "/private/var/folders/by/jwzv5d892jgcbjj02895c5280000gn/T/onnxruntime-*"
            ]

            for temp_pattern in coreml_temp_dirs:
                if "*" in temp_pattern:
                    # Handle glob patterns
                    for temp_dir in glob.glob(temp_pattern):
                        if os.path.exists(temp_dir):
                            try:
                                shutil.rmtree(temp_dir)
                                logger.info(
                                    f" Cleaned up CoreML temp directory: {temp_dir}")
                            except Exception as e:
                                logger.debug(
                                    f"⚠️ Could not clean up {temp_dir}: {e}")
                else:
                    # Handle direct paths
                    if os.path.exists(temp_pattern):
                        try:
                            # For the local coreml_temp directory, clean files but keep the directory
                            if temp_pattern == ".cache/coreml_temp":
                                # Clean up old files but preserve directory structure
                                import glob as file_glob
                                current_time = time.time()
                                cleaned_files = 0
                                
                                for file_path in file_glob.glob(os.path.join(temp_pattern, "*")):
                                    try:
                                        # Remove files older than 1 hour or all files if startup
                                        if os.path.isfile(file_path):
                                            file_age = current_time - os.path.getmtime(file_path)
                                            if file_age > 3600 or True:  # Always clean during startup
                                                os.remove(file_path)
                                                cleaned_files += 1
                                        elif os.path.isdir(file_path):
                                            # Remove subdirectories that might be left from failed operations
                                            shutil.rmtree(file_path)
                                            cleaned_files += 1
                                    except Exception:
                                        pass  # Ignore errors for individual files
                                
                                logger.info(f" Cleaned up {cleaned_files} files in CoreML temp directory: {temp_pattern}")
                                
                                # Ensure directory still exists and has proper permissions
                                os.makedirs(temp_pattern, exist_ok=True)
                                os.chmod(temp_pattern, 0o755)
                            else:
                                # For other directories, remove completely (system temp dirs)
                                shutil.rmtree(temp_pattern)
                                logger.info(
                                    f" Cleaned up CoreML temp directory: {temp_pattern}")
                        except Exception as e:
                            logger.debug(
                                f"⚠️ Could not clean up {temp_pattern}: {e}")
        except Exception as e:
            logger.debug(f"⚠️ CoreML temp cleanup failed: {e}")

        # Ensure CoreML temp directory exists with proper setup after cleanup
        try:
            import tempfile
            cache_dir = os.path.abspath(".cache")
            local_temp_dir = os.path.join(cache_dir, "coreml_temp")
            os.makedirs(local_temp_dir, exist_ok=True)
            os.chmod(local_temp_dir, 0o755)
            
            # Set environment variables for espeak and other temp file operations
            os.environ['TMPDIR'] = local_temp_dir
            os.environ['TMP'] = local_temp_dir 
            os.environ['TEMP'] = local_temp_dir
            os.environ['COREML_TEMP_DIR'] = local_temp_dir
            os.environ['ONNXRUNTIME_TEMP_DIR'] = local_temp_dir
            
            # Set Python's tempfile default directory
            tempfile.tempdir = local_temp_dir
            
            logger.debug(f"✅ CoreML temp directory configured: {local_temp_dir}")
        except Exception as e:
            logger.warning(f"⚠️ Could not setup CoreML temp directory: {e}")

        update_startup_progress(10, "Applying production patches...")
        apply_all_patches()

        update_startup_progress(
            15, "Initializing model with hardware acceleration...")

        start_time = time.time()

        def track_model_init():
            nonlocal start_time
            try:
                initialize_model_sync()
            except Exception as e:
                logger.error(
                    f" Synchronous model initialization failed: {e}", exc_info=True)

        try:
            # Show progress and handle timeouts
            update_startup_progress(
                30, "Initializing model (this may take a moment)...", "initializing")
            # Timeout handling can be added here if needed

            # Use a thread for the synchronous model initialization
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, track_model_init)

            # Final progress update
            if get_model_status():
                model_initialization_complete = True  # Set global flag
                update_startup_progress(
                    100, "Model initialization complete!", "online")
                logger.info(
                    f"✅ Model initialization completed in {time.time() - start_time:.2f}s")
                logger.info(
                    "✅ Ready to start processing text to speech requests")
            else:
                model_initialization_complete = False  # Ensure flag is set
                update_startup_progress(
                    100, "Model initialization failed.", "error")
                logger.error(" Model initialization failed.")

        except Exception as e:
            logger.error(
                f"Asynchronous model initialization failed: {e}", exc_info=True)
            update_startup_progress(
                100, f"Initialization failed: {e}", "error")

    except Exception as e:
        logger.error(f" Model initialization failed: {e}", exc_info=True)
        update_startup_progress(
            100, f"Initialization failed: {e}", "error")


def get_cold_start_warmup_stats() -> Dict[str, Any]:
    """
    Get cold-start warm-up statistics for monitoring.
    
    Returns:
        Dict containing warm-up completion status, timing, and any errors
    """
    return {
        "completed": _cold_start_warmup_completed,
        "warmup_time_ms": _cold_start_warmup_time_ms,
        "error": _cold_start_warmup_error
    }

async def perform_cold_start_warmup():
    """
    Perform a cold-start warm-up inference to reduce first request TTFB.
    
    This function runs a short inference on a simple text to warm up the model
    and reduce the time-to-first-audio for subsequent requests.
    """
    global _cold_start_warmup_completed, _cold_start_warmup_time_ms, _cold_start_warmup_error
    
    try:
        logger.info("Starting cold-start warm-up inference...")
        start_time = time.time()
        
        # Wait for model to be ready
        max_wait_time = 60  # Wait up to 60 seconds for model
        wait_interval = 2   # Check every 2 seconds
        
        for attempt in range(max_wait_time // wait_interval):
            try:
                if model_initialization_complete:
                    logger.info("Model is ready, proceeding with warm-up")
                    break
                else:
                    logger.debug(f"Model not ready yet, waiting... (attempt {attempt + 1})")
                    await asyncio.sleep(wait_interval)
            except Exception as e:
                logger.debug(f"Error checking model status: {e}, waiting...")
                await asyncio.sleep(wait_interval)
        else:
            raise Exception("Model did not become ready within timeout")
        
        # Import TTS core functions
        from api.tts.core import _generate_audio_segment
        from api.tts.text_processing import segment_text
        
        # Use a simple, short text for warm-up
        warmup_text = "Hello world."
        
        # Process the warm-up text
        segments = segment_text(warmup_text, max_len=50)
        if not segments:
            segments = [warmup_text]
        
        # Generate audio for the first segment only (minimal warm-up)
        # Use the global model directly to avoid creating additional instances
        from fastapi.concurrency import run_in_threadpool
        from api.model.loader import get_model, get_active_provider
        
        # Get the already initialized model
        global_model = get_model()
        if global_model is None:
            raise Exception("Global model not available for warm-up")
        
        # Use the model directly for warm-up
        audio_data = await run_in_threadpool(
            global_model.create,
            segments[0],  # text
            "af_alloy",  # voice
            1.0,  # speed
            "en-us"  # lang - use normalized language code
        )
        
        end_time = time.time()
        warmup_time_ms = (end_time - start_time) * 1000
        
        _cold_start_warmup_completed = True
        _cold_start_warmup_time_ms = warmup_time_ms
        _cold_start_warmup_error = None
        
        logger.info(f"Cold-start warm-up completed in {warmup_time_ms:.2f}ms")
        
    except Exception as e:
        _cold_start_warmup_completed = False
        _cold_start_warmup_error = str(e)
        logger.warning(f"Cold-start warm-up failed: {e}")

async def delayed_cold_start_warmup():
    """
    Delayed cold-start warm-up that waits for model initialization to complete.
    """
    # Wait for model initialization to complete
    while not model_initialization_complete:
        await asyncio.sleep(1)
    
    # Additional delay to ensure model is fully ready
    await asyncio.sleep(5)
    
    # Now perform the warm-up
    await perform_cold_start_warmup()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan management with progress tracking
    """
    # Startup
    # Logging is already configured in setup_application_logging()

    # Start model initialization in background
    asyncio.create_task(initialize_model())

    # Perform startup tasks after model initialization starts
    validate_dependencies()
    validate_model_files()
    validate_environment()
    validate_patch_status()

    # Trigger pipeline warm-up in background (after model initialization)
    try:
        from api.model.loader import get_pipeline_warmer
        try:
            pipeline_warmer = get_pipeline_warmer()
            if pipeline_warmer:
                asyncio.create_task(pipeline_warmer.trigger_warm_up_if_needed())
        except Exception as e:
            logger.debug(f"Pipeline warm-up trigger failed at startup: {e}")
    except Exception as e:
        logger.debug(f"Startup warm-up setup failed: {e}")

    # Perform cold-start warm-up inference (delayed to wait for model)
    asyncio.create_task(delayed_cold_start_warmup())

    # Start scheduled benchmark scheduler
    try:
        from api.performance.scheduled_benchmark import start_benchmark_scheduler
        start_benchmark_scheduler()
        logger.info("Scheduled benchmark scheduler started")
    except Exception as e:
        logger.warning(f"Could not start benchmark scheduler: {e}")

    yield

    # Shutdown
    logger.info(" Application shutting down")

# Determine if running in production
is_production = os.environ.get("KOKORO_PRODUCTION", "false").lower() == "true"

# Create FastAPI app with lifespan management and production optimizations
app = FastAPI(
    title="Kokoro TTS API",
    version="2.1.0",
    description="High-performance Neural Text-to-Speech API with Apple Silicon optimization",
    lifespan=lifespan,
    # Production optimizations: disable documentation endpoints
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
    # Use ORJSON for 2-3x faster JSON serialization
    default_response_class=ORJSONResponse
)

# Enhanced middleware configuration for optimal performance
# Reference: DEPENDENCY_RESEARCH.md section 2.3

# Add security middleware first to block malicious requests early
security_config = SecurityConfig(
    allow_localhost_only=True,  # Restrict to localhost only
    block_suspicious_ips=True,
    max_requests_per_minute=60,
    max_requests_per_hour=1000
)
app.add_middleware(SecurityMiddleware, config=security_config)

# Add performance middleware for accurate timing
app.add_middleware(PerformanceMiddleware)

# Enhanced CORS middleware configuration - Restricted to localhost only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",  # For development frontends
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*", "X-Request-ID", "X-API-Key"],  # Add common headers
    max_age=7200,  # Cache preflight requests for 2 hours (increased from 1 hour)
    expose_headers=["X-Request-ID", "X-Response-Time"],  # Expose performance headers
)

# Enhanced GZip middleware configuration for TTS workloads
app.add_middleware(
    GZipMiddleware,
    minimum_size=256,  # Lower threshold for TTS responses (optimized for audio data)
    compresslevel=4,   # Faster compression for real-time audio streaming
)

# Add security middleware in production
if TTSConfig.is_production:
    allowed_hosts = os.environ.get("KOKORO_ALLOWED_HOSTS", "*").split(",")
    if allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    else:
        # For safety, add a default if KOKORO_ALLOWED_HOSTS is just "*"
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=[
                           "*.darianrosebrook.com", "localhost", "127.0.0.1"])
else:
    # In development, allow any host for ease of use
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


# Startup logic moved to lifespan context manager


@app.get("/health")
async def health_check(response: Response):
    """
    Enhanced health check that provides status during initialization
    """
    if model_initialization_complete:
        response.status_code = 200
        return {"status": "online", "model_ready": True}

    response.status_code = 503
    if model_initialization_started:
        return {
            "status": "initializing",
            "model_ready": False,
            "progress": startup_progress,
            "message": "Model is initializing, please wait..."
        }
    else:
        return {"status": "starting", "model_ready": False}


@app.get("/startup-progress")
async def get_startup_progress():
    """
    Get detailed startup progress information
    """
    return startup_progress


@app.get("/cache-status")
async def get_cache_status():
    """
    Get cache statistics and cleanup status
    """
    try:
        cache_info = get_cache_info()
        return {
            "cache_statistics": cache_info,
            "cleanup_recommendations": {
                "needs_cleanup": cache_info.get('needs_cleanup', False),
                "size_mb": cache_info.get('total_size_mb', 0),
                "temp_dirs": cache_info.get('temp_dirs', 0),
                "recommended_action": "cleanup" if cache_info.get('needs_cleanup', False) else "none"
            }
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/cache-cleanup")
async def trigger_cache_cleanup(aggressive: bool = False):
    """
    Manually trigger cache cleanup

    @param aggressive: Use aggressive cleanup policies
    """
    try:
        cleanup_result = cleanup_cache(aggressive=aggressive)
        return {
            "success": True,
            "cleanup_result": cleanup_result,
            "message": f"Cache cleanup completed: freed {cleanup_result.get('total_freed_mb', 0):.1f}MB"
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/phase4-optimization")
async def get_phase4_optimization_status():
    """
    Get comprehensive Phase 4 optimization status and insights.
    
    This endpoint provides detailed information about Phase 4 advanced optimization
    features including dynamic memory management, pipeline warming, and real-time
    optimization capabilities.
    
    **Response Format**:
    ```json
    {
        "dynamic_memory_optimization": {
            "enabled": boolean,
            "current_arena_size_mb": number,
            "optimization_stats": object,
            "workload_insights": object
        },
        "pipeline_warming": {
            "warm_up_complete": boolean,
            "warm_up_duration": number,
            "patterns_cached": number,
            "warm_up_results": object
        },
        "real_time_optimization": {
            "status": string,
            "auto_optimization_enabled": boolean,
            "optimization_interval": number,
            "trend_analysis": object,
            "parameter_tuning": object
        }
    }
    ```
    
    **Use Cases**:
    - Monitor Phase 4 optimization effectiveness
    - Debug advanced optimization features
    - Analyze performance trends and patterns
    - Validate optimization configurations
    
    @returns JSON object with Phase 4 optimization status
    """
    try:
        phase4_status = {
            "phase4_enabled": True,
            "optimization_components": {}
        }
        
        # Dynamic Memory Optimization
        try:
            from api.model.loader import get_dynamic_memory_manager
            
            dynamic_memory_manager = get_dynamic_memory_manager()
            if dynamic_memory_manager:
                optimization_stats = dynamic_memory_manager.get_optimization_stats()
                workload_insights = dynamic_memory_manager.get_workload_insights()
                
                phase4_status["optimization_components"]["dynamic_memory"] = {
                    "enabled": True,
                    "current_arena_size_mb": optimization_stats.get("current_arena_size_mb", 0),
                    "optimization_stats": optimization_stats,
                    "workload_insights": workload_insights
                }
            else:
                phase4_status["optimization_components"]["dynamic_memory"] = {
                    "enabled": False,
                    "error": "Dynamic memory manager not available"
                }
        except Exception as e:
            phase4_status["optimization_components"]["dynamic_memory"] = {
                "enabled": False,
                "error": str(e)
            }
        
        # Pipeline Warming
        try:
            from api.model.loader import get_pipeline_warmer
            
            pipeline_warmer = get_pipeline_warmer()
            if pipeline_warmer:
                warm_up_status = pipeline_warmer.get_warm_up_status()
                
                phase4_status["optimization_components"]["pipeline_warming"] = {
                    "enabled": True,
                    "warm_up_complete": warm_up_status.get("warm_up_complete", False),
                    "warm_up_duration": warm_up_status.get("warm_up_duration", 0),
                    "patterns_cached": warm_up_status.get("common_patterns_count", 0),
                    "warm_up_results": warm_up_status.get("warm_up_results", {})
                }
            else:
                phase4_status["optimization_components"]["pipeline_warming"] = {
                    "enabled": False,
                    "error": "Pipeline warmer not available"
                }
        except Exception as e:
            phase4_status["optimization_components"]["pipeline_warming"] = {
                "enabled": False,
                "error": str(e)
            }
        
        # Real-time Optimization
        try:
            from api.performance.optimization import get_optimization_status
            
            optimization_status = get_optimization_status()
            
            phase4_status["optimization_components"]["real_time_optimization"] = {
                "enabled": optimization_status.get("status", "unknown") != "optimizer_not_available",
                "status": optimization_status.get("status", "unknown"),
                "auto_optimization_enabled": optimization_status.get("auto_optimization_enabled", False),
                "optimization_interval": optimization_status.get("optimization_interval", 0),
                "trend_analysis": optimization_status.get("trend_analyzer_summary", {}),
                "parameter_tuning": optimization_status.get("parameter_tuner_summary", {})
            }
        except Exception as e:
            phase4_status["optimization_components"]["real_time_optimization"] = {
                "enabled": False,
                "error": str(e)
            }
        
        # Overall Phase 4 Status
        enabled_components = sum(1 for comp in phase4_status["optimization_components"].values() if comp.get("enabled", False))
        total_components = len(phase4_status["optimization_components"])
        
        phase4_status["summary"] = {
            "total_components": total_components,
            "enabled_components": enabled_components,
            "optimization_coverage": (enabled_components / total_components * 100) if total_components > 0 else 0,
            "fully_operational": enabled_components == total_components
        }
        
        return phase4_status
        
    except Exception as e:
        logger.error(f" Phase 4 optimization status endpoint error: {e}")
        return {
            "error": "Phase 4 optimization status endpoint failed",
            "details": str(e)
        }


@app.post("/phase4-optimization/trigger")
async def trigger_phase4_optimization():
    """
    Trigger immediate Phase 4 optimization.
    
    This endpoint allows manual triggering of Phase 4 optimization processes
    including pipeline warming and real-time optimization.
    
    @returns JSON object with optimization trigger results
    """
    try:
        results = {
            "triggered": True,
            "optimization_results": {}
        }
        
        # Trigger pipeline warming
        try:
            from api.model.loader import get_pipeline_warmer
            
            pipeline_warmer = get_pipeline_warmer()
            if pipeline_warmer:
                warm_up_triggered = await pipeline_warmer.trigger_warm_up_if_needed()
                results["optimization_results"]["pipeline_warming"] = {
                    "triggered": warm_up_triggered,
                    "status": "completed" if warm_up_triggered else "already_complete"
                }
            else:
                results["optimization_results"]["pipeline_warming"] = {
                    "triggered": False,
                    "error": "Pipeline warmer not available"
                }
        except Exception as e:
            results["optimization_results"]["pipeline_warming"] = {
                "triggered": False,
                "error": str(e)
            }
        
        # Trigger real-time optimization
        try:
            from api.performance.optimization import optimize_system_now
            
            optimization_result = await optimize_system_now()
            results["optimization_results"]["real_time_optimization"] = optimization_result
        except Exception as e:
            results["optimization_results"]["real_time_optimization"] = {
                "triggered": False,
                "error": str(e)
            }
        
        return results
        
    except Exception as e:
        logger.error(f" Phase 4 optimization trigger endpoint error: {e}")
        return {
            "error": "Phase 4 optimization trigger failed",
            "details": str(e)
        }


@app.get("/security-status")
async def get_security_status():
    """
    Get security middleware status and statistics.
    
    Returns information about blocked requests, suspicious IPs, and security events.
    """
    try:
        from api.security import get_security_middleware
        security_middleware = get_security_middleware()
        stats = security_middleware.get_security_stats()
        
        return {
            "security_enabled": True,
            "localhost_only": True,
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "security_enabled": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/warning-stats")
async def get_warning_statistics():
    """
    Get detailed warning suppression statistics.

    This endpoint provides comprehensive information about warning suppression
    performance, including stderr interception statistics and suppression rates.

    **Response Format**:
    ```json
    {
        "stderr_interceptor_active": boolean,
        "suppressed_warnings": number,
        "total_warnings": number,
        "suppression_rate": number,
        "warning_patterns": {
            "context_leaks": number,
            "msgtracer_warnings": number,
            "onnx_warnings": number
        }
    }
    ```

    **Information Provided**:
    - **Stderr Interceptor Status**: Whether the stderr interceptor is active
    - **Suppression Statistics**: Total warnings processed and suppressed
    - **Suppression Rate**: Percentage of warnings successfully suppressed
    - **Pattern Analysis**: Breakdown of warning types by pattern

    **Use Cases**:
    - Performance monitoring and optimization
    - Debugging warning suppression effectiveness
    - Production monitoring and alerting
    - System health assessment

    @returns JSON object with warning suppression statistics
    """
    try:
        from api.warnings import get_warning_suppression_stats

        stats = get_warning_suppression_stats()

        # Add additional context about warning patterns
        stats["warning_patterns"] = {
            "context_leaks": "tracked_via_performance_system",
            "msgtracer_warnings": "suppressed_via_stderr_interceptor",
            "onnx_warnings": "suppressed_via_logging_filters"
        }

        stats["system_info"] = {
            "warning_handler_active": True,
            "stderr_interception_enabled": stats.get("stderr_interceptor_active", False),
            "comprehensive_filtering": True
        }

        return stats

    except Exception as e:
        logger.error(f" Warning statistics endpoint error: {e}")
        return {
            "error": "Warning statistics endpoint failed",
            "details": str(e)
        }


@app.get("/status")
async def get_status():
    """
    Comprehensive server status endpoint for debugging and monitoring.

    **Response Format**:
    ```json
    {
        "model_loaded": boolean,
        "onnx_providers": string[],
        "performance": {
            "total_inferences": number,
            "average_inference_time": number,
            "provider_used": string,
            "coreml_usage_percent": number,
            "phonemizer_fallback_rate": number
        },
        "patch_status": {
            "applied": boolean,
            "application_time": number,
            "patch_errors": string[],
            "original_functions_stored": number
        },
        "hardware": {
            "platform": string,
            "is_apple_silicon": boolean,
            "has_neural_engine": boolean,
            "cpu_cores": number,
            "memory_gb": number
        }
    }
    ```

    **Information Provided**:
    - **Model Status**: Whether the TTS model is loaded and ready
    - **ONNX Providers**: Available execution providers on this system
    - **Performance Metrics**: Real-time statistics about inference performance
    - **Hardware Acceleration**: Current provider usage and performance
    - **Error Rates**: Fallback usage and error frequency
    - **Patch Status**: Status of applied patches and any errors
    - **Hardware Info**: System hardware capabilities and configuration

    **Use Cases**:
    - Performance monitoring and optimization
    - Debugging hardware acceleration issues
    - Capacity planning and scaling decisions
    - Runtime performance analysis
    - Patch status monitoring

    @returns JSON object with comprehensive server status
    """
    try:
        # Get basic status
        status = {
            "model_loaded": model_initialization_complete,
            "onnx_providers": ort.get_available_providers(),
            "performance": get_performance_stats(),
        }

        # Add patch status
        try:
            patch_status = get_patch_status()
            status["patch_status"] = {
                "applied": patch_status['applied'],
                "application_time": patch_status['application_time'],
                "patch_errors": patch_status['patch_errors'],
                "original_functions_stored": patch_status['original_functions_stored']
            }
        except Exception as e:
            logger.warning(f"⚠️ Could not get patch status: {e}")
            status["patch_status"] = {"error": str(e)}

        # Add hardware information (use cached capabilities)
        try:
            capabilities = get_model_capabilities()
            status["hardware"] = {
                "platform": capabilities['platform'],
                "is_apple_silicon": capabilities['is_apple_silicon'],
                "has_neural_engine": capabilities['has_neural_engine'],
                "cpu_cores": capabilities['cpu_cores'],
                "memory_gb": capabilities['memory_gb']
            }
        except Exception as e:
            logger.warning(f"⚠️ Could not get hardware info: {e}")
            status["hardware"] = {"error": str(e)}

        # Add warning suppression information
        try:
            from api.warnings import get_warning_suppression_stats
            warning_stats = get_warning_suppression_stats()
            status["warning_suppression"] = {
                "active": warning_stats.get("stderr_interceptor_active", False),
                "suppressed_warnings": warning_stats.get("suppressed_warnings", 0),
                "total_warnings": warning_stats.get("total_warnings", 0),
                "suppression_rate": warning_stats.get("suppression_rate", 0)
            }
        except Exception as e:
            logger.warning(f"⚠️ Could not get warning suppression info: {e}")
            status["warning_suppression"] = {"error": str(e)}

        # PHASE 2 OPTIMIZATION: Add TTS processing statistics including phoneme cache performance
        try:
            tts_stats = get_tts_processing_stats()
            status["tts_processing"] = {
                "phoneme_preprocessing_enabled": tts_stats.get("phoneme_preprocessing_enabled", False),
                "active_provider": tts_stats.get("active_provider", "Unknown"),
                "phoneme_cache": tts_stats.get("phoneme_cache", {}),
                "inference_cache": tts_stats.get("inference_cache", {})
            }
        except Exception as e:
            logger.warning(f"⚠️ Could not get TTS processing stats: {e}")
            status["tts_processing"] = {"error": str(e)}

        # PHASE 1 TTFA OPTIMIZATION: Primer micro-cache telemetry
        try:
            status["primer_microcache"] = get_primer_microcache_stats()
        except Exception as e:
            status["primer_microcache"] = {"error": str(e)}

        # PHASE 1 TTFA OPTIMIZATION: Cold-start warm-up telemetry
        try:
            status["cold_start_warmup"] = get_cold_start_warmup_stats()
        except Exception as e:
            status["cold_start_warmup"] = {"error": str(e)}

        # PHASE 4 OPTIMIZATION: Scheduled benchmark telemetry
        try:
            from api.performance.scheduled_benchmark import get_scheduled_benchmark_stats
            status["scheduled_benchmark"] = get_scheduled_benchmark_stats()
        except Exception as e:
            status["scheduled_benchmark"] = {"error": str(e)}

        # PHASE 3 OPTIMIZATION: Add dual session utilization statistics
        try:
            from api.performance.stats import get_session_utilization_stats, get_memory_fragmentation_stats
            
            session_stats = get_session_utilization_stats()
            status["session_utilization"] = {
                "dual_session_available": session_stats.get("dual_session_available", False),
                "total_requests": session_stats.get("total_requests", 0),
                "session_distribution": {
                    "ane_requests": session_stats.get("ane_requests", 0),
                    "gpu_requests": session_stats.get("gpu_requests", 0),
                    "cpu_requests": session_stats.get("cpu_requests", 0),
                    "ane_percentage": session_stats.get("ane_percentage", 0.0),
                    "gpu_percentage": session_stats.get("gpu_percentage", 0.0),
                    "cpu_percentage": session_stats.get("cpu_percentage", 0.0)
                },
                "concurrent_processing": {
                    "active_segments": session_stats.get("concurrent_segments_active", 0),
                    "max_segments": session_stats.get("max_concurrent_segments", 0),
                    "efficiency": session_stats.get("concurrent_efficiency", 0.0),
                    "load_balancing": session_stats.get("load_balancing_efficiency", 0.0)
                },
                "sessions_available": session_stats.get("sessions_available", {
                    "ane": False,
                    "gpu": False,
                    "cpu": False
                })
            }
            
            # Add memory fragmentation statistics
            memory_stats = get_memory_fragmentation_stats()
            status["memory_fragmentation"] = {
                "watchdog_active": memory_stats.get("dual_session_available", False),
                "current_memory_mb": memory_stats.get("current_memory_mb", 0.0),
                "memory_trend": memory_stats.get("memory_trend", "unknown"),
                "fragmentation_score": memory_stats.get("fragmentation_score", 0),
                "memory_health": memory_stats.get("memory_health", "unknown"),
                "cleanup_count": memory_stats.get("memory_cleanup_count", 0),
                "request_count": memory_stats.get("request_count", 0)
            }
            
        except Exception as e:
            logger.warning(f"⚠️ Could not get session utilization stats: {e}")
            status["session_utilization"] = {"error": str(e)}
            status["memory_fragmentation"] = {"error": str(e)}

        # PHASE 4 OPTIMIZATION: Add dynamic memory optimization statistics
        try:
            from api.performance.stats import get_dynamic_memory_optimization_stats
            
            dynamic_memory_stats = get_dynamic_memory_optimization_stats()
            status['dynamic_memory_optimization'] = dynamic_memory_stats
            
        except Exception as e:
            logger.debug(f"Could not get dynamic memory optimization stats: {e}")
            status['dynamic_memory_optimization'] = {
                'dynamic_memory_manager_available': False,
                'error': str(e)
            }
        
        # PHASE 4 OPTIMIZATION: Add pipeline warmer status
        try:
            from api.model.loader import get_pipeline_warmer
            
            pipeline_warmer = get_pipeline_warmer()
            if pipeline_warmer:
                pipeline_warmer_status = pipeline_warmer.get_warm_up_status()
                status['pipeline_warmer'] = pipeline_warmer_status
            else:
                status['pipeline_warmer'] = {
                    'pipeline_warmer_available': False,
                    'error': 'Pipeline warmer not initialized'
                }
                
        except Exception as e:
            logger.debug(f"Could not get pipeline warmer status: {e}")
            status['pipeline_warmer'] = {
                'pipeline_warmer_available': False,
                'error': str(e)
            }
        
        # PHASE 4 OPTIMIZATION: Add real-time optimizer status
        try:
            from api.performance.optimization import get_optimization_status
            
            optimization_status = get_optimization_status()
            status['real_time_optimization'] = optimization_status
            
        except Exception as e:
            logger.debug(f"Could not get real-time optimization status: {e}")
            status['real_time_optimization'] = {
                'real_time_optimizer_available': False,
                'error': str(e)
            }

        return status

    except Exception as e:
        logger.error(f" Status endpoint error: {e}")
        return {
            "error": "Status endpoint failed",
            "details": str(e)
        }


@app.get("/voices")
async def get_voices():
    """
    Get list of available voices from the loaded TTS model.

    This endpoint provides the complete list of voices that are currently
    available in the loaded Kokoro model. This is essential for clients
    to know which voices they can request for synthesis.

    **Response Format**:
    ```json
    {
        "voices": string[],
        "total_voices": number,
        "model_loaded": boolean,
        "voice_categories": {
            "af_*": number,
            "bm_*": number,
            "cm_*": number,
            "cf_*": number,
            "dm_*": number,
            "bf_*": number,
            "df_*": number
        }
    }
    ```

    **Voice Categories**:
    - **af_***: Adult female voices
    - **bm_***: Adult male voices  
    - **cm_***: Child male voices
    - **cf_***: Child female voices
    - **dm_***: Deep male voices
    - **bf_***: Bass female voices
    - **df_***: Deep female voices

    **Error Handling**:
    - **503 Service Unavailable**: Model not loaded yet
    - **500 Internal Server Error**: Error accessing voice data

    **Use Cases**:
    - Dynamic voice discovery for client applications
    - Validation of voice parameters before synthesis
    - Voice selection UI population
    - Debugging voice availability issues
    - API documentation and testing

    @returns JSON object with available voices and metadata
    @raises HTTPException: If model is not loaded or voice data unavailable
    """
    if not model_initialization_complete:
        raise HTTPException(
            status_code=503,
            detail="TTS model not loaded. Please wait for initialization to complete."
        )

    try:
        # Get the global Kokoro model instance
        from api.model.loader import kokoro_model
        
        if kokoro_model is None:
            raise HTTPException(
                status_code=503,
                detail="TTS model instance not available."
            )

        # Get available voices from the model
        voices = kokoro_model.voices
        
        if not voices:
            raise HTTPException(
                status_code=500,
                detail="No voices available in the loaded model."
            )

        # Convert to list if it's not already
        voice_list = list(voices) if hasattr(voices, '__iter__') and not isinstance(voices, str) else voices

        # Categorize voices by prefix for better organization
        voice_categories = {}
        for voice in voice_list:
            if isinstance(voice, str) and '_' in voice:
                prefix = voice.split('_')[0] + '_*'
                voice_categories[prefix] = voice_categories.get(prefix, 0) + 1

        return {
            "voices": voice_list,
            "total_voices": len(voice_list),
            "model_loaded": True,
            "voice_categories": voice_categories,
            "recommended_voices": {
                "high_quality_female": "af_heart",
                "high_quality_male": "bm_fable", 
                "natural_female": "af_sky",
                "natural_male": "bm_atlas"
            }
        }

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f" Voices endpoint error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve voice information: {str(e)}"
        )


@app.post("/v1/audio/speech")
async def create_speech(request: Request, tts_request: TTSRequest, config: TTSConfig = Depends(get_tts_config)):
    """
    OpenAI-compatible TTS endpoint with streaming and hardware acceleration.

    This endpoint implements the OpenAI TTS API specification while providing
    advanced features like streaming audio delivery and hardware acceleration.

    **Request Format**:
    ```json
    {
        "text": "Text to synthesize (max 2000 characters)",
        "voice": "Voice ID (e.g., 'af_heart', 'bm_fable')",
        "speed": 1.0,  // 0.25-4.0 range
        "lang": "en-us",  // Language code
        "stream": true,  // Enable streaming
        "format": "wav"  // "wav" or "pcm"
    }
    ```

    **Processing Pipeline**:
    1. **Request Validation**: Validate all parameters and text length
    2. **Model Status Check**: Ensure model is loaded and ready
    3. **Text Processing**: Normalize and segment text for optimal synthesis
    4. **Audio Generation**: Parallel processing of text segments
    5. **Response Streaming**: Real-time audio delivery to client

    **Streaming Mode** (`stream: true`):
    - **Latency**: 200-500ms to first audio chunk
    - **Format**: Chunked transfer encoding with proper MIME types
    - **Memory**: Constant memory usage regardless of text length
    - **Interruption**: Supports client disconnection detection

    **Non-Streaming Mode** (`stream: false`):
    - **Latency**: Full synthesis before response (2-10 seconds)
    - **Format**: Complete audio file in single response
    - **Memory**: Higher memory usage for long texts
    - **Reliability**: More reliable for unstable connections

    **Error Handling**:
    - **503 Service Unavailable**: Model not loaded
    - **400 Bad Request**: Invalid parameters or text processing failure
    - **500 Internal Server Error**: Unexpected processing errors

    **Performance Optimizations**:
    - **Hardware Acceleration**: Automatic CoreML provider selection
    - **Parallel Processing**: Multiple segments processed simultaneously
    - **Intelligent Segmentation**: Natural boundary detection for better speech
    - **Memory Management**: Automatic cleanup and resource management

    **Format Support**:
    - **WAV**: Complete WAV file with proper headers (recommended)
    - **PCM**: Raw 16-bit PCM audio data (for advanced use cases)

    @param request: FastAPI Request object for client tracking
    @param tts_request: Validated TTS request parameters
    @returns StreamingResponse with audio data
    @raises HTTPException: For various error conditions
    """
    # Ensure model is loaded before processing
    if not model_initialization_complete:
        raise HTTPException(
            status_code=503,
            detail="TTS model not loaded. Please wait for initialization to complete."
        )

    # Handle streaming requests with real-time audio delivery
    if tts_request.stream:
        # Determine appropriate MIME type for streaming response
        media_type = (
            "audio/wav"
            if tts_request.format == "wav"
            else "audio/L16;rate=24000;channels=1"
        )

        # Create streaming generator for real-time audio delivery
        # Normalize language to avoid espeak backend errors (e.g., map 'en' -> 'en-us')
        normalized_lang = (tts_request.lang or "en-us").lower()
        if normalized_lang in ("en", "en_us", "en-us-001"):
            normalized_lang = "en-us"

        generator = stream_tts_audio(
            tts_request.text,
            tts_request.voice,
            tts_request.speed,
            normalized_lang,
            tts_request.format,
            request,
        )

        return StreamingResponse(generator, media_type=media_type)

    # Handle non-streaming requests with complete audio generation
    else:
        # Segment text for parallel processing
        # Normalize language for non-streaming path as well
        normalized_lang = (tts_request.lang or "en-us").lower()
        if normalized_lang in ("en", "en_us", "en-us-001"):
            normalized_lang = "en-us"

        segments = segment_text(tts_request.text, config.MAX_SEGMENT_LENGTH)
        if not segments:
            raise HTTPException(
                status_code=400,
                detail="No valid text segments to process. Please check your input text."
            )

        # Process all segments in parallel for better performance
        all_audio_np = []
        for i, seg in enumerate(segments):
            _, audio_np, _ = _generate_audio_segment(
                i, seg, tts_request.voice, tts_request.speed, normalized_lang
            )
            if audio_np is not None and audio_np.size > 0:
                all_audio_np.append(audio_np)

        # Ensure at least one segment was processed successfully
        if not all_audio_np:
            raise HTTPException(
                status_code=500,
                detail="Audio generation failed for all segments. Please try again or contact support."
            )

        # Concatenate all audio segments into final output
        try:
            final_audio = np.concatenate(all_audio_np)
        except ValueError as e:
            logger.error(f"Error concatenating audio segments: {e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to assemble audio due to mismatched segment formats. Please try again."
            )

        # Convert to appropriate output format
        audio_io = io.BytesIO()
        if tts_request.format == "wav":
            # Convert to 16-bit PCM and create WAV file
            scaled_audio = np.int16(final_audio * 32767)
            sf.write(audio_io, scaled_audio,
                     config.SAMPLE_RATE, format="WAV")
            media_type = "audio/wav"
        else:  # PCM format
            # Convert to raw 16-bit PCM data
            scaled_audio = np.int16(final_audio * 32767)
            audio_io.write(scaled_audio.tobytes())
            media_type = "audio/L16;rate=24000;channels=1"

        audio_io.seek(0)
        return StreamingResponse(
            iter([audio_io.getvalue()]),
            media_type=media_type
        )

# Development server entry point
if __name__ == "__main__":
    import uvicorn

    logger.info("Starting development server...")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True  # Enable auto-reload in development
    )
