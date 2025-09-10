"""
Fast model initialization module.

This module provides optimized, non-blocking model initialization strategies
for the Kokoro-ONNX TTS model with background optimization.
"""

import os
import time
import threading
import logging
from typing import Dict, Any, Optional

from api.performance.startup_profiler import step_timer
from api.model.hardware import detect_apple_silicon_capabilities
from api.model.providers import (
    create_optimized_session_options,
    get_cached_provider_options, 
    setup_coreml_temp_directory
)
from api.model.benchmarking import benchmark_providers
from api.model.sessions import (
    initialize_dual_session_manager,
    get_model,
    set_model
)
from api.model.memory import initialize_dynamic_memory_manager
from api.model.pipeline import initialize_pipeline_warmer
from api.config import TTSConfig
from kokoro_onnx import Kokoro

import onnxruntime as ort

# Setup logger
logger = logging.getLogger(__name__)

# Cache for provider strategy
_cached_provider_strategy = None


def read_cached_provider_strategy() -> Optional[Dict[str, Any]]:
    """Read cached provider strategy from disk."""
    global _cached_provider_strategy
    if _cached_provider_strategy is not None:
        return _cached_provider_strategy
    
    # Implementation would read from cache file
    # For now, return None to use default strategy
    return None


def _initialize_session_for_provider(provider_name: str, capabilities: Dict[str, Any]) -> Kokoro:
    """
    Create a Kokoro model session for a specific provider using optimized options.

    @param provider_name: Name of the ONNX Runtime provider to use
    @param capabilities: Hardware capabilities dictionary
    @returns: Initialized Kokoro model instance
    @raises: Exception if initialization fails
    """
    # CoreML temp dir must be configured before CoreML session
    if provider_name == "CoreMLExecutionProvider":
        setup_coreml_temp_directory()

    session_options = create_optimized_session_options(capabilities)
    provider_options = get_cached_provider_options(provider_name, capabilities)
    providers = [(provider_name, provider_options)] if provider_options else [provider_name]

    # Use memory-managed session creation for CoreML provider
    if provider_name == "CoreMLExecutionProvider":
        try:
            from api.model.providers.coreml import coreml_memory_managed_session_creation
            
            def create_session():
                return ort.InferenceSession(
                    TTSConfig.MODEL_PATH,
                    sess_options=session_options,
                    providers=providers,
                )
            
            session = coreml_memory_managed_session_creation(create_session)
            logger.debug("✅ CoreML session created with memory management")
            
        except ImportError:
            logger.debug(" CoreML memory management not available, using standard creation")
            session = ort.InferenceSession(
                TTSConfig.MODEL_PATH,
                sess_options=session_options,
                providers=providers,
            )
    else:
        session = ort.InferenceSession(
            TTSConfig.MODEL_PATH,
            sess_options=session_options,
            providers=providers,
        )

    return Kokoro.from_session(session=session, voices_path=TTSConfig.VOICES_PATH)


def _hot_swap_provider(new_provider: str, capabilities: Dict[str, Any]) -> bool:
    """
    Reinitialize the global model with a new provider if different.
    
    This function is now thread-safe and ensures the model remains available 
    during the swap process to prevent 503 errors for API endpoints.

    @param new_provider: Name of the new provider to switch to
    @param capabilities: Hardware capabilities dictionary
    @returns: True on successful swap, False otherwise
    """
    from api.model.sessions import get_active_provider
    
    # Check if we're already using this provider
    if new_provider == get_active_provider():
        logger.debug(f"Already using {new_provider}, skipping hot-swap")
        return True
    
    # Verify current model is available before attempting swap
    current_model = get_model()
    if not current_model:
        logger.warning("Cannot hot-swap: no current model available")
        return False
        
    try:
        # Create the new model first (without setting it yet)
        logger.info(f"Preparing to switch to {new_provider} provider...")
        new_model = _initialize_session_for_provider(new_provider, capabilities)
        
        # Only set the new model after successful creation
        # This ensures the old model stays available until the new one is ready
        set_model(new_model, new_provider)
        logger.info(f"✅ Successfully switched active provider to {new_provider}")
        return True
        
    except Exception as e:
        logger.warning(f"Hot-swap to {new_provider} failed: {e}, keeping current provider")
        return False


def _initialize_heavy_components_async(capabilities: Dict[str, Any]) -> None:
    """
    Start heavy components (dual session manager, dynamic memory manager, pipeline warmer,
    real-time optimizer) in background threads to avoid blocking startup.
    
    This function is called from fast_init.py to initialize heavy components asynchronously.
    The lifecycle.py no longer duplicates this work, so this is the single initialization point.
    
    @param capabilities: Hardware capabilities dictionary
    """
    def _run():
        try:
            try:
                logger.info("Initializing dual session manager for concurrent ANE/GPU processing...")
                dsm = initialize_dual_session_manager(capabilities=capabilities)
                if dsm:
                    logger.info("✅ Dual session manager initialized successfully in background thread")
                    
                    # Pre-warm dual sessions to eliminate cold start penalty
                    try:
                        logger.info(" Pre-warming dual sessions...")
                        warming_start = time.perf_counter()
                        
                        # Test each session type with progressively complex text
                        warming_patterns = [
                            ("Hi", 0.2),  # Simple, should go to CPU/fast session
                            ("This is a more complex sentence for testing.", 0.7),  # Complex, should go to ANE/GPU
                        ]
                        
                        for text, expected_complexity in warming_patterns:
                            try:
                                # Use the dual session manager directly
                                result = dsm.process_segment_concurrent(text, "af_heart", 1.0, "en-us")
                                complexity = dsm.calculate_segment_complexity(text)
                                optimal_session = dsm.get_optimal_session(complexity)
                                logger.debug(f"Pre-warmed: '{text[:30]}...' → session={optimal_session}, complexity={complexity:.2f}")
                            except Exception as warmup_err:
                                logger.debug(f"Dual session warming failed for '{text[:20]}...': {warmup_err}")
                        
                        warming_time = (time.perf_counter() - warming_start) * 1000
                        logger.info(f"✅ Dual session pre-warming completed in {warming_time:.1f}ms")
                        
                    except Exception as warming_e:
                        logger.debug(f"Dual session pre-warming failed: {warming_e}")
                        
                else:
                    logger.error(" Dual session manager initialization returned None")
            except Exception as e:
                logger.error(f" Dual session init error: {e}", exc_info=True)

            try:
                logger.info("Initializing dynamic memory manager for adaptive memory sizing...")
                initialize_dynamic_memory_manager(capabilities=capabilities)
            except Exception as e:
                logger.debug(f"Dynamic memory init deferred error: {e}")

            try:
                logger.info("Initializing inference pipeline warmer...")
                initialize_pipeline_warmer()
            except Exception as e:
                logger.debug(f"Pipeline warmer init deferred error: {e}")

            try:
                from api.performance.optimization import initialize_real_time_optimizer
                logger.info("Initializing real-time performance optimizer...")
                initialize_real_time_optimizer()
            except Exception as e:
                logger.debug(f"Real-time optimizer init deferred error: {e}")
        except Exception:
            # Avoid crashing background thread
            pass

    t = threading.Thread(target=_run, name="kokoro-heavy-init", daemon=True)
    t.start()


def _benchmark_and_hotswap_async(capabilities: Dict[str, Any]) -> None:
    """
    Run provider benchmarking in the background and hot-swap if a better provider is found.
    
    @param capabilities: Hardware capabilities dictionary
    """
    import os
    
    # Check if CPU provider is forced via environment variables
    force_cpu = (
        os.environ.get('KOKORO_FORCE_CPU_PROVIDER', '').lower() == 'true' or
        os.environ.get('KOKORO_COREML_COMPUTE_UNITS', '').upper() == 'CPUONLY' or
        os.environ.get('KOKORO_DEV_PERFORMANCE_PROFILE', '').lower() == 'minimal'
    )
    
    # Check if benchmarking is disabled
    disable_benchmarking = (
        os.environ.get('KOKORO_DISABLE_PROVIDER_BENCHMARKING', '').lower() == 'true' or
        os.environ.get('KOKORO_DISABLE_ADAPTIVE_PROVIDER', '').lower() == 'true'
    )
    
    if force_cpu or disable_benchmarking:
        logger.info(" CPU provider locked via environment variables - skipping hot-swap")
        return
    
    def _run():
        try:
            optimal_provider, _results = benchmark_providers(capabilities=capabilities)
            from api.model.sessions import get_active_provider
            if optimal_provider and optimal_provider != get_active_provider():
                _hot_swap_provider(optimal_provider, capabilities)
        except Exception as e:
            logger.debug(f"Background benchmark/hot-swap failed: {e}")

    t = threading.Thread(target=_run, name="kokoro-bench-hotswap", daemon=True)
    t.start()


def initialize_model_fast():
    """
    Fast, non-blocking model initialization.

    This function implements a multi-stage initialization strategy:
    1. Quick hardware detection and capability analysis
    2. Fast provider selection based on cached results or safe defaults
    3. Model initialization with chosen provider and minimal warmup
    4. Background initialization of heavy components and benchmarking
    5. Hot-swap to optimal provider when benchmarking completes

    The goal is to get a working model as quickly as possible while
    optimizing performance in the background.
    """
    from api.model.sessions import get_model, set_model, is_model_loaded
    
    if is_model_loaded():
        return

    logger.info("Starting optimized model initialization...")
    start_ts = time.perf_counter()

    with step_timer("capabilities_detection"):
        capabilities = detect_apple_silicon_capabilities()

    # Determine initial provider quickly
    cached = read_cached_provider_strategy()
    initial_provider = cached.get("provider") if cached else None
    
    # Check for development mode provider configuration
    from api.config import TTSConfig
    force_cpu = TTSConfig.FORCE_CPU_PROVIDER if hasattr(TTSConfig, 'FORCE_CPU_PROVIDER') else False
    
    # Check for CPU-only environment variable (for production optimization)
    cpu_only_env = os.environ.get('KOKORO_COREML_COMPUTE_UNITS', '').upper() == 'CPUONLY'
    
    if force_cpu or cpu_only_env:
        initial_provider = "CPUExecutionProvider"
        reason = "development mode" if force_cpu else "CPU-only configuration"
        logger.info(f" {reason}: forcing CPU provider for consistent performance")
    elif not initial_provider:
        # Safe default
        initial_provider = "CoreMLExecutionProvider" if capabilities.get("is_apple_silicon") else "CPUExecutionProvider"

    # Attempt init with initial provider, fallback to CPU if needed
    tried_cpu_fallback = False
    for provider_attempt in [initial_provider, "CPUExecutionProvider"]:
        if provider_attempt == "CPUExecutionProvider" and tried_cpu_fallback:
            continue
        try:
            with step_timer(f"init_provider_{provider_attempt}"):
                model_candidate = _initialize_session_for_provider(provider_attempt, capabilities)
            set_model(model_candidate, provider_attempt)
            logger.info(f"✅ Fast init: provider={provider_attempt}")
            break
        except Exception as e:
            logger.warning(f"Fast init failed with {provider_attempt}: {e}")
            tried_cpu_fallback = tried_cpu_fallback or (provider_attempt == "CPUExecutionProvider")
            continue

    if not is_model_loaded():
        raise RuntimeError("Fast initialization failed for all providers")

    # Enhanced session warming to eliminate cold start penalty
    try:
        with step_timer("enhanced_session_warming"):
            model = get_model()
            if model:
                # Perform multiple warming inferences to pre-compile execution paths
                warming_texts = [
                    "Hi",  # Very short - forces fast path compilation  
                    "Hello world",  # Short - typical quick request
                    "This is a test sentence to warm up the model."  # Medium - more graph paths
                ]
                
                for i, text in enumerate(warming_texts):
                    try:
                        start_warmup = time.perf_counter()
                        model.create(text, "af_heart", 1.0, "en-us")
                        warmup_time = (time.perf_counter() - start_warmup) * 1000
                        logger.debug(f"Warming {i+1}/3: '{text[:20]}...' took {warmup_time:.1f}ms")
                    except Exception as warmup_err:
                        logger.debug(f"Warming {i+1}/3 failed: {warmup_err}")

                logger.info("✅ Enhanced session warming completed - cold start eliminated")
                
                # CRITICAL: Pre-warm ALL model caches used by adaptive provider
                # This prevents 2+ second cache misses when streaming switches providers
                try:
                    from api.tts.core import _get_cached_model
                    logger.info(" Pre-warming model cache for adaptive provider scenarios...")
                    adaptive_start = time.perf_counter()
                    
                    # Get the current active provider (already initialized)
                    current_provider = "CoreMLExecutionProvider" if "CoreML" in str(model.__class__) else "CPUExecutionProvider"
                    logger.debug(f"Current provider: {current_provider}")
                    
                    # ALWAYS pre-warm CPU model (for short text < 200 chars via adaptive provider)
                    logger.info(" Pre-warming CPU model for short text...")
                    cpu_model = _get_cached_model("CPUExecutionProvider")
                    cpu_model.create("Hi there", "af_heart", 1.0, "en-us")
                    logger.debug("✅ CPU model cache ready")
                    
                    # ALWAYS pre-warm CoreML model (for medium/long text > 200 chars via adaptive provider)
                    logger.info(" Pre-warming CoreML model for medium/long text...")
                    coreml_model = _get_cached_model("CoreMLExecutionProvider")
                    coreml_model.create("This is a longer test to warm up CoreML", "af_heart", 1.0, "en-us")
                    logger.debug("✅ CoreML model cache ready")
                    
                    adaptive_time = (time.perf_counter() - adaptive_start) * 1000
                    logger.info(f"✅ Adaptive provider cache pre-warming completed in {adaptive_time:.1f}ms")
                    
                except Exception as adaptive_err:
                    logger.debug(f"Adaptive provider cache pre-warming failed: {adaptive_err}")
    except Exception as e:
        logger.debug(f"Enhanced session warming failed: {e}")

    # Check for aggressive session warming (enabled by default to eliminate cold start)
    aggressive_warming = os.environ.get('KOKORO_AGGRESSIVE_WARMING', 'true').lower() == 'true'
    if aggressive_warming:
        try:
            with step_timer("aggressive_session_warming"):
                logger.info(" Starting aggressive session warming to eliminate cold start...")
                from api.model.pipeline import get_pipeline_warmer, initialize_pipeline_warmer
                
                # Initialize and trigger pipeline warmer immediately
                pipeline_warmer = initialize_pipeline_warmer()
                if pipeline_warmer:
                    # Run abbreviated warming focused on common short requests
                    import asyncio
                    
                    async def quick_warming():
                        await pipeline_warmer._cache_common_patterns()
                    
                    # Run the warming in a thread to avoid blocking
                    def run_warming():
                        try:
                            asyncio.run(quick_warming())
                            logger.info("✅ Aggressive session warming completed")
                        except Exception as warm_err:
                            logger.debug(f"Aggressive warming failed: {warm_err}")
                    
                    warming_thread = threading.Thread(target=run_warming, daemon=True)
                    warming_thread.start()
                    
        except Exception as e:
            logger.debug(f"Aggressive session warming failed: {e}")

    logger.info(f"✅ Fast initialization completed in {time.perf_counter() - start_ts:.2f}s")

    # Defer heavy components and benchmarking based on development profile
    skip_background = TTSConfig.SKIP_BACKGROUND_BENCHMARKING if hasattr(TTSConfig, 'SKIP_BACKGROUND_BENCHMARKING') else force_cpu
    disable_dual_sessions = TTSConfig.DISABLE_DUAL_SESSIONS if hasattr(TTSConfig, 'DISABLE_DUAL_SESSIONS') else False
    
    # Check if we should defer background initialization for fast startup
    defer_background_init = os.environ.get('KOKORO_DEFER_BACKGROUND_INIT', 'false').lower() == 'true'
    
    # Always initialize dual session manager unless explicitly disabled
    if not disable_dual_sessions:
        if defer_background_init:
            logger.info(" Dual session manager initialization deferred for fast startup")
            logger.info(" Use KOKORO_DEFER_BACKGROUND_INIT=false to enable background initialization")
        else:
            logger.info(f" Starting dual session manager initialization (disable_dual_sessions={disable_dual_sessions})")
            _initialize_heavy_components_async(capabilities)
    else:
        logger.info(f" Dual session manager initialization skipped (disable_dual_sessions={disable_dual_sessions})")
    
    # Only skip benchmarking if configured to do so
    if not skip_background:
        _benchmark_and_hotswap_async(capabilities)
    else:
        profile_name = getattr(TTSConfig, 'DEV_PERFORMANCE_PROFILE', 'unknown')
        logger.info(f" Skipping background benchmarking in {profile_name} development mode")

