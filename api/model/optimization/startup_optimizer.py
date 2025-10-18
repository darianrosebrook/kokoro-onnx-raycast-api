"""
Startup Time Optimization Module

This module provides intelligent startup optimization to reduce the 47+ second
startup time while maintaining system reliability and performance.

@author: @darianrosebrook
@date: 2025-01-17
@version: 1.0.0
@license: MIT
"""

import asyncio
import logging
import time
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import concurrent.futures

logger = logging.getLogger(__name__)


class StartupPhase(Enum):
    """Startup phases for optimization"""
    DEPENDENCIES = "dependencies"
    HARDWARE_DETECTION = "hardware_detection"
    MODEL_LOADING = "model_loading"
    SESSION_WARMING = "session_warming"
    CACHE_INITIALIZATION = "cache_initialization"
    BACKGROUND_SERVICES = "background_services"


@dataclass
class StartupTask:
    """Individual startup task definition"""
    name: str
    phase: StartupPhase
    function: Callable
    dependencies: List[str] = field(default_factory=list)
    critical: bool = True
    parallelizable: bool = False
    estimated_duration_ms: int = 1000
    timeout_ms: int = 30000


@dataclass
class StartupMetrics:
    """Startup performance metrics"""
    total_startup_time_ms: float
    phase_timings: Dict[StartupPhase, float]
    task_timings: Dict[str, float]
    parallelization_savings_ms: float
    optimization_score: float
    bottlenecks: List[str]


class StartupOptimizer:
    """
    Startup time optimization manager.
    
    This class provides intelligent startup optimization through:
    1. Parallel execution of independent tasks
    2. Lazy loading of non-critical components
    3. Background initialization of heavy components
    4. Intelligent caching and pre-warming
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.tasks: Dict[str, StartupTask] = {}
        self.metrics: Optional[StartupMetrics] = None
        self.optimization_enabled = True
        
    def register_task(self, task: StartupTask) -> None:
        """
        Register a startup task for optimization.
        
        @param task: Startup task definition
        """
        self.tasks[task.name] = task
        self.logger.debug(f"Registered startup task: {task.name} ({task.phase.value})")
    
    def optimize_startup_sequence(self) -> Dict[str, Any]:
        """
        Optimize the startup sequence for minimal time.
        
        @returns: Optimization plan and estimated savings
        """
        if not self.optimization_enabled:
            return {'optimization_enabled': False}
        
        # Analyze current startup sequence
        critical_path = self._analyze_critical_path()
        parallelizable_tasks = self._identify_parallelizable_tasks()
        lazy_loadable_tasks = self._identify_lazy_loadable_tasks()
        
        # Calculate potential savings
        current_estimated_time = sum(task.estimated_duration_ms for task in self.tasks.values())
        optimized_estimated_time = self._calculate_optimized_time(
            critical_path, parallelizable_tasks, lazy_loadable_tasks
        )
        
        savings_ms = current_estimated_time - optimized_estimated_time
        savings_percent = (savings_ms / current_estimated_time) * 100 if current_estimated_time > 0 else 0
        
        optimization_plan = {
            'current_estimated_time_ms': current_estimated_time,
            'optimized_estimated_time_ms': optimized_estimated_time,
            'potential_savings_ms': savings_ms,
            'potential_savings_percent': savings_percent,
            'critical_path': critical_path,
            'parallelizable_tasks': parallelizable_tasks,
            'lazy_loadable_tasks': lazy_loadable_tasks,
            'optimization_strategies': self._generate_optimization_strategies()
        }
        
        self.logger.info(f"Startup optimization plan: {savings_percent:.1f}% time reduction possible")
        return optimization_plan
    
    def _analyze_critical_path(self) -> List[str]:
        """Analyze the critical path through startup tasks."""
        # Simple topological sort to find critical path
        visited = set()
        critical_path = []
        
        def visit(task_name: str):
            if task_name in visited:
                return
            visited.add(task_name)
            
            task = self.tasks.get(task_name)
            if task and task.critical:
                critical_path.append(task_name)
                for dep in task.dependencies:
                    visit(dep)
        
        # Start with tasks that have no dependencies
        for task_name, task in self.tasks.items():
            if not task.dependencies and task.critical:
                visit(task_name)
        
        return critical_path
    
    def _identify_parallelizable_tasks(self) -> List[str]:
        """Identify tasks that can be run in parallel."""
        parallelizable = []
        
        for task_name, task in self.tasks.items():
            if task.parallelizable and not task.critical:
                parallelizable.append(task_name)
        
        return parallelizable
    
    def _identify_lazy_loadable_tasks(self) -> List[str]:
        """Identify tasks that can be deferred to after startup."""
        lazy_loadable = []
        
        for task_name, task in self.tasks.items():
            if not task.critical and task.phase in [
                StartupPhase.BACKGROUND_SERVICES,
                StartupPhase.CACHE_INITIALIZATION
            ]:
                lazy_loadable.append(task_name)
        
        return lazy_loadable
    
    def _calculate_optimized_time(self, critical_path: List[str], 
                                parallelizable: List[str], 
                                lazy_loadable: List[str]) -> int:
        """Calculate optimized startup time."""
        # Critical path time (cannot be optimized)
        critical_time = sum(
            self.tasks[name].estimated_duration_ms 
            for name in critical_path 
            if name in self.tasks
        )
        
        # Parallelizable tasks (can run concurrently)
        parallel_time = max(
            (self.tasks[name].estimated_duration_ms for name in parallelizable if name in self.tasks),
            default=0
        )
        
        # Lazy loadable tasks (deferred to background)
        lazy_time = 0  # These don't count toward startup time
        
        return critical_time + parallel_time + lazy_time
    
    def _generate_optimization_strategies(self) -> List[Dict[str, Any]]:
        """Generate specific optimization strategies."""
        strategies = []
        
        # Strategy 1: Parallel initialization
        strategies.append({
            'name': 'parallel_initialization',
            'description': 'Run independent tasks in parallel',
            'impact': 'high',
            'implementation': 'Use ThreadPoolExecutor for parallelizable tasks'
        })
        
        # Strategy 2: Lazy loading
        strategies.append({
            'name': 'lazy_loading',
            'description': 'Defer non-critical initialization to background',
            'impact': 'medium',
            'implementation': 'Move background services to post-startup initialization'
        })
        
        # Strategy 3: Cache pre-warming
        strategies.append({
            'name': 'cache_prewarming',
            'description': 'Pre-warm caches during idle time',
            'impact': 'medium',
            'implementation': 'Background cache warming after critical path'
        })
        
        # Strategy 4: Provider selection optimization
        strategies.append({
            'name': 'provider_optimization',
            'description': 'Skip provider benchmarking on startup',
            'impact': 'high',
            'implementation': 'Use cached provider selection or safe defaults'
        })
        
        return strategies
    
    async def execute_optimized_startup(self) -> StartupMetrics:
        """
        Execute optimized startup sequence.
        
        @returns: Startup performance metrics
        """
        start_time = time.perf_counter()
        phase_timings = {}
        task_timings = {}
        bottlenecks = []
        
        try:
            # Phase 1: Critical path (sequential)
            critical_start = time.perf_counter()
            await self._execute_critical_path()
            phase_timings[StartupPhase.DEPENDENCIES] = (time.perf_counter() - critical_start) * 1000
            
            # Phase 2: Parallel initialization
            parallel_start = time.perf_counter()
            await self._execute_parallel_tasks()
            phase_timings[StartupPhase.MODEL_LOADING] = (time.perf_counter() - parallel_start) * 1000
            
            # Phase 3: Background initialization (non-blocking)
            background_start = time.perf_counter()
            self._start_background_initialization()
            phase_timings[StartupPhase.BACKGROUND_SERVICES] = (time.perf_counter() - background_start) * 1000
            
        except Exception as e:
            self.logger.error(f"Optimized startup failed: {e}")
            bottlenecks.append(f"Startup error: {str(e)}")
        
        total_time = (time.perf_counter() - start_time) * 1000
        
        # Calculate optimization score
        optimization_score = self._calculate_optimization_score(phase_timings, bottlenecks)
        
        self.metrics = StartupMetrics(
            total_startup_time_ms=total_time,
            phase_timings=phase_timings,
            task_timings=task_timings,
            parallelization_savings_ms=0,  # Would need baseline comparison
            optimization_score=optimization_score,
            bottlenecks=bottlenecks
        )
        
        self.logger.info(f"Optimized startup completed in {total_time:.1f}ms")
        return self.metrics
    
    async def _execute_critical_path(self) -> None:
        """Execute critical path tasks sequentially."""
        critical_tasks = [name for name, task in self.tasks.items() if task.critical]
        
        for task_name in critical_tasks:
            task = self.tasks[task_name]
            try:
                start_time = time.perf_counter()
                await self._execute_task(task)
                duration = (time.perf_counter() - start_time) * 1000
                self.logger.debug(f"Critical task {task_name} completed in {duration:.1f}ms")
            except Exception as e:
                self.logger.error(f"Critical task {task_name} failed: {e}")
                raise
    
    async def _execute_parallel_tasks(self) -> None:
        """Execute parallelizable tasks concurrently."""
        parallel_tasks = [task for task in self.tasks.values() if task.parallelizable]
        
        if not parallel_tasks:
            return
        
        # Execute tasks in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for task in parallel_tasks:
                future = executor.submit(self._execute_task_sync, task)
                futures.append(future)
            
            # Wait for all tasks to complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Parallel task failed: {e}")
    
    def _start_background_initialization(self) -> None:
        """Start background initialization of non-critical components."""
        background_tasks = [
            task for task in self.tasks.values() 
            if not task.critical and task.phase == StartupPhase.BACKGROUND_SERVICES
        ]
        
        for task in background_tasks:
            # Start background thread for non-critical initialization
            thread = threading.Thread(
                target=self._execute_task_sync,
                args=(task,),
                name=f"background-{task.name}",
                daemon=True
            )
            thread.start()
            self.logger.debug(f"Started background task: {task.name}")
    
    async def _execute_task(self, task: StartupTask) -> None:
        """Execute a startup task."""
        if asyncio.iscoroutinefunction(task.function):
            await task.function()
        else:
            # Run sync function in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, task.function)
    
    def _execute_task_sync(self, task: StartupTask) -> None:
        """Execute a startup task synchronously."""
        try:
            if asyncio.iscoroutinefunction(task.function):
                # Run async function in new event loop
                asyncio.run(task.function())
            else:
                task.function()
        except Exception as e:
            self.logger.error(f"Task {task.name} failed: {e}")
    
    def _calculate_optimization_score(self, phase_timings: Dict[StartupPhase, float], 
                                    bottlenecks: List[str]) -> float:
        """Calculate optimization score (0-100)."""
        score = 100.0
        
        # Penalize for bottlenecks
        score -= len(bottlenecks) * 10
        
        # Penalize for slow phases
        for phase, timing in phase_timings.items():
            if timing > 10000:  # > 10 seconds
                score -= 20
            elif timing > 5000:  # > 5 seconds
                score -= 10
        
        return max(0.0, score)
    
    def get_startup_report(self) -> Dict[str, Any]:
        """
        Get comprehensive startup performance report.
        
        @returns: Startup performance report
        """
        report = {
            'optimization_enabled': self.optimization_enabled,
            'total_tasks_registered': len(self.tasks),
            'metrics': self.metrics.__dict__ if self.metrics else None,
            'optimization_plan': self.optimize_startup_sequence() if self.optimization_enabled else None
        }
        
        return report


# Global startup optimizer instance
_startup_optimizer: Optional[StartupOptimizer] = None


def get_startup_optimizer() -> StartupOptimizer:
    """Get the global startup optimizer instance."""
    global _startup_optimizer
    if _startup_optimizer is None:
        _startup_optimizer = StartupOptimizer()
    return _startup_optimizer


def register_startup_task(task: StartupTask) -> None:
    """
    Register a startup task for optimization.
    
    @param task: Startup task definition
    """
    optimizer = get_startup_optimizer()
    optimizer.register_task(task)


def get_startup_optimization_report() -> Dict[str, Any]:
    """
    Get startup optimization report.
    
    @returns: Startup optimization report
    """
    optimizer = get_startup_optimizer()
    return optimizer.get_startup_report()
