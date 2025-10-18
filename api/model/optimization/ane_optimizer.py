"""
Neural Engine (ANE) Optimization Module

This module provides intelligent ANE utilization optimization for Apple Silicon devices,
ensuring maximum performance from the Neural Engine while maintaining system stability.

@author: @darianrosebrook
@date: 2025-01-17
@version: 1.0.0
@license: MIT
"""

import os
import logging
import time
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ANEConfiguration:
    """Configuration for Neural Engine optimization"""
    compute_units: str
    model_format: str
    allow_low_precision: bool
    require_static_shapes: bool
    optimization_level: str
    memory_pressure_threshold: float


@dataclass
class ANEPerformanceMetrics:
    """Performance metrics for ANE utilization"""
    ane_utilization_percent: float
    total_requests: int
    ane_requests: int
    average_latency_ms: float
    memory_usage_mb: float
    optimization_score: float


class ANEOptimizer:
    """
    Neural Engine optimization manager for Apple Silicon devices.
    
    This class provides intelligent ANE configuration and monitoring to maximize
    performance while maintaining system stability.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.current_config: Optional[ANEConfiguration] = None
        self.performance_metrics: Optional[ANEPerformanceMetrics] = None
        self.optimization_history: list = []
        
    def detect_optimal_ane_config(self, capabilities: Dict[str, Any]) -> ANEConfiguration:
        """
        Detect optimal ANE configuration based on hardware capabilities.
        
        @param capabilities: Hardware capabilities dictionary
        @returns: Optimal ANE configuration
        """
        neural_engine_cores = capabilities.get('neural_engine_cores', 0)
        memory_gb = capabilities.get('memory_gb', 8)
        chip_family = capabilities.get('chip_family', 'unknown')
        
        # Base configuration
        config = ANEConfiguration(
            compute_units='CPUAndNeuralEngine',
            model_format='MLProgram',
            allow_low_precision=True,
            require_static_shapes=False,
            optimization_level='balanced',
            memory_pressure_threshold=0.8
        )
        
        # Optimize based on chip family
        if neural_engine_cores >= 32:  # M1 Max / M2 Max
            self.logger.info(f"Optimizing for M1 Max/M2 Max with {neural_engine_cores} ANE cores")
            config.optimization_level = 'aggressive'
            config.memory_pressure_threshold = 0.9
            
        elif neural_engine_cores >= 18:  # M3
            self.logger.info(f"Optimizing for M3 with {neural_engine_cores} ANE cores")
            config.optimization_level = 'aggressive'
            config.memory_pressure_threshold = 0.85
            
        elif neural_engine_cores >= 16:  # M1 / M2
            self.logger.info(f"Optimizing for M1/M2 with {neural_engine_cores} ANE cores")
            config.optimization_level = 'balanced'
            config.memory_pressure_threshold = 0.8
            
        else:
            self.logger.warning(f"Limited ANE cores ({neural_engine_cores}), using conservative settings")
            config.optimization_level = 'conservative'
            config.memory_pressure_threshold = 0.7
        
        # Memory-based adjustments
        if memory_gb >= 32:
            config.memory_pressure_threshold = min(0.95, config.memory_pressure_threshold + 0.1)
        elif memory_gb < 16:
            config.memory_pressure_threshold = max(0.6, config.memory_pressure_threshold - 0.1)
        
        self.current_config = config
        return config
    
    def apply_ane_environment_optimizations(self, config: ANEConfiguration) -> None:
        """
        Apply environment variable optimizations for ANE.
        
        @param config: ANE configuration to apply
        """
        # Set CoreML compute units
        os.environ['KOKORO_COREML_COMPUTE_UNITS'] = config.compute_units
        
        # Set ANE-specific optimizations
        if config.optimization_level == 'aggressive':
            os.environ['COREML_NEURAL_ENGINE_OPTIMIZATION'] = '1'
            os.environ['COREML_USE_FLOAT16'] = '1'
            os.environ['COREML_OPTIMIZE_FOR_APPLE_SILICON'] = '1'
            os.environ['COREML_ANE_MEMORY_OPTIMIZATION'] = '1'
            
        elif config.optimization_level == 'balanced':
            os.environ['COREML_NEURAL_ENGINE_OPTIMIZATION'] = '1'
            os.environ['COREML_USE_FLOAT16'] = '1'
            
        # Memory pressure management
        os.environ['COREML_MEMORY_PRESSURE_THRESHOLD'] = str(config.memory_pressure_threshold)
        
        self.logger.info(f"Applied ANE environment optimizations: {config.optimization_level} mode")
    
    def create_ane_provider_options(self, config: ANEConfiguration) -> Dict[str, Any]:
        """
        Create optimized CoreML provider options for ANE.
        
        @param config: ANE configuration
        @returns: CoreML provider options dictionary
        """
        options = {
            'MLComputeUnits': config.compute_units,
            'ModelFormat': config.model_format,
            'AllowLowPrecisionAccumulationOnGPU': '1' if config.allow_low_precision else '0',
            'RequireStaticInputShapes': '1' if config.require_static_shapes else '0',
        }
        
        # Add optimization-specific options
        if config.optimization_level == 'aggressive':
            options.update({
                'EnableANE': '1',
                'ANE_MemoryOptimization': '1',
                'ANE_PerformanceMode': '1',
            })
        
        return options
    
    def monitor_ane_performance(self, session_utilization: Dict[str, Any]) -> ANEPerformanceMetrics:
        """
        Monitor ANE performance and calculate optimization metrics.
        
        @param session_utilization: Session utilization data
        @returns: ANE performance metrics
        """
        total_requests = session_utilization.get('total_requests', 0)
        ane_requests = session_utilization.get('ane_requests', 0)
        ane_percentage = session_utilization.get('ane_percentage', 0.0)
        
        # Calculate optimization score (0-100)
        optimization_score = 0.0
        if total_requests > 0:
            # Base score from ANE utilization
            optimization_score += ane_percentage * 0.6
            
            # Bonus for high request volume
            if total_requests > 100:
                optimization_score += 10
            
            # Bonus for consistent ANE usage
            if ane_percentage > 50:
                optimization_score += 20
            elif ane_percentage > 25:
                optimization_score += 10
        
        metrics = ANEPerformanceMetrics(
            ane_utilization_percent=ane_percentage,
            total_requests=total_requests,
            ane_requests=ane_requests,
            average_latency_ms=0.0,  # Would need additional data
            memory_usage_mb=0.0,     # Would need additional data
            optimization_score=optimization_score
        )
        
        self.performance_metrics = metrics
        return metrics
    
    def get_optimization_recommendations(self, metrics: ANEPerformanceMetrics) -> list:
        """
        Get optimization recommendations based on current performance.
        
        @param metrics: Current ANE performance metrics
        @returns: List of optimization recommendations
        """
        recommendations = []
        
        if metrics.ane_utilization_percent < 10:
            recommendations.append({
                'priority': 'high',
                'type': 'ane_utilization',
                'message': 'ANE utilization is very low. Check CoreML configuration and model compatibility.',
                'action': 'Verify KOKORO_COREML_COMPUTE_UNITS=CPUAndNeuralEngine and model format'
            })
        
        elif metrics.ane_utilization_percent < 25:
            recommendations.append({
                'priority': 'medium',
                'type': 'ane_utilization',
                'message': 'ANE utilization could be improved. Consider optimizing text segmentation.',
                'action': 'Use shorter text segments for better ANE utilization'
            })
        
        if metrics.optimization_score < 30:
            recommendations.append({
                'priority': 'high',
                'type': 'overall_performance',
                'message': 'Overall optimization score is low. Review ANE configuration.',
                'action': 'Run ANE diagnostic and adjust configuration'
            })
        
        return recommendations
    
    def optimize_for_text_length(self, text_length: int) -> Dict[str, Any]:
        """
        Get ANE optimization strategy for specific text length.
        
        @param text_length: Length of text to be processed
        @returns: Optimization strategy dictionary
        """
        if not self.current_config:
            return {'strategy': 'default', 'reason': 'No ANE configuration available'}
        
        if text_length < 100:
            return {
                'strategy': 'ane_optimized',
                'reason': 'Short text - optimal for ANE processing',
                'recommended_provider': 'CoreMLExecutionProvider',
                'compute_units': 'CPUAndNeuralEngine'
            }
        elif text_length < 500:
            return {
                'strategy': 'ane_balanced',
                'reason': 'Medium text - balanced ANE/CPU processing',
                'recommended_provider': 'CoreMLExecutionProvider',
                'compute_units': 'CPUAndNeuralEngine'
            }
        else:
            return {
                'strategy': 'ane_cautious',
                'reason': 'Long text - use ANE with memory monitoring',
                'recommended_provider': 'CoreMLExecutionProvider',
                'compute_units': 'CPUAndNeuralEngine',
                'memory_monitoring': True
            }
    
    def get_ane_status_report(self) -> Dict[str, Any]:
        """
        Get comprehensive ANE status report.
        
        @returns: ANE status report dictionary
        """
        report = {
            'ane_available': True,
            'configuration': self.current_config.__dict__ if self.current_config else None,
            'performance_metrics': self.performance_metrics.__dict__ if self.performance_metrics else None,
            'environment_variables': {
                'KOKORO_COREML_COMPUTE_UNITS': os.environ.get('KOKORO_COREML_COMPUTE_UNITS', 'not_set'),
                'COREML_NEURAL_ENGINE_OPTIMIZATION': os.environ.get('COREML_NEURAL_ENGINE_OPTIMIZATION', 'not_set'),
                'COREML_USE_FLOAT16': os.environ.get('COREML_USE_FLOAT16', 'not_set'),
            },
            'optimization_recommendations': []
        }
        
        if self.performance_metrics:
            report['optimization_recommendations'] = self.get_optimization_recommendations(self.performance_metrics)
        
        return report


# Global ANE optimizer instance
_ane_optimizer: Optional[ANEOptimizer] = None


def get_ane_optimizer() -> ANEOptimizer:
    """Get the global ANE optimizer instance."""
    global _ane_optimizer
    if _ane_optimizer is None:
        _ane_optimizer = ANEOptimizer()
    return _ane_optimizer


def initialize_ane_optimization(capabilities: Dict[str, Any]) -> ANEConfiguration:
    """
    Initialize ANE optimization with hardware capabilities.
    
    @param capabilities: Hardware capabilities dictionary
    @returns: Applied ANE configuration
    """
    optimizer = get_ane_optimizer()
    config = optimizer.detect_optimal_ane_config(capabilities)
    optimizer.apply_ane_environment_optimizations(config)
    return config


def get_ane_performance_report() -> Dict[str, Any]:
    """
    Get current ANE performance report.
    
    @returns: ANE performance report
    """
    optimizer = get_ane_optimizer()
    return optimizer.get_ane_status_report()
