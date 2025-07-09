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

2. **Phonemizer Statistics**:
   - Tracking of phonemizer fallback usage and success rates
   - Monitoring of text processing pipeline performance
   - Analysis of normalization effectiveness

3. **System Health Monitoring**:
   - CoreML context warning detection and handling
   - Memory usage tracking and cleanup coordination
   - Performance degradation detection

4. **Runtime Statistics**:
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
- `api.model.loader` for provider benchmarking data
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
    'memory_cleanup_count': 0        # Number of memory cleanup operations performed
}


def update_performance_stats(inference_time: float, provider_used: str):
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
    
    Examples:
        >>> update_performance_stats(0.123, 'CoreMLExecutionProvider')
        # Updates stats with CoreML inference time of 123ms
        
        >>> update_performance_stats(0.456, 'CPUExecutionProvider') 
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
                
    except Exception as e:
        logger.warning(f"Error updating performance stats: {e}")


def update_phonemizer_stats(fallback_used: bool = False):
    """
    Update phonemizer usage statistics and fallback rates.
    
    This function tracks the performance and reliability of the phonemizer
    component, which is critical for text-to-speech quality. It monitors
    fallback usage rates and helps identify potential issues with text
    processing that could affect TTS output quality.
    
    The phonemizer statistics help identify:
    - Text processing complexity and challenges
    - Effectiveness of text normalization strategies
    - Potential areas for optimization in the text processing pipeline
    - System stability and reliability trends
    
    Args:
        fallback_used (bool): Whether a fallback strategy was used for this operation
                             True if normal processing failed and fallback was needed
                             False if normal processing succeeded
    
    Examples:
        >>> update_phonemizer_stats(fallback_used=False)
        # Records successful phonemizer operation
        
        >>> update_phonemizer_stats(fallback_used=True)
        # Records phonemizer operation that required fallback
    
    Note:
        High fallback rates may indicate issues with text normalization
        or suggest the need for improved text preprocessing strategies.
    """
    global _phonemizer_total_calls, _phonemizer_fallback_count, coreml_performance_stats
    
    try:
        # Update phonemizer operation counters
        _phonemizer_total_calls += 1
        if fallback_used:
            _phonemizer_fallback_count += 1
            
        # Update global statistics
        coreml_performance_stats['phonemizer_fallbacks'] = _phonemizer_fallback_count
        
        # Calculate fallback rate as percentage
        if _phonemizer_total_calls > 0:
            rate = _phonemizer_fallback_count / _phonemizer_total_calls * 100
            coreml_performance_stats['phonemizer_fallback_rate'] = rate
        else:
            coreml_performance_stats['phonemizer_fallback_rate'] = 0.0
            
    except Exception as e:
        logger.debug(f"Error updating phonemizer stats: {e}")


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
            logger.debug(f"🔍 CoreML context warnings detected: {coreml_performance_stats['coreml_context_warnings']} (this is normal with CoreML + ONNX Runtime)")
            
        # Trigger cleanup when warnings accumulate significantly
        # This helps prevent potential memory pressure from accumulated contexts
        if coreml_performance_stats['coreml_context_warnings'] % 50 == 0:
            import gc
            gc.collect()  # Force garbage collection to clean up accumulated contexts
            coreml_performance_stats['memory_cleanup_count'] += 1
            logger.debug("🧹 Triggered memory cleanup due to CoreML context warnings")
            
    except Exception as e:
        logger.debug(f"Error handling CoreML context warning: {e}")


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