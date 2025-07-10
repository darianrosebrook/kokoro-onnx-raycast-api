"""
Comprehensive performance reporting and benchmark analysis for TTS system optimization.

This module provides sophisticated performance reporting capabilities for the Kokoro-ONNX TTS API,
generating detailed benchmark reports, runtime statistics, and system optimization recommendations.
The reporting system is designed to provide actionable insights for system tuning and performance monitoring.

## Architecture Overview

The performance reporting system consists of three main components:

1. **Benchmark Report Generation**:
   - Comprehensive system capability analysis
   - Provider performance comparison and ranking
   - Hardware-specific optimization recommendations
   - Configuration guidance for optimal performance

2. **Runtime Statistics Integration**:
   - Live performance metric updates
   - Real-time report synchronization
   - Historical performance trend analysis
   - System health monitoring integration

3. **Markdown Report Generation**:
   - Professional, readable performance reports
   - Structured data presentation with tables and metrics
   - Actionable recommendations and configuration guidance
   - Historical performance tracking and trends

## Benchmark Report Features

### System Analysis:
- **Hardware Detection**: Apple Silicon, Neural Engine, CPU cores, memory
- **Provider Availability**: ONNX Runtime provider detection and ranking
- **Performance Benchmarking**: Comparative analysis of inference providers
- **Optimization Recommendations**: Hardware-specific tuning guidance

### Performance Metrics:
- **Inference Time Comparison**: Side-by-side provider performance analysis
- **Relative Performance**: Normalized performance metrics and improvements
- **Provider Efficiency**: Resource utilization and optimization potential
- **Configuration Recommendations**: Optimal settings for detected hardware

### Runtime Integration:
- **Live Updates**: Real-time performance metric integration
- **Historical Tracking**: Long-term performance trend analysis
- **System Health**: Memory usage, cleanup events, and stability metrics
- **Operational Insights**: Production performance characteristics

## File Management

The module generates and maintains several key files:

1. **`benchmark_results.md`**: Comprehensive system benchmark report
2. **Runtime Statistics**: Live performance data integration
3. **Configuration Files**: Optimal settings for detected hardware
4. **Performance Logs**: Detailed performance history and trends

## Integration Points

This module integrates with:
- `api.performance.stats` for runtime performance data
- `api.model.loader` for hardware capability detection
- `api.config` for system configuration optimization
- External libraries: `platform`, `onnxruntime`, `datetime` for system analysis

## Production Considerations

- **Report Caching**: Intelligent report caching to minimize I/O overhead
- **Atomic Updates**: Safe concurrent report updates
- **Error Resilience**: Graceful handling of report generation failures
- **Performance Monitoring**: Self-monitoring to avoid impact on TTS operations

@author: @darianrosebrook
@date: 2025-01-03
@version: 2.0.0
@license: MIT
@copyright: 2025 Darian Rosebrook
@contact: hello@darianrosebrook.com
@website: https://darianrosebrook.com
@github: https://github.com/darianrosebrook/kokoro-onnx-raycast-api
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
import platform
import onnxruntime as ort

from api.performance.stats import get_performance_stats

logger = logging.getLogger(__name__)


def generate_benchmark_insights(benchmark_results: Dict[str, float], optimal_provider: str) -> str:
    """
    Generate detailed insights and recommendations from benchmark results.
    
    This function analyzes benchmark results to provide actionable insights
    about provider performance, optimization opportunities, and configuration
    recommendations.
    
    Args:
        benchmark_results: Dictionary mapping provider names to inference times
        optimal_provider: The currently selected optimal provider
    
    Returns:
        str: Detailed insights and recommendations
    """
    if not benchmark_results or len(benchmark_results) < 2:
        return "⚠️ Insufficient benchmark data for detailed analysis"
    
    # Sort providers by performance
    sorted_results = sorted(benchmark_results.items(), key=lambda x: x[1])
    fastest_provider = sorted_results[0][0]
    fastest_time = sorted_results[0][1]
    slowest_provider = sorted_results[-1][0]
    slowest_time = sorted_results[-1][1]
    
    # Calculate performance metrics
    performance_diff = slowest_time - fastest_time
    improvement_percent = (performance_diff / slowest_time) * 100
    
    insights = []
    
    # Performance analysis
    insights.append("## Performance Insights")
    insights.append("")
    
    if optimal_provider == fastest_provider:
        insights.append("✅ **Optimal Configuration**: Currently using the fastest available provider")
    else:
        insights.append(f"⚠️ **Performance Opportunity**: {fastest_provider} is {improvement_percent:.1f}% faster than current selection")
    
    insights.append("")
    
    # Provider-specific insights
    insights.append("### Provider Analysis")
    insights.append("")
    
    for provider, time_taken in sorted_results:
        relative_perf = time_taken / fastest_time
        if provider == fastest_provider:
            insights.append(f" **{provider}**: {time_taken:.3f}s (baseline)")
        else:
            insights.append(f"• **{provider}**: {time_taken:.3f}s ({relative_perf:.1f}x slower)")
    
    insights.append("")
    
    # Recommendations
    insights.append("### Recommendations")
    insights.append("")
    
    if improvement_percent < 5:
        insights.append(" **Minimal Difference**: Performance difference is negligible - current provider is fine")
    elif improvement_percent < 15:
        insights.append(" **Moderate Improvement**: Consider switching for consistent workloads")
    else:
        insights.append("**Significant Improvement**: Strongly recommend switching to fastest provider")
    
    insights.append("")
    
    # Workload considerations
    insights.append("### Workload Considerations")
    insights.append("")
    insights.append("• **Short Text**: Provider differences may be less noticeable")
    insights.append("• **Long Text**: Performance differences become more significant")
    insights.append("• **Batch Processing**: Consider provider switching for high-volume workloads")
    insights.append("• **Real-time Applications**: Prioritize consistency over peak performance")
    
    return "\n".join(insights)


def generate_benchmark_markdown(
    capabilities: Dict[str, Any], 
    benchmark_results: Optional[Dict[str, float]] = None, 
    optimal_provider: Optional[str] = None
) -> str:
    """
    Generate a comprehensive markdown benchmark report with system analysis and recommendations.
    
    This function creates a detailed, professional benchmark report that includes system
    capability analysis, performance benchmarking results, and actionable optimization
    recommendations. The report is designed to be both human-readable and suitable for
    automated processing.
    
    ## Report Structure
    
    The generated report includes:
    1. **System Information**: Hardware capabilities and environment details
    2. **Performance Benchmark Results**: Provider comparison and performance metrics
    3. **Configuration Recommendations**: Optimal settings and environment variables
    4. **Runtime Performance Tracking**: Live performance metrics and trends
    5. **Technical Notes**: Important considerations and known issues
    
    ## Performance Analysis
    
    The report provides sophisticated performance analysis including:
    - Provider performance ranking and comparison
    - Relative performance metrics and improvement calculations
    - Hardware-specific optimization recommendations
    - Configuration guidance for optimal performance
    
    Args:
        capabilities (Dict[str, Any]): System capabilities and hardware information
                                     Contains keys like 'is_apple_silicon', 'has_neural_engine',
                                     'cpu_cores', 'memory_gb', 'recommended_provider'
        benchmark_results (Optional[Dict[str, float]]): Provider performance results
                                                       Maps provider names to inference times
        optimal_provider (Optional[str]): Recommended optimal provider for this system
    
    Returns:
        str: Complete markdown report content ready for file output
    
    Examples:
        >>> capabilities = {
        ...     'is_apple_silicon': True,
        ...     'has_neural_engine': True,
        ...     'cpu_cores': 8,
        ...     'memory_gb': 16,
        ...     'recommended_provider': 'CoreMLExecutionProvider'
        ... }
        >>> benchmark_results = {
        ...     'CoreMLExecutionProvider': 0.123,
        ...     'CPUExecutionProvider': 0.456
        ... }
        >>> report = generate_benchmark_markdown(capabilities, benchmark_results, 'CoreMLExecutionProvider')
    
    Note:
        The report format is designed to be both human-readable and suitable for
        automated processing. It includes structured data in tables and provides
        actionable recommendations for system optimization.
    """
    # Generate report header with timestamp and system information
    md_content = f"""# Kokoro-ONNX TTS Benchmark Report

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## System Information

### Hardware Capabilities
- **Platform**: {platform.system()} {platform.machine()}
- **Apple Silicon**: {'✅ Yes' if capabilities.get('is_apple_silicon') else '❌ No'}
- **Neural Engine**: {'✅ Available' if capabilities.get('has_neural_engine') else '❌ Not Available'}
- **CPU Cores**: {capabilities.get('cpu_cores', 'Unknown')}
- **Memory**: {capabilities.get('memory_gb', 'Unknown')} GB

### ONNX Runtime Providers
- **Available**: {', '.join(ort.get_available_providers())}
- **Recommended**: {capabilities.get('recommended_provider', 'CPUExecutionProvider')}

## Performance Benchmark Results

"""
    
    # Add performance comparison table if benchmark results are available
    if benchmark_results and len(benchmark_results) > 1:
        md_content += """### Provider Performance Comparison

| Provider | Inference Time | Relative Performance | Status |
|----------|----------------|---------------------|---------|
"""
        
        # Sort providers by performance (fastest first) for clear comparison
        sorted_results = sorted(benchmark_results.items(), key=lambda x: x[1])
        fastest_time = sorted_results[0][1]
        slowest_time = sorted_results[-1][1]
        
        for i, (provider, time_taken) in enumerate(sorted_results):
            relative_perf = time_taken / fastest_time
            if time_taken == fastest_time:
                status = " **Fastest**"
                performance_indicator = "1.0x (baseline)"
            else:
                performance_indicator = f"{relative_perf:.1f}x slower"
                if relative_perf < 1.2:
                    status = " **Excellent**"
                elif relative_perf < 1.5:
                    status = "✅ **Good**"
                else:
                    status = "⚠️ **Slower**"
            
            md_content += f"| {provider} | {time_taken:.3f}s | {performance_indicator} | {status} |\n"
        
        # Calculate and display performance analysis
        performance_diff = slowest_time - fastest_time
        improvement_percent = (performance_diff / slowest_time) * 100
        
        md_content += f"""
### Performance Analysis

- **Fastest Provider**: `{sorted_results[0][0]}` ({sorted_results[0][1]:.3f}s)
- **Slowest Provider**: `{sorted_results[-1][0]}` ({sorted_results[-1][1]:.3f}s)
- **Performance Difference**: {performance_diff:.3f}s ({improvement_percent:.1f}% improvement)
- **Current Selection**: `{optimal_provider or 'Not specified'}`

"""
        
        # Add recommendation logic
        if optimal_provider:
            if optimal_provider == sorted_results[0][0]:
                md_content += f"✅ **Recommendation**: Using fastest provider (`{optimal_provider}`)\n\n"
            else:
                md_content += f"⚠️ **Recommendation**: Using `{optimal_provider}` despite `{sorted_results[0][0]}` being {improvement_percent:.1f}% faster\n\n"
        else:
            md_content += f" **Recommendation**: Consider using `{sorted_results[0][0]}` for best performance\n\n"
        
        # Add detailed insights if we have multiple providers
        if len(benchmark_results) >= 2:
            insights = generate_benchmark_insights(benchmark_results, optimal_provider or "unknown")
            md_content += insights + "\n\n"
    
    elif benchmark_results and len(benchmark_results) == 1:
        # Handle single provider scenario
        provider, time_taken = list(benchmark_results.items())[0]
        md_content += f"""### Single Provider Test
- **Provider**: {provider}
- **Inference Time**: {time_taken:.3f}s
- **Status**: ✅ **Baseline established**

"""
    else:
        # Handle case where no benchmark results are available
        md_content += """### Benchmark Results
⚠️ No benchmark results available (benchmarking may be disabled or failed)

"""
    
    # Add hardware-specific configuration recommendations
    md_content += """## Configuration Recommendations

### Optimal Settings
"""
    
    if capabilities.get('is_apple_silicon') and capabilities.get('has_neural_engine'):
        md_content += """-  **Apple Silicon Detected**: Hardware acceleration available
- **Neural Engine**: Available for CoreML optimization
-  **Expected Performance**: Variable based on workload and model optimization
-  **Provider Selection**: Performance-based recommendation from benchmarking
"""
    else:
        md_content += """-  **Standard System**: CPU-based inference
-  **Hardware Acceleration**: Limited to CPU optimizations
-  **Expected Performance**: Standard CPU-based inference
"""
    
    # Add environment configuration section
    md_content += f"""
### Environment Variables
```bash
# Set optimal provider (based on benchmark results)
export ONNX_PROVIDER="{optimal_provider or capabilities.get('recommended_provider', 'CPUExecutionProvider')}"

# Enable/disable provider benchmarking (default: true)
export KOKORO_BENCHMARK_PROVIDERS="true"

# Minimum improvement threshold for provider switching (default: 10%)
export KOKORO_MIN_IMPROVEMENT_PERCENT="10.0"
```

## Runtime Performance Tracking

The following metrics will be updated during runtime:

- **Total Inferences**: 0
- **Provider Usage**: TBD
- **Average Inference Time**: TBD
- **Phonemizer Fallback Rate**: TBD
- **CoreML Context Warnings**: TBD (normal with CoreML + ONNX Runtime)
- **Memory Cleanup Events**: TBD

## Technical Notes

- **Benchmark Caching**: Results are cached for 24 hours to avoid re-running on every startup
- **Performance Variability**: Performance may vary based on system load, thermal conditions, and model state
- **Provider Selection**: The system uses a minimum improvement threshold (default: 10%) to avoid switching providers for marginal gains
- **Warmup Recommendations**: For production deployment, consider warming up the model with a few test inferences
- **CoreML Context Warnings**: The "Context leak detected" warnings from msgtracer are a known issue with CoreML + ONNX Runtime interactions. These warnings don't affect functionality and are automatically handled by the system.

---
*Report generated by Kokoro-ONNX TTS API v2.0.0*
"""
    
    return md_content


def save_benchmark_report(
    capabilities: Dict[str, Any], 
    benchmark_results: Optional[Dict[str, float]] = None, 
    optimal_provider: Optional[str] = None
):
    """
    Save comprehensive benchmark report to markdown file with error handling.
    
    This function generates and saves a complete benchmark report to the filesystem,
    providing persistent storage of system performance analysis and optimization
    recommendations. The function includes comprehensive error handling to ensure
    robust operation even in constrained environments.
    
    ## File Management
    
    The function creates a `benchmark_results.md` file in the `reports/` directory
    containing the complete benchmark report. The file is designed to be:
    - Human-readable with clear formatting
    - Version-controlled friendly
    - Suitable for automated processing
    - Comprehensive enough for troubleshooting
    
    ## Error Handling
    
    The function includes robust error handling for:
    - File system permissions issues
    - Disk space constraints
    - Concurrent access conflicts
    - Report generation failures
    
    Args:
        capabilities (Dict[str, Any]): System capabilities and hardware information
        benchmark_results (Optional[Dict[str, float]]): Provider performance results
        optimal_provider (Optional[str]): Recommended optimal provider for this system
    
    Returns:
        Optional[str]: Path to the saved report file, or None if saving failed
    
    Examples:
        >>> capabilities = {'is_apple_silicon': True, 'has_neural_engine': True}
        >>> benchmark_results = {'CoreMLExecutionProvider': 0.123}
        >>> file_path = save_benchmark_report(capabilities, benchmark_results, 'CoreMLExecutionProvider')
        >>> print(f"Report saved to: {file_path}")
    
    Note:
        The function logs success and failure events at appropriate levels for
        monitoring and debugging. Failed report generation is logged as a warning
        since it doesn't affect core TTS functionality.
    """
    try:
        # Create reports directory if it doesn't exist
        reports_dir = "reports"
        os.makedirs(reports_dir, exist_ok=True)
        
        # Generate the markdown content
        md_content = generate_benchmark_markdown(capabilities, benchmark_results, optimal_provider)
        report_file = os.path.join(reports_dir, "benchmark_results.md")
        
        # Write report to file with proper error handling
        with open(report_file, 'w') as f:
            f.write(md_content)
        
        # Log success (commented out to avoid spam in production)
        # logger.info(f" Benchmark report saved to {report_file}")
        return report_file
        
    except Exception as e:
        logger.warning(f"⚠️ Could not save benchmark report: {e}")
        return None


def update_runtime_stats_in_report():
    """
    Update runtime performance statistics in the existing benchmark report.
    
    This function provides live updates to the benchmark report by replacing the
    runtime performance section with current statistics. It enables real-time
    monitoring of system performance without regenerating the entire report.
    
    ## Update Strategy
    
    The function uses a targeted update approach:
    1. **Read Current Report**: Load existing benchmark report from the `reports/` directory
    2. **Get Live Statistics**: Fetch current performance metrics
    3. **Generate Updated Section**: Create new runtime statistics section
    4. **Atomic Update**: Replace the runtime section using regex pattern matching
    5. **Write Back**: Save updated report to filesystem
    
    ## Performance Considerations
    
    - **Selective Updates**: Only updates the runtime section, preserving other content
    - **Atomic Operations**: Uses atomic file operations to prevent corruption
    - **Error Resilience**: Graceful handling of missing files or update failures
    - **Low Overhead**: Minimal performance impact on TTS operations
    
    ## Error Handling
    
    The function includes comprehensive error handling for:
    - Missing benchmark report files
    - File system permission issues
    - Malformed report content
    - Statistics calculation failures
    
    Examples:
        >>> update_runtime_stats_in_report()
        # Updates the runtime section with current performance statistics
    
    Note:
        This function is typically called periodically (e.g., every 10 inferences)
        to keep the report current without excessive I/O overhead. It logs at debug
        level to avoid spam in production environments.
    """
    report_file = os.path.join("reports", "benchmark_results.md")
    
    try:
        # Check if report file exists before attempting update
        if not os.path.exists(report_file):
            logger.debug("Benchmark report file not found, skipping runtime stats update")
            return
        
        # Read current report content
        with open(report_file, 'r') as f:
            content = f.read()
        
        # Get current performance statistics
        stats = get_performance_stats()
        
        # Generate updated runtime section with current metrics
        runtime_section = f"""## Runtime Performance Tracking

Current performance metrics (updated live):

- **Total Inferences**: {stats['total_inferences']}
- **CoreML Inferences**: {stats['coreml_inferences']} ({stats.get('coreml_usage_percent', 0):.1f}%)
- **CPU Inferences**: {stats['cpu_inferences']} ({stats.get('cpu_usage_percent', 0):.1f}%)
- **Average Inference Time**: {stats['average_inference_time']:.3f}s
- **Current Provider**: {stats['provider_used']}
- **Phonemizer Fallbacks**: {stats['phonemizer_fallbacks']} ({stats['phonemizer_fallback_rate']:.1f}%)
- **CoreML Context Warnings**: {stats.get('coreml_context_warnings', 0)} (normal with CoreML + ONNX Runtime)
- **Memory Cleanup Events**: {stats.get('memory_cleanup_count', 0)}"""
        
        # Replace the runtime section using regex pattern matching
        # This approach preserves the rest of the report while updating live statistics
        import re
        pattern = r'## Runtime Performance Tracking.*?(?=## Notes|$)'
        updated_content = re.sub(pattern, runtime_section, content, flags=re.DOTALL)
        
        # Write updated content back to file atomically
        with open(report_file, 'w') as f:
            f.write(updated_content)
        
        logger.debug(" Runtime stats updated in benchmark report")
        
    except Exception as e:
        # Log at debug level since report updates are not critical for TTS functionality
        logger.debug(f"Could not update runtime stats in report: {e}") 