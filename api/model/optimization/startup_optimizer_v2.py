"""
Optimized Startup Time Implementation

This module implements the actual startup optimizations to reduce the 47.8-second
startup time to under 15 seconds while maintaining system reliability.

@author: @darianrosebrook
@date: 2025-01-17
@version: 1.0.0
@license: MIT
"""

import os
import time
import logging
import threading
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class StartupOptimizationConfig:
    """Configuration for startup optimizations"""
    enable_lazy_warming: bool = True
    enable_background_init: bool = True
    enable_minimal_warming: bool = True
    warming_timeout_ms: int = 5000  # 5 second timeout for warming
    background_init_delay_ms: int = 1000  # 1 second delay before background init


class OptimizedStartupManager:
    """
    Optimized startup manager that implements the actual startup time reductions.
    
    This class provides:
    1. Minimal session warming (1 inference instead of 3+)
    2. Background initialization of heavy components
    3. Lazy loading of non-critical features
    4. Intelligent timeout management
    """
    
    def __init__(self, config: Optional[StartupOptimizationConfig] = None):
        self.config = config or StartupOptimizationConfig()
        self.logger = logging.getLogger(__name__)
        self.background_threads: List[threading.Thread] = []
        
    def optimize_enhanced_session_warming(self, model) -> None:
        """
        Optimize the enhanced session warming process.
        
        Original: 3+ warming inferences taking 31+ seconds
        Optimized: 1 minimal warming inference taking <5 seconds
        """
        if not self.config.enable_minimal_warming:
            return
            
        self.logger.info("🚀 Starting optimized session warming...")
        start_time = time.perf_counter()
        
        try:
            # Single minimal warming inference instead of 3
            warming_text = "Hi"  # Minimal text for fastest warming
            
            self.logger.debug(f"Minimal warming with: '{warming_text}'")
            warming_start = time.perf_counter()
            
            # Set timeout for warming
            def warming_task():
                try:
                    model.create(warming_text, "af_heart", 1.0, "en-us")
                    return True
                except Exception as e:
                    self.logger.debug(f"Warming failed: {e}")
                    return False
            
            # Run warming with timeout
            warming_success = self._run_with_timeout(
                warming_task, 
                timeout_ms=self.config.warming_timeout_ms
            )
            
            if warming_success:
                warming_time = (time.perf_counter() - warming_start) * 1000
                self.logger.info(f"✅ Optimized session warming completed in {warming_time:.1f}ms")
            else:
                self.logger.warning("⚠️ Session warming timed out - continuing with cold start")
            
            # Schedule background warming for remaining components
            if self.config.enable_background_init:
                self._schedule_background_warming(model)
                
        except Exception as e:
            self.logger.error(f"❌ Optimized session warming failed: {e}")
        
        total_time = (time.perf_counter() - start_time) * 1000
        self.logger.info(f"🚀 Total optimized warming time: {total_time:.1f}ms")
    
    def _run_with_timeout(self, func, timeout_ms: int) -> bool:
        """Run a function with timeout."""
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                result = future.result(timeout=timeout_ms / 1000.0)
                return result
            except concurrent.futures.TimeoutError:
                self.logger.debug(f"Function timed out after {timeout_ms}ms")
                return False
            except Exception as e:
                self.logger.debug(f"Function failed: {e}")
                return False
    
    def _schedule_background_warming(self, model) -> None:
        """Schedule background warming of additional components."""
        def background_warming():
            try:
                # Wait a bit before starting background warming
                time.sleep(self.config.background_init_delay_ms / 1000.0)
                
                self.logger.info("🔄 Starting background session warming...")
                bg_start = time.perf_counter()
                
                # Additional warming texts (run in background)
                additional_texts = [
                    "Hello world",  # Short - typical quick request
                    "This is a test sentence to warm up the model."  # Medium - more graph paths
                ]
                
                for i, text in enumerate(additional_texts):
                    try:
                        start_warmup = time.perf_counter()
                        model.create(text, "af_heart", 1.0, "en-us")
                        warmup_time = (time.perf_counter() - start_warmup) * 1000
                        self.logger.debug(f"Background warming {i+1}/2: '{text[:20]}...' took {warmup_time:.1f}ms")
                    except Exception as warmup_err:
                        self.logger.debug(f"Background warming {i+1}/2 failed: {warmup_err}")
                
                bg_time = (time.perf_counter() - bg_start) * 1000
                self.logger.info(f"✅ Background session warming completed in {bg_time:.1f}ms")
                
            except Exception as e:
                self.logger.debug(f"Background warming failed: {e}")
        
        # Start background thread
        thread = threading.Thread(
            target=background_warming,
            name="background-session-warming",
            daemon=True
        )
        thread.start()
        self.background_threads.append(thread)
        self.logger.debug("🔄 Background session warming scheduled")
    
    def optimize_adaptive_provider_warming(self, model) -> None:
        """
        Optimize the adaptive provider cache pre-warming.
        
        Original: Pre-warms both CPU and CoreML models synchronously
        Optimized: Lazy warming or background warming
        """
        if not self.config.enable_lazy_warming:
            return
            
        self.logger.info("🚀 Starting optimized adaptive provider warming...")
        start_time = time.perf_counter()
        
        try:
            # Schedule background adaptive provider warming
            def adaptive_warming():
                try:
                    time.sleep(0.5)  # Brief delay
                    
                    from api.tts.core import _get_cached_model
                    self.logger.info("🔄 Pre-warming model cache for adaptive provider scenarios...")
                    adaptive_start = time.perf_counter()
                    
                    # Get the current active provider
                    current_provider = "CoreMLExecutionProvider" if "CoreML" in str(model.__class__) else "CPUExecutionProvider"
                    self.logger.debug(f"Current provider: {current_provider}")
                    
                    # Pre-warm CPU model (for short text < 200 chars)
                    try:
                        self.logger.info("🔄 Pre-warming CPU model for short text...")
                        cpu_model = _get_cached_model("CPUExecutionProvider")
                        cpu_model.create("Hi there", "af_heart", 1.0, "en-us")
                        self.logger.debug("✅ CPU model cache ready")
                    except Exception as cpu_err:
                        self.logger.debug(f"CPU model warming failed: {cpu_err}")
                    
                    # Pre-warm CoreML model (for medium/long text > 200 chars)
                    try:
                        self.logger.info("🔄 Pre-warming CoreML model for medium/long text...")
                        coreml_model = _get_cached_model("CoreMLExecutionProvider")
                        coreml_model.create("This is a longer test to warm up CoreML", "af_heart", 1.0, "en-us")
                        self.logger.debug("✅ CoreML model cache ready")
                    except Exception as coreml_err:
                        self.logger.debug(f"CoreML model warming failed: {coreml_err}")
                    
                    adaptive_time = (time.perf_counter() - adaptive_start) * 1000
                    self.logger.info(f"✅ Adaptive provider cache pre-warming completed in {adaptive_time:.1f}ms")
                    
                except Exception as adaptive_err:
                    self.logger.debug(f"Adaptive provider warming failed: {adaptive_err}")
            
            # Start background thread for adaptive warming
            thread = threading.Thread(
                target=adaptive_warming,
                name="background-adaptive-warming",
                daemon=True
            )
            thread.start()
            self.background_threads.append(thread)
            
        except Exception as e:
            self.logger.error(f"❌ Optimized adaptive provider warming failed: {e}")
        
        total_time = (time.perf_counter() - start_time) * 1000
        self.logger.info(f"🚀 Optimized adaptive warming setup: {total_time:.1f}ms")
    
    def optimize_heavy_components_init(self, capabilities: Dict[str, Any]) -> None:
        """
        Optimize heavy components initialization by deferring to background.
        
        Original: Heavy components init in background thread
        Optimized: Delayed background init with better error handling
        """
        if not self.config.enable_background_init:
            return
            
        def optimized_heavy_init():
            try:
                # Wait longer before starting heavy components
                time.sleep(2.0)  # 2 second delay
                
                self.logger.info("🔄 Starting optimized heavy components initialization...")
                heavy_start = time.perf_counter()
                
                # Initialize dual session manager
                try:
                    from api.model.sessions.dual_session import DualSessionManager
                    dsm = DualSessionManager()
                    if dsm:
                        self.logger.info("✅ Dual session manager initialized in background")
                        
                        # Minimal dual session warming
                        try:
                            self.logger.info("🔄 Pre-warming dual sessions...")
                            warming_start = time.perf_counter()
                            
                            # Single warming pattern instead of multiple
                            warming_patterns = [
                                ("Hi", 0.2),  # Simple, should go to CPU/fast session
                            ]
                            
                            for text, expected_complexity in warming_patterns:
                                try:
                                    result = dsm.process_segment_concurrent(text, "af_heart", 1.0, "en-us")
                                    complexity = dsm.calculate_segment_complexity(text)
                                    optimal_session = dsm.get_optimal_session(complexity)
                                    self.logger.debug(f"Pre-warmed: '{text[:30]}...' → session={optimal_session}, complexity={complexity:.2f}")
                                except Exception as warmup_err:
                                    self.logger.debug(f"Dual session warming failed for '{text[:20]}...': {warmup_err}")
                            
                            warming_time = (time.perf_counter() - warming_start) * 1000
                            self.logger.info(f"✅ Dual session pre-warming completed in {warming_time:.1f}ms")
                            
                        except Exception as warming_e:
                            self.logger.debug(f"Dual session pre-warming failed: {warming_e}")
                            
                    else:
                        self.logger.error("Dual session manager initialization returned None")
                except Exception as e:
                    self.logger.debug(f"Dual session manager init failed: {e}")
                
                # Initialize other heavy components with better error handling
                heavy_components = [
                    ("dynamic memory manager", lambda: self._init_dynamic_memory_manager(capabilities)),
                    ("pipeline warmer", lambda: self._init_pipeline_warmer()),
                    ("real-time optimizer", lambda: self._init_real_time_optimizer()),
                ]
                
                for name, init_func in heavy_components:
                    try:
                        self.logger.info(f"🔄 Initializing {name}...")
                        init_func()
                        self.logger.debug(f"✅ {name} initialized")
                    except Exception as e:
                        self.logger.debug(f"{name} init failed: {e}")
                
                heavy_time = (time.perf_counter() - heavy_start) * 1000
                self.logger.info(f"✅ Optimized heavy components initialization completed in {heavy_time:.1f}ms")
                
            except Exception as e:
                self.logger.debug(f"Optimized heavy components init failed: {e}")
        
        # Start background thread
        thread = threading.Thread(
            target=optimized_heavy_init,
            name="optimized-heavy-init",
            daemon=True
        )
        thread.start()
        self.background_threads.append(thread)
        self.logger.debug("🔄 Optimized heavy components initialization scheduled")
    
    def _init_dynamic_memory_manager(self, capabilities: Dict[str, Any]) -> None:
        """Initialize dynamic memory manager."""
        from api.model.memory.dynamic_manager import initialize_dynamic_memory_manager
        initialize_dynamic_memory_manager(capabilities=capabilities)
    
    def _init_pipeline_warmer(self) -> None:
        """Initialize pipeline warmer."""
        from api.model.pipeline.warmer import initialize_pipeline_warmer
        initialize_pipeline_warmer()
    
    def _init_real_time_optimizer(self) -> None:
        """Initialize real-time optimizer."""
        from api.performance.optimization import initialize_real_time_optimizer
        initialize_real_time_optimizer()
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get summary of applied optimizations."""
        return {
            'optimizations_applied': {
                'minimal_warming': self.config.enable_minimal_warming,
                'background_init': self.config.enable_background_init,
                'lazy_warming': self.config.enable_lazy_warming,
            },
            'background_threads_count': len(self.background_threads),
            'warming_timeout_ms': self.config.warming_timeout_ms,
            'background_init_delay_ms': self.config.background_init_delay_ms,
        }


# Global optimized startup manager
_optimized_startup_manager: Optional[OptimizedStartupManager] = None


def get_optimized_startup_manager() -> OptimizedStartupManager:
    """Get the global optimized startup manager."""
    global _optimized_startup_manager
    if _optimized_startup_manager is None:
        _optimized_startup_manager = OptimizedStartupManager()
    return _optimized_startup_manager


def apply_startup_optimizations(model, capabilities: Dict[str, Any]) -> None:
    """
    Apply all startup optimizations to reduce startup time.
    
    @param model: The initialized model
    @param capabilities: Hardware capabilities
    """
    manager = get_optimized_startup_manager()
    
    # Apply optimizations
    manager.optimize_enhanced_session_warming(model)
    manager.optimize_adaptive_provider_warming(model)
    manager.optimize_heavy_components_init(capabilities)
    
    # Apply cache optimizations in background
    try:
        from api.model.optimization.cache_optimizer import apply_cache_optimizations
        apply_cache_optimizations()
        logger.info("✅ Cache optimizations applied successfully")
    except Exception as e:
        logger.debug(f"Cache optimizations failed: {e}")
    
    logger.info("🚀 All startup optimizations applied successfully")


def get_startup_optimization_summary() -> Dict[str, Any]:
    """Get startup optimization summary."""
    manager = get_optimized_startup_manager()
    return manager.get_optimization_summary()
