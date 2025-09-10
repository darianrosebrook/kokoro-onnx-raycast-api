#!/usr/bin/env python3
"""
Comprehensive Optimization Pipeline for Kokoro TTS

This script implements a complete optimization pipeline that combines:
- Phase 5: Advanced Quantization (per-channel INT8, hybrid FP16)
- Phase 6: ONNX Graph Optimizations (fusion, constant folding, static shapes)
- Performance benchmarking and validation
- Quality assessment and comparison

## Pipeline Stages

### Stage 1: Model Analysis
- Load and validate input model
- Analyze model structure and operations
- Identify optimization opportunities

### Stage 2: Graph Optimization
- Apply operator fusion and constant folding
- Implement static shape binding
- Optimize for Apple Silicon hardware

### Stage 3: Quantization
- Per-channel INT8 quantization
- Hybrid INT8+FP16 strategy
- Calibration with representative data

### Stage 4: Validation & Benchmarking
- Model validation and quality assessment
- Performance benchmarking
- Memory usage analysis

@author: @darianrosebrook
@date: 2025-08-08
@version: 1.0.0
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import TTSConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OptimizationPipeline:
    """
    Comprehensive optimization pipeline for Kokoro TTS model.
    
    This class orchestrates the complete optimization process from
    model analysis through quantization and validation.
    """
    
    def __init__(self, input_model_path: str, output_dir: str):
        """
        Initialize the optimization pipeline.
        
        Args:
            input_model_path: Path to input model
            output_dir: Directory for output files
        """
        self.input_model_path = input_model_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Pipeline stages
        self.stages = {
            'analysis': False,
            'graph_optimization': False,
            'quantization': False,
            'validation': False,
            'benchmarking': False
        }
        
        # Results tracking
        self.results = {
            'pipeline_start_time': time.time(),
            'stage_results': {},
            'final_metrics': {},
            'optimization_summary': {}
        }
    
    def run_stage_analysis(self) -> bool:
        """
        Stage 1: Model analysis and optimization planning.
        
        Returns:
            True if analysis completed successfully, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("STAGE 1: MODEL ANALYSIS")
            logger.info("=" * 60)
            
            start_time = time.time()
            
            # Import analysis modules
            try:
                import onnx
                from scripts.optimize_onnx_graph import ONNXGraphOptimizer
            except ImportError as e:
                logger.error(f"Failed to import analysis modules: {e}")
                return False
            
            # Load model for analysis
            optimizer = ONNXGraphOptimizer(self.input_model_path)
            if not optimizer.load_model():
                logger.error("Failed to load model for analysis")
                return False
            
            # Get model statistics
            stats = optimizer.get_optimization_stats()
            
            # Analyze model structure
            model_info = {
                'model_path': self.input_model_path,
                'model_size_mb': stats.get('original_size_mb', 0),
                'total_operations': stats.get('total_original_ops', 0),
                'operation_types': stats.get('original_operations', {}),
                'analysis_time_seconds': time.time() - start_time
            }
            
            # Save analysis results
            analysis_file = self.output_dir / "model_analysis.json"
            with open(analysis_file, 'w') as f:
                json.dump(model_info, f, indent=2)
            
            self.results['stage_results']['analysis'] = model_info
            self.stages['analysis'] = True
            
            logger.info(f"Model analysis completed in {model_info['analysis_time_seconds']:.2f}s")
            logger.info(f"Model size: {model_info['model_size_mb']:.2f} MB")
            logger.info(f"Total operations: {model_info['total_operations']}")
            
            return True
            
        except Exception as e:
            logger.error(f"Model analysis failed: {e}")
            return False
    
    def run_stage_graph_optimization(self) -> bool:
        """
        Stage 2: ONNX graph optimization.
        
        Returns:
            True if optimization completed successfully, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("STAGE 2: ONNX GRAPH OPTIMIZATION")
            logger.info("=" * 60)
            
            start_time = time.time()
            
            # Import optimization modules
            try:
                from scripts.optimize_onnx_graph import ONNXGraphOptimizer
            except ImportError as e:
                logger.error(f"Failed to import graph optimization modules: {e}")
                return False
            
            # Initialize optimizer
            optimizer = ONNXGraphOptimizer(self.input_model_path)
            if not optimizer.load_model():
                logger.error("Failed to load model for graph optimization")
                return False
            
            # Apply all graph optimizations
            optimizations_applied = []
            
            if optimizer.apply_basic_optimizations():
                optimizations_applied.append("basic")
            
            if optimizer.apply_advanced_fusion():
                optimizations_applied.append("fusion")
            
            if optimizer.apply_constant_folding():
                optimizations_applied.append("constant_folding")
            
            if optimizer.apply_static_shape_binding():
                optimizations_applied.append("static_shapes")
            
            if optimizer.apply_apple_silicon_optimizations():
                optimizations_applied.append("apple_silicon")
            
            # Save optimized model
            graph_optimized_path = self.output_dir / "model_graph_optimized.onnx"
            if not optimizer.save_optimized_model(str(graph_optimized_path)):
                logger.error("Failed to save graph-optimized model")
                return False
            
            # Get optimization statistics
            stats = optimizer.get_optimization_stats()
            
            # Record results
            graph_optimization_results = {
                'optimizations_applied': optimizations_applied,
                'optimization_stats': stats,
                'output_model_path': str(graph_optimized_path),
                'optimization_time_seconds': time.time() - start_time
            }
            
            self.results['stage_results']['graph_optimization'] = graph_optimization_results
            self.stages['graph_optimization'] = True
            
            logger.info(f"Graph optimization completed in {graph_optimization_results['optimization_time_seconds']:.2f}s")
            logger.info(f"Optimizations applied: {', '.join(optimizations_applied)}")
            logger.info(f"Operation reduction: {stats.get('operation_reduction_percent', 0):.1f}%")
            logger.info(f"Size reduction: {stats.get('size_reduction_percent', 0):.1f}%")
            
            return True
            
        except Exception as e:
            logger.error(f"Graph optimization failed: {e}")
            return False
    
    def run_stage_quantization(self) -> bool:
        """
        Stage 3: Model quantization.
        
        Returns:
            True if quantization completed successfully, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("STAGE 3: MODEL QUANTIZATION")
            logger.info("=" * 60)
            
            start_time = time.time()
            
            # Import quantization modules
            try:
                from scripts.quantize_model import quantize_model_per_channel
            except ImportError as e:
                logger.error(f"Failed to import quantization modules: {e}")
                return False
            
            # Determine input model for quantization
            if self.stages['graph_optimization']:
                input_model = self.output_dir / "model_graph_optimized.onnx"
                logger.info(f"Using graph-optimized model for quantization: {input_model}")
            else:
                input_model = self.input_model_path
                logger.info(f"Using original model for quantization: {input_model}")
            
            # Perform quantization
            quantized_model_path = self.output_dir / "model_quantized.onnx"
            
            success = quantize_model_per_channel(
                input_model_path=str(input_model),
                output_model_path=str(quantized_model_path),
                calibration_samples=100,
                optimize=True
            )
            
            if not success:
                logger.error("Quantization failed")
                return False
            
            # Record results
            quantization_results = {
                'input_model_path': str(input_model),
                'output_model_path': str(quantized_model_path),
                'calibration_samples': 100,
                'quantization_time_seconds': time.time() - start_time
            }
            
            self.results['stage_results']['quantization'] = quantization_results
            self.stages['quantization'] = True
            
            logger.info(f"Quantization completed in {quantization_results['quantization_time_seconds']:.2f}s")
            logger.info(f"Quantized model saved to: {quantized_model_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"Quantization failed: {e}")
            return False
    
    def run_stage_validation(self) -> bool:
        """
        Stage 4: Model validation and quality assessment.
        
        Returns:
            True if validation completed successfully, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("STAGE 4: MODEL VALIDATION")
            logger.info("=" * 60)
            
            start_time = time.time()
            
            # Import validation modules
            try:
                import onnx
                from scripts.optimize_onnx_graph import ONNXGraphOptimizer
            except ImportError as e:
                logger.error(f"Failed to import validation modules: {e}")
                return False
            
            # Validate final model
            final_model_path = self.output_dir / "model_quantized.onnx"
            if not final_model_path.exists():
                logger.error(f"Final model not found: {final_model_path}")
                return False
            
            # Load and validate model
            optimizer = ONNXGraphOptimizer(str(final_model_path))
            if not optimizer.load_model():
                logger.error("Failed to load final model for validation")
                return False
            
            if not optimizer.validate_optimized_model():
                logger.error("Final model validation failed")
                return False
            
            # Get final statistics
            final_stats = optimizer.get_optimization_stats()
            
            # Record validation results
            validation_results = {
                'final_model_path': str(final_model_path),
                'model_valid': True,
                'final_stats': final_stats,
                'validation_time_seconds': time.time() - start_time
            }
            
            self.results['stage_results']['validation'] = validation_results
            self.stages['validation'] = True
            
            logger.info(f"Validation completed in {validation_results['validation_time_seconds']:.2f}s")
            logger.info("✅ Final model validation passed!")
            
            return True
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False
    
    def run_stage_benchmarking(self) -> bool:
        """
        Stage 5: Performance benchmarking.
        
        Returns:
            True if benchmarking completed successfully, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("STAGE 5: PERFORMANCE BENCHMARKING")
            logger.info("=" * 60)
            
            start_time = time.time()
            
            # Import benchmarking modules
            try:
                from scripts.optimize_onnx_graph import benchmark_model_performance
            except ImportError as e:
                logger.error(f"Failed to import benchmarking modules: {e}")
                return False
            
            # Benchmark original model
            logger.info("Benchmarking original model...")
            original_benchmark = benchmark_model_performance(self.input_model_path, num_runs=10)
            
            # Benchmark final optimized model
            final_model_path = self.output_dir / "model_quantized.onnx"
            logger.info("Benchmarking optimized model...")
            optimized_benchmark = benchmark_model_performance(str(final_model_path), num_runs=10)
            
            # Calculate improvements
            speed_improvement = 0.0
            if original_benchmark and optimized_benchmark:
                speed_improvement = ((original_benchmark['avg_inference_time_ms'] - 
                                    optimized_benchmark['avg_inference_time_ms']) / 
                                   original_benchmark['avg_inference_time_ms']) * 100
            
            # Record benchmarking results
            benchmarking_results = {
                'original_benchmark': original_benchmark,
                'optimized_benchmark': optimized_benchmark,
                'speed_improvement_percent': speed_improvement,
                'benchmarking_time_seconds': time.time() - start_time
            }
            
            self.results['stage_results']['benchmarking'] = benchmarking_results
            self.stages['benchmarking'] = True
            
            logger.info(f"Benchmarking completed in {benchmarking_results['benchmarking_time_seconds']:.2f}s")
            if original_benchmark and optimized_benchmark:
                logger.info(f"Original inference time: {original_benchmark['avg_inference_time_ms']:.2f} ms")
                logger.info(f"Optimized inference time: {optimized_benchmark['avg_inference_time_ms']:.2f} ms")
                logger.info(f"Speed improvement: {speed_improvement:.1f}%")
            
            return True
            
        except Exception as e:
            logger.error(f"Benchmarking failed: {e}")
            return False
    
    def generate_final_report(self) -> bool:
        """
        Generate comprehensive optimization report.
        
        Returns:
            True if report generated successfully, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("GENERATING FINAL REPORT")
            logger.info("=" * 60)
            
            # Calculate overall metrics
            total_time = time.time() - self.results['pipeline_start_time']
            
            # Compile final metrics
            final_metrics = {
                'total_pipeline_time_seconds': total_time,
                'stages_completed': sum(self.stages.values()),
                'total_stages': len(self.stages),
                'success_rate': (sum(self.stages.values()) / len(self.stages)) * 100
            }
            
            # Add stage-specific metrics
            if 'analysis' in self.results['stage_results']:
                final_metrics['original_model_size_mb'] = self.results['stage_results']['analysis']['model_size_mb']
            
            if 'validation' in self.results['stage_results']:
                final_stats = self.results['stage_results']['validation']['final_stats']
                final_metrics['final_model_size_mb'] = final_stats.get('optimized_size_mb', 0)
                final_metrics['size_reduction_percent'] = final_stats.get('size_reduction_percent', 0)
                final_metrics['operation_reduction_percent'] = final_stats.get('operation_reduction_percent', 0)
            
            if 'benchmarking' in self.results['stage_results']:
                benchmarking = self.results['stage_results']['benchmarking']
                final_metrics['speed_improvement_percent'] = benchmarking.get('speed_improvement_percent', 0)
            
            self.results['final_metrics'] = final_metrics
            
            # Generate optimization summary
            summary = {
                'pipeline_version': '1.0.0',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'input_model': self.input_model_path,
                'output_directory': str(self.output_dir),
                'stages_completed': list(k for k, v in self.stages.items() if v),
                'stages_failed': list(k for k, v in self.stages.items() if not v),
                'performance_improvements': {
                    'size_reduction_percent': final_metrics.get('size_reduction_percent', 0),
                    'operation_reduction_percent': final_metrics.get('operation_reduction_percent', 0),
                    'speed_improvement_percent': final_metrics.get('speed_improvement_percent', 0)
                },
                'total_time_seconds': final_metrics['total_pipeline_time_seconds']
            }
            
            self.results['optimization_summary'] = summary
            
            # Save comprehensive report
            report_file = self.output_dir / "optimization_report.json"
            with open(report_file, 'w') as f:
                json.dump(self.results, f, indent=2)
            
            # Save summary report
            summary_file = self.output_dir / "optimization_summary.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            # Print summary
            logger.info("=" * 60)
            logger.info("OPTIMIZATION PIPELINE COMPLETED")
            logger.info("=" * 60)
            logger.info(f"Total time: {total_time:.2f} seconds")
            logger.info(f"Stages completed: {final_metrics['stages_completed']}/{final_metrics['total_stages']}")
            logger.info(f"Success rate: {final_metrics['success_rate']:.1f}%")
            
            if 'size_reduction_percent' in final_metrics:
                logger.info(f"Model size reduction: {final_metrics['size_reduction_percent']:.1f}%")
            
            if 'speed_improvement_percent' in final_metrics:
                logger.info(f"Speed improvement: {final_metrics['speed_improvement_percent']:.1f}%")
            
            logger.info(f"Reports saved to: {self.output_dir}")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate final report: {e}")
            return False
    
    def run_pipeline(self, stages: Optional[List[str]] = None) -> bool:
        """
        Run the complete optimization pipeline.
        
        Args:
            stages: List of stages to run (None for all stages)
            
        Returns:
            True if pipeline completed successfully, False otherwise
        """
        try:
            logger.info("Starting comprehensive optimization pipeline...")
            logger.info(f"Input model: {self.input_model_path}")
            logger.info(f"Output directory: {self.output_dir}")
            
            # Define stage execution order
            stage_order = ['analysis', 'graph_optimization', 'quantization', 'validation', 'benchmarking']
            
            # Filter stages if specified
            if stages:
                stage_order = [s for s in stage_order if s in stages]
            
            # Execute stages
            for stage in stage_order:
                logger.info(f"\nExecuting stage: {stage}")
                
                stage_method = getattr(self, f'run_stage_{stage}')
                if not stage_method():
                    logger.error(f"Stage {stage} failed, stopping pipeline")
                    return False
            
            # Generate final report
            self.generate_final_report()
            
            return True
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            return False


def main():
    """Main function for optimization pipeline."""
    parser = argparse.ArgumentParser(description="Comprehensive optimization pipeline for Kokoro TTS")
    parser.add_argument("--input", "-i", required=True, help="Input model path")
    parser.add_argument("--output-dir", "-o", required=True, help="Output directory")
    parser.add_argument("--stages", nargs="+", choices=['analysis', 'graph_optimization', 'quantization', 'validation', 'benchmarking'],
                       help="Specific stages to run (default: all stages)")
    parser.add_argument("--skip-stages", nargs="+", choices=['analysis', 'graph_optimization', 'quantization', 'validation', 'benchmarking'],
                       help="Stages to skip")
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = OptimizationPipeline(args.input, args.output_dir)
    
    # Determine stages to run
    all_stages = ['analysis', 'graph_optimization', 'quantization', 'validation', 'benchmarking']
    
    if args.stages:
        stages_to_run = args.stages
    elif args.skip_stages:
        stages_to_run = [s for s in all_stages if s not in args.skip_stages]
    else:
        stages_to_run = all_stages
    
    # Run pipeline
    success = pipeline.run_pipeline(stages_to_run)
    
    if success:
        logger.info("✅ Optimization pipeline completed successfully!")
        return 0
    else:
        logger.error(" Optimization pipeline failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
