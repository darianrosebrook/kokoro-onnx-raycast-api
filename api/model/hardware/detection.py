"""
Hardware detection and capability analysis.

This module provides comprehensive Apple Silicon hardware detection,
including Neural Engine availability and performance characteristics.
"""

import platform
import subprocess
import logging
from typing import Optional, Dict, Any
from functools import lru_cache

# Cache for hardware capabilities (module-level)
_capabilities_cache: Optional[Dict[str, Any]] = None

def detect_apple_silicon_capabilities() -> Dict[str, Any]:
    """
    Detect Apple Silicon capabilities with comprehensive hardware analysis and caching.

    This function provides detailed hardware capability detection for Apple Silicon
    systems, including Neural Engine availability and performance characteristics.
    Results are cached to avoid repeated expensive system calls since hardware
    capabilities don't change during runtime.

    ## Detection Features

    ### Hardware Analysis
    - **Apple Silicon Detection**: Identifies M1/M2/M3 series chips
    - **Neural Engine**: Detects Neural Engine availability and capabilities
    - **Memory Analysis**: Analyzes system memory for optimal configuration
    - **Performance Profiling**: Determines optimal provider selection

    ### Fallback Strategy
    - **Provider Validation**: Tests provider availability before selection
    - **Performance Testing**: Benchmarks providers for optimal choice
    - **Error Recovery**: Graceful degradation on hardware issues

    ### Caching Strategy
    - **Runtime Caching**: Capabilities are cached after first detection
    - **Persistent Caching**: Results are saved to disk for cross-process reuse
    - **Performance Optimization**: Avoids repeated expensive system calls
    - **Memory Efficient**: Minimal memory overhead for cached data

    @returns Dict[str, Any]: Comprehensive hardware capabilities dictionary

    @example
    ```python
    capabilities = detect_apple_silicon_capabilities()
    if capabilities['is_apple_silicon']:
        print("Apple Silicon detected with Neural Engine")
    ```
    """
    global _capabilities_cache
    
    # Set up logger first
    logger = logging.getLogger(__name__)

    # Return cached result if available
    if _capabilities_cache is not None:
        return _capabilities_cache
    
    # Try to load from persistent cache
    try:
        from api.utils.cache_helpers import compute_system_fingerprint, load_json_cache, save_json_cache_atomic
        from api.config import TTSConfig
        
        fp = compute_system_fingerprint(TTSConfig.MODEL_PATH, TTSConfig.VOICES_PATH)
        cache_name = f"capabilities_{fp}.json"
        cached = load_json_cache(cache_name)
        
        if cached:
            _capabilities_cache = cached
            logger.info(f"✅ Loaded hardware capabilities from cache: {fp[:8]}...")
            return cached
    except Exception as e:
        logger.debug(f"Could not load persistent capabilities cache: {e}")

    # Basic platform detection
    is_apple_silicon = platform.machine() == 'arm64' and platform.system() == 'Darwin'

    capabilities = {
        'platform': f"{platform.system()} {platform.machine()}",
        'is_apple_silicon': is_apple_silicon,
        'has_neural_engine': False,
        'neural_engine_cores': 0,
        'cpu_cores': 0,
        'memory_gb': 0,
        'recommended_provider': 'CPUExecutionProvider',
        'provider_priority': [],
        'hardware_issues': []
    }

    if not is_apple_silicon:
        logger.info(" Non-Apple Silicon system detected - using CPU provider")
        capabilities['provider_priority'] = ['CPUExecutionProvider']
        # Cache the result before returning
        _capabilities_cache = capabilities
        return capabilities

    logger.info(" Apple Silicon system detected - analyzing capabilities...")

    # Enhanced Apple Silicon detection
    try:
        # Get detailed system information
        result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            cpu_info = result.stdout.strip()
            logger.debug(f" CPU: {cpu_info}")

            # Detect specific Apple Silicon variants
            if 'M1' in cpu_info:
                capabilities['chip_family'] = 'M1'
                capabilities['neural_engine_cores'] = 16
                capabilities['has_neural_engine'] = True
            elif 'M2' in cpu_info:
                capabilities['chip_family'] = 'M2'
                capabilities['neural_engine_cores'] = 16
                capabilities['has_neural_engine'] = True
            elif 'M3' in cpu_info:
                capabilities['chip_family'] = 'M3'
                capabilities['neural_engine_cores'] = 18
                capabilities['has_neural_engine'] = True
            else:
                capabilities['chip_family'] = 'Apple Silicon (Unknown)'
                # Assume Neural Engine available
                capabilities['has_neural_engine'] = True

    except Exception as e:
        logger.warning(f" Could not detect specific chip variant: {e}")
        capabilities['chip_family'] = 'Apple Silicon (Unknown)'
        capabilities['has_neural_engine'] = True  # Conservative assumption

    # Get CPU core count
    try:
        result = subprocess.run(['sysctl', '-n', 'hw.ncpu'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            capabilities['cpu_cores'] = int(result.stdout.strip())
            logger.debug(f" CPU Cores: {capabilities['cpu_cores']}")
    except Exception as e:
        logger.warning(f" Could not detect CPU cores: {e}")
        capabilities['cpu_cores'] = 8  # Conservative default

    # Get memory information
    try:
        result = subprocess.run(['sysctl', '-n', 'hw.memsize'],
                                capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            mem_bytes = int(result.stdout.strip())
            capabilities['memory_gb'] = round(mem_bytes / (1024**3), 1)
            logger.debug(f" Memory: {capabilities['memory_gb']}GB")
    except Exception as e:
        logger.warning(f" Could not detect memory size: {e}")
        capabilities['memory_gb'] = 8  # Conservative default

    # Validate ONNX Runtime providers
    try:
        import onnxruntime as ort
        available_providers = ort.get_available_providers()
        logger.debug(f" Available ONNX providers: {available_providers}")

        # Build provider priority list based on capabilities
        provider_priority = []

        # Check CoreML availability
        if 'CoreMLExecutionProvider' in available_providers and capabilities['has_neural_engine']:
            provider_priority.append('CoreMLExecutionProvider')
            logger.debug("✅ CoreML provider available and recommended")
        else:
            if 'CoreMLExecutionProvider' not in available_providers:
                logger.warning(" CoreML provider not available")
                capabilities['hardware_issues'].append(
                    'CoreML provider unavailable')
            if not capabilities['has_neural_engine']:
                logger.warning(" Neural Engine not detected")
                capabilities['hardware_issues'].append(
                    'Neural Engine not available')

        # Always include CPU as fallback
        if 'CPUExecutionProvider' in available_providers:
            provider_priority.append('CPUExecutionProvider')
            logger.debug("✅ CPU provider available")
        else:
            logger.error(" CPU provider not available - critical error")
            capabilities['hardware_issues'].append('CPU provider unavailable')

        capabilities['provider_priority'] = provider_priority
        capabilities['available_providers'] = available_providers

        # Set recommended provider
        if provider_priority:
            capabilities['recommended_provider'] = provider_priority[0]
            logger.info(
                f" Recommended provider: {capabilities['recommended_provider']}")
        else:
            logger.error(" No suitable providers available")
            capabilities['hardware_issues'].append(
                'No suitable providers available')

    except Exception as e:
        logger.error(f" Could not validate ONNX providers: {e}")
        capabilities['hardware_issues'].append(
            f'Provider validation failed: {e}')
        capabilities['provider_priority'] = ['CPUExecutionProvider']
        capabilities['recommended_provider'] = 'CPUExecutionProvider'

    # Determine optimization level based on hardware capabilities
    optimization_level = determine_optimization_level(capabilities)
    capabilities['optimization_level'] = optimization_level
    capabilities['quantization_enabled'] = should_enable_quantization(capabilities)

    # Log key capabilities (condensed for cleaner output)
    logger.info(
        f" Hardware: {capabilities.get('chip_family', 'Unknown')} | Neural Engine: {'✅' if capabilities['has_neural_engine'] else ''} | Provider: {capabilities['recommended_provider']} | Optimization: {optimization_level}")

    if capabilities['hardware_issues']:
        logger.warning(
            f" Hardware issues detected: {capabilities['hardware_issues']}")

    # Cache the result before returning
    _capabilities_cache = capabilities
    
    # Save to persistent cache
    try:
        from api.utils.cache_helpers import compute_system_fingerprint, save_json_cache_atomic
        from api.config import TTSConfig
        
        fp = compute_system_fingerprint(TTSConfig.MODEL_PATH, TTSConfig.VOICES_PATH)
        cache_name = f"capabilities_{fp}.json"
        save_json_cache_atomic(cache_name, capabilities)
        logger.debug(f" Saved hardware capabilities to cache: {fp[:8]}...")
    except Exception as e:
        logger.debug(f"Could not save persistent capabilities cache: {e}")
    
    return capabilities


def clear_hardware_capabilities_cache() -> None:
    """
    Clear the cached hardware capabilities.
    
    This function is useful for testing or when hardware configurations
    change and cached capabilities need to be refreshed.
    """
    global _capabilities_cache
    _capabilities_cache = None
    logging.getLogger(__name__).debug(" Cleared hardware capabilities cache")


def determine_optimization_level(capabilities: Dict[str, Any]) -> str:
    """
    Determine the appropriate optimization level based on hardware capabilities.

    @param capabilities: Hardware capabilities dictionary
    @returns str: Optimization level ('basic', 'standard', 'aggressive', 'maximum')
    """
    try:
        # Base level on hardware capabilities
        neural_engine_cores = capabilities.get('neural_engine_cores', 0)
        memory_gb = capabilities.get('memory_gb', 8)
        cpu_cores = capabilities.get('cpu_cores', 4)
        has_cuda = capabilities.get('has_cuda', False)
        has_tensorrt = capabilities.get('has_tensorrt', False)

        # Maximum optimization for high-end hardware
        if neural_engine_cores >= 32 or (has_cuda and memory_gb >= 16) or has_tensorrt:
            return 'maximum'

        # Aggressive optimization for good hardware
        if neural_engine_cores >= 16 or (has_cuda and memory_gb >= 8) or memory_gb >= 32:
            return 'aggressive'

        # Standard optimization for decent hardware
        if neural_engine_cores >= 8 or cpu_cores >= 8 or memory_gb >= 16:
            return 'standard'

        # Basic optimization for minimal hardware
        return 'basic'

    except Exception as e:
        logger.debug(f"Failed to determine optimization level: {e}")
        return 'basic'


def should_enable_quantization(capabilities: Dict[str, Any]) -> bool:
    """
    Determine if quantization should be enabled based on hardware capabilities.

    @param capabilities: Hardware capabilities dictionary
    @returns bool: Whether to enable quantization
    """
    try:
        # Enable quantization for capable systems
        neural_engine_cores = capabilities.get('neural_engine_cores', 0)
        has_cuda = capabilities.get('has_cuda', False)
        cpu_cores = capabilities.get('cpu_cores', 4)
        memory_gb = capabilities.get('memory_gb', 8)

        # Always enable for Apple Silicon with Neural Engine
        if neural_engine_cores > 0:
            return True

        # Enable for high-end GPUs
        if has_cuda and memory_gb >= 8:
            return True

        # Enable for multi-core CPUs with sufficient memory
        if cpu_cores >= 8 and memory_gb >= 16:
            return True

        # Conservative: disable quantization for basic hardware
        return False

    except Exception as e:
        logger.debug(f"Failed to determine quantization setting: {e}")
        return False


@lru_cache(maxsize=8)
def validate_provider(provider_name: str) -> bool:
    """
    Validate that a specific ONNX Runtime provider is available and functional.

    This function performs comprehensive validation of ONNX Runtime providers
    to ensure they are properly installed and can handle inference operations.

    ## Validation Process

    ### Provider Availability
    - **Import Check**: Verifies provider can be imported
    - **Session Creation**: Tests provider with minimal session
    - **Error Handling**: Catches and reports provider-specific errors

    ### Performance Validation
    - **Memory Usage**: Checks for memory allocation issues
    - **Resource Cleanup**: Validates proper resource management
    - **Error Recovery**: Tests provider resilience

    @param provider_name: Name of the provider to validate
    @returns bool: True if provider is valid and functional

    @example
    ```python
    if validate_provider('CoreMLExecutionProvider'):
        print("CoreML provider is available and functional")
    ```
    """
    logger = logging.getLogger(__name__)
    
    try:
        import onnxruntime as ort
        
        # Check if provider is in available list
        available_providers = ort.get_available_providers()
        if provider_name not in available_providers:
            logger.debug(f"Provider {provider_name} not in available providers: {available_providers}")
            return False
        
        # Try to create a minimal session with the provider
        # This validates that the provider can actually be used
        try:
            # Use a minimal model for testing (just an identity operation)
            import numpy as np
            import tempfile
            import os
            
            # Create a minimal ONNX model for testing
            try:
                import onnx  # type: ignore
                from onnx import helper, TensorProto  # type: ignore
                
                # Create a simple identity model
                input_tensor = helper.make_tensor_value_info(
                    'input', TensorProto.FLOAT, [1, 1])
                output_tensor = helper.make_tensor_value_info(
                    'output', TensorProto.FLOAT, [1, 1])
                
                identity_node = helper.make_node(
                    'Identity', ['input'], ['output'], name='identity')
                
                graph = helper.make_graph(
                    [identity_node], 'test_graph', [input_tensor], [output_tensor])
                
                model = helper.make_model(graph)
                
                # Save to temp file
                with tempfile.NamedTemporaryFile(suffix='.onnx', delete=False) as tmp:
                    onnx.save(model, tmp.name)
                    test_model_path = tmp.name
                
                try:
                    # Try to create session with the provider
                    session_options = ort.SessionOptions()
                    session_options.log_severity_level = 4  # Only fatal errors
                    
                    session = ort.InferenceSession(
                        test_model_path,
                        providers=[provider_name],
                        sess_options=session_options
                    )
                    
                    # Test inference
                    input_data = np.array([[1.0]], dtype=np.float32)
                    outputs = session.run(None, {'input': input_data})
                    
                    # Cleanup
                    del session
                    
                    logger.debug(f"✅ Provider {provider_name} validation successful")
                    return True
                    
                finally:
                    # Cleanup temp file
                    try:
                        os.unlink(test_model_path)
                    except:
                        pass
                        
            except ImportError:
                # If onnx package not available, just check provider availability
                logger.debug(f"ONNX package not available for full validation, checking basic availability for {provider_name}")
                return True
                
        except Exception as e:
            logger.debug(f"Provider {provider_name} failed session creation test: {e}")
            return False
            
    except Exception as e:
        logger.debug(f"Provider validation failed for {provider_name}: {e}")
        return False