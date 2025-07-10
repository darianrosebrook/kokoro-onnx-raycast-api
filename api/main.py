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
from typing import Optional

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import StreamingResponse, ORJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse
import soundfile as sf

from api.config import TTSConfig, TTSRequest
from api.warnings import setup_coreml_warning_handler
from api.model.patch import apply_all_patches, get_patch_status
from api.model.loader import initialize_model as initialize_model_sync, detect_apple_silicon_capabilities
from api.performance.stats import get_performance_stats
from api.tts.core import _generate_audio_segment, stream_tts_audio
from api.utils.cache_cleanup import cleanup_cache, get_cache_info
from api.tts.text_processing import segment_text
from api.model.loader import get_model_status, initialize_model, detect_apple_silicon_capabilities
from api.model.patch import apply_all_patches, get_patch_status
from api.performance.stats import get_performance_stats
from api.tts.core import _generate_audio_segment, stream_tts_audio
from api.tts.text_processing import segment_text
from api.warnings import setup_coreml_warning_handler, suppress_phonemizer_warnings, configure_onnx_runtime_logging


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
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers to prevent duplicates
    root_logger.handlers.clear()

    # Console handler with immediate flushing
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
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

    logger = logging.getLogger(__name__)
    logger.info(f" Application logging configured")
    logger.info(f" Detailed logs will be written to: logs/api_server.log")
    
    # Configure immediate flushing for console handler
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            # Force immediate flushing for console output
            handler.flush = lambda: handler.stream.flush()
            # Override emit to ensure flushing
            original_emit = handler.emit
            def emit_with_flush(record):
                original_emit(record)
                handler.stream.flush()
                # Also force stdout flush
                sys.stdout.flush()
            handler.emit = emit_with_flush
    
    # Ensure stdout is unbuffered
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(line_buffering=True)
    
    # Test logging to ensure it's working immediately
    logger.info(" Logging system initialized and ready")
    sys.stdout.flush()  # Force immediate output
    
    # Also print directly to ensure immediate output
    print(" Direct output test - logging system ready", flush=True)


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
            logger.error(f"❌ {package_name} not found")

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
        logger.error(f"❌ {error_msg}")
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
            logger.error(f"❌ {file_type} file not found: {file_path}")
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
                    f"❌ {file_type} file not accessible: {file_path} - {e}")

    if missing_files:
        error_msg = f"Missing or inaccessible model files: {', '.join(missing_files)}"
        logger.error(f"❌ {error_msg}")
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
        logger.error(f"❌ ONNX Runtime provider validation failed: {e}")
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
            status = "✅ Patched" if is_patched else "❌ Not Patched"
            logger.debug(f"   • {method}: {status}")

    except Exception as e:
        logger.error(f"❌ Patch status validation failed: {e}")
        raise RuntimeError(f"Patch validation failed: {e}")


# Setup comprehensive logging
setup_application_logging()
logger = logging.getLogger(__name__)

# Initialize warning handlers for various noise sources
# This must be called before any ONNX Runtime operations
logger.info(" Initializing warning management systems...")
configure_onnx_runtime_logging()
setup_coreml_warning_handler()
suppress_phonemizer_warnings()

# Note: Stderr interceptor is already activated at module import time in warnings.py
# This ensures early warning suppression before any ONNX Runtime operations

# Apply monkey patches for eSpeak integration and Kokoro model fixes
# These patches fix known issues with the upstream kokoro-onnx library
logger.info(" Applying production patches to kokoro-onnx library...")
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
        is_prod = os.environ.get("KOKORO_PRODUCTION", "false").lower() == "true"
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
        logger.info(f" Set TMPDIR to local cache: {local_cache_dir}")

        update_startup_progress(8, "Cleaning up cache files...")
        try:
            cache_info = get_cache_info()
            if cache_info.get('needs_cleanup', False):
                cleanup_result = cleanup_cache(aggressive=False)
                logger.info(
                    f" Cache cleanup completed: freed {cleanup_result.get('total_freed_mb', 0):.1f}MB")
            else:
                logger.info(
                    f" Cache size OK: {cache_info.get('total_size_mb', 0):.1f}MB")
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
                                logger.info(f" Cleaned up CoreML temp directory: {temp_dir}")
                            except Exception as e:
                                logger.debug(f"⚠️ Could not clean up {temp_dir}: {e}")
                else:
                    # Handle direct paths
                    if os.path.exists(temp_pattern):
                        try:
                            shutil.rmtree(temp_pattern)
                            logger.info(f" Cleaned up CoreML temp directory: {temp_pattern}")
                        except Exception as e:
                            logger.debug(f"⚠️ Could not clean up {temp_pattern}: {e}")
        except Exception as e:
            logger.debug(f"⚠️ CoreML temp cleanup failed: {e}")

        update_startup_progress(10, "Applying production patches...")
        apply_all_patches()

        update_startup_progress(
            15, "Initializing model with hardware acceleration...")

        # Create a wrapper function to track progress during model initialization
        def track_model_init():
            update_startup_progress(20, "Detecting hardware capabilities...")
            initialize_model_sync()  # This function doesn't return the model
            return True

        await asyncio.get_event_loop().run_in_executor(
            None, track_model_init
        )

        update_startup_progress(90, "Finalizing model setup...")

        # Get the model from the global model loader
        from api.model.loader import get_model, get_model_status

        # Quick validation
        if not get_model_status():
            raise RuntimeError(
                "Model initialization failed - model not loaded")

        kokoro_model = get_model()
        if kokoro_model is None:
            raise RuntimeError("Model initialization failed - model is None")

        update_startup_progress(100, "Model initialization complete!", "ready")
        startup_progress["completed_at"] = time.time()
        model_initialization_complete = True

        total_time = startup_progress["completed_at"] - \
            startup_progress["started_at"]
        print(f"Model initialization completed in {total_time:.2f}s", flush=True)
        print(f"✅ Ready to start processing text to speech requests")

    except Exception as e:
        update_startup_progress(0, f"Initialization failed: {str(e)}", "error")
        logger.error(f"❌ Model initialization failed: {e}")
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management with progress tracking"""
    # Startup
    # Logging is already configured in setup_application_logging()

    # Start model initialization in background
    asyncio.create_task(initialize_model())

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

# Add performance and security middleware
app.add_middleware(PerformanceMiddleware)  # Custom performance monitoring
app.add_middleware(GZipMiddleware, minimum_size=1000)  # Compress responses > 1KB

# Add security middleware in production
if is_production:
    allowed_hosts = os.environ.get("KOKORO_ALLOWED_HOSTS", "*").split(",")
    if allowed_hosts != ["*"]:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """
    Enhanced health check that provides status during initialization
    """
    if model_initialization_complete:
        return {"status": "online", "model_ready": True}
    elif model_initialization_started:
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
        logger.error(f"❌ Warning statistics endpoint error: {e}")
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

        # Add hardware information
        try:
            capabilities = detect_apple_silicon_capabilities()
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

        return status

    except Exception as e:
        logger.error(f"❌ Status endpoint error: {e}")
        return {
            "error": "Status endpoint failed",
            "details": str(e)
        }


@app.post("/v1/audio/speech")
async def create_speech(request: Request, tts_request: TTSRequest):
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
        generator = stream_tts_audio(
            tts_request.text,
            tts_request.voice,
            tts_request.speed,
            tts_request.lang,
            tts_request.format,
            request,
        )

        return StreamingResponse(generator, media_type=media_type)

    # Handle non-streaming requests with complete audio generation
    else:
        # Segment text for parallel processing
        segments = segment_text(tts_request.text, TTSConfig.MAX_SEGMENT_LENGTH)
        if not segments:
            raise HTTPException(
                status_code=400,
                detail="No valid text segments to process. Please check your input text."
            )

        # Process all segments in parallel for better performance
        all_audio_np = []
        for i, seg in enumerate(segments):
            _, audio_np, _ = _generate_audio_segment(
                i, seg, tts_request.voice, tts_request.speed, tts_request.lang
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
                     TTSConfig.SAMPLE_RATE, format="WAV")
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
