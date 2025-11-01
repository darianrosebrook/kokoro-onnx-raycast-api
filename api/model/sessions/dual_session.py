"""
Dual session management for concurrent ANE + GPU processing.

This module implements intelligent session routing based on segment complexity
and hardware availability, enabling parallel processing across Apple Silicon's
Neural Engine and GPU cores for optimal performance.
"""

import logging

# Global dual session manager instance with thread safety
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

dual_session_manager: Optional["DualSessionManager"] = None
_dual_session_lock = threading.Lock()


@dataclass
class SessionUtilization:
    """Tracks session utilization statistics."""

    total_requests: int = 0
    ane_requests: int = 0
    gpu_requests: int = 0
    cpu_requests: int = 0
    total_processing_time: float = 0.0
    ane_processing_time: float = 0.0
    gpu_processing_time: float = 0.0
    cpu_processing_time: float = 0.0
    concurrent_segments_active: int = 0
    peak_concurrent_segments: int = 0

    def update_request(self, session_type: str, processing_time: float):
        """Update utilization statistics for a completed request."""
        self.total_requests += 1
        self.total_processing_time += processing_time

        if session_type == "ane":
            self.ane_requests += 1
            self.ane_processing_time += processing_time
        elif session_type == "gpu":
            self.gpu_requests += 1
            self.gpu_processing_time += processing_time
        elif session_type == "cpu":
            self.cpu_requests += 1
            self.cpu_processing_time += processing_time


class MemoryFragmentationWatchdog:
    """
    Monitors and manages memory fragmentation in long-running systems.

    This watchdog detects memory fragmentation patterns and triggers
    cleanup operations to maintain optimal performance.
    """

    def __init__(self):
        self.last_cleanup_time = time.time()
        self.cleanup_interval = 14400.0  # 4 hours (was 1 hour)
        self.memory_pressure_threshold = 0.95  # 95% memory usage (was 85%)
        self.logger = logging.getLogger(__name__ + ".MemoryFragmentationWatchdog")

    def check_memory_pressure(self) -> bool:
        """Check if system is under memory pressure."""
        try:
            import psutil

            memory = psutil.virtual_memory()
            return memory.percent / 100.0 > self.memory_pressure_threshold
        except ImportError:
            return False
        except Exception as e:
            self.logger.debug(f"Could not check memory pressure: {e}")
            return False

    def should_cleanup(self) -> bool:
        """Determine if cleanup should be performed."""
        time_since_cleanup = time.time() - self.last_cleanup_time
        memory_pressure = self.check_memory_pressure()

        # Log cleanup decision for debugging
        if time_since_cleanup > self.cleanup_interval:
            self.logger.info(
                f"Cleanup triggered by time interval: {time_since_cleanup / 3600:.1f}h > {self.cleanup_interval / 3600:.1f}h"
            )
        elif memory_pressure:
            try:
                import psutil

                mem = psutil.virtual_memory()
                self.logger.info(
                    f"Cleanup triggered by memory pressure: {mem.percent:.1f}% > {self.memory_pressure_threshold * 100:.1f}%"
                )
            except:
                self.logger.info(
                    "Cleanup triggered by memory pressure (details unavailable)"
                )

        return time_since_cleanup > self.cleanup_interval or memory_pressure

    def cleanup_if_needed(self):
        """Perform cleanup if needed."""
        if not self.should_cleanup():
            return

        self.logger.info("Performing memory fragmentation cleanup...")

        try:
            # Get dual session manager if available
            dual_session_manager = get_dual_session_manager()
            if dual_session_manager:
                # Try incremental cleanup first
                try:
                    dual_session_manager.incremental_cleanup()
                    self.logger.info("Incremental cleanup completed successfully")
                except Exception as inc_error:
                    self.logger.warning(f"Incremental cleanup failed: {inc_error}")
                    self.logger.info("Falling back to full session reinitialization...")
                    dual_session_manager.cleanup_sessions()

            # Force garbage collection
            import gc

            gc.collect()

            self.last_cleanup_time = time.time()
            self.logger.info("Memory cleanup completed")

        except Exception as e:
            self.logger.warning(f"Memory cleanup failed: {e}")


class DualSessionManager:
    """
    Manages dual CoreML sessions for ANE + GPU concurrent processing.

    This manager implements intelligent session routing based on segment complexity
    and hardware availability, enabling parallel processing across Apple Silicon's
    Neural Engine and GPU cores for optimal performance.
    """

    def __init__(self, capabilities: Optional[Dict[str, Any]] = None):
        self.sessions = {
            "ane": None,  # Neural Engine optimized session
            "gpu": None,  # GPU optimized session
            "cpu": None,  # CPU fallback session
        }
        self.session_locks = {
            "ane": threading.Lock(),
            "gpu": threading.Lock(),
            "cpu": threading.Lock(),
        }
        self.utilization = SessionUtilization()
        self.memory_watchdog = MemoryFragmentationWatchdog()

        # Semaphore-based load control to prevent CoreML queue thrashing
        # Align concurrency with global config for better throughput
        try:
            from api.config import TTSConfig

            self.max_concurrent_segments = max(
                2, int(getattr(TTSConfig, "MAX_CONCURRENT_SEGMENTS", 4))
            )
        except Exception:
            self.max_concurrent_segments = 4
        self.segment_semaphore = threading.Semaphore(self.max_concurrent_segments)

        self.logger = logging.getLogger(__name__ + ".DualSessionManager")

        # Store capabilities for session configuration
        if capabilities is None:
            from api.model.hardware import detect_apple_silicon_capabilities

            capabilities = detect_apple_silicon_capabilities()
        self.capabilities = capabilities

        # Initialize sessions based on hardware capabilities
        self._initialize_sessions()

    def process_segment_concurrent(
        self, text: str, voice: str, speed: float, lang: str = "en"
    ):
        """
        Process a text segment using concurrent session management.

        This method intelligently routes the segment to the best available session
        (ANE, GPU, or CPU) based on complexity analysis and current load.

        @param text: Text to process
        @param voice: Voice to use for synthesis
        @param speed: Speech speed multiplier
        @param lang: Language code
        @returns: Tuple of (audio_samples, metadata)
        """
        # Acquire semaphore to control concurrency
        with self.segment_semaphore:
            self.utilization.concurrent_segments_active += 1
            self.utilization.peak_concurrent_segments = max(
                self.utilization.peak_concurrent_segments,
                self.utilization.concurrent_segments_active,
            )

            try:
                # Analyze segment complexity to determine optimal session
                session_type = self._determine_optimal_session(text)

                start_time = time.perf_counter()

                # Get the session and process the segment
                session = self._get_session(session_type)
                if session is None:
                    # Fallback to any available session
                    session_type = "cpu"
                    session = self._get_session("cpu")

                if session is None:
                    raise RuntimeError("No available sessions for processing")

                # Use the session to generate audio with memory management
                with self.session_locks[session_type]:
                    # Apply CoreML memory management for inference operations
                    try:
                        from api.model.memory.coreml_leak_mitigation import (
                            get_memory_manager,
                        )

                        manager = get_memory_manager()

                        with manager.managed_operation(
                            f"inference_{session_type}_{text[:20]}"
                        ):
                            result = session.create(text, voice, speed, lang)

                    except ImportError:
                        # Fallback without memory management if not available
                        result = session.create(text, voice, speed, lang)

                    # Kokoro.create() returns (samples, model_metadata)
                    if isinstance(result, tuple) and len(result) >= 2:
                        samples, model_metadata = result[0], result[1]
                    else:
                        samples = result
                        model_metadata = {}

                processing_time = time.perf_counter() - start_time

                # Update utilization statistics
                self.utilization.update_request(session_type, processing_time)

                # Memory cleanup check
                self.memory_watchdog.cleanup_if_needed()

                # Validate samples before returning
                if samples is None or (
                    hasattr(samples, "__len__") and len(samples) == 0
                ):
                    self.logger.warning(
                        f"Session {session_type} returned empty samples for text: '{text[:50]}...'"
                    )
                    raise RuntimeError(
                        f"Session {session_type} produced no audio output"
                    )

                metadata = {
                    "session_type": session_type,
                    "processing_time": processing_time,
                    "concurrent_active": self.utilization.concurrent_segments_active,
                    "model_metadata": model_metadata,
                }

                self.logger.debug(
                    f"Processed segment with {session_type} session in {processing_time:.3f}s"
                )

                return samples, metadata

            except Exception as e:
                error_msg = str(e)
                self.logger.error(
                    f"Error processing segment with dual session manager: {error_msg}"
                )

                # Enhanced error handling with CoreML-specific fallback strategies
                try:
                    from api.model.providers.coreml import handle_coreml_execution_error

                    error_analysis = handle_coreml_execution_error(error_msg, len(text))

                    if (
                        error_analysis.get("fallback_provider")
                        == "CPUExecutionProvider"
                    ):
                        # Track CoreML error for this session type to avoid retrying soon
                        if not hasattr(self, "_recent_coreml_errors"):
                            self._recent_coreml_errors = {}
                        self._recent_coreml_errors[session_type] = time.time()

                        self.logger.info(
                            f" Switching to CPU fallback due to: {error_analysis.get('reason')}"
                        )
                        cpu_session = self._get_session("cpu")
                        if cpu_session:
                            with self.session_locks["cpu"]:
                                result = cpu_session.create(text, voice, speed, lang)
                                if isinstance(result, tuple) and len(result) >= 2:
                                    samples = result[0]
                                else:
                                    samples = result
                            return samples, {
                                "session_type": "cpu_fallback",
                                "error": str(e),
                                "fallback_reason": error_analysis.get("reason"),
                                "coreml_disabled": error_analysis.get(
                                    "coreml_disabled", False
                                ),
                            }

                    elif error_analysis.get("cleanup_performed"):
                        # Retry with CoreML after cleanup
                        self.logger.info(" Retrying with CoreML after cleanup...")
                        try:
                            result = session.create(text, voice, speed, lang)
                            if isinstance(result, tuple) and len(result) >= 2:
                                samples = result[0]
                                model_metadata = result[1] if len(result) > 1 else {}
                            else:
                                samples = result
                                model_metadata = {}
                            return samples, {
                                "session_type": session_type,
                                "retry_after_cleanup": True,
                                "cleanup_reason": error_analysis.get("reason"),
                            }
                        except Exception as retry_error:
                            self.logger.warning(
                                f"CoreML retry after cleanup failed: {retry_error}"
                            )
                            # Fall through to CPU fallback

                except ImportError:
                    # Fallback if CoreML error handling not available
                    pass

                # Standard CPU fallback
                try:
                    cpu_session = self._get_session("cpu")
                    if cpu_session:
                        with self.session_locks["cpu"]:
                            result = cpu_session.create(text, voice, speed, lang)
                            if isinstance(result, tuple) and len(result) >= 2:
                                samples = result[0]
                            else:
                                samples = result
                        return samples, {
                            "session_type": "cpu_fallback",
                            "error": str(e),
                        }
                except Exception as fallback_error:
                    self.logger.error(f"CPU fallback also failed: {fallback_error}")

                raise e

            finally:
                # CRITICAL FIX: Always decrement concurrent counter
                self.utilization.concurrent_segments_active -= 1

    def _determine_optimal_session(self, text: str) -> str:
        """
        Determine the optimal session type based on text complexity and availability.

        Enhanced with CoreML error history tracking to avoid problematic sessions.

        @param text: Text to analyze
        @returns: Session type ('ane', 'gpu', or 'cpu')
        """
        # Simple heuristic based on text length and complexity
        text_length = len(text)
        word_count = len(text.split())

        # Check session availability (if locked, prefer alternatives)
        ane_available = self.session_locks["ane"].acquire(blocking=False)
        gpu_available = self.session_locks["gpu"].acquire(blocking=False)
        cpu_available = self.session_locks["cpu"].acquire(blocking=False)

        # Release the locks immediately (we just wanted to check availability)
        if ane_available:
            self.session_locks["ane"].release()
        if gpu_available:
            self.session_locks["gpu"].release()
        if cpu_available:
            self.session_locks["cpu"].release()

        # Check for recent CoreML errors to avoid problematic sessions
        recent_errors = getattr(self, "_recent_coreml_errors", {})
        current_time = time.time()

        # Clean old error records (older than 5 minutes)
        for session_type in list(recent_errors.keys()):
            if current_time - recent_errors[session_type] > 300:  # 5 minutes
                del recent_errors[session_type]

        # Skip sessions that have had recent CoreML errors
        if (
            recent_errors.get("ane", 0) > current_time - 60
        ):  # Skip ANE if error in last minute
            ane_available = False
        if (
            recent_errors.get("gpu", 0) > current_time - 60
        ):  # Skip GPU if error in last minute
            gpu_available = False

        # Decision logic based on complexity and availability
        if text_length > 200 or word_count > 30:
            # Complex text - prefer ANE if available, then GPU
            if ane_available and self.sessions["ane"]:
                return "ane"
            elif gpu_available and self.sessions["gpu"]:
                return "gpu"
            else:
                return "cpu"
        elif text_length > 80 or word_count > 15:
            # Medium text - prefer CPU unless ANE is clearly beneficial
            if cpu_available and self.sessions["cpu"]:
                return "cpu"
            elif ane_available and self.sessions["ane"]:
                return "ane"
            elif gpu_available and self.sessions["gpu"]:
                return "gpu"
            else:
                return "cpu"
        else:
            # Simple text - force CPU for minimal TTFA
            if cpu_available and self.sessions["cpu"]:
                return "cpu"
            elif gpu_available and self.sessions["gpu"]:
                return "gpu"
            elif ane_available and self.sessions["ane"]:
                return "ane"
            else:
                return "cpu"  # Always fallback to CPU

    def _get_session(self, session_type: str):
        """Get a session by type."""
        return self.sessions.get(session_type)

    def _initialize_sessions(self):
        """Initialize sessions based on hardware capabilities."""
        try:
            # Only initialize on Apple Silicon with Neural Engine
            if not (
                self.capabilities.get("is_apple_silicon", False)
                and self.capabilities.get("has_neural_engine", False)
            ):
                self.logger.info(
                    "Non-Apple Silicon or no Neural Engine - dual sessions not supported"
                )
                return

            # Pre-create shared session options and provider options to avoid duplication
            import onnxruntime as ort

            from api.config import TTSConfig
            from api.model.providers import (
                create_coreml_provider_options,
                create_optimized_session_options,
            )

            self.logger.debug(
                "Creating shared session and provider options for dual sessions..."
            )

            # Create shared session options (these are the same for all sessions)
            self._shared_session_options = create_optimized_session_options(
                self.capabilities
            )

            # Create base CoreML provider options (will be modified per session)
            self._base_coreml_options = create_coreml_provider_options(
                self.capabilities
            )

            # OPTIMIZATION: Initialize CPU session FIRST to populate cache early
            # This ensures CPU model is available for ANE/GPU sessions that may need fallback
            self._initialize_cpu_session()

            # Initialize ANE-optimized session
            self._initialize_ane_session()

            # Initialize GPU-optimized session if supported
            self._initialize_gpu_session()

        except Exception as e:
            self.logger.error(f"Failed to initialize dual sessions: {e}")

    def _initialize_ane_session(self):
        """Initialize Neural Engine optimized session."""
        try:
            import onnxruntime as ort

            from api.config import TTSConfig

            # Use shared session options
            session_options = self._shared_session_options

            # Create ANE-specific CoreML provider options from base
            coreml_options = self._base_coreml_options.copy()
            coreml_options["MLComputeUnits"] = "CPUAndNeuralEngine"  # Force ANE usage

            # Create the session
            providers = [
                ("CoreMLExecutionProvider", coreml_options),
                "CPUExecutionProvider",
            ]

            # Create ONNX Runtime session with context leak mitigation
            self.logger.debug("Creating ANE-optimized ONNX Runtime session...")

            # Pre-session cleanup to minimize context leaks
            try:
                from api.model.providers.coreml import startup_context_leak_mitigation

                startup_context_leak_mitigation()
            except Exception as cleanup_error:
                self.logger.debug(f"Pre-ANE session cleanup failed: {cleanup_error}")

            ort_session = ort.InferenceSession(
                TTSConfig.MODEL_PATH, sess_options=session_options, providers=providers
            )

            # Post-session cleanup to address any context leaks
            try:
                import time

                time.sleep(0.1)  # Brief pause to allow CoreML to settle
                from api.model.providers.coreml import startup_context_leak_mitigation

                startup_context_leak_mitigation()
                self.logger.debug("Post-ANE session cleanup completed")
            except Exception as cleanup_error:
                self.logger.debug(f"Post-ANE session cleanup failed: {cleanup_error}")

            # Wrap in Kokoro model to get the .generate() method
            from kokoro_onnx import Kokoro

            self.sessions["ane"] = Kokoro.from_session(
                session=ort_session, voices_path=TTSConfig.VOICES_PATH
            )

            self.logger.info("✅ ANE-optimized session initialized")

        except Exception as e:
            self.logger.warning(f"Failed to initialize ANE session: {e}")

    def _initialize_gpu_session(self):
        """Initialize GPU optimized session."""
        try:
            import onnxruntime as ort

            from api.config import TTSConfig

            # Use shared session options
            session_options = self._shared_session_options

            # Create GPU-specific CoreML provider options from base
            coreml_options = self._base_coreml_options.copy()
            coreml_options["MLComputeUnits"] = "CPUAndGPU"  # Force GPU usage

            # Create the session
            providers = [
                ("CoreMLExecutionProvider", coreml_options),
                "CPUExecutionProvider",
            ]

            # Create ONNX Runtime session with context leak mitigation
            self.logger.debug("Creating GPU-optimized ONNX Runtime session...")

            # Pre-session cleanup to minimize context leaks
            try:
                from api.model.providers.coreml import startup_context_leak_mitigation

                startup_context_leak_mitigation()
            except Exception as cleanup_error:
                self.logger.debug(f"Pre-GPU session cleanup failed: {cleanup_error}")

            ort_session = ort.InferenceSession(
                TTSConfig.MODEL_PATH, sess_options=session_options, providers=providers
            )

            # Post-session cleanup to address any context leaks
            try:
                import time

                time.sleep(0.1)  # Brief pause to allow CoreML to settle
                from api.model.providers.coreml import startup_context_leak_mitigation

                startup_context_leak_mitigation()
                self.logger.debug("Post-GPU session cleanup completed")
            except Exception as cleanup_error:
                self.logger.debug(f"Post-GPU session cleanup failed: {cleanup_error}")

            # Wrap in Kokoro model to get the .generate() method
            from kokoro_onnx import Kokoro

            self.sessions["gpu"] = Kokoro.from_session(
                session=ort_session, voices_path=TTSConfig.VOICES_PATH
            )

            self.logger.info("✅ GPU-optimized session initialized")

        except Exception as e:
            self.logger.warning(f"Failed to initialize GPU session: {e}")

    def _initialize_cpu_session(self):
        """Initialize CPU fallback session using shared model cache when available."""
        try:
            from api.config import TTSConfig

            # OPTIMIZATION: Try to use cached CPU model from shared cache to avoid duplicate model loading
            # This saves ~7-8 seconds on startup by reusing the existing CPU model instance
            try:
                from api.tts.core import get_or_create_cached_model, is_model_cached

                # Check if CPU model is already cached
                was_cached = is_model_cached("CPUExecutionProvider")
                cached_cpu_model = get_or_create_cached_model("CPUExecutionProvider")

                if was_cached:
                    self.logger.info(
                        "✅ Using cached CPU model from shared cache (avoiding duplicate model load)"
                    )
                else:
                    # Model was just created and cached - log appropriately
                    self.logger.info(
                        "✅ CPU model created and cached for dual session manager"
                    )

                self.sessions["cpu"] = cached_cpu_model
                return

            except ImportError:
                # Fallback if import fails
                self.logger.debug(
                    "Could not import model cache functions, creating new CPU session"
                )
            except Exception as cache_error:
                self.logger.debug(
                    f"Could not use cached CPU model: {cache_error}, creating new session"
                )

            # Fallback: Create new CPU session if cache is unavailable
            import onnxruntime as ort

            # Use shared session options
            session_options = self._shared_session_options

            # Create ONNX Runtime session with CPU provider only
            ort_session = ort.InferenceSession(
                TTSConfig.MODEL_PATH,
                sess_options=session_options,
                providers=["CPUExecutionProvider"],
            )

            # Wrap in Kokoro model to get the .generate() method
            from kokoro_onnx import Kokoro

            self.sessions["cpu"] = Kokoro.from_session(
                session=ort_session, voices_path=TTSConfig.VOICES_PATH
            )

            self.logger.info("✅ CPU fallback session initialized (standalone)")

        except Exception as e:
            self.logger.error(f"Failed to initialize CPU session: {e}")

    def calculate_segment_complexity(self, text: str) -> float:
        """
        Calculate text complexity for session routing decisions.

        @param text: Input text to analyze
        @returns float: Complexity score (0.0 - 1.0)
        """
        if not text:
            return 0.0

        # Simple complexity heuristics
        complexity = 0.0

        # Length-based complexity
        length_factor = min(1.0, len(text) / 200)
        complexity += length_factor * 0.4

        # Character diversity
        unique_chars = len(set(text.lower()))
        diversity_factor = min(1.0, unique_chars / 50)
        complexity += diversity_factor * 0.3

        # Special characters and numbers
        special_count = sum(1 for c in text if not c.isalnum() and not c.isspace())
        special_factor = min(1.0, special_count / 20)
        complexity += special_factor * 0.3

        return min(1.0, complexity)

    def get_optimal_session(self, complexity: float) -> str:
        """
        Determine optimal session based on complexity and availability.

        @param complexity: Text complexity score (0.0 - 1.0)
        @returns str: Session type ('ane', 'gpu', or 'cpu')
        """
        # High complexity -> ANE (if available)
        if complexity > 0.7 and self.sessions["ane"] is not None:
            if not self.session_locks["ane"].locked():
                return "ane"

        # Medium complexity -> GPU (if available)
        if complexity > 0.3 and self.sessions["gpu"] is not None:
            if not self.session_locks["gpu"].locked():
                return "gpu"

        # Low complexity or fallback -> CPU
        return "cpu"

    def process_with_session(self, session_type: str, inputs: Dict[str, Any]) -> Any:
        """
        Process inputs with the specified session type.

        @param session_type: Type of session to use ('ane', 'gpu', 'cpu')
        @param inputs: Input data for inference
        @returns: Inference results
        """
        session = self.sessions.get(session_type)
        if session is None:
            raise ValueError(f"Session type {session_type} not available")

        start_time = time.time()

        try:
            with self.segment_semaphore:
                with self.session_locks[session_type]:
                    self.utilization.concurrent_segments_active += 1
                    self.utilization.peak_concurrent_segments = max(
                        self.utilization.peak_concurrent_segments,
                        self.utilization.concurrent_segments_active,
                    )

                    try:
                        result = session.run(None, inputs)
                        return result
                    finally:
                        self.utilization.concurrent_segments_active -= 1

        finally:
            processing_time = time.time() - start_time
            self.utilization.update_request(session_type, processing_time)

            # Check for memory cleanup
            self.memory_watchdog.cleanup_if_needed()

    def get_utilization_stats(self) -> Dict[str, Any]:
        """Get current utilization statistics."""
        total_time = self.utilization.total_processing_time

        return {
            "total_requests": self.utilization.total_requests,
            "ane_requests": self.utilization.ane_requests,
            "gpu_requests": self.utilization.gpu_requests,
            "cpu_requests": self.utilization.cpu_requests,
            "ane_percentage": (self.utilization.ane_processing_time / total_time * 100)
            if total_time > 0
            else 0,
            "gpu_percentage": (self.utilization.gpu_processing_time / total_time * 100)
            if total_time > 0
            else 0,
            "cpu_percentage": (self.utilization.cpu_processing_time / total_time * 100)
            if total_time > 0
            else 0,
            "concurrent_segments_active": self.utilization.concurrent_segments_active,
            "max_concurrent_segments": self.max_concurrent_segments,
            "sessions_available": {
                "ane": self.sessions["ane"] is not None,
                "gpu": self.sessions["gpu"] is not None,
                "cpu": self.sessions["cpu"] is not None,
            },
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get detailed session statistics for monitoring."""
        total_time = self.utilization.total_processing_time
        return {
            "utilization": {
                "total_requests": self.utilization.total_requests,
                "session_breakdown": {
                    "ane_requests": self.utilization.ane_requests,
                    "gpu_requests": self.utilization.gpu_requests,
                    "cpu_requests": self.utilization.cpu_requests,
                },
                "percentage_breakdown": {
                    "ane_percentage": (
                        self.utilization.ane_processing_time / total_time * 100
                    )
                    if total_time > 0
                    else 0,
                    "gpu_percentage": (
                        self.utilization.gpu_processing_time / total_time * 100
                    )
                    if total_time > 0
                    else 0,
                    "cpu_percentage": (
                        self.utilization.cpu_processing_time / total_time * 100
                    )
                    if total_time > 0
                    else 0,
                },
                "timing": {
                    "total_processing_time": self.utilization.total_processing_time,
                    "average_processing_time": self.utilization.total_processing_time
                    / max(self.utilization.total_requests, 1),
                    "ane_processing_time": self.utilization.ane_processing_time,
                    "gpu_processing_time": self.utilization.gpu_processing_time,
                    "cpu_processing_time": self.utilization.cpu_processing_time,
                },
            },
            "concurrency": {
                "max_concurrent_segments": self.max_concurrent_segments,
                "peak_concurrent_segments": self.utilization.peak_concurrent_segments,
                "current_concurrent_segments": self.utilization.concurrent_segments_active,
            },
            "sessions": {
                "ane_available": self.sessions["ane"] is not None,
                "gpu_available": self.sessions["gpu"] is not None,
                "cpu_available": self.sessions["cpu"] is not None,
            },
        }

    def cleanup_sessions(self):
        """
        Enhanced session cleanup with complete session destruction and reinitialization.

        This method performs aggressive cleanup to prevent TTS model session corruption
        that causes silent audio generation after the first successful request.
        """
        self.logger.info("Performing enhanced session cleanup and resource reset...")

        # Reset concurrent counter to prevent session blocking
        self.utilization.concurrent_segments_active = 0

        # ENHANCED FIX: Complete session destruction and cleanup
        # Step 1: Force complete destruction of all TTS model sessions
        self.logger.debug("Step 1: Destroying existing sessions...")
        for session_type in ["ane", "gpu", "cpu"]:
            if self.sessions[session_type] is not None:
                try:
                    # Get reference to session for proper cleanup
                    session = self.sessions[session_type]

                    # If this is a Kokoro model with underlying ONNX session, clean it up
                    if hasattr(session, "session"):
                        try:
                            # Force ONNX Runtime session cleanup
                            onnx_session = session.session
                            if hasattr(onnx_session, "end_profiling"):
                                onnx_session.end_profiling()
                            # Explicitly delete the ONNX session
                            del onnx_session
                            self.logger.debug(
                                f"Destroyed ONNX Runtime session for {session_type}"
                            )
                        except Exception as onnx_err:
                            self.logger.warning(
                                f"ONNX session cleanup failed for {session_type}: {onnx_err}"
                            )

                    # Delete the Kokoro model instance
                    del session
                    self.sessions[session_type] = None
                    self.logger.debug(f"Completely destroyed {session_type} session")
                except Exception as e:
                    self.logger.warning(f"Error destroying {session_type} session: {e}")
                    # Force None assignment even if cleanup failed
                    self.sessions[session_type] = None

        # Step 2: Force garbage collection to free memory
        self.logger.debug("Step 2: Aggressive memory cleanup...")
        try:
            import gc

            # Multiple garbage collection passes to ensure cleanup
            for i in range(3):
                collected = gc.collect()
                if collected > 0:
                    self.logger.debug(f"GC pass {i + 1}: collected {collected} objects")
        except Exception as e:
            self.logger.warning(f"Garbage collection failed: {e}")

        # Step 3: Clear CoreML temp directories and contexts
        self.logger.debug("Step 3: CoreML context cleanup...")
        try:
            # Clear any CoreML temporary files that might be causing context leaks
            from api.model.providers.coreml import cleanup_coreml_contexts

            cleanup_coreml_contexts(
                aggressive=True
            )  # Use aggressive mode for full cleanup
            self.logger.debug("CoreML context cleanup completed")
        except ImportError:
            self.logger.debug(
                "CoreML context cleanup not available (expected if not using CoreML)"
            )
        except Exception as e:
            self.logger.warning(f"CoreML context cleanup failed: {e}")

        # Step 4: Reset all synchronization primitives
        self.logger.debug("Step 4: Resetting synchronization primitives...")

        # Force release all session locks
        for session_type, lock in self.session_locks.items():
            try:
                # Try to acquire and immediately release to clear any stuck locks
                if lock.acquire(blocking=False):
                    lock.release()
                    self.logger.debug(f"Released {session_type} session lock")
            except Exception as e:
                self.logger.warning(f"Could not release {session_type} lock: {e}")

        # Reset semaphore
        try:
            # Drain the semaphore and recreate it
            while self.segment_semaphore.acquire(blocking=False):
                pass
            # Recreate with proper count
            self.segment_semaphore = threading.Semaphore(self.max_concurrent_segments)
            self.logger.debug("Reset segment semaphore")
        except Exception as e:
            self.logger.warning(f"Could not reset semaphore: {e}")

        # Step 5: Reinitialize sessions from scratch with context leak prevention
        self.logger.debug("Step 5: Reinitializing sessions from scratch...")
        try:
            # Add a small delay to allow CoreML contexts to fully release
            import time

            time.sleep(0.5)

            # Additional pre-initialization cleanup
            try:
                from api.model.providers.coreml import cleanup_coreml_contexts

                cleanup_coreml_contexts(aggressive=True)
                self.logger.debug("Pre-initialization CoreML cleanup completed")
            except Exception as pre_cleanup_error:
                self.logger.debug(
                    f"Pre-initialization cleanup failed: {pre_cleanup_error}"
                )

            self._initialize_sessions()
            self.logger.info("Successfully reinitialized TTS model sessions")

            # Post-initialization context leak check
            self.logger.debug("Monitoring for context leaks after reinitialization...")

        except Exception as e:
            self.logger.error(f"Failed to reinitialize sessions: {e}")
            # Even if initialization fails, log the attempt
            self.logger.warning(
                "Session reinitialization failed - sessions will be unavailable until next restart"
            )

        self.logger.info("Enhanced session cleanup completed")

    def incremental_cleanup(self):
        """
        Perform incremental cleanup without full session reinitialization.

        This is a lighter-weight alternative to cleanup_sessions() that performs
        memory cleanup and context clearing without destroying and recreating sessions.
        """
        self.logger.info("Performing incremental session cleanup...")

        # Reset concurrent counter to prevent session blocking
        self.utilization.concurrent_segments_active = 0

        # Step 1: Clear CoreML contexts without destroying sessions
        self.logger.debug("Step 1: CoreML context cleanup...")
        try:
            from api.model.providers.coreml import cleanup_coreml_contexts

            cleanup_coreml_contexts(
                aggressive=False
            )  # Use non-aggressive mode for incremental cleanup
            self.logger.debug("CoreML context cleanup completed")
        except ImportError:
            self.logger.debug("CoreML context cleanup not available")
        except Exception as e:
            self.logger.warning(f"CoreML context cleanup failed: {e}")

        # Step 2: Garbage collection
        self.logger.debug("Step 2: Memory cleanup...")
        try:
            import gc

            collected = gc.collect()
            if collected > 0:
                self.logger.debug(f"Garbage collection freed {collected} objects")
        except Exception as e:
            self.logger.warning(f"Garbage collection failed: {e}")

        # Step 3: Reset synchronization primitives (but keep sessions alive)
        self.logger.debug("Step 3: Resetting synchronization primitives...")

        # Force release all session locks
        for session_type, lock in self.session_locks.items():
            try:
                if lock.acquire(blocking=False):
                    lock.release()
                    self.logger.debug(f"Released {session_type} session lock")
            except Exception as e:
                self.logger.warning(f"Could not release {session_type} lock: {e}")

        # Reset semaphore
        try:
            while self.segment_semaphore.acquire(blocking=False):
                pass
            self.segment_semaphore = threading.Semaphore(self.max_concurrent_segments)
            self.logger.debug("Reset segment semaphore")
        except Exception as e:
            self.logger.warning(f"Could not reset semaphore: {e}")

        # Step 4: Reset session state without destroying sessions
        self.reset_session_state()

        self.logger.info("Incremental session cleanup completed")

    def reset_session_state(self):
        """
        Reset session state to prevent blocking between requests.

        This method is lightweight and non-blocking - it only resets counters and
        releases locks if they're available. It does NOT recreate the semaphore
        because that would leave threads waiting on the old semaphore object.
        """
        # Reset concurrent tracking counter
        # This is safe because the counter is only used for tracking, not blocking
        self.utilization.concurrent_segments_active = 0

        # CRITICAL FIX: Release locks if they're stuck (non-blocking)
        # This ensures consecutive requests don't get stuck waiting for locks
        try:
            # Force release all session locks (non-blocking - only if immediately available)
            for session_type, lock in self.session_locks.items():
                try:
                    # Try to acquire and immediately release to clear any stuck locks
                    # This is non-blocking - if lock is held, we skip it
                    if lock.acquire(blocking=False):
                        lock.release()
                        self.logger.debug(
                            f"Released {session_type} session lock during reset"
                        )
                except Exception as e:
                    self.logger.debug(
                        f"Could not release {session_type} lock during reset (may be in use): {e}"
                    )

            # IMPORTANT: Do NOT recreate the semaphore here
            # If threads are waiting on the semaphore, recreating it leaves them
            # waiting on the old object. The semaphore will naturally release permits
            # when segments complete. The counter reset above ensures we don't
            # double-count segments.

        except Exception as e:
            self.logger.warning(f"Error during session state reset: {e}")

        # Log current state for debugging
        self.logger.debug(
            f"Session state reset - Active segments: {self.utilization.concurrent_segments_active}"
        )

        return True


def get_dual_session_manager() -> Optional[DualSessionManager]:
    """Get the global dual session manager instance with thread safety."""
    global dual_session_manager
    with _dual_session_lock:
        return dual_session_manager


def initialize_dual_session_manager(capabilities: Optional[Dict[str, Any]] = None):
    """Initialize the global dual session manager with thread safety."""
    global dual_session_manager

    with _dual_session_lock:
        if dual_session_manager is not None:
            logging.getLogger(__name__).debug(
                "✅ Dual session manager already initialized, skipping duplicate"
            )
            return dual_session_manager

        try:
            dual_session_manager = DualSessionManager(capabilities)
            return dual_session_manager
        except Exception as e:
            logging.getLogger(__name__).error(
                f"Failed to initialize dual session manager: {e}"
            )
            return None


def set_dual_session_manager(manager: "DualSessionManager"):
    """Set the global dual session manager instance with thread safety."""
    global dual_session_manager
    with _dual_session_lock:
        dual_session_manager = manager
