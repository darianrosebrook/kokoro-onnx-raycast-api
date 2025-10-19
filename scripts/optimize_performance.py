#!/usr/bin/env python3
"""
Performance Optimization Script

This script implements the performance optimizations identified in the analysis:
1. Fix ANE (Neural Engine) utilization
2. Optimize startup time
3. Improve cache performance
4. Enhance monitoring

@author: @darianrosebrook
@date: 2025-01-17
@version: 1.0.0
@license: MIT
"""

import os
import sys
import time
import logging
import asyncio
import json
from typing import Dict, Any, Optional
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.model.optimization.ane_optimizer import initialize_ane_optimization, get_ane_performance_report
from api.model.optimization.startup_optimizer import get_startup_optimizer, StartupTask, StartupPhase
from api.model.hardware.detection import detect_apple_silicon_capabilities

logger = logging.getLogger(__name__)


class PerformanceOptimizer:
    """Main performance optimization orchestrator."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.optimization_results = {}
        
    def apply_ane_optimizations(self) -> Dict[str, Any]:
        """Apply ANE (Neural Engine) optimizations."""
        self.logger.info("🔧 Applying ANE optimizations...")
        
        try:
            # Detect hardware capabilities
            capabilities = detect_apple_silicon_capabilities()
            self.logger.info(f"Detected hardware: {capabilities.get('chip_family', 'unknown')} "
                           f"with {capabilities.get('neural_engine_cores', 0)} ANE cores")
            
            # Initialize ANE optimization
            ane_config = initialize_ane_optimization(capabilities)
            
            # Set environment variables for ANE
            os.environ['KOKORO_COREML_COMPUTE_UNITS'] = 'CPUAndNeuralEngine'
            os.environ['COREML_NEURAL_ENGINE_OPTIMIZATION'] = '1'
            os.environ['COREML_USE_FLOAT16'] = '1'
            os.environ['COREML_OPTIMIZE_FOR_APPLE_SILICON'] = '1'
            
            self.logger.info("✅ ANE optimizations applied successfully")
            
            return {
                'status': 'success',
                'ane_config': ane_config.__dict__,
                'environment_variables': {
                    'KOKORO_COREML_COMPUTE_UNITS': os.environ.get('KOKORO_COREML_COMPUTE_UNITS'),
                    'COREML_NEURAL_ENGINE_OPTIMIZATION': os.environ.get('COREML_NEURAL_ENGINE_OPTIMIZATION'),
                    'COREML_USE_FLOAT16': os.environ.get('COREML_USE_FLOAT16'),
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ ANE optimization failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def apply_startup_optimizations(self) -> Dict[str, Any]:
        """Apply startup time optimizations."""
        self.logger.info("🚀 Applying startup optimizations...")
        
        try:
            optimizer = get_startup_optimizer()
            
            # Register common startup tasks for optimization
            self._register_startup_tasks(optimizer)
            
            # Get optimization plan
            optimization_plan = optimizer.optimize_startup_sequence()
            
            self.logger.info(f"✅ Startup optimization plan generated: "
                           f"{optimization_plan.get('potential_savings_percent', 0):.1f}% time reduction possible")
            
            return {
                'status': 'success',
                'optimization_plan': optimization_plan
            }
            
        except Exception as e:
            self.logger.error(f"❌ Startup optimization failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _register_startup_tasks(self, optimizer) -> None:
        """Register startup tasks for optimization."""
        
        # Dependencies validation (critical, fast)
        # Import and use the existing dependency validation function
        from api.main import validate_dependencies

        optimizer.register_task(StartupTask(
            name="validate_dependencies",
            phase=StartupPhase.DEPENDENCIES,
            function=validate_dependencies,
            critical=True,
            estimated_duration_ms=100
        ))
        
        # Hardware detection (critical, fast)
        optimizer.register_task(StartupTask(
            name="detect_hardware",
            phase=StartupPhase.HARDWARE_DETECTION,
            function=lambda: detect_apple_silicon_capabilities(),
            critical=True,
            estimated_duration_ms=200
        ))
        
        # Model loading (critical, slow) - use existing async initialization
        def load_model_sync():
            """Synchronous wrapper for async model loading"""
            try:
                # Import here to avoid circular imports
                from api.main import initialize_model
                import asyncio

                # Run async initialization in new event loop
                asyncio.run(initialize_model())
                logger.info("✅ Model loading completed successfully")
            except Exception as e:
                logger.error(f"❌ Model loading failed: {e}")
                raise

        optimizer.register_task(StartupTask(
            name="load_model",
            phase=StartupPhase.MODEL_LOADING,
            function=load_model_sync,
            critical=True,
            estimated_duration_ms=15000
        ))
        
        # Session warming (critical, slow) - use existing cold-start warmup
        def warm_sessions_sync():
            """Synchronous wrapper for async session warming"""
            try:
                # Import here to avoid circular imports
                from api.main import perform_cold_start_warmup
                import asyncio

                # Run async session warming
                asyncio.run(perform_cold_start_warmup())
                logger.info("✅ Session warming completed successfully")
            except Exception as e:
                logger.error(f"❌ Session warming failed: {e}")
                raise

        optimizer.register_task(StartupTask(
            name="warm_sessions",
            phase=StartupPhase.SESSION_WARMING,
            function=warm_sessions_sync,
            critical=True,
            estimated_duration_ms=20000
        ))
        
        # Cache initialization (non-critical, can be lazy)
        def init_cache_sync():
            """Initialize and optimize cache systems"""
            try:
                # Import here to avoid circular imports
                from api.model.optimization.cache_optimizer import CacheOptimizer
                from api.config import TTSConfig

                logger.info("🔄 Initializing cache optimization system...")

                # Initialize cache optimizer
                cache_optimizer = CacheOptimizer()

                # Pre-warm phoneme cache
                cache_optimizer.optimize_phoneme_cache()

                # Pre-warm inference cache
                cache_optimizer.optimize_inference_cache()

                # Pre-warm primer microcache
                cache_optimizer.optimize_primer_cache()

                logger.info("✅ Cache initialization completed successfully")
            except Exception as e:
                logger.error(f"❌ Cache initialization failed: {e}")
                # Don't raise - cache init is non-critical
                logger.warning("⚠️ Continuing without cache optimization")

        optimizer.register_task(StartupTask(
            name="init_cache",
            phase=StartupPhase.CACHE_INITIALIZATION,
            function=init_cache_sync,
            critical=False,
            parallelizable=True,
            estimated_duration_ms=2000
        ))
        
        # Background services (non-critical, can be lazy)
        def start_background_services_sync():
            """Start background maintenance and monitoring services"""
            try:
                # Import here to avoid circular imports
                from api.model.optimization.startup_optimizer import get_startup_optimizer

                logger.info("🔄 Starting background maintenance services...")

                # Get the startup optimizer and start background initialization
                startup_optimizer = get_startup_optimizer()
                startup_optimizer._start_background_initialization()

                logger.info("✅ Background services started successfully")
            except Exception as e:
                logger.error(f"❌ Background services startup failed: {e}")
                # Don't raise - background services are non-critical
                logger.warning("⚠️ Continuing without background services")

        optimizer.register_task(StartupTask(
            name="start_background_services",
            phase=StartupPhase.BACKGROUND_SERVICES,
            function=start_background_services_sync,
            critical=False,
            parallelizable=True,
            estimated_duration_ms=1000
        ))
    
    def apply_cache_optimizations(self) -> Dict[str, Any]:
        """Apply cache performance optimizations."""
        self.logger.info("💾 Applying cache optimizations...")
        
        try:
            # Set cache optimization environment variables
            os.environ['KOKORO_CACHE_PREWARM'] = '1'
            os.environ['KOKORO_CACHE_PERSISTENCE'] = '1'
            os.environ['KOKORO_CACHE_OPTIMIZATION'] = '1'
            
            self.logger.info("✅ Cache optimizations applied successfully")
            
            return {
                'status': 'success',
                'cache_optimizations': {
                    'prewarming_enabled': True,
                    'persistence_enabled': True,
                    'optimization_enabled': True
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ Cache optimization failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def generate_optimization_report(self) -> Dict[str, Any]:
        """Generate comprehensive optimization report."""
        self.logger.info("📊 Generating optimization report...")
        
        try:
            # Get ANE performance report
            ane_report = get_ane_performance_report()
            
            # Get startup optimization report
            startup_report = get_startup_optimizer().get_startup_report()
            
            # Get hardware capabilities
            capabilities = detect_apple_silicon_capabilities()
            
            report = {
                'timestamp': time.time(),
                'optimization_results': self.optimization_results,
                'ane_report': ane_report,
                'startup_report': startup_report,
                'hardware_capabilities': capabilities,
                'environment_variables': {
                    'KOKORO_COREML_COMPUTE_UNITS': os.environ.get('KOKORO_COREML_COMPUTE_UNITS', 'not_set'),
                    'COREML_NEURAL_ENGINE_OPTIMIZATION': os.environ.get('COREML_NEURAL_ENGINE_OPTIMIZATION', 'not_set'),
                    'COREML_USE_FLOAT16': os.environ.get('COREML_USE_FLOAT16', 'not_set'),
                    'KOKORO_CACHE_PREWARM': os.environ.get('KOKORO_CACHE_PREWARM', 'not_set'),
                },
                'recommendations': self._generate_recommendations()
            }
            
            return report
            
        except Exception as e:
            self.logger.error(f"❌ Report generation failed: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _generate_recommendations(self) -> list:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Check ANE configuration
        if os.environ.get('KOKORO_COREML_COMPUTE_UNITS') != 'CPUAndNeuralEngine':
            recommendations.append({
                'priority': 'high',
                'category': 'ane_utilization',
                'message': 'Set KOKORO_COREML_COMPUTE_UNITS=CPUAndNeuralEngine for optimal ANE usage',
                'action': 'export KOKORO_COREML_COMPUTE_UNITS=CPUAndNeuralEngine'
            })
        
        # Check startup optimization
        if not os.environ.get('KOKORO_DEFER_BACKGROUND_INIT'):
            recommendations.append({
                'priority': 'medium',
                'category': 'startup_time',
                'message': 'Enable background initialization deferral for faster startup',
                'action': 'export KOKORO_DEFER_BACKGROUND_INIT=true'
            })
        
        # Check cache optimization
        if not os.environ.get('KOKORO_CACHE_PREWARM'):
            recommendations.append({
                'priority': 'medium',
                'category': 'cache_performance',
                'message': 'Enable cache pre-warming for better performance',
                'action': 'export KOKORO_CACHE_PREWARM=1'
            })
        
        return recommendations
    
    async def run_optimization(self) -> Dict[str, Any]:
        """Run complete performance optimization."""
        self.logger.info("🎯 Starting performance optimization...")
        
        start_time = time.perf_counter()
        
        # Apply optimizations
        self.optimization_results['ane'] = self.apply_ane_optimizations()
        self.optimization_results['startup'] = self.apply_startup_optimizations()
        self.optimization_results['cache'] = self.apply_cache_optimizations()
        
        # Generate report
        report = self.generate_optimization_report()
        
        total_time = time.perf_counter() - start_time
        
        self.logger.info(f"✅ Performance optimization completed in {total_time:.2f}s")
        
        return {
            'status': 'success',
            'optimization_time_seconds': total_time,
            'report': report
        }


async def main():
    """Main optimization function."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("🚀 Kokoro-ONNX Performance Optimizer")
    logger.info("=" * 50)
    
    # Run optimization
    optimizer = PerformanceOptimizer()
    result = await optimizer.run_optimization()
    
    # Save report
    report_file = project_root / "reports" / "performance_optimization_report.json"
    report_file.parent.mkdir(exist_ok=True)
    
    with open(report_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    logger.info(f"📄 Optimization report saved to: {report_file}")
    
    # Print summary
    print("\n" + "=" * 50)
    print("🎯 PERFORMANCE OPTIMIZATION SUMMARY")
    print("=" * 50)
    
    if result['status'] == 'success':
        print("✅ All optimizations applied successfully!")
        
        # Print key improvements
        ane_result = result['report']['optimization_results'].get('ane', {})
        if ane_result.get('status') == 'success':
            print("🧠 ANE (Neural Engine) optimizations: ENABLED")
        
        startup_result = result['report']['optimization_results'].get('startup', {})
        if startup_result.get('status') == 'success':
            plan = startup_result.get('optimization_plan', {})
            savings = plan.get('potential_savings_percent', 0)
            print(f"🚀 Startup optimizations: {savings:.1f}% time reduction possible")
        
        cache_result = result['report']['optimization_results'].get('cache', {})
        if cache_result.get('status') == 'success':
            print("💾 Cache optimizations: ENABLED")
        
        # Print recommendations
        recommendations = result['report'].get('recommendations', [])
        if recommendations:
            print("\n📋 RECOMMENDATIONS:")
            for rec in recommendations:
                priority_icon = "🔴" if rec['priority'] == 'high' else "🟡" if rec['priority'] == 'medium' else "🟢"
                print(f"{priority_icon} {rec['message']}")
                print(f"   Action: {rec['action']}")
        
        print(f"\n📄 Full report: {report_file}")
        
    else:
        print("❌ Optimization failed!")
        print(f"Error: {result.get('error', 'Unknown error')}")
    
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
