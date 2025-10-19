"""
ONNX Runtime provider configuration and optimization.

This module handles ONNX Runtime-specific optimizations including
session options, memory management, and cross-platform optimizations.
"""

import os
import logging
import onnxruntime as ort
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Cache for session options (hardware-specific, deterministic)
_session_options_cache: Optional[ort.SessionOptions] = None
_provider_options_cache: Dict[str, Dict[str, Any]] = {}


def create_optimized_session_options(capabilities: Dict[str, Any]) -> ort.SessionOptions:
    """
    Create optimized ONNX Runtime session options based on hardware capabilities.
    
    This function analyzes the hardware configuration and creates optimal
    ONNX Runtime session settings for maximum performance.
    
    @param capabilities: Hardware capabilities from detect_apple_silicon_capabilities()
    @returns ort.SessionOptions: Optimized session options
    """
    global _session_options_cache
    
    # Return cached options if available and hardware hasn't changed
    if _session_options_cache is not None:
        return _session_options_cache
    
    session_options = ort.SessionOptions()
    
    # Set up temporary directory for ONNX Runtime
    from api.config import TTSConfig
    cache_dir = getattr(TTSConfig, 'CACHE_DIR', os.path.join(os.getcwd(), ".cache"))
    local_temp_dir = os.path.join(cache_dir, "coreml_temp")
    
    if os.path.exists(local_temp_dir):
        session_options.add_session_config_entry("session.use_env_allocators", "1")
        session_options.add_session_config_entry("session.temp_dir_path", local_temp_dir)
    
    # Graph optimization level - BASIC is best-balanced for TTS workloads
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    session_options.use_deterministic_compute = False  # Allow non-deterministic optimizations
    
    # Thread configuration based on hardware
    if capabilities.get('is_apple_silicon', False):
        neural_engine_cores = capabilities.get('neural_engine_cores', 0)
        
        if neural_engine_cores >= 32:  # M1 Max / M2 Max
            session_options.intra_op_num_threads = 8
            session_options.inter_op_num_threads = 4
            logger.debug(" M1 Max/M2 Max: Using 8 intra-op, 4 inter-op threads")
            
        elif neural_engine_cores >= 16:  # M1 / M2
            session_options.intra_op_num_threads = 6
            session_options.inter_op_num_threads = 2
            logger.debug(" M1/M2: Using 6 intra-op, 2 inter-op threads")
            
        else:  # Other Apple Silicon
            session_options.intra_op_num_threads = 4
            session_options.inter_op_num_threads = 2
            logger.debug(" Apple Silicon: Using 4 intra-op, 2 inter-op threads")
    else:
        # Conservative settings for non-Apple Silicon
        session_options.intra_op_num_threads = 2
        session_options.inter_op_num_threads = 1
        logger.debug(" Non-Apple Silicon: Using 2 intra-op, 1 inter-op threads")
    
    # Dynamic memory arena sizing
    try:
        from api.model.memory import get_dynamic_memory_manager
        dynamic_memory_manager = get_dynamic_memory_manager()
        
        if dynamic_memory_manager is not None:
            optimal_mb = dynamic_memory_manager.calculate_optimal_arena_size()
            session_options.add_session_config_entry("arena_extend_strategy", "kSameAsRequested")
            session_options.add_session_config_entry("session.dynamic_arena_initial", str(optimal_mb))
            logger.debug(f" Dynamic arena size: {optimal_mb}MB")
    except Exception as e:
        logger.debug(f"Could not configure dynamic memory arena: {e}")
    
    # Enable memory optimizations
    session_options.enable_mem_pattern = True
    session_options.enable_mem_reuse = True
    session_options.enable_cpu_mem_arena = True
    
    # Cache the session options
    _session_options_cache = session_options
    logger.info("✅ ONNX Runtime session options optimized and cached")
    
    return session_options


def get_cached_provider_options(provider_name: str, capabilities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get cached provider options or create new ones if not cached.
    
    This function provides provider-specific options optimized for the given hardware.
    
    @param provider_name: Name of the ONNX Runtime provider
    @param capabilities: Hardware capabilities from detect_apple_silicon_capabilities()
    @returns Dict[str, Any]: Provider-specific options
    """
    global _provider_options_cache
    
    # Return cached options if available
    if provider_name in _provider_options_cache:
        return _provider_options_cache[provider_name]
    
    provider_options = {}
    
    if provider_name == "CoreMLExecutionProvider":
        # Import CoreML-specific options
        from .coreml import create_coreml_provider_options
        provider_options = create_coreml_provider_options(capabilities)
        
    elif provider_name == "CPUExecutionProvider":
        # CPU provider optimizations
        cpu_cores = capabilities.get("cpu_cores", 4)
        
        provider_options = {
            "intra_op_num_threads": min(4, cpu_cores),
            "inter_op_num_threads": 1,
            "arena_extend_strategy": "kSameAsRequested",
            "enable_cpu_mem_arena": "1",
            "enable_mem_pattern": "1",
        }
        
        # Memory-based optimizations for CPU provider
        memory_gb = capabilities.get('memory_gb', 8)
        if memory_gb >= 16:
            provider_options.update({
                "cpu_mem_arena_initial_chunk_size": "67108864",  # 64MB
                "cpu_mem_arena_max_chunk_size": "134217728",     # 128MB
            })
        else:
            provider_options.update({
                "cpu_mem_arena_initial_chunk_size": "33554432",  # 32MB
                "cpu_mem_arena_max_chunk_size": "67108864",      # 64MB
            })
        
        logger.debug(f" CPU provider: {cpu_cores} cores, {memory_gb}GB RAM")
        
    else:
        # Default empty options for unknown providers
        logger.debug(f" Unknown provider {provider_name}: using default options")
    
    # Cache the options
    _provider_options_cache[provider_name] = provider_options
    
    return provider_options


def should_use_ort_optimization(capabilities: Dict[str, Any]) -> bool:
    """
    Determine if ONNX Runtime graph optimization should be used.
    
    This function analyzes the hardware and model characteristics to decide
    whether ONNX Runtime's graph optimization will benefit performance.
    
    @param capabilities: Hardware capabilities from detect_apple_silicon_capabilities()
    @returns bool: True if ORT optimization should be used
    """
    # Always use basic optimizations for TTS workloads
    # These are generally beneficial and have minimal overhead
    return True


def get_or_create_ort_model() -> str:
    """
    Get or create an optimized ONNX model file path.
    
    This function manages ONNX model optimization and caching.
    
    @returns str: Path to the optimized ONNX model
    """
    try:
        import onnxruntime as ort
        import onnx
        from onnx import optimizer
        import os
        from pathlib import Path
        import hashlib

        # Create optimized models directory
        optimized_dir = Path("optimized_models")
        optimized_dir.mkdir(exist_ok=True)

        # Generate cache key based on model file and optimization settings
        model_path = Path(TTSConfig.MODEL_PATH)
        if not model_path.exists():
            logger.warning(f"Model file not found: {model_path}")
            return TTSConfig.MODEL_PATH

        cache_key = generate_model_cache_key(model_path, capabilities or {})
        optimized_path = optimized_dir / f"optimized_{cache_key}.onnx"

        # Check if optimized model already exists
        if optimized_path.exists():
            logger.info(f"Using cached optimized model: {optimized_path}")
            return str(optimized_path)

        # Load original model
        logger.info(f"Optimizing ONNX model: {model_path}")
        original_model = onnx.load(str(model_path))

        # Apply optimization pipeline
        optimized_model = apply_onnx_optimizations(original_model, capabilities or {})

        # Save optimized model
        onnx.save(optimized_model, str(optimized_path))
        logger.info(f"Optimized model saved to: {optimized_path}")

        return str(optimized_path)

    except ImportError as e:
        logger.warning(f"ONNX optimization not available: {e}")
        return TTSConfig.MODEL_PATH
    except Exception as e:
        logger.error(f"Failed to optimize ONNX model: {e}")
        return TTSConfig.MODEL_PATH


def generate_model_cache_key(model_path: Path, capabilities: Dict[str, Any]) -> str:
    """
    Generate a cache key for the optimized model based on model file and capabilities.

    @param model_path: Path to the original model file
    @param capabilities: Hardware capabilities and optimization settings
    @returns str: Cache key for the optimized model
    """
    # Include model file hash
    model_hash = hashlib.md5()
    with open(model_path, 'rb') as f:
        # Read first 1MB for hash (performance optimization)
        chunk = f.read(1024 * 1024)
        model_hash.update(chunk)

    # Include relevant capabilities in cache key
    cache_components = [
        model_hash.hexdigest(),
        str(capabilities.get('cpu_cores', 'unknown')),
        str(capabilities.get('memory_gb', 'unknown')),
        str(capabilities.get('has_cuda', False)),
        str(capabilities.get('has_tensorrt', False)),
        str(capabilities.get('optimization_level', 'basic')),
        str(capabilities.get('quantization_enabled', False)),
    ]

    full_cache_key = '_'.join(cache_components)
    return hashlib.md5(full_cache_key.encode()).hexdigest()[:16]


def apply_onnx_optimizations(model: onnx.ModelProto, capabilities: Dict[str, Any]) -> onnx.ModelProto:
    """
    Apply comprehensive ONNX optimizations to the model.

    @param model: Original ONNX model
    @param capabilities: Hardware capabilities for optimization selection
    @returns onnx.ModelProto: Optimized ONNX model
    """
    try:
        import onnxruntime as ort
        from onnx import optimizer
        import onnxoptimizer

        logger.info("Applying ONNX optimizations...")

        # Start with basic optimizations
        optimized_model = model

        # Apply onnx-optimizer passes
        try:
            passes = onnxoptimizer.get_fuse_and_elimination_passes()
            optimized_model = onnxoptimizer.optimize(optimized_model, passes)
            logger.debug(f"Applied {len(passes)} optimization passes")
        except Exception as e:
            logger.debug(f"onnx-optimizer passes failed: {e}")

        # Apply additional optimization based on capabilities
        optimization_level = capabilities.get('optimization_level', 'basic')

        if optimization_level == 'aggressive':
            # Apply more aggressive optimizations for better performance
            try:
                # Use ONNX optimizer with extended passes
                optimized_model = optimizer.optimize(
                    optimized_model,
                    ['eliminate_deadend', 'eliminate_nop_monotone_argmax', 'fuse_consecutive_squeezes',
                     'fuse_consecutive_transposes', 'fuse_matmul_add_bias_into_gemm']
                )
                logger.debug("Applied aggressive optimization passes")
            except Exception as e:
                logger.debug(f"Extended optimization passes failed: {e}")

        # Apply quantization if enabled and supported
        if capabilities.get('quantization_enabled', False):
            try:
                optimized_model = apply_quantization(optimized_model, capabilities)
                logger.info("Applied quantization optimization")
            except Exception as e:
                logger.warning(f"Quantization failed: {e}")

        # Validate the optimized model
        try:
            onnx.checker.check_model(optimized_model)
            logger.debug("Optimized model validation passed")
        except Exception as e:
            logger.error(f"Optimized model validation failed: {e}")
            # Return original model if optimization broke it
            return model

        # Log optimization results
        original_size = len(onnx.save_to_string(model))
        optimized_size = len(onnx.save_to_string(optimized_model))
        compression_ratio = optimized_size / original_size if original_size > 0 else 1.0

        logger.info(f"ONNX optimization complete: {compression_ratio:.2%} of original size")

        return optimized_model

    except ImportError as e:
        logger.warning(f"ONNX optimization libraries not available: {e}")
        return model
    except Exception as e:
        logger.error(f"ONNX optimization failed: {e}")
        return model


def apply_quantization(model: onnx.ModelProto, capabilities: Dict[str, Any]) -> onnx.ModelProto:
    """
    Apply quantization to the ONNX model for reduced precision inference.

    @param model: ONNX model to quantize
    @param capabilities: Hardware capabilities
    @returns onnx.ModelProto: Quantized model
    """
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType

        # Create temporary files for quantization
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix='.onnx', delete=False) as input_file:
            onnx.save(model, input_file.name)
            input_path = input_file.name

        with tempfile.NamedTemporaryFile(suffix='.onnx', delete=False) as output_file:
            output_path = output_file.name

        try:
            # Apply dynamic quantization
            quantize_dynamic(
                model_input=input_path,
                model_output=output_path,
                weight_type=QuantType.QInt8,  # Use 8-bit quantization
                optimize_model=True
            )

            # Load and return quantized model
            quantized_model = onnx.load(output_path)
            logger.info("Dynamic quantization applied successfully")

            return quantized_model

        finally:
            # Clean up temporary files
            try:
                os.unlink(input_path)
                os.unlink(output_path)
            except:
                pass

    except ImportError as e:
        logger.warning(f"ONNX quantization not available: {e}")
        raise e
    except Exception as e:
        logger.error(f"Quantization failed: {e}")
        raise e


def configure_ort_providers(capabilities: Optional[Dict[str, Any]] = None) -> List[str]:
    """
    Configure and prioritize ONNX Runtime providers based on hardware capabilities.
    
    @param capabilities: Hardware capabilities (auto-detected if not provided)
    @returns List[str]: Ordered list of provider names by priority
    """
    if capabilities is None:
        from api.model.hardware import detect_apple_silicon_capabilities
        capabilities = detect_apple_silicon_capabilities()
    
    providers = []
    
    # Add providers in order of preference
    if capabilities.get('is_apple_silicon', False) and capabilities.get('has_neural_engine', False):
        if 'CoreMLExecutionProvider' in capabilities.get('available_providers', []):
            providers.append('CoreMLExecutionProvider')
            logger.info(" CoreML provider configured for Apple Silicon")
    
    # Always include CPU as fallback
    if 'CPUExecutionProvider' in capabilities.get('available_providers', []):
        providers.append('CPUExecutionProvider')
        logger.info(" CPU provider configured as fallback")
    
    if not providers:
        logger.warning(" No suitable ONNX Runtime providers available")
        providers = ['CPUExecutionProvider']  # Force CPU as last resort
    
    logger.info(f" Provider priority: {' → '.join(providers)}")
    return providers


def clear_provider_cache() -> None:
    """
    Clear cached provider options and session options.
    
    This forces fresh configuration on the next provider setup.
    """
    global _session_options_cache, _provider_options_cache
    
    _session_options_cache = None
    _provider_options_cache.clear()
    
    logger.debug(" Cleared ONNX Runtime provider cache")


def get_provider_info(provider_name: str) -> Dict[str, Any]:
    """
    Get information about a specific ONNX Runtime provider.
    
    @param provider_name: Name of the provider
    @returns Dict[str, Any]: Provider information and capabilities
    """
    try:
        available_providers = ort.get_available_providers()
        
        info = {
            'name': provider_name,
            'available': provider_name in available_providers,
            'version': ort.__version__,
            'build_info': ort.get_build_info() if hasattr(ort, 'get_build_info') else None
        }
        
        # Provider-specific information
        if provider_name == 'CoreMLExecutionProvider':
            info.update({
                'requires_apple_silicon': True,
                'requires_neural_engine': True,
                'supports_gpu': True,
                'supports_neural_engine': True
            })
        elif provider_name == 'CPUExecutionProvider':
            info.update({
                'requires_apple_silicon': False,
                'requires_neural_engine': False,
                'supports_gpu': False,
                'supports_neural_engine': False,
                'universal_compatibility': True
            })
        
        return info
        
    except Exception as e:
        logger.error(f"Failed to get provider info for {provider_name}: {e}")
        return {
            'name': provider_name,
            'available': False,
            'error': str(e)
        }
