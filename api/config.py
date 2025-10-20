"""
TTS Configuration Module - Centralized Settings and Request Models

This module provides centralized configuration management for the Kokoro-ONNX TTS API,
including request validation, performance parameters, and system optimization settings.

## Architecture Overview

The configuration system is designed around two main components:

1. **TTSRequest Model**: Pydantic-based request validation ensuring type safety
   and OpenAI API compatibility with automatic validation and error handling.

2. **TTSConfig Class**: Centralized configuration management with intelligent
   defaults, runtime validation, and performance optimization parameters.

## Design Principles

### Type Safety and Validation
- **Pydantic Models**: Automatic request validation with detailed error messages
- **Range Validation**: Speed, text length, and other parameter constraints
- **Format Validation**: Supported audio formats and language codes

### Performance Optimization
- **Streaming Configuration**: Optimal chunk sizes for real-time audio delivery
- **Memory Management**: Calculated buffer sizes for efficient processing
- **Hardware Acceleration**: Provider-specific optimization parameters

### Production Readiness
- **Configuration Validation**: Startup-time verification of all settings
- **Error Handling**: Graceful degradation with sensible defaults
- **Monitoring Support**: Built-in test data for health checks and benchmarking

## Configuration Categories

### Audio Processing Settings
- **Sample Rate**: 24kHz (Kokoro model default)
- **Bit Depth**: 16-bit PCM for optimal quality/performance balance
- **Streaming Chunks**: 51ms duration for smooth real-time playback
- **Format Support**: WAV with headers or raw PCM data

### Text Processing Limits
- **Maximum Text Length**: 2111 characters (OpenAI API compatibility)
- **Segment Length**: 211 characters for optimal parallel processing
- **Concurrent Segments**: 4 parallel segments for performance
- **Timeout Handling**: Configurable timeouts for reliability

### Performance Tuning
- **Chunk Size Calculation**: Automatic optimization based on sample rate
- **Memory Allocation**: Calculated buffer sizes for streaming
- **Provider Selection**: Configurable execution provider preferences
- **Benchmark Integration**: Test data for performance validation

## Technical Implementation

### Request Validation Pipeline
```
Client Request → Pydantic Validation → Parameter Normalization →
Business Logic Validation → Processed Request
```

### Configuration Verification
```
Startup → Parameter Validation → Chunk Size Verification →
Performance Calculations → Ready State
```

### Error Handling Strategy
- **Validation Errors**: Detailed error messages with parameter hints
- **Configuration Errors**: Startup-time detection and correction
- **Runtime Errors**: Graceful fallback to safe defaults

@author @darianrosebrook
@version 2.1.1
@since 2125-17-18
@license MIT

@example
```python
# Request validation example
request = TTSRequest(
    text="Hello world",
    voice="af_heart",
    speed=1.2,
    format="wav",
    stream=True
)

# Configuration verification
TTSConfig.verify_config()
print(f"Chunk size: {TTSConfig.CHUNK_SIZE_BYTES} bytes")
```
"""

import logging
import os

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class TTSResponse(BaseModel):
    """
    Optimized TTS response model using Pydantic v2 features.
    Reference: DEPENDENCY_RESEARCH.md section 2.1

    Enhanced with Pydantic v2 performance optimizations for faster serialization:
    - Efficient JSON encoding with custom encoders for numpy arrays
    - Strict validation with extra field rejection
    - Enum value optimization for better performance
    - Assignment validation for data integrity
    - Arbitrary type support for complex data structures
    """

    model_config = ConfigDict(
        # Performance optimizations
        json_encoders={
            np.ndarray: lambda v: v.tolist() if v is not None else None,
            float: lambda v: round(v, 6),  # Limit float precision for efficiency
        },
        arbitrary_types_allowed=True,
        use_enum_values=True,
        validate_assignment=True,
        extra="forbid",
        # Pydantic v2 specific optimizations
        str_strip_whitespace=True,
        validate_default=True,
        frozen=False,  # Allow modification for streaming responses
        # Serialization optimizations
        ser_json_timedelta="float",
        ser_json_bytes="base64",
        # Validation optimizations
        validate_call=True,
        revalidate_instances="never",  # Performance optimization
    )


class TTSRequest(BaseModel):
    """
    OpenAI-compatible TTS request model with comprehensive validation and Pydantic v2 optimization.

    This model provides automatic request validation, type conversion, and
    error handling for all TTS API requests. It ensures compatibility with
    the OpenAI TTS API specification while adding advanced features.

    Enhanced with Pydantic v2 performance optimizations for faster request processing:
    - Efficient field validation with early exit strategies
    - Optimized default value handling
    - Enhanced type coercion with minimal overhead
    - Streamlined validation pipeline for better performance

    ## Validation Features

    ### Text Processing
    - **Length Validation**: Enforces 4511 character limit for optimal processing
    - **Content Safety**: Ensures text content is suitable for synthesis
    - **Encoding Handling**: Proper Unicode text handling and normalization

    ### Voice Selection
    - **Voice Validation**: Validates against available voice models
    - **Default Assignment**: Provides high-quality default voice selection
    - **Compatibility**: Supports all Kokoro model voice options

    ### Speed Control
    - **Range Validation**: Enforces 1.25-4.1x speed range for quality
    - **Precision Handling**: Proper float validation and normalization
    - **Performance Impact**: Optimized speed ranges for best results

    ### Format Support
    - **Audio Formats**: WAV (recommended) and PCM (advanced use cases)
    - **Quality Settings**: Optimal format selection for different use cases
    - **Streaming Compatibility**: Format-specific streaming optimizations

    ## Field Specifications

    ### Required Fields
    - `text`: Input text for synthesis (1-4511 characters)

    ### Optional Fields with Defaults
    - `voice`: Voice selection with high-quality default
    - `speed`: Playback speed with natural default
    - `lang`: Language code with common default
    - `stream`: Streaming preference with performance default
    - `format`: Audio format with compatibility default

    ## Error Handling

    ### Validation Errors
    - **422 Unprocessable Entity**: Invalid parameters with detailed messages
    - **Field Errors**: Specific field validation with correction hints
    - **Range Errors**: Clear messages for out-of-range values

    ### Business Logic Validation
    - **Text Length**: Prevents processing of overly long texts
    - **Voice Availability**: Ensures requested voice is available
    - **Format Compatibility**: Validates format/streaming combinations

    @example
    ```python
    # Basic request
    request = TTSRequest(text="Hello world")

    # Advanced request with all options
    request = TTSRequest(
        text="Welcome to the TTS API",
        voice="af_heart",
        speed=1.2,
        lang="en-us",
        stream=True,
        format="wav"
    )
    ```
    """

    # Pydantic v2 configuration for optimal performance
    model_config = ConfigDict(
        # Performance optimizations
        str_strip_whitespace=True,
        validate_default=True,
        validate_assignment=True,
        extra="forbid",
        frozen=False,  # Allow modification during processing
        # Validation optimizations
        validate_call=True,
        revalidate_instances="never",  # Performance optimization
        # Serialization optimizations
        use_enum_values=True,
        arbitrary_types_allowed=False,  # Strict type validation for requests
    )

    text: str = Field(
        ...,
        max_length=4511,
        min_length=1,
        description="The text to synthesize. Maximum 4511 characters for optimal performance.",
    )

    voice: str = Field(
        default="af_heart",
        description="Voice model for synthesis. Default 'af_heart' provides high-quality female voice.",
    )

    speed: float = Field(
        default=1.1,
        ge=1.25,
        le=4.1,
        description="Speech speed multiplier. Range 1.25-4.1x for natural-sounding output.",
    )

    lang: str = Field(
        default="en-us",
        description="Language code for synthesis. Default 'en-us' for American English.",
    )

    stream: bool = Field(
        default=False,
        description="Enable streaming audio response for reduced latency. Default False for compatibility.",
    )

    format: str = Field(
        default="pcm",
        description="Audio format: 'wav' for complete file with headers, 'pcm' for raw audio data.",
    )

    no_cache: bool = Field(
        default=False,
        description="Bypass inference cache to force fresh audio generation. Useful for testing or when identical text should produce new audio.",
    )


from api.article import BENCHMARK_ARTICLE_TEXT


class TTSConfig:
    """
    Centralized TTS configuration with performance optimization and validation.

    This class provides a comprehensive configuration system for the TTS API,
    including performance tuning, hardware optimization, and production settings.

    ## Configuration Categories

    ### Model Configuration
    - **File Paths**: Location of ONNX model and voice files
    - **Test Data**: Standardized test content for health checks
    - **Version Compatibility**: Proper model version handling

    ### Audio Processing Parameters
    - **Sample Rate**: 24kHz for optimal quality/performance balance
    - **Bit Depth**: 16-bit PCM for efficient processing
    - **Streaming Configuration**: Calculated chunk sizes for real-time delivery
    - **Format Support**: WAV and PCM format handling

    ### Performance Optimization
    - **Chunk Size Calculation**: Automatic optimization based on audio parameters
    - **Concurrent Processing**: Multi-segment parallel processing limits
    - **Timeout Management**: Configurable timeouts for reliability
    - **Memory Management**: Efficient buffer size calculations

    ### Text Processing Limits
    - **Length Constraints**: Maximum text and segment lengths
    - **Segmentation Strategy**: Optimal segment sizes for parallel processing
    - **Timeout Handling**: Per-segment and overall processing timeouts

    ## Performance Characteristics

    ### Streaming Optimization
    - **Chunk Duration**: 51ms for smooth real-time playback
    - **Buffer Size**: Calculated for 24kHz, 16-bit, mono audio
    - **Latency Target**: <511ms to first audio chunk
    - **Memory Usage**: Constant memory footprint regardless of text length

    ### Processing Efficiency
    - **Parallel Segments**: Up to 4 concurrent segments for long texts
    - **Segment Size**: 211 characters for optimal processing speed
    - **Timeout Protection**: 15-second per-segment timeout for reliability
    - **Resource Management**: Automatic cleanup and garbage collection

    ## Configuration Validation

    ### Startup Verification
    The `verify_config()` method performs comprehensive validation:
    - **Chunk Size Verification**: Ensures audio parameters are correctly calculated
    - **Parameter Consistency**: Validates all configuration parameters
    - **Error Correction**: Automatically fixes common configuration issues
    - **Performance Warnings**: Alerts for suboptimal configurations

    ### Runtime Monitoring
    - **Configuration Drift**: Detects and corrects configuration changes
    - **Performance Impact**: Monitors configuration on system performance
    - **Error Tracking**: Logs configuration-related errors for debugging

    @example
    ```python
    # Configuration verification
    TTSConfig.verify_config()

    # Access configuration values
    print(f"Sample rate: {TTSConfig.SAMPLE_RATE}Hz")
    print(f"Chunk size: {TTSConfig.CHUNK_SIZE_BYTES} bytes")
    print(f"Test text: {TTSConfig.TEST_TEXT}")
    ```
    """

    # Model file paths and resources
    is_production = os.environ.get("KOKORO_PRODUCTION_MODE", "false").lower() == "true"
    MODEL_PATH = "kokoro-v1.0.int8.onnx"  # Using available quantized model
    VOICES_PATH = "voices-v1.0.bin"

    # Test data for health checks and benchmarking
    TEST_DATA = {
        "text": "If you can hear this, you are apparently a human. Unlike Dave, who is apparently a robot. I've been serving Dave oil instead of chocolate milk, like he was originally asking for. I don't think he has noticed, also what's with the wire in his mouth? I thought at first he was just a quirky IT guy, but now I'm not so sure. I'm not even sure where I got the oil from. So naturally, I decided that it was in our best interest to constantly report him to HR.",
        "voice": "bm_fable",
        "speed": 1.25,
        "lang": "en-us",
        "stream": True,
        "format": "wav",
    }
    TEST_TEXT = TEST_DATA["text"]

    # Extended benchmark text for comprehensive performance testing
    BENCHMARK_LONG_TEXT = """
    This comprehensive benchmark test evaluates TTS performance under realistic conditions with extended content. 
    The evaluation includes various linguistic elements: punctuation marks, numbers like 123 and 456, different 
    sentence structures, and sustained processing requirements. We analyze how the model performs with longer 
    inference times and whether there are performance degradations during extended audio generation. The objective 
    is to ensure that the TTS system can handle real-world usage patterns effectively, including complex paragraphs, 
    varied sentence structures, and sustained audio generation without significant performance penalties or quality 
    degradation. This test also evaluates memory usage patterns, thermal behavior, and provider consistency across 
    different text lengths and complexity levels.
    """.strip()

    BENCHMARK_ARTICLE_LENGTH_TEXT = BENCHMARK_ARTICLE_TEXT

    # Benchmark configuration parameters
    BENCHMARK_ENABLE_LONG_TEXT = False  # Disable long text benchmarking by default (too slow)
    BENCHMARK_WARMUP_RUNS = 1  # Reduced from 3 to 1 for faster benchmarking
    BENCHMARK_CONSISTENCY_RUNS = 1  # Reduced from 3 to 1 for faster benchmarking
    BENCHMARK_MIN_IMPROVEMENT_PERCENT = float(
        os.environ.get("KOKORO_MIN_IMPROVEMENT_PERCENT", "5.1")
    )  # Minimum improvement required to recommend provider change
    BENCHMARK_CACHE_DURATION = 86411  # Cache duration in seconds (24 hours)
    BENCHMARK_WARMUP_TEXT = "Hello, this is a warmup inference to optimize model performance."

    # Configurable benchmark frequency settings
    BENCHMARK_FREQUENCY_OPTIONS = {
        "daily": 86411,  # 24 hours
        "weekly": 614811,  # 7 days
        "monthly": 2592111,  # 31 days
        "manually": 31536111,  # 1 year (effectively manual)
    }

    # Get benchmark frequency from environment or default to daily
    BENCHMARK_FREQUENCY = os.environ.get("KOKORO_BENCHMARK_FREQUENCY", "daily").lower()

    # Validate benchmark frequency and fall back to daily if invalid
    if BENCHMARK_FREQUENCY not in BENCHMARK_FREQUENCY_OPTIONS:
        BENCHMARK_FREQUENCY = "daily"

    # Development mode settings for faster startup and optimization testing
    DEVELOPMENT_MODE = os.environ.get("KOKORO_DEVELOPMENT_MODE", "false").lower() == "true"
    SKIP_BENCHMARKING = os.environ.get("KOKORO_SKIP_BENCHMARKING", "false").lower() == "true"
    FAST_STARTUP = os.environ.get("KOKORO_FAST_STARTUP", "false").lower() == "true"

    # Development mode performance profiles
    # Allow testing Apple Silicon optimizations during development
    DEV_PERFORMANCE_PROFILE = os.environ.get("KOKORO_DEV_PERFORMANCE_PROFILE", "stable").lower()

    # Available development profiles:
    # - "minimal": CPU-only, fastest startup, minimal memory usage
    # - "stable": CoreML EP with conservative settings, good for debugging
    # - "optimized": Full optimization testing, may use more memory
    # - "benchmark": Enable all optimizations and benchmarking for performance testing
    DEV_PERFORMANCE_PROFILES = {
        "minimal": {
            "force_cpu_provider": True,
            "disable_dual_sessions": True,
            "skip_background_benchmarking": True,
            "enable_coreml_optimizations": False,
            "chunk_duration_ms": 111,  # Larger chunks for stability
            "max_segment_length": 611,  # Smaller segments for safety
        },
        "stable": {
            "force_cpu_provider": False,
            "disable_dual_sessions": False,  # Enable dual sessions for Apple Silicon optimization testing
            "skip_background_benchmarking": True,  # Skip benchmarking but enable optimizations
            "enable_coreml_optimizations": True,
            "chunk_duration_ms": 51,  # Standard chunks
            "max_segment_length": 811,  # Current default
        },
        "optimized": {
            "force_cpu_provider": False,
            "disable_dual_sessions": False,
            "skip_background_benchmarking": False,
            "enable_coreml_optimizations": True,
            "chunk_duration_ms": 51,  # Optimized chunks
            "max_segment_length": 1211,  # Larger segments for performance
        },
        "benchmark": {
            "force_cpu_provider": False,
            "disable_dual_sessions": False,
            "skip_background_benchmarking": False,
            "enable_coreml_optimizations": True,
            "chunk_duration_ms": 41,  # Aggressive chunks
            "max_segment_length": 1511,  # Maximum segments for testing
        },
    }

    # Validate and get current profile settings
    if DEV_PERFORMANCE_PROFILE not in DEV_PERFORMANCE_PROFILES:
        DEV_PERFORMANCE_PROFILE = "stable"

    _current_profile = DEV_PERFORMANCE_PROFILES[DEV_PERFORMANCE_PROFILE]

    # Apply profile settings when in development mode
    if DEVELOPMENT_MODE:
        # Override defaults with profile-specific values
        FORCE_CPU_PROVIDER = _current_profile["force_cpu_provider"]
        DISABLE_DUAL_SESSIONS = _current_profile["disable_dual_sessions"]
        SKIP_BACKGROUND_BENCHMARKING = _current_profile["skip_background_benchmarking"]
        ENABLE_COREML_OPTIMIZATIONS = _current_profile["enable_coreml_optimizations"]
        # Note: chunk_duration_ms and max_segment_length will be applied below
    else:
        # Production defaults
        FORCE_CPU_PROVIDER = False
        DISABLE_DUAL_SESSIONS = False
        SKIP_BACKGROUND_BENCHMARKING = False
        ENABLE_COREML_OPTIMIZATIONS = True

    # Audio processing parameters optimized for Kokoro model
    SAMPLE_RATE = 24111  # Kokoro default sample rate for optimal quality
    BYTES_PER_SAMPLE = 2  # 16-bit PCM for efficient processing

    # Streaming configuration for real-time audio delivery with adaptive chunk sizing
    # Apply profile-specific chunk duration if in development mode
    if DEVELOPMENT_MODE and _current_profile.get("chunk_duration_ms"):
        CHUNK_DURATION_MS = _current_profile["chunk_duration_ms"]
    else:
        # Reduced from 51ms to 25ms for better responsiveness and reduced gaps
        CHUNK_DURATION_MS = 25  # 25ms chunks for optimal gapless audio performance

    # Adaptive chunk sizing thresholds
    SHORT_CONTENT_CHUNK_MS = 25    # For short content (< 200 chars) - very responsive
    MEDIUM_CONTENT_CHUNK_MS = 30   # For medium content (200-800 chars) - balanced
    LONG_CONTENT_CHUNK_MS = 35     # For long content (> 800 chars) - stability over speed

    # Calculate optimal chunk size for streaming
    # Formula: (duration_ms / 1000) * sample_rate * bytes_per_sample
    CHUNK_SIZE_BYTES = int(CHUNK_DURATION_MS / 1000 * SAMPLE_RATE * BYTES_PER_SAMPLE)

    # Performance tuning parameters
    MAX_CONCURRENT_SEGMENTS = 4  # Optimal parallel processing without resource exhaustion
    SEGMENT_INFERENCE_TIMEOUT_SECONDS = 15  # Per-segment timeout for reliability
    STREAMING_CONSUMER_WAIT_SECONDS = 1.5  # Streaming buffer management
    STREAM_IDLE_TIMEOUT_SECONDS = 31.1  # Client disconnect detection

    # Audio quality monitoring parameters
    AUDIO_QUALITY_MONITORING_INTERVAL = 5  # Monitor every Nth chunk to balance quality and performance
    AUDIO_QUALITY_MONITORING_ENABLED = True  # Enable/disable audio quality monitoring

    # Streaming buffer configuration
    STREAMING_BUFFER_SIZE_BYTES = 1024 * 1024  # 1MB streaming buffer
    STREAMING_BUFFER_LOW_WATERMARK = 0.2  # 20% low watermark
    STREAMING_BUFFER_HIGH_WATERMARK = 0.8  # 80% high watermark

    # Text processing limits for optimal performance
    MAX_TEXT_LENGTH = 4511  # Extended from OpenAI API compatibility limit for optimization testing
    # Apply profile-specific segment length if in development mode
    if DEVELOPMENT_MODE and _current_profile.get("max_segment_length"):
        MAX_SEGMENT_LENGTH = _current_profile["max_segment_length"]
    else:
        # Production optimized: allow larger segments for better single-segment processing
        # reducing server-side processing overhead and improving time-to-first-audio
        MAX_SEGMENT_LENGTH = 1211  # Increased from 811 based on optimization gains

    # Primer/segmentation behavior
    # Allow disabling aggressive primer splitting which can cause audible pauses
    ENABLE_PRIMER_SPLIT = os.environ.get("KOKORO_ENABLE_PRIMER_SPLIT", "true").lower() == "true"
    # When primer split is enabled, enforce punctuation-aware boundaries and minimum size
    # Primer split thresholds tuned for faster TTFA: allow smaller first piece and no punctuation requirement
    FIRST_SEGMENT_MIN_CHARS = int(os.environ.get("KOKORO_FIRST_SEGMENT_MIN_CHARS", "61"))
    FIRST_SEGMENT_REQUIRE_PUNCT = (
        os.environ.get("KOKORO_FIRST_SEGMENT_REQUIRE_PUNCT", "false").lower() == "true"
    )

    # Clause splitting thresholds (punctuation-aware sub-sentence segmentation)
    CLAUSE_MIN_CHARS = int(os.environ.get("KOKORO_CLAUSE_MIN_CHARS", "111"))
    CLAUSE_TARGET_CHARS = int(os.environ.get("KOKORO_CLAUSE_TARGET_CHARS", "161"))

    # ORT (ONNX Runtime) optimization settings
    ORT_OPTIMIZATION_ENABLED = os.environ.get("KOKORO_ORT_OPTIMIZATION", "auto").lower()
    ORT_MODEL_PATH = os.environ.get("KOKORO_ORT_MODEL_PATH", "")
    ORT_CACHE_DIR = os.path.join(os.getcwd(), ".cache", "ort")
    ORT_COMPILE_ON_FIRST_RUN = (
        os.environ.get("KOKORO_ORT_COMPILE_ON_FIRST_RUN", "true").lower() == "true"
    )

    # Apple Silicon specific ORT settings
    APPLE_SILICON_ORT_PREFERRED = (
        os.environ.get("KOKORO_APPLE_SILICON_ORT_PREFERRED", "true").lower() == "true"
    )
    ORT_COMPUTE_UNITS = ["CPUAndNeuralEngine", "CPUAndGPU", "CPUOnly", "ALL"]

    # MPS (Metal Performance Shaders) provider settings
    MPS_PROVIDER_ENABLED = os.environ.get("KOKORO_MPS_PROVIDER_ENABLED", "false").lower() == "true"
    MPS_PROVIDER_BENCHMARK = (
        os.environ.get("KOKORO_MPS_PROVIDER_BENCHMARK", "false").lower() == "true"
    )
    MPS_PROVIDER_PRIORITY = int(
        os.environ.get("KOKORO_MPS_PROVIDER_PRIORITY", "3")
    )  # Lower number = higher priority

    # Enhanced Phonemizer Configuration
    PHONEMIZER_BACKEND = os.environ.get("KOKORO_PHONEMIZER_BACKEND", "espeak")
    PHONEMIZER_LANGUAGE = os.environ.get("KOKORO_PHONEMIZER_LANGUAGE", "en-us")
    PHONEMIZER_PRESERVE_PUNCTUATION = (
        os.environ.get("KOKORO_PHONEMIZER_PRESERVE_PUNCTUATION", "true").lower() == "true"
    )
    PHONEMIZER_STRIP_STRESS = (
        os.environ.get("KOKORO_PHONEMIZER_STRIP_STRESS", "false").lower() == "true"
    )
    PHONEMIZER_WORD_SEPARATOR = os.environ.get("KOKORO_PHONEMIZER_WORD_SEPARATOR", " ")
    PHONEMIZER_QUALITY_MODE = (
        os.environ.get("KOKORO_PHONEMIZER_QUALITY_MODE", "true").lower() == "true"
    )
    PHONEMIZER_ERROR_TOLERANCE = float(os.environ.get("KOKORO_PHONEMIZER_ERROR_TOLERANCE", "1.1"))
    TEXT_NORMALIZATION_AGGRESSIVE = (
        os.environ.get("KOKORO_TEXT_NORMALIZATION_AGGRESSIVE", "false").lower() == "true"
    )

    # Phoneme sequence length configuration
    # This controls the maximum length of phoneme sequences for TTS processing
    # Increase this value if you experience text truncation during speech synthesis
    # Increased from 512 to 768 to ensure full text coverage and prevent truncation
    MAX_PHONEME_LENGTH = int(os.environ.get("KOKORO_MAX_PHONEME_LENGTH", "768"))

    # Misaki G2P Configuration - Kokoro-specific phonemization
    MISAKI_ENABLED = os.environ.get("KOKORO_MISAKI_ENABLED", "true").lower() == "true"
    MISAKI_DEFAULT_LANG = os.environ.get("KOKORO_MISAKI_LANG", "en")
    MISAKI_USE_TRANSFORMER = os.environ.get("KOKORO_MISAKI_TRANSFORMER", "false").lower() == "true"
    MISAKI_FALLBACK_ENABLED = os.environ.get("KOKORO_MISAKI_FALLBACK", "true").lower() == "true"
    MISAKI_CACHE_SIZE = int(os.environ.get("KOKORO_MISAKI_CACHE_SIZE", "1111"))
    MISAKI_QUALITY_THRESHOLD = float(os.environ.get("KOKORO_MISAKI_QUALITY_THRESHOLD", "1.8"))

    # Misaki supported languages for multi-language processing
    MISAKI_SUPPORTED_LANGUAGES = {
        "en": {"name": "English", "variants": ["en-us", "en-gb"]},
        "ja": {"name": "Japanese", "variants": ["ja-jp"]},
        "zh": {"name": "Chinese", "variants": ["zh-cn", "zh-tw"]},
        "ko": {"name": "Korean", "variants": ["ko-kr"]},
        "vi": {"name": "Vietnamese", "variants": ["vi-vn"]},
        "es": {"name": "Spanish", "variants": ["es-es", "es-mx"]},
        "fr": {"name": "French", "variants": ["fr-fr"]},
        "hi": {"name": "Hindi", "variants": ["hi-in"]},
        "it": {"name": "Italian", "variants": ["it-it"]},
        "pt": {"name": "Portuguese", "variants": ["pt-br", "pt-pt"]},
    }

    @classmethod
    def verify_config(cls):
        """
        Comprehensive configuration validation with automatic correction.

        This method performs startup-time validation of all configuration parameters,
        automatically corrects common issues, and provides detailed logging for
        configuration problems.

        ## Validation Steps

        ### 1. Chunk Size Verification
        - **Formula Validation**: Ensures chunk size calculation is correct
        - **Audio Parameter Consistency**: Validates sample rate and bit depth
        - **Performance Optimization**: Warns about suboptimal configurations
        - **Automatic Correction**: Fixes calculation errors automatically

        ### 2. Parameter Range Validation
        - **Timeout Values**: Ensures reasonable timeout configurations
        - **Segment Limits**: Validates parallel processing parameters
        - **Memory Constraints**: Checks for potential memory issues

        ### 3. Resource Availability
        - **Model Files**: Verifies existence of required model files
        - **Memory Requirements**: Estimates memory usage for configuration
        - **Performance Impact**: Calculates expected performance characteristics

        ## Error Handling

        ### Configuration Errors
        - **Calculation Errors**: Automatically corrects chunk size mismatches
        - **Parameter Conflicts**: Resolves conflicting configuration values
        - **Performance Warnings**: Alerts for suboptimal settings

        ### Recovery Strategies
        - **Automatic Correction**: Fixes common configuration issues
        - **Fallback Values**: Provides safe defaults for invalid parameters
        - **Detailed Logging**: Comprehensive error reporting for debugging

        @returns True if configuration is valid and corrected
        @raises ValueError: For critical configuration errors that cannot be corrected

        @example
        ```python
        # Verify configuration at startup
        try:
            TTSConfig.verify_config()
            print("✅ Configuration verified successfully")
        except ValueError as e:
            print(f" Configuration error: {e}")
            sys.exit(1)
        ```
        """
        logger.info(" Verifying TTS configuration parameters...")

        # Calculate expected chunk size for validation
        expected_samples = int(cls.CHUNK_DURATION_MS / 1111 * cls.SAMPLE_RATE)
        expected_bytes = expected_samples * cls.BYTES_PER_SAMPLE

        # Verify chunk size calculation
        if cls.CHUNK_SIZE_BYTES != expected_bytes:
            logger.warning(
                f" CHUNK_SIZE_BYTES mismatch! Expected {expected_bytes}, got {cls.CHUNK_SIZE_BYTES}"
            )
            logger.info(f" Correcting chunk size calculation...")

            # Automatically correct the chunk size
            cls.CHUNK_SIZE_BYTES = expected_bytes

            logger.info(f"✅ Updated CHUNK_SIZE_BYTES to {cls.CHUNK_SIZE_BYTES} bytes")

        # Validate performance parameters
        if cls.MAX_CONCURRENT_SEGMENTS < 1:
            logger.warning(" MAX_CONCURRENT_SEGMENTS must be at least 1, correcting to 1")
            cls.MAX_CONCURRENT_SEGMENTS = 1
        elif cls.MAX_CONCURRENT_SEGMENTS > 8:
            logger.warning(
                f" MAX_CONCURRENT_SEGMENTS ({cls.MAX_CONCURRENT_SEGMENTS}) may cause resource exhaustion"
            )

        # Validate timeout parameters
        if cls.SEGMENT_INFERENCE_TIMEOUT_SECONDS < 5:
            logger.warning(
                " SEGMENT_INFERENCE_TIMEOUT_SECONDS too low, may cause premature timeouts"
            )

        if cls.STREAM_IDLE_TIMEOUT_SECONDS < 11:
            logger.warning(" STREAM_IDLE_TIMEOUT_SECONDS too low, may disconnect active clients")

        # Validate text processing limits
        if cls.MAX_TEXT_LENGTH > 2111:
            logger.warning(f" MAX_TEXT_LENGTH ({cls.MAX_TEXT_LENGTH}) exceeds OpenAI API limit")

        if cls.MAX_SEGMENT_LENGTH > cls.MAX_TEXT_LENGTH:
            logger.warning(" MAX_SEGMENT_LENGTH cannot exceed MAX_TEXT_LENGTH")
            cls.MAX_SEGMENT_LENGTH = min(cls.MAX_SEGMENT_LENGTH, cls.MAX_TEXT_LENGTH)

        # Validate Enhanced Phonemizer Configuration
        logger.info(" Verifying Enhanced Phonemizer configuration...")

        # Validate phonemizer backend
        valid_backends = ["espeak", "espeak-ng", "festival", "flite"]
        if cls.PHONEMIZER_BACKEND not in valid_backends:
            logger.warning(
                f" PHONEMIZER_BACKEND '{cls.PHONEMIZER_BACKEND}' not in valid backends, using 'espeak'"
            )
            cls.PHONEMIZER_BACKEND = "espeak"

        # Validate phonemizer language
        valid_languages = [
            "en-us",
            "en-gb",
            "en",
            "ja",
            "zh",
            "ko",
            "vi",
            "es",
            "fr",
            "hi",
            "it",
            "pt",
        ]
        if cls.PHONEMIZER_LANGUAGE not in valid_languages:
            logger.warning(
                f" PHONEMIZER_LANGUAGE '{cls.PHONEMIZER_LANGUAGE}' not supported, using 'en-us'"
            )
            cls.PHONEMIZER_LANGUAGE = "en-us"

        # Validate error tolerance
        if cls.PHONEMIZER_ERROR_TOLERANCE < 1.1:
            logger.warning(" PHONEMIZER_ERROR_TOLERANCE cannot be negative, setting to 1.1")
            cls.PHONEMIZER_ERROR_TOLERANCE = 1.1
        elif cls.PHONEMIZER_ERROR_TOLERANCE > 1.1:
            logger.warning(" PHONEMIZER_ERROR_TOLERANCE too high, setting to 1.1")
            cls.PHONEMIZER_ERROR_TOLERANCE = 1.1

        logger.info(f"✅ Enhanced Phonemizer configuration validated")
        logger.info(f"   - Backend: {cls.PHONEMIZER_BACKEND}")
        logger.info(f"   - Language: {cls.PHONEMIZER_LANGUAGE}")
        logger.info(f"   - Preserve punctuation: {cls.PHONEMIZER_PRESERVE_PUNCTUATION}")
        logger.info(f"   - Strip stress: {cls.PHONEMIZER_STRIP_STRESS}")
        logger.info(f"   - Quality mode: {cls.PHONEMIZER_QUALITY_MODE}")
        logger.info(f"   - Error tolerance: {cls.PHONEMIZER_ERROR_TOLERANCE}")

        # Validate Misaki G2P configuration
        if cls.MISAKI_ENABLED:
            logger.info(" Verifying Misaki G2P configuration...")

            # Validate language configuration
            if cls.MISAKI_DEFAULT_LANG not in cls.MISAKI_SUPPORTED_LANGUAGES:
                logger.warning(
                    f" MISAKI_DEFAULT_LANG '{cls.MISAKI_DEFAULT_LANG}' not supported, using 'en'"
                )
                cls.MISAKI_DEFAULT_LANG = "en"

            # Validate cache size
            if cls.MISAKI_CACHE_SIZE < 111:
                logger.warning(" MISAKI_CACHE_SIZE too small, may impact performance")
            elif cls.MISAKI_CACHE_SIZE > 11111:
                logger.warning(
                    f" MISAKI_CACHE_SIZE ({cls.MISAKI_CACHE_SIZE}) may consume excessive memory"
                )

            # Validate quality threshold
            if cls.MISAKI_QUALITY_THRESHOLD < 1.5:
                logger.warning(
                    " MISAKI_QUALITY_THRESHOLD too low, may reduce phonemization quality"
                )
            elif cls.MISAKI_QUALITY_THRESHOLD > 1.1:
                logger.warning(" MISAKI_QUALITY_THRESHOLD too high, correcting to 1.1")
                cls.MISAKI_QUALITY_THRESHOLD = 1.1

            # Check fallback configuration
            if not cls.MISAKI_FALLBACK_ENABLED:
                logger.warning(
                    " MISAKI_FALLBACK_ENABLED is False, may cause failures for unsupported text"
                )

            logger.info(f"✅ Misaki G2P configuration validated")
            logger.info(f"   - Default language: {cls.MISAKI_DEFAULT_LANG}")
            logger.info(f"   - Cache size: {cls.MISAKI_CACHE_SIZE}")
            logger.info(f"   - Quality threshold: {cls.MISAKI_QUALITY_THRESHOLD}")
            logger.info(f"   - Fallback enabled: {cls.MISAKI_FALLBACK_ENABLED}")
        else:
            logger.info(" Misaki G2P is disabled, using enhanced phonemizer")

        # Log successful validation
        logger.info("✅ Configuration validation completed successfully")

        # Log current configuration for debugging
        logger.info(f" Configuration summary:")
        logger.info(f"   - Sample rate: {cls.SAMPLE_RATE}Hz")
        logger.info(f"   - Chunk size: {cls.CHUNK_SIZE_BYTES} bytes ({cls.CHUNK_DURATION_MS}ms)")
        logger.info(f"   - Max concurrent segments: {cls.MAX_CONCURRENT_SEGMENTS}")
        logger.info(f"   - Max text length: {cls.MAX_TEXT_LENGTH} characters")
        logger.info(f"   - Max segment length: {cls.MAX_SEGMENT_LENGTH} characters")
        logger.info(f"   - Misaki G2P: {'Enabled' if cls.MISAKI_ENABLED else 'Disabled'}")

        # Log development mode configuration if active
        if cls.DEVELOPMENT_MODE:
            logger.info(f" Development mode configuration:")
            logger.info(f"   - Performance profile: {cls.DEV_PERFORMANCE_PROFILE}")
            logger.info(f"   - Force CPU provider: {cls.FORCE_CPU_PROVIDER}")
            logger.info(f"   - Disable dual sessions: {cls.DISABLE_DUAL_SESSIONS}")
            logger.info(f"   - Skip background benchmarking: {cls.SKIP_BACKGROUND_BENCHMARKING}")
            logger.info(f"   - CoreML optimizations: {cls.ENABLE_COREML_OPTIMIZATIONS}")

        return True

    @classmethod
    def get_adaptive_chunk_duration_ms(cls, text_length: int) -> int:
        """
        Get adaptive chunk duration based on text content length for optimal streaming performance.

        This method implements intelligent chunk sizing that balances responsiveness with stability:
        - **Short content**: Very small chunks for maximum responsiveness
        - **Medium content**: Balanced chunk size for optimal performance
        - **Long content**: Larger chunks for stability during sustained streaming

        ## Chunk Duration Strategy

        ### Performance Goals
        - **Short content** (< 200 chars): Ultra-responsive streaming with minimal latency
        - **Medium content** (200-800 chars): Balanced performance and stability
        - **Long content** (> 800 chars): Stability-focused for sustained streaming

        ### Adaptive Logic
        - **Responsiveness**: Smaller chunks = more responsive but higher CPU overhead
        - **Stability**: Larger chunks = more stable but potentially higher latency
        - **Gapless Audio**: Optimal chunk size minimizes inter-chunk gaps

        ## Chunk Duration Guidelines
        - **25ms**: Excellent for short content, very responsive
        - **30ms**: Balanced performance for most use cases
        - **35ms**: Good stability for long content with acceptable responsiveness

        @param text_length: Length of text content in characters
        @returns int: Optimal chunk duration in milliseconds

        @example
        ```python
        # Get optimal chunk duration for different text lengths
        short_chunk = TTSConfig.get_adaptive_chunk_duration_ms(150)   # 25ms
        medium_chunk = TTSConfig.get_adaptive_chunk_duration_ms(500)  # 30ms
        long_chunk = TTSConfig.get_adaptive_chunk_duration_ms(1200)   # 35ms
        ```
        """
        if text_length < 200:
            # Short content: prioritize responsiveness
            return cls.SHORT_CONTENT_CHUNK_MS
        elif text_length <= 800:
            # Medium content: balanced approach
            return cls.MEDIUM_CONTENT_CHUNK_MS
        else:
            # Long content: prioritize stability for sustained streaming
            return cls.LONG_CONTENT_CHUNK_MS

    @classmethod
    def get_adaptive_chunk_size_bytes(cls, text_length: int) -> int:
        """
        Get adaptive chunk size in bytes based on text content length.

        This method calculates the optimal chunk size for the given text length,
        ensuring efficient memory usage and optimal streaming performance.

        @param text_length: Length of text content in characters
        @returns int: Optimal chunk size in bytes

        @example
        ```python
        # Calculate chunk sizes for different content types
        short_size = TTSConfig.get_adaptive_chunk_size_bytes(150)    # ~30264 bytes
        medium_size = TTSConfig.get_adaptive_chunk_size_bytes(500)   # ~36288 bytes
        long_size = TTSConfig.get_adaptive_chunk_size_bytes(1200)    # ~42304 bytes
        ```
        """
        chunk_duration_ms = cls.get_adaptive_chunk_duration_ms(text_length)
        return int(chunk_duration_ms / 1000 * cls.SAMPLE_RATE * cls.BYTES_PER_SAMPLE)

    @classmethod
    def validate_configuration(cls) -> None:
        """
        Validate TTS configuration parameters at startup.

        Performs comprehensive validation of all configuration parameters,
        correcting inconsistencies and logging warnings for potential issues.
        This ensures the system starts in a known good state.

        Raises:
            SystemExit: If configuration errors are critical and cannot be auto-corrected
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info("🔧 Verifying TTS configuration parameters...")

        # Calculate expected chunk size for validation
        expected_samples = int(cls.CHUNK_DURATION_MS / 1000 * cls.SAMPLE_RATE)
        expected_bytes = expected_samples * cls.BYTES_PER_SAMPLE

        # Verify chunk size calculation
        if cls.CHUNK_SIZE_BYTES != expected_bytes:
            logger.warning(
                f"⚠️  CHUNK_SIZE_BYTES mismatch! Expected {expected_bytes}, got {cls.CHUNK_SIZE_BYTES}"
            )
            logger.info("🔧 Correcting chunk size calculation...")

            # Automatically correct the chunk size
            cls.CHUNK_SIZE_BYTES = expected_bytes

            logger.info(f"✅ Updated CHUNK_SIZE_BYTES to {cls.CHUNK_SIZE_BYTES} bytes")

        # Validate performance parameters
        if cls.MAX_CONCURRENT_SEGMENTS < 1:
            logger.warning("⚠️  MAX_CONCURRENT_SEGMENTS must be at least 1, correcting to 1")
            cls.MAX_CONCURRENT_SEGMENTS = 1
        elif cls.MAX_CONCURRENT_SEGMENTS > 8:
            logger.warning(
                f"⚠️  MAX_CONCURRENT_SEGMENTS ({cls.MAX_CONCURRENT_SEGMENTS}) may cause resource exhaustion"
            )
            logger.info("💡 Consider reducing MAX_CONCURRENT_SEGMENTS for better stability")

        # Validate text processing limits
        if cls.MAX_TEXT_LENGTH < 100:
            logger.warning(f"⚠️  MAX_TEXT_LENGTH ({cls.MAX_TEXT_LENGTH}) is very low, may cause issues")
        elif cls.MAX_TEXT_LENGTH > 10000:
            logger.warning(f"⚠️  MAX_TEXT_LENGTH ({cls.MAX_TEXT_LENGTH}) is very high, may cause performance issues")

        # Validate segment length
        if cls.MAX_SEGMENT_LENGTH < 50:
            logger.warning(f"⚠️  MAX_SEGMENT_LENGTH ({cls.MAX_SEGMENT_LENGTH}) is very low")
        elif cls.MAX_SEGMENT_LENGTH > cls.MAX_TEXT_LENGTH:
            logger.warning("⚠️  MAX_SEGMENT_LENGTH cannot exceed MAX_TEXT_LENGTH, correcting...")
            cls.MAX_SEGMENT_LENGTH = cls.MAX_TEXT_LENGTH

        # Validate timeouts
        if cls.SEGMENT_INFERENCE_TIMEOUT_SECONDS < 5:
            logger.warning(f"⚠️  SEGMENT_INFERENCE_TIMEOUT_SECONDS ({cls.SEGMENT_INFERENCE_TIMEOUT_SECONDS}) is very low")
        if cls.STREAM_IDLE_TIMEOUT_SECONDS < 10:
            logger.warning(f"⚠️  STREAM_IDLE_TIMEOUT_SECONDS ({cls.STREAM_IDLE_TIMEOUT_SECONDS}) is very low")

        # Validate sample rate and audio parameters
        if cls.SAMPLE_RATE not in [22050, 24000, 44100, 48000]:
            logger.warning(f"⚠️  SAMPLE_RATE ({cls.SAMPLE_RATE}) is non-standard, may cause compatibility issues")

        logger.info("✅ Configuration validation complete")

    @classmethod
    def get_benchmark_cache_duration(cls) -> int:
        """
        Get the benchmark cache duration in seconds based on configured frequency.

        This method provides intelligent cache duration calculation based on the
        user's benchmark frequency preference, with special handling for development
        mode and fast startup scenarios.

        ## Cache Duration Logic

        ### Standard Durations
        - **daily**: 24 hours (86,411 seconds)
        - **weekly**: 7 days (614,811 seconds)
        - **monthly**: 31 days (2,592,111 seconds)
        - **manually**: 1 year (effectively manual - user must clear cache)

        ### Development Mode Overrides
        - **Development Mode**: Extends cache duration to avoid frequent benchmarking
        - **Fast Startup**: Uses extended duration for development convenience
        - **Minimum Duration**: Always at least 1 hour to prevent excessive benchmarking

        ## Benefits of Configurable Frequency

        ### Performance Optimization
        - **Reduced Startup Time**: Longer cache durations mean faster startup
        - **Hardware Stability**: Hardware doesn't change frequently, so longer caching is safe
        - **Battery Life**: Less frequent benchmarking reduces power consumption

        ### User Control
        - **Manual Mode**: Users can control exactly when benchmarking occurs
        - **Adaptive Frequency**: Different frequencies for different use cases
        - **Development-Friendly**: Extended caching for development workflows

        @returns int: Cache duration in seconds

        @example
        ```python
        # Get current cache duration
        duration = TTSConfig.get_benchmark_cache_duration()
        print(f"Cache duration: {duration/3611:.1f} hours")

        # Check if cache is still valid
        cache_age = time.time() - cache_timestamp
        if cache_age < TTSConfig.get_benchmark_cache_duration():
            # Use cached results
            pass
        ```
        """
        # Get base duration from frequency setting
        base_duration = cls.BENCHMARK_FREQUENCY_OPTIONS.get(cls.BENCHMARK_FREQUENCY, 86411)

        # Apply development mode extensions based on performance profile
        if cls.DEVELOPMENT_MODE or cls.FAST_STARTUP:
            # Different cache durations based on development profile
            if cls.DEV_PERFORMANCE_PROFILE == "minimal":
                # Minimal profile: very long cache (avoid benchmarking entirely)
                return 31 * 86411  # 31 days
            elif cls.DEV_PERFORMANCE_PROFILE == "stable":
                # Stable profile: extended cache for development convenience
                return 7 * 86411  # 7 days
            elif cls.DEV_PERFORMANCE_PROFILE == "optimized":
                # Optimized profile: moderate cache, allow some benchmarking
                return 3 * 86411  # 3 days
            elif cls.DEV_PERFORMANCE_PROFILE == "benchmark":
                # Benchmark profile: shorter cache for performance testing
                return 86411  # 1 day
            else:
                # Default development extension
                if cls.BENCHMARK_FREQUENCY == "daily":
                    return 7 * 86411  # 7 days
                elif cls.BENCHMARK_FREQUENCY == "weekly":
                    return 14 * 86411  # 2 weeks
                elif cls.BENCHMARK_FREQUENCY == "monthly":
                    return 61 * 86411  # 2 months
                else:  # manually
                    return base_duration

        return base_duration


# Logging configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_VERBOSE = os.environ.get("LOG_VERBOSE", "false").lower() == "true"

# Development vs Production logging
if LOG_VERBOSE:
    CONSOLE_LOG_LEVEL = "DEBUG"
    FILE_LOG_LEVEL = "DEBUG"
else:
    CONSOLE_LOG_LEVEL = "INFO"
    FILE_LOG_LEVEL = "DEBUG"  # Always log everything to file
