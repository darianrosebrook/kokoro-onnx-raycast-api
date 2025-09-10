"""
Memory optimization strategies and session options.

This module provides optimized ONNX Runtime session options and memory
management strategies for different hardware configurations.
"""

import os
import logging
import onnxruntime as ort
from typing import Dict, Any, Optional


def create_optimized_session_options(capabilities: Dict[str, Any]) -> ort.SessionOptions:
    """
    Create optimized ONNX Runtime session options based on hardware capabilities.
    
    This function analyzes the hardware configuration and creates optimal
    ONNX Runtime session settings for maximum performance, including
    dynamic memory arena sizing based on workload analysis.
    
    @param capabilities: Hardware capabilities from detect_apple_silicon_capabilities()
    @returns ort.SessionOptions: Optimized session options
    """
    logger = logging.getLogger(__name__)
    
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
    
    # Dynamic memory arena sizing based on workload analysis
    try:
        from .dynamic_manager import get_dynamic_memory_manager
        dynamic_memory_manager = get_dynamic_memory_manager()
        
        if dynamic_memory_manager is not None:
            optimal_mb = dynamic_memory_manager.calculate_optimal_arena_size()
            session_options.add_session_config_entry("arena_extend_strategy", "kSameAsRequested")
            session_options.add_session_config_entry("session.dynamic_arena_initial", str(optimal_mb))
            logger.debug(f" Dynamic arena size: {optimal_mb}MB")
        else:
            # Fallback to static sizing based on hardware
            arena_size = _calculate_static_arena_size(capabilities)
            session_options.add_session_config_entry("arena_extend_strategy", "kSameAsRequested")
            session_options.add_session_config_entry("session.dynamic_arena_initial", str(arena_size))
            logger.debug(f" Static arena size: {arena_size}MB")
            
    except Exception as e:
        logger.debug(f"Could not configure dynamic memory arena: {e}")
        # Use basic arena configuration
        arena_size = _calculate_static_arena_size(capabilities)
        session_options.add_session_config_entry("arena_extend_strategy", "kSameAsRequested")
        session_options.add_session_config_entry("session.dynamic_arena_initial", str(arena_size))
    
    # Enable memory optimizations
    session_options.enable_mem_pattern = True
    session_options.enable_mem_reuse = True
    session_options.enable_cpu_mem_arena = True
    
    # Set optimization level based on hardware
    if capabilities.get('is_apple_silicon', False):
        # Apple Silicon can handle more aggressive optimizations
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
        session_options.execution_mode = ort.ExecutionMode.ORT_PARALLEL
    else:
        # Conservative settings for other platforms
        session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    
    logger.info("✅ ONNX Runtime session options optimized based on hardware capabilities")
    
    return session_options


def _calculate_static_arena_size(capabilities: Dict[str, Any]) -> int:
    """
    Calculate static memory arena size based on hardware capabilities.
    
    This is used as a fallback when dynamic memory management is not available.
    
    @param capabilities: Hardware capabilities
    @returns int: Arena size in MB
    """
    base_size = 512  # Default base size in MB
    
    # Scale based on available system RAM
    ram_gb = capabilities.get('memory_gb', 8)
    if ram_gb >= 32:  # High-memory systems
        base_size = 1024
    elif ram_gb >= 16:  # Standard systems
        base_size = 768
    elif ram_gb <= 8:  # Low-memory systems
        base_size = 384
    
    # Adjust for Neural Engine capabilities
    neural_engine_cores = capabilities.get('neural_engine_cores', 0)
    if neural_engine_cores >= 32:  # M1 Max/M2 Max
        base_size = int(base_size * 1.2)
    elif neural_engine_cores >= 16:  # M1/M2
        base_size = int(base_size * 1.1)
    
    # Ensure reasonable bounds
    return min(2048, max(256, base_size))


def get_memory_optimization_recommendations(capabilities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get memory optimization recommendations based on hardware capabilities.
    
    @param capabilities: Hardware capabilities
    @returns Dict[str, Any]: Optimization recommendations
    """
    recommendations = {
        'arena_size_mb': _calculate_static_arena_size(capabilities),
        'optimizations': [],
        'warnings': []
    }
    
    ram_gb = capabilities.get('memory_gb', 8)
    neural_engine_cores = capabilities.get('neural_engine_cores', 0)
    
    # Memory-based recommendations
    if ram_gb >= 32:
        recommendations['optimizations'].append(
            "High memory system detected - enable aggressive memory caching"
        )
    elif ram_gb <= 8:
        recommendations['warnings'].append(
            "Low memory system - consider conservative memory settings"
        )
    
    # Neural Engine recommendations
    if neural_engine_cores >= 16:
        recommendations['optimizations'].append(
            "Neural Engine available - enable hardware acceleration"
        )
    
    # Apple Silicon specific recommendations
    if capabilities.get('is_apple_silicon', False):
        recommendations['optimizations'].extend([
            "Apple Silicon detected - use CoreML provider",
            "Enable extended graph optimizations for better performance"
        ])
    
    return recommendations


def create_memory_profile_for_workload(text_length: int, complexity: float, 
                                     concurrent_requests: int) -> Dict[str, Any]:
    """
    Create a memory profile recommendation for a specific workload.
    
    @param text_length: Length of the text to process
    @param complexity: Text complexity score (0.0 - 1.0)
    @param concurrent_requests: Number of concurrent requests
    @returns Dict[str, Any]: Memory profile recommendations
    """
    # Base memory requirements
    base_memory_mb = 256
    
    # Adjust for text length
    length_factor = min(2.0, text_length / 100)  # Scale up to 2x for long texts
    base_memory_mb *= length_factor
    
    # Adjust for complexity
    complexity_factor = 1.0 + (complexity * 0.5)  # Up to 1.5x for high complexity
    base_memory_mb *= complexity_factor
    
    # Adjust for concurrency
    concurrency_factor = 1.0 + (concurrent_requests - 1) * 0.2  # 20% per additional request
    base_memory_mb *= concurrency_factor
    
    # Ensure reasonable bounds
    recommended_mb = min(2048, max(256, int(base_memory_mb)))
    
    return {
        'recommended_arena_size_mb': recommended_mb,
        'factors': {
            'text_length': text_length,
            'complexity': complexity,
            'concurrent_requests': concurrent_requests,
            'length_factor': length_factor,
            'complexity_factor': complexity_factor,
            'concurrency_factor': concurrency_factor
        },
        'optimization_level': 'high' if complexity > 0.7 else 'medium' if complexity > 0.3 else 'low'
    }


def optimize_session_for_inference(session_options: ort.SessionOptions, 
                                 workload_info: Optional[Dict[str, Any]] = None) -> ort.SessionOptions:
    """
    Apply inference-specific optimizations to session options.
    
    @param session_options: Existing session options to optimize
    @param workload_info: Optional workload information for optimization
    @returns ort.SessionOptions: Optimized session options
    """
    if workload_info:
        # Apply workload-specific optimizations
        if workload_info.get('high_frequency', False):
            # High frequency workloads benefit from aggressive caching
            session_options.add_session_config_entry("session.enable_cpu_mem_arena", "1")
            session_options.add_session_config_entry("session.enable_mem_pattern", "1")
        
        if workload_info.get('low_latency_required', False):
            # Low latency workloads should minimize optimization overhead
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
        
        if workload_info.get('batch_processing', False):
            # Batch processing can use more aggressive optimizations
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    
    return session_options
