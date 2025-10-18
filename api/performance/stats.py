"""
Real-time performance monitoring and statistics collection for TTS operations.

This module provides comprehensive performance tracking and statistics collection for the Kokoro-ONNX TTS API,
enabling detailed monitoring of inference performance, provider usage, and system behavior in production environments.

## Architecture Overview

The performance monitoring system consists of several key components:

1. **Inference Performance Tracking**:
   - Real-time collection of inference times and provider usage
   - Automatic calculation of rolling averages and performance metrics
   - Provider-specific performance comparisons (CoreML vs CPU)

2. **Session Utilization Monitoring** 
   - Tracking of dual session manager performance and utilization
   - ANE vs GPU session routing optimization
   - Concurrent processing efficiency metrics

3. **Phonemizer Statistics**:
   - Tracking of phonemizer fallback usage and success rates
   - Monitoring of text processing pipeline performance
   - Analysis of normalization effectiveness

4. **System Health Monitoring**:
   - CoreML context warning detection and handling
   - Memory usage tracking and cleanup coordination
   - Performance degradation detection

5. **Runtime Statistics**:
   - Live performance metrics for dashboard display
   - Historical performance data collection
   - System resource utilization tracking

## Performance Metrics

### Core Statistics Tracked:
- **total_inferences**: Total number of TTS inference operations
- **coreml_inferences**: Number of inferences using CoreML provider
- **cpu_inferences**: Number of inferences using CPU provider
- **average_inference_time**: Rolling average of inference times
- **provider_used**: Currently active inference provider
- **phonemizer_fallbacks**: Count of phonemizer fallback operations
- **phonemizer_fallback_rate**: Percentage of operations requiring fallbacks
- **coreml_context_warnings**: Count of CoreML context leak warnings
- **memory_cleanup_count**: Number of memory cleanup operations performed

### Session Utilization Metrics:
- **dual_session_requests**: Total requests processed by dual session manager
- **ane_utilization**: Neural Engine session utilization percentage
- **gpu_utilization**: GPU session utilization percentage
- **concurrent_efficiency**: Concurrent processing efficiency rating
- **session_routing_accuracy**: Accuracy of complexity-based session routing

### Derived Metrics:
- **coreml_usage_percent**: Percentage of inferences using CoreML
- **cpu_usage_percent**: Percentage of inferences using CPU
- **performance_efficiency**: Overall system performance rating
- **stability_score**: System stability and reliability metric

## Memory Management

The module implements intelligent memory management strategies:

1. **CoreML Context Monitoring**: Detects and handles CoreML context leaks
2. **Automatic Cleanup**: Triggers garbage collection when warnings accumulate
3. **Memory Pressure Detection**: Monitors system memory usage patterns
4. **Resource Optimization**: Coordinates with model loader for efficient resource use

## Integration Points

This module integrates with:
- `api.tts.core` for inference performance tracking
- `api.model.loader` for provider benchmarking data and dual session management
- `api.performance.reporting` for report generation and updates
- `api.warnings` for CoreML warning suppression and handling

## Production Considerations

- **Low Overhead**: Minimal performance impact on TTS operations
- **Thread Safety**: Safe for concurrent access across multiple requests
- **Error Resilience**: Graceful handling of monitoring failures
- **Scalability**: Efficient memory usage even with high request volumes

@author: @darianrosebrook
@date: 2025-07-08
@version: 2.0.0
@license: MIT
@copyright: 2025 Darian Rosebrook
@contact: hello@darianrosebrook.com
@website: https://darianrosebrook.com
@github: https://github.com/darianrosebrook/kokoro-onnx-raycast-api
"""
import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Global performance tracking variables
# These variables maintain state across the application lifecycle

# Phonemizer performance tracking
_phonemizer_fallback_count = 0  # Count of phonemizer fallback operations
_phonemizer_total_calls = 0     # Total phonemizer operations attempted

# Comprehensive performance statistics dictionary
# This dictionary serves as the central store for all performance metrics
coreml_performance_stats = {
    # Core inference metrics
    'total_inferences': 0,           # Total number of TTS inference operations
    'coreml_inferences': 0,          # Number of inferences using CoreML provider
    'cpu_inferences': 0,             # Number of inferences using CPU provider
    'average_inference_time': 0.0,   # Rolling average of inference times (seconds)
    'provider_used': 'unknown',      # Currently active inference provider
    
    # Phonemizer and text processing metrics
    'phonemizer_fallbacks': 0,       # Count of phonemizer fallback operations
    'phonemizer_fallback_rate': 0.0, # Percentage of operations requiring fallbacks
    
    # System health and stability metrics
    'coreml_context_warnings': 0,    # Count of CoreML context leak warnings
    'memory_cleanup_count': 0,       # Number of memory cleanup operations performed
    
    #  performance metrics
    'total_requests': 0,      # Total requests processed in
    'success_count': 0,       # Number of requests meeting targets
    'ttfa_average': 0.0,      # Average Time to First Audio (ms)
    'rtf_average': 0.0,       # Average Real-Time Factor
    'efficiency_average': 0.0, # Average streaming efficiency
    'success_rate': 0.0,      # Percentage of requests meeting all targets
    'ttfa_target': 800,       # TTFA target in milliseconds
    'rtf_target': 1.0,        # RTF target (must be < 1.0)
    'efficiency_target': 0.90, # Streaming efficiency target (must be > 90%)

    # TTFA OPTIMIZATION: Fast-path processing metrics
    'fast_path_requests': 0,         # Number of requests using fast-path processing
    'fast_path_ttfa_average': 0.0,   # Average TTFA for fast-path requests (ms)
    'fast_path_success_rate': 0.0,   # Percentage of fast-path requests meeting TTFA target
    'phonemizer_preinitialized': False, # Whether phonemizer was pre-initialized
    'text_processing_method_counts': {  # Count of processing methods used
        'fast_path': 0,
        'misaki': 0, 
        'phonemizer': 0,
        'character': 0
    },
}

# New phonemizer stats tracking
_phonemizer_stats = {
    "total_requests": 0,
    "successful_requests": 0,
    "fallback_uses": 0,
    "quality_mode_requests": 0,
    "quality_mode_successes": 0,
    "success_rate": 0.0,
    "fallback_rate": 0.0,
    "quality_success_rate": 0.0,
    "last_updated": time.time()
}


def update_inference_stats(inference_time: float, provider_used: str, **kwargs):
    """
    Update performance statistics with new inference data.
    
    This function is called after each TTS inference operation to update
    the global performance statistics. It maintains rolling averages,
    tracks provider usage, and triggers reporting updates.
    
    The function performs several key operations:
    1. Updates inference counters and averages
    2. Categorizes performance by provider type
    3. Triggers periodic report updates
    4. Maintains statistical accuracy across high-volume operations
    
    Args:
        inference_time (float): Time taken for the inference operation (seconds)
        provider_used (str): Name of the ONNX provider used for inference
                             (e.g., 'CoreMLExecutionProvider', 'CPUExecutionProvider')
        **kwargs: Optional metadata such as 'segment_count', 'cache_hit',
                  and 'phoneme_preprocessing' for deeper analysis
    
    Examples:
        >>> update_inference_stats(0.123, 'CoreMLExecutionProvider')
        # Updates stats with CoreML inference time of 123ms
        
        >>> update_inference_stats(0.456, 'CPUExecutionProvider') 
        # Updates stats with CPU inference time of 456ms
    
    Note:
        This function is designed to be called frequently (once per inference)
        and is optimized for minimal performance overhead. Report updates
        are batched to reduce I/O frequency.
    """
    from api.performance.reporting import update_runtime_stats_in_report
    global coreml_performance_stats
    
    try:
        # Update inference count and rolling average
        coreml_performance_stats['total_inferences'] += 1
        total = coreml_performance_stats['total_inferences']
        avg_time = coreml_performance_stats['average_inference_time']
        
        # Calculate new rolling average using incremental formula
        # This approach is more memory efficient than maintaining a full history
        coreml_performance_stats['average_inference_time'] = ((avg_time * (total - 1)) + inference_time) / total
        
        # Categorize performance by provider type
        if 'CoreML' in provider_used:
            coreml_performance_stats['coreml_inferences'] += 1
            coreml_performance_stats['provider_used'] = 'CoreMLExecutionProvider'
        else:
            coreml_performance_stats['cpu_inferences'] += 1
            coreml_performance_stats['provider_used'] = 'CPUExecutionProvider'
        
        # Trigger periodic report updates to avoid excessive I/O
        # Updates every 10 inferences to balance freshness with performance
        if total % 10 == 0:
            try:
                update_runtime_stats_in_report()
            except Exception as e:
                logger.debug(f"Could not update runtime stats in report: {e}")
        
        # Record performance metric for dynamic memory optimization
        try:
            from api.model.loader import get_dynamic_memory_manager
            
            dynamic_memory_manager = get_dynamic_memory_manager()
            if dynamic_memory_manager:
                dynamic_memory_manager.record_performance_metric(inference_time)
        except Exception as e:
            logger.debug(f"Could not record performance metric for dynamic memory optimization: {e}")
        
        # Record performance metric for real-time optimization
        try:
            from api.performance.optimization import record_performance_metric

            metadata = {
                "provider": provider_used,
                "segment_count": int(kwargs.get("segment_count", 0)),
                "cache_hit": bool(kwargs.get("cache_hit", False)),
                "phoneme_preprocessing": kwargs.get("phoneme_preprocessing", None),
            }

            record_performance_metric(
                metric_type="inference_time",
                value=inference_time,
                metadata=metadata,
            )
        except Exception as e:
            logger.debug(f"Could not record performance metric for real-time optimization: {e}")
                
    except Exception as e:
        logger.warning(f"Error updating performance stats: {e}")


def update_phonemizer_stats(fallback_used: bool = False, quality_mode: bool = False):
    """
    Update phonemizer performance statistics with quality mode tracking.
    
    This function tracks phonemizer usage patterns, success rates, and quality
    improvements to monitor the effectiveness of enhanced phonemization settings.
    
    ## Statistics Tracking
    
    ### Quality Mode Benefits
    - **Enhanced Settings**: Tracks usage of quality-optimized phonemizer settings
    - **Word Mismatch Reduction**: Monitors reduction in word count mismatches
    - **Punctuation Preservation**: Tracks better punctuation handling
    - **Stress Preservation**: Monitors stress mark retention for natural speech
    
    ### Performance Metrics
    - **Success Rate**: Percentage of successful phonemizations
    - **Fallback Rate**: Percentage of requests requiring fallback
    - **Quality Success Rate**: Success rate with enhanced quality settings
    - **Improvement Tracking**: Comparison between standard and quality modes
    
    Args:
        fallback_used (bool): Whether fallback was used instead of phonemizer
        quality_mode (bool): Whether enhanced quality settings were used
        
    Example:
        >>> update_phonemizer_stats(fallback_used=False, quality_mode=True)
        # Records successful phonemization with quality settings
        
        >>> update_phonemizer_stats(fallback_used=True, quality_mode=True)
        # Records fallback usage but with quality mode attempted
    """
    global _phonemizer_stats
    
    current_time = time.time()
    
    # Update basic stats
    _phonemizer_stats["total_requests"] += 1
    
    if fallback_used:
        _phonemizer_stats["fallback_uses"] += 1
    else:
        _phonemizer_stats["successful_requests"] += 1
    
    # Update quality mode stats
    if quality_mode:
        _phonemizer_stats["quality_mode_requests"] += 1
        if not fallback_used:
            _phonemizer_stats["quality_mode_successes"] += 1
    
    # Calculate success rates
    total = _phonemizer_stats["total_requests"]
    if total > 0:
        _phonemizer_stats["success_rate"] = _phonemizer_stats["successful_requests"] / total
        _phonemizer_stats["fallback_rate"] = _phonemizer_stats["fallback_uses"] / total
        
        # Calculate quality mode success rate
        quality_total = _phonemizer_stats["quality_mode_requests"]
        if quality_total > 0:
            _phonemizer_stats["quality_success_rate"] = _phonemizer_stats["quality_mode_successes"] / quality_total
        else:
            _phonemizer_stats["quality_success_rate"] = 0.0
    else:
        _phonemizer_stats["success_rate"] = 0.0
        _phonemizer_stats["fallback_rate"] = 0.0
        _phonemizer_stats["quality_success_rate"] = 0.0
    
    # Update timing
    _phonemizer_stats["last_updated"] = current_time
    
    # Log quality improvements periodically
    if total > 0 and total % 100 == 0:
        quality_improvement = _phonemizer_stats["quality_success_rate"] - _phonemizer_stats["success_rate"]
        if quality_improvement > 0:
            logger.info(f" Quality mode improvement: {quality_improvement:.1%} higher success rate")
        
        logger.debug(f" Phonemizer stats: {_phonemizer_stats['successful_requests']}/{total} success rate, "
                    f"{_phonemizer_stats['quality_mode_successes']}/{_phonemizer_stats['quality_mode_requests']} quality mode success")


def get_phonemizer_stats() -> Dict[str, Any]:
    """
    Get current phonemizer performance statistics with quality metrics.
    
    Returns comprehensive statistics about phonemizer usage, including
    quality mode performance and improvement tracking.
    
    Returns:
        Dict containing:
            - total_requests: Total phonemization requests
            - successful_requests: Successful phonemizations
            - fallback_uses: Number of fallback uses
            - quality_mode_requests: Requests with quality settings
            - quality_mode_successes: Successful quality mode requests
            - success_rate: Overall success rate (0.0-1.0)
            - fallback_rate: Fallback usage rate (0.0-1.0)
            - quality_success_rate: Quality mode success rate (0.0-1.0)
            - quality_improvement: Quality mode improvement over standard
            - last_updated: Timestamp of last update
            
    Example:
        >>> stats = get_phonemizer_stats()
        >>> print(f"Quality improvement: {stats['quality_improvement']:.1%}")
        >>> print(f"Success rate: {stats['success_rate']:.1%}")
    """
    stats = _phonemizer_stats.copy()
    
    # Calculate quality improvement
    quality_improvement = stats["quality_success_rate"] - stats["success_rate"]
    stats["quality_improvement"] = max(0.0, quality_improvement)
    
    # Add formatted summary
    stats["summary"] = {
        "total": stats["total_requests"],
        "success_rate": f"{stats['success_rate']:.1%}",
        "fallback_rate": f"{stats['fallback_rate']:.1%}",
        "quality_success_rate": f"{stats['quality_success_rate']:.1%}",
        "quality_improvement": f"{quality_improvement:.1%}"
    }
    
    return stats


def reset_phonemizer_stats():
    """
    Reset phonemizer statistics to initial state.
    
    Useful for benchmarking and testing to start with clean metrics.
    """
    global _phonemizer_stats
    _phonemizer_stats = {
        "total_requests": 0,
        "successful_requests": 0,
        "fallback_uses": 0,
        "quality_mode_requests": 0,
        "quality_mode_successes": 0,
        "success_rate": 0.0,
        "fallback_rate": 0.0,
        "quality_success_rate": 0.0,
        "last_updated": time.time()
    }
    logger.info(" Phonemizer statistics reset")


def handle_coreml_context_warning():
    """
    Handle CoreML context leak warnings gracefully with intelligent cleanup.
    
    This function manages the known issue of CoreML context leaks when using
    CoreML with ONNX Runtime. While these warnings are cosmetic and don't
    affect functionality, they can accumulate over time and impact performance.
    
    The function implements a multi-tier response strategy:
    1. **Counting**: Track warning frequency for monitoring
    2. **Throttled Logging**: Log warnings at reduced frequency to avoid spam
    3. **Automatic Cleanup**: Trigger memory cleanup when warnings accumulate
    4. **Performance Monitoring**: Track cleanup effectiveness
    
    ## CoreML Context Leak Background
    
    CoreML context leaks are a known issue when using CoreML execution provider
    with ONNX Runtime. These warnings are generated by the system's msgtracer
    and are cosmetic - they don't affect the functionality of the TTS system.
    However, they can accumulate over time and potentially impact performance.
    
    Examples:
        >>> handle_coreml_context_warning()
        # Increments warning count and potentially triggers cleanup
    
    Note:
        This function is typically called by the warning suppression system
        when CoreML context leak warnings are detected. It provides intelligent
        handling without completely suppressing important system warnings.
    """
    global coreml_performance_stats
    
    try:
        # Increment warning counter
        coreml_performance_stats['coreml_context_warnings'] += 1
        
        # Throttled logging to avoid spam while maintaining visibility
        # Log every 10th warning to balance monitoring with performance
        if coreml_performance_stats['coreml_context_warnings'] % 10 == 0:
            logger.debug(f" CoreML context warnings detected: {coreml_performance_stats['coreml_context_warnings']} (this is normal with CoreML + ONNX Runtime)")
            
        # Trigger cleanup when warnings accumulate significantly
        # This helps prevent potential memory pressure from accumulated contexts
        if coreml_performance_stats['coreml_context_warnings'] % 50 == 0:
            import gc
            gc.collect()  # Force garbage collection to clean up accumulated contexts
            coreml_performance_stats['memory_cleanup_count'] += 1
            logger.debug(" Triggered memory cleanup due to CoreML context warnings")
            
            # Also trigger the new advanced memory management system
            try:
                from api.model.memory.coreml_leak_mitigation import force_coreml_memory_cleanup
                cleanup_result = force_coreml_memory_cleanup()
                freed_mb = cleanup_result.get('memory_freed_mb', 0)
                if freed_mb > 0:
                    logger.debug(f" Advanced memory cleanup freed {freed_mb:.1f}MB")
            except Exception as cleanup_e:
                logger.debug(f" Could not trigger advanced memory cleanup: {cleanup_e}")
            
    except Exception as e:
        logger.debug(f"Error handling CoreML context warning: {e}")


def update_endpoint_performance_stats(endpoint: str, processing_time: float, success: bool = True,
                                      ttfa_ms: float = 0, rtf: float = 0, streaming_efficiency: float = 0,
                                      compliant: bool = False, **kwargs):
    """
    Update optimization performance statistics.
    
    This function tracks the key performance metrics including:
    - Time to First Audio (TTFA) with <800ms target
    - Real-Time Factor (RTF) with <1.0 target  
    - Streaming Efficiency with >90% target
    - Overall compliance rate
    
    Args:
        endpoint (str): The API endpoint being tracked
        processing_time (float): Total processing time in seconds
        success (bool): Whether the request completed successfully
        ttfa_ms (float): Time to First Audio in milliseconds
        rtf (float): Real-Time Factor (processing_time / audio_duration)
        streaming_efficiency (float): Streaming efficiency (0.0 to 1.0)
        compliant (bool): Whether request met all targets
        **kwargs: Additional metrics for future extensions
    
    Examples:
        >>> update_endpoint_performance_stats(
        ...     endpoint="stream_tts_audio",
        ...     processing_time=0.75,
        ...     success=True,
        ...     ttfa_ms=650,
        ...     rtf=0.85,
        ...     streaming_efficiency=0.92,
        ...     compliant=True
        ... )
    """
    from api.performance.reporting import update_runtime_stats_in_report
    global coreml_performance_stats
    
    try:
        # Update request counters
        coreml_performance_stats['total_requests'] += 1
        total_requests = coreml_performance_stats['total_requests']
        
        # Track success rate
        if compliant:
            coreml_performance_stats['success_count'] += 1
        
        # Calculate success rate
        coreml_performance_stats['success_rate'] = (
            coreml_performance_stats['success_count'] / total_requests
        ) if total_requests > 0 else 0.0
        
        # Update rolling averages for metrics
        if ttfa_ms > 0:
            current_avg = coreml_performance_stats['ttfa_average']
            coreml_performance_stats['ttfa_average'] = (
                (current_avg * (total_requests - 1)) + ttfa_ms
            ) / total_requests
        
        if rtf > 0:
            current_avg = coreml_performance_stats['rtf_average']
            coreml_performance_stats['rtf_average'] = (
                (current_avg * (total_requests - 1)) + rtf
            ) / total_requests
        
        if streaming_efficiency > 0:
            current_avg = coreml_performance_stats['efficiency_average']
            coreml_performance_stats['efficiency_average'] = (
                (current_avg * (total_requests - 1)) + streaming_efficiency
            ) / total_requests
        
        # Log performance summary periodically
        if total_requests % 10 == 0:
            logger.info(f"Performance Summary (last {total_requests} requests):")
            logger.info(f"  Success Rate: {coreml_performance_stats['success_rate']*100:.1f}%")
            logger.info(f"  Avg TTFA: {coreml_performance_stats['ttfa_average']:.1f}ms (target: <{coreml_performance_stats['ttfa_target']}ms)")
            logger.info(f"  Avg RTF: {coreml_performance_stats['rtf_average']:.3f} (target: <{coreml_performance_stats['rtf_target']})")
            logger.info(f"  Avg Efficiency: {coreml_performance_stats['efficiency_average']*100:.1f}% (target: >{coreml_performance_stats['efficiency_target']*100:.0f}%)")
        
        # Trigger periodic report updates for metrics
        if total_requests % 5 == 0:  # Update more frequently for monitoring
            try:
                update_runtime_stats_in_report()
            except Exception as e:
                logger.debug(f"Could not update runtime stats in report: {e}")
        
        # Log warnings for target misses and check for severe performance degradation
        severe_degradation = False
        
        if ttfa_ms > coreml_performance_stats['ttfa_target']:
            logger.warning(f"TTFA target missed: {ttfa_ms:.1f}ms > {coreml_performance_stats['ttfa_target']}ms")
            # Check for severe TTFA degradation (>15x target, was 10x)
            if ttfa_ms > coreml_performance_stats['ttfa_target'] * 15:
                severe_degradation = True
                logger.error(f"SEVERE TTFA degradation detected: {ttfa_ms:.1f}ms is {ttfa_ms/coreml_performance_stats['ttfa_target']:.1f}x the target")
        
        if rtf > coreml_performance_stats['rtf_target']:
            logger.warning(f"RTF target missed: {rtf:.3f} > {coreml_performance_stats['rtf_target']}")
            # Check for severe RTF degradation (>3x target, was 2x)
            if rtf > coreml_performance_stats['rtf_target'] * 3:
                severe_degradation = True
                logger.error(f"SEVERE RTF degradation detected: {rtf:.3f} is {rtf/coreml_performance_stats['rtf_target']:.1f}x the target")
        
        if streaming_efficiency < coreml_performance_stats['efficiency_target']:
            logger.warning(f"Streaming efficiency target missed: {streaming_efficiency*100:.1f}% < {coreml_performance_stats['efficiency_target']*100:.0f}%")
        
        # Trigger emergency cleanup if severe degradation is detected (with cooldown)
        if severe_degradation:
            # Check cooldown period to prevent too frequent emergency cleanups
            import time
            current_time = time.time()
            cooldown_period = 300  # 5 minutes
            
            # Initialize last cleanup time if not exists
            if not hasattr(update_endpoint_performance_stats, '_last_emergency_cleanup'):
                update_endpoint_performance_stats._last_emergency_cleanup = 0
            
            time_since_last_cleanup = current_time - update_endpoint_performance_stats._last_emergency_cleanup
            
            if time_since_last_cleanup >= cooldown_period:
                logger.error("Severe performance degradation detected - triggering emergency session cleanup")
                try:
                    from api.model.sessions.dual_session import get_dual_session_manager
                    dual_session_manager = get_dual_session_manager()
                    if dual_session_manager:
                        dual_session_manager.cleanup_sessions()
                        update_endpoint_performance_stats._last_emergency_cleanup = current_time
                        logger.info("Emergency session cleanup completed")
                except Exception as cleanup_error:
                    logger.error(f"Emergency cleanup failed: {cleanup_error}")
            else:
                remaining_cooldown = cooldown_period - time_since_last_cleanup
                logger.warning(f"Emergency cleanup on cooldown - {remaining_cooldown:.0f}s remaining")
        
    except Exception as e:
        logger.error(f"Error updating performance stats: {e}")


def get_performance_stats():
    """
    Retrieve current performance statistics with calculated derived metrics.
    
    This function provides a comprehensive view of system performance by
    returning both raw performance data and calculated derived metrics.
    It's designed to be safe for frequent access and provides consistent
    data even during high-concurrency operations.
    
    ## Returned Statistics
    
    ### Core Metrics:
    - **total_inferences**: Total inference operations performed
    - **coreml_inferences**: Operations using CoreML provider
    - **cpu_inferences**: Operations using CPU provider
    - **average_inference_time**: Rolling average inference time
    - **provider_used**: Currently active provider
    - **phonemizer_fallbacks**: Count of phonemizer fallback operations
    - **phonemizer_fallback_rate**: Percentage of operations requiring fallbacks
    - **coreml_context_warnings**: Count of CoreML context warnings
    - **memory_cleanup_count**: Number of cleanup operations performed
    
    ### Derived Metrics:
    - **coreml_usage_percent**: Percentage of inferences using CoreML
    - **cpu_usage_percent**: Percentage of inferences using CPU
    
    Returns:
        dict: Dictionary containing all performance statistics and derived metrics
    
    Examples:
        >>> stats = get_performance_stats()
        >>> print(f"Average inference time: {stats['average_inference_time']:.3f}s")
        >>> print(f"CoreML usage: {stats['coreml_usage_percent']:.1f}%")
    
    Note:
        This function includes comprehensive error handling and will return
        a safe default dictionary if any errors occur during statistics calculation.
    """
    try:
        # Create a copy of the stats to avoid modification during access
        stats = coreml_performance_stats.copy()
        total = stats.get('total_inferences', 0)
        
        # Calculate derived metrics if we have inference data
        if total > 0:
            coreml_inferences = stats.get('coreml_inferences', 0)
            cpu_inferences = stats.get('cpu_inferences', 0)
            
            # Calculate usage percentages
            stats['coreml_usage_percent'] = (coreml_inferences / total) * 100
            stats['cpu_usage_percent'] = (cpu_inferences / total) * 100
        else:
            # Default values when no inferences have been performed
            stats['coreml_usage_percent'] = 0
            stats['cpu_usage_percent'] = 0
        
        #  Add session utilization statistics
        try:
            session_stats = get_session_utilization_stats()
            stats['session_utilization'] = session_stats
            
            # Add memory fragmentation stats
            memory_stats = get_memory_fragmentation_stats()
            stats['memory_fragmentation'] = memory_stats
            
        except Exception as e:
            logger.debug(f"Could not get session utilization stats: {e}")
            stats['session_utilization'] = {
                'dual_session_available': False,
                'error': str(e)
            }
            stats['memory_fragmentation'] = {
                'dual_session_available': False,
                'error': str(e)
            }
        
        # Add dynamic memory optimization statistics
        try:
            dynamic_memory_stats = get_dynamic_memory_optimization_stats()
            stats['dynamic_memory_optimization'] = dynamic_memory_stats
            
        except Exception as e:
            logger.debug(f"Could not get dynamic memory optimization stats: {e}")
            stats['dynamic_memory_optimization'] = {
                'dynamic_memory_available': False,
                'error': str(e)
            }
            
        return stats
        
    except Exception as e:
        logger.warning(f"Error getting performance stats: {e}")
        
        # Return safe default statistics if calculation fails
        return {
            'total_inferences': 0,
            'coreml_inferences': 0, 
            'cpu_inferences': 0,
            'average_inference_time': 0.0,
            'provider_used': 'unknown',
            'phonemizer_fallbacks': 0,
            'phonemizer_fallback_rate': 0.0,
            'coreml_usage_percent': 0,
            'cpu_usage_percent': 0,
            'coreml_context_warnings': 0,
            'memory_cleanup_count': 0
        } 


def get_session_utilization_stats():
    """
    Get comprehensive session utilization statistics for dual session management.
    
    This function provides detailed metrics about the dual session manager's
    performance, including session routing, utilization rates, and concurrent
    processing efficiency. These metrics are essential for optimizing the
    multi-session concurrency implementation.
    
    ## Session Utilization Metrics
    
    ### Core Metrics:
    - **Total Requests**: Total number of requests processed by dual session manager
    - **ANE Utilization**: Neural Engine session usage percentage
    - **GPU Utilization**: GPU session usage percentage  
    - **CPU Utilization**: CPU fallback session usage percentage
    - **Concurrent Efficiency**: Percentage of requests processed concurrently
    - **Load Balancing**: How evenly distributed requests are across sessions
    
    ### Performance Indicators:
    - **Session Routing Accuracy**: How well complexity-based routing works
    - **Concurrent Processing Rate**: Percentage of requests processed in parallel
    - **Memory Fragmentation**: Indicators of memory fragmentation issues
    - **Session Availability**: Real-time session availability status
    
    Returns:
        Dict[str, Any]: Comprehensive session utilization statistics
    
    Examples:
        >>> stats = get_session_utilization_stats()
        >>> print(f"ANE utilization: {stats['ane_percentage']:.1f}%")
        >>> print(f"Concurrent efficiency: {stats['concurrent_efficiency']:.1f}%")
    
    Note:
        This function imports the dual session manager dynamically to avoid
        circular import issues during module initialization.
    """
    try:
        # Import dual session manager here to avoid circular imports
        from api.model.loader import get_dual_session_manager
        
        dual_session_manager = get_dual_session_manager()
        if dual_session_manager is None:
            return {
                'dual_session_available': False,
                'total_requests': 0,
                'ane_requests': 0,
                'gpu_requests': 0,
                'cpu_requests': 0,
                'ane_percentage': 0.0,
                'gpu_percentage': 0.0,
                'cpu_percentage': 0.0,
                'concurrent_segments_active': 0,
                'max_concurrent_segments': 0,
                'concurrent_efficiency': 0.0,
                'load_balancing_efficiency': 0.0,
                'sessions_available': {
                    'ane': False,
                    'gpu': False,
                    'cpu': False
                }
            }
        
        # Get utilization stats from dual session manager
        utilization_stats = dual_session_manager.get_utilization_stats()
        
        # Calculate derived metrics
        total_requests = utilization_stats['total_requests']
        concurrent_efficiency = 0.0
        load_balancing_efficiency = 0.0
        
        if total_requests > 0:
            # Calculate concurrent efficiency (percentage of requests using concurrent sessions)
            concurrent_requests = utilization_stats['ane_requests'] + utilization_stats['gpu_requests']
            concurrent_efficiency = (concurrent_requests / total_requests) * 100
            
            # Calculate load balancing efficiency (how evenly distributed requests are)
            # Perfect balance would be 50/50 between ANE and GPU, or 100% of whichever is available
            if utilization_stats['sessions_available']['ane'] and utilization_stats['sessions_available']['gpu']:
                ane_ratio = utilization_stats['ane_requests'] / concurrent_requests if concurrent_requests > 0 else 0
                gpu_ratio = utilization_stats['gpu_requests'] / concurrent_requests if concurrent_requests > 0 else 0
                # Efficiency is higher when load is more balanced (closer to 50/50)
                load_balancing_efficiency = 100 - (abs(ane_ratio - gpu_ratio) * 100)
            elif utilization_stats['sessions_available']['ane'] or utilization_stats['sessions_available']['gpu']:
                # If only one session is available, efficiency is 100% if we're using it
                load_balancing_efficiency = 100 if concurrent_requests > 0 else 0
        
        return {
            'dual_session_available': True,
            'total_requests': total_requests,
            'ane_requests': utilization_stats['ane_requests'],
            'gpu_requests': utilization_stats['gpu_requests'],
            'cpu_requests': utilization_stats['cpu_requests'],
            'ane_percentage': utilization_stats['ane_percentage'],
            'gpu_percentage': utilization_stats['gpu_percentage'],
            'cpu_percentage': utilization_stats['cpu_percentage'],
            'concurrent_segments_active': utilization_stats['concurrent_segments_active'],
            'max_concurrent_segments': utilization_stats['max_concurrent_segments'],
            'concurrent_efficiency': concurrent_efficiency,
            'load_balancing_efficiency': load_balancing_efficiency,
            'sessions_available': utilization_stats['sessions_available']
        }
        
    except Exception as e:
        logger.warning(f"Error getting session utilization stats: {e}")
        return {
            'dual_session_available': False,
            'error': str(e),
            'total_requests': 0,
            'ane_requests': 0,
            'gpu_requests': 0,
            'cpu_requests': 0,
            'ane_percentage': 0.0,
            'gpu_percentage': 0.0,
            'cpu_percentage': 0.0,
            'concurrent_segments_active': 0,
            'max_concurrent_segments': 0,
            'concurrent_efficiency': 0.0,
            'load_balancing_efficiency': 0.0,
            'sessions_available': {
                'ane': False,
                'gpu': False,
                'cpu': False
            }
        }


def calculate_load_balancing_efficiency():
    """
    Calculate load balancing efficiency for dual session management.
    
    This function analyzes how effectively the dual session manager distributes
    workload across available sessions. Higher efficiency indicates better
    utilization of available hardware resources.
    
    ## Efficiency Calculation
    
    The efficiency is calculated based on:
    1. **Session Availability**: Which sessions are available for processing
    2. **Request Distribution**: How evenly requests are distributed
    3. **Complexity Routing**: How well complexity-based routing works
    4. **Resource Utilization**: Overall utilization of available resources
    
    ### Efficiency Scoring:
    - **100%**: Perfect load balancing across all available sessions
    - **80-99%**: Good load balancing with minor imbalances
    - **60-79%**: Moderate load balancing with some optimization needed
    - **40-59%**: Poor load balancing with significant imbalances
    - **0-39%**: Very poor load balancing requiring immediate attention
    
    Returns:
        float: Load balancing efficiency percentage (0.0 to 100.0)
    
    Examples:
        >>> efficiency = calculate_load_balancing_efficiency()
        >>> if efficiency > 80:
        ...     print("Load balancing is working well")
        >>> elif efficiency > 60:
        ...     print("Load balancing needs optimization")
        >>> else:
        ...     print("Load balancing needs immediate attention")
    
    Note:
        This function is automatically called as part of get_session_utilization_stats()
        and is also available for standalone analysis.
    """
    try:
        from api.model.loader import get_dual_session_manager
        
        dual_session_manager = get_dual_session_manager()
        if dual_session_manager is None:
            return 0.0
        
        utilization_stats = dual_session_manager.get_utilization_stats()
        total_requests = utilization_stats['total_requests']
        
        if total_requests == 0:
            return 100.0  # Perfect efficiency with no requests
        
        # Get available sessions
        ane_available = utilization_stats['sessions_available']['ane']
        gpu_available = utilization_stats['sessions_available']['gpu']
        cpu_available = utilization_stats['sessions_available']['cpu']
        
        # Calculate efficiency based on available sessions
        if ane_available and gpu_available:
            # Both ANE and GPU available - ideal is balanced usage
            ane_ratio = utilization_stats['ane_requests'] / total_requests
            gpu_ratio = utilization_stats['gpu_requests'] / total_requests
            cpu_ratio = utilization_stats['cpu_requests'] / total_requests
            
            # Ideal distribution would be minimal CPU usage, balanced ANE/GPU
            cpu_penalty = cpu_ratio * 50  # Penalty for CPU usage when better options available
            balance_score = 100 - (abs(ane_ratio - gpu_ratio) * 100) - cpu_penalty
            
            return max(0.0, min(100.0, balance_score))
            
        elif ane_available or gpu_available:
            # Only one accelerated session available
            accelerated_requests = utilization_stats['ane_requests'] + utilization_stats['gpu_requests']
            accelerated_ratio = accelerated_requests / total_requests
            
            # Efficiency is the percentage of requests using accelerated sessions
            return accelerated_ratio * 100
            
        elif cpu_available:
            # Only CPU available - efficiency is 100% if we're using it
            return 100.0 if utilization_stats['cpu_requests'] > 0 else 0.0
            
    except Exception as e:
        logger.warning(f"Error calculating load balancing efficiency: {e}")
        return 0.0


def get_memory_fragmentation_stats():
    """
    Get memory fragmentation statistics from the dual session manager.
    
    This function provides insights into memory usage patterns and potential
    fragmentation issues that can affect long-running TTS systems. Memory
    fragmentation can lead to performance degradation and should be monitored
    in production environments.
    
    ## Memory Fragmentation Metrics
    
    ### Core Metrics:
    - **Memory Cleanup Count**: Number of automatic memory cleanups performed
    - **Memory Trend**: Current memory usage trend (increasing/decreasing)
    - **Fragmentation Score**: Overall fragmentation risk score (0-100)
    - **Cleanup Frequency**: How often memory cleanup is triggered
    
    ### Warning Indicators:
    - **High Cleanup Frequency**: Frequent memory cleanups may indicate issues
    - **Increasing Memory Trend**: Steadily increasing memory usage
    - **High Fragmentation Score**: Risk of memory fragmentation problems
    
    Returns:
        Dict[str, Any]: Memory fragmentation statistics and health indicators
    
    Examples:
        >>> stats = get_memory_fragmentation_stats()
        >>> if stats['fragmentation_score'] > 70:
        ...     print("High memory fragmentation risk detected")
        >>> if stats['cleanup_frequency'] > 10:
        ...     print("Frequent memory cleanup - investigate potential leaks")
    
    Note:
        This function provides early warning indicators for memory-related
        issues that could affect TTS performance in production environments.
    """
    try:
        from api.model.loader import get_dual_session_manager
        
        dual_session_manager = get_dual_session_manager()
        if dual_session_manager is None:
            return {
                'dual_session_available': False,
                'memory_cleanup_count': 0,
                'memory_trend': 'stable',
                'fragmentation_score': 0,
                'cleanup_frequency': 0.0,
                'current_memory_mb': 0.0,
                'memory_health': 'unknown'
            }
        
        # Get memory watchdog stats
        watchdog = dual_session_manager.memory_watchdog
        
        # Calculate memory trend
        memory_trend = 'stable'
        fragmentation_score = 0
        current_memory = watchdog._get_memory_usage()
        
        if len(watchdog.memory_usage_history) >= 10:
            recent_memory = list(watchdog.memory_usage_history)[-10:]
            first_memory = recent_memory[0]
            last_memory = recent_memory[-1]
            
            if last_memory > first_memory * 1.1:  # 10% increase
                memory_trend = 'increasing'
                fragmentation_score = min(100, (last_memory - first_memory) / first_memory * 100)
            elif last_memory < first_memory * 0.9:  # 10% decrease
                memory_trend = 'decreasing'
                fragmentation_score = max(0, fragmentation_score - 10)
        
        # Calculate cleanup frequency (cleanups per 1000 requests)
        cleanup_frequency = 0.0
        if watchdog.request_count > 0:
            cleanup_frequency = (watchdog.request_count / 1000) * 100
        
        # Determine memory health status
        if fragmentation_score > 70:
            memory_health = 'critical'
        elif fragmentation_score > 50:
            memory_health = 'warning'
        elif fragmentation_score > 30:
            memory_health = 'caution'
        else:
            memory_health = 'healthy'
        
        return {
            'dual_session_available': True,
            'memory_cleanup_count': watchdog.request_count // 1000,  # Estimate cleanup count
            'memory_trend': memory_trend,
            'fragmentation_score': fragmentation_score,
            'cleanup_frequency': cleanup_frequency,
            'current_memory_mb': current_memory,
            'memory_health': memory_health,
            'request_count': watchdog.request_count,
            'memory_history_size': len(watchdog.memory_usage_history)
        }
        
    except Exception as e:
        logger.warning(f"Error getting memory fragmentation stats: {e}")
        return {
            'dual_session_available': False,
            'error': str(e),
            'memory_cleanup_count': 0,
            'memory_trend': 'unknown',
            'fragmentation_score': 0,
            'cleanup_frequency': 0.0,
            'current_memory_mb': 0.0,
            'memory_health': 'unknown'
        }


def get_dynamic_memory_optimization_stats():
    """
    Get comprehensive dynamic memory optimization statistics for monitoring.
    
    This function provides detailed insights into the dynamic memory manager's
    performance, including arena sizing optimization, workload adaptation, and
    system resource utilization. These metrics are essential for validating
    advanced optimization effectiveness.
    
    ## Dynamic Memory Optimization Metrics
    
    ### Core Metrics:
    - **Current Arena Size**: Current ONNX Runtime memory arena size
    - **Optimization Frequency**: How often arena size is being optimized
    - **Performance Impact**: Impact of optimizations on inference performance
    - **Workload Adaptation**: How well the system adapts to changing workloads
    
    ### Optimization Factors:
    - **Hardware Multiplier**: Hardware-based scaling factor
    - **Workload Multiplier**: Workload-based scaling factor
    - **Pressure Adjustment**: Memory pressure-based adjustment factor
    - **Efficiency Score**: Overall optimization effectiveness
    
    ### Performance Indicators:
    - **Arena Utilization**: How efficiently the allocated memory is being used
    - **Optimization Success Rate**: Percentage of successful optimizations
    - **Performance Trend**: How performance changes with optimizations
    - **System Stability**: Impact on overall system stability
    
    Returns:
        Dict[str, Any]: Comprehensive dynamic memory optimization statistics
    
    Examples:
        >>> stats = get_dynamic_memory_optimization_stats()
        >>> print(f"Current arena size: {stats['current_arena_size_mb']}MB")
        >>> print(f"Optimization efficiency: {stats['optimization_efficiency']:.1f}%")
        >>> if stats['needs_optimization']:
        ...     print("Memory arena optimization recommended")
    
    Note:
        This function provides comprehensive insights into advanced
        optimization effectiveness and helps identify optimization opportunities.
    """
    try:
        from api.model.loader import get_dynamic_memory_manager
        
        dynamic_memory_manager = get_dynamic_memory_manager()
        if dynamic_memory_manager is None:
            return {
                'dynamic_memory_available': False,
                'current_arena_size_mb': 512,  # Default fallback
                'optimization_active': False,
                'optimization_stats': {},
                'performance_impact': 'unknown',
                'recommendation': 'Dynamic memory manager not available'
            }
        
        # Get optimization stats from dynamic memory manager
        optimization_stats = dynamic_memory_manager.get_optimization_stats()
        
        # Calculate derived metrics
        performance_impact = 'neutral'
        optimization_efficiency = 0.0
        needs_optimization = dynamic_memory_manager.should_optimize()
        
        # Calculate optimization efficiency
        if len(dynamic_memory_manager.performance_history) >= 10:
            recent_avg = sum(dynamic_memory_manager.performance_history[-5:]) / 5
            older_avg = sum(dynamic_memory_manager.performance_history[-10:-5]) / 5
            
            if recent_avg < older_avg * 0.95:  # 5% improvement
                performance_impact = 'positive'
                optimization_efficiency = ((older_avg - recent_avg) / older_avg) * 100
            elif recent_avg > older_avg * 1.05:  # 5% degradation
                performance_impact = 'negative'
                optimization_efficiency = ((recent_avg - older_avg) / older_avg) * -100
            else:
                performance_impact = 'neutral'
                optimization_efficiency = 0.0
        
        # Calculate arena utilization estimate
        arena_utilization = min(100, optimization_stats.get('recent_avg_performance', 0) * 100)
        
        # Determine recommendation
        if needs_optimization:
            if optimization_stats.get('recent_avg_performance', 0) > 1.0:
                recommendation = "Reduce arena size due to performance issues"
            elif optimization_stats.get('recent_avg_performance', 0) < 0.5:
                recommendation = "Increase arena size for better performance"
            else:
                recommendation = "Optimize arena size based on current workload"
        else:
            recommendation = "Current arena size is optimal"
        
        return {
            'dynamic_memory_available': True,
            'current_arena_size_mb': optimization_stats['current_arena_size_mb'],
            'optimization_active': True,
            'needs_optimization': needs_optimization,
            'optimization_stats': {
                'last_optimization_time': optimization_stats['last_optimization_time'],
                'time_since_last_optimization': optimization_stats['time_since_last_optimization'],
                'optimization_interval': optimization_stats['optimization_interval']
            },
            'workload_profile': optimization_stats.get('hardware_capabilities', {}),
            'hardware_info': optimization_stats.get('hardware_capabilities', {}),
            'optimization_factors': {
                'workload_multiplier': optimization_stats.get('recent_avg_performance', 1.0),
                'pressure_adjustment': 1.0,  # Default value
                'hardware_multiplier': optimization_stats.get('hardware_capabilities', {}).get('memory_gb', 8) / 8.0
            },
            'performance_metrics': {
                'performance_impact': performance_impact,
                'optimization_efficiency': optimization_efficiency,
                'arena_utilization': arena_utilization,
                'performance_history_size': len(dynamic_memory_manager.performance_history)
            },
            'system_status': {
                'memory_pressure': 'high' if optimization_stats.get('recent_avg_performance', 0) > 1.0 else 'normal',
                'concurrent_load': 'normal',  # Default value since we don't have concurrent request data
                'stability': 'stable' if abs(optimization_efficiency) < 10 else 'variable'
            },
            'recommendation': recommendation
        }
        
    except Exception as e:
        logger.warning(f"Error getting dynamic memory optimization stats: {e}")
        return {
            'dynamic_memory_available': False,
            'error': str(e),
            'current_arena_size_mb': 512,
            'optimization_active': False,
            'optimization_stats': {},
            'performance_impact': 'unknown',
            'recommendation': 'Error retrieving optimization statistics'
        } 


def update_fast_path_performance_stats(
    processing_method: str, 
    ttfa_ms: float, 
    success: bool = True,
    **kwargs
):
    """
    Update fast-path processing performance statistics for TTFA optimization tracking.
    
    This function tracks the performance of the TTFA optimizations including:
    - Fast-path text processing performance
    - Pre-initialized phonemizer backend effectiveness
    - Text processing method distribution
    - TTFA improvement metrics
    
    Args:
        processing_method (str): Method used ('fast_path', 'misaki', 'phonemizer', 'character')
        ttfa_ms (float): Time to First Audio in milliseconds
        success (bool): Whether the processing was successful
        **kwargs: Additional metrics for future extensions
    
    Examples:
        >>> update_fast_path_performance_stats(
        ...     processing_method="fast_path",
        ...     ttfa_ms=150,
        ...     success=True
        ... )
    """
    global coreml_performance_stats
    
    try:
        # Update method-specific counters
        if processing_method in coreml_performance_stats['text_processing_method_counts']:
            coreml_performance_stats['text_processing_method_counts'][processing_method] += 1
        
        # Track fast-path specific metrics
        if processing_method == 'fast_path':
            coreml_performance_stats['fast_path_requests'] += 1
            
            # Update fast-path TTFA average
            current_average = coreml_performance_stats['fast_path_ttfa_average']
            current_count = coreml_performance_stats['fast_path_requests']
            
            new_average = ((current_average * (current_count - 1)) + ttfa_ms) / current_count
            coreml_performance_stats['fast_path_ttfa_average'] = new_average
            
            # Update fast-path success rate
            if ttfa_ms < coreml_performance_stats['ttfa_target']:
                # This is a success
                success_count = int(coreml_performance_stats['fast_path_success_rate'] * (current_count - 1))
                success_count += 1
                coreml_performance_stats['fast_path_success_rate'] = success_count / current_count
            else:
                # Update success rate without incrementing success count
                success_count = int(coreml_performance_stats['fast_path_success_rate'] * (current_count - 1))
                coreml_performance_stats['fast_path_success_rate'] = success_count / current_count
        
        # Log performance improvements periodically
        total_fast_path = coreml_performance_stats['fast_path_requests']
        if total_fast_path > 0 and total_fast_path % 5 == 0:
            avg_ttfa = coreml_performance_stats['fast_path_ttfa_average']
            success_rate = coreml_performance_stats['fast_path_success_rate'] * 100
            target = coreml_performance_stats['ttfa_target']
            
            logger.info(f"Fast-Path Performance Summary (last {total_fast_path} requests):")
            logger.info(f"  Average TTFA: {avg_ttfa:.1f}ms (target: <{target}ms)")
            logger.info(f"  Success Rate: {success_rate:.1f}%")
            logger.info(f"  Processing Method Distribution: {coreml_performance_stats['text_processing_method_counts']}")
            
            if avg_ttfa < target:
                improvement = ((target - avg_ttfa) / target) * 100
                logger.info(f"  ✅ TTFA Improvement: {improvement:.1f}% better than target")
            else:
                shortfall = ((avg_ttfa - target) / target) * 100
                logger.warning(f"   TTFA Shortfall: {shortfall:.1f}% above target")
        
        # Log warnings for performance issues
        if processing_method == 'fast_path' and ttfa_ms > 200:
            logger.warning(f"Fast-path TTFA slower than expected: {ttfa_ms:.1f}ms > 200ms")
        
        if processing_method in ['misaki', 'phonemizer'] and ttfa_ms > 1000:
            logger.warning(f"Complex text processing taking too long: {processing_method} {ttfa_ms:.1f}ms > 1000ms")
            
    except Exception as e:
        logger.error(f"Error updating fast-path performance stats: {e}")


def mark_phonemizer_preinitialized():
    """
    Mark that the phonemizer backend was successfully pre-initialized.
    
    This is called when the phonemizer backend is pre-initialized during
    module startup to track the effectiveness of this optimization.
    """
    global coreml_performance_stats
    
    coreml_performance_stats['phonemizer_preinitialized'] = True
    logger.info("✅ TTFA OPTIMIZATION: Phonemizer pre-initialization recorded in performance stats") 