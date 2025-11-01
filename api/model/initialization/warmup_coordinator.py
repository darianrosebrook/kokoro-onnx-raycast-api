"""
Warmup Coordinator - Centralized warmup management to eliminate duplicate inferences.

This module coordinates all warmup systems to prevent redundant inference work
during startup, reducing startup time and eliminating duplicate warmup patterns.
"""

import logging
import threading
import time
from typing import Dict, Set, Optional, Callable, Tuple, Any
from enum import Enum

logger = logging.getLogger(__name__)


class WarmupStage(Enum):
    """Enumeration of warmup stages."""
    MINIMAL = "minimal"  # Fast init minimal warmup
    EXTENDED = "extended"  # Background extended warming
    DUAL_SESSION = "dual_session"  # Dual session pre-warming
    PIPELINE = "pipeline"  # Pipeline warmer
    COLD_START = "cold_start"  # Cold start warmup


class WarmupCoordinator:
    """
    Centralized warmup coordinator that prevents duplicate inference work.
    
    This coordinator tracks completed warmup patterns and coordinates between
    different warmup systems to eliminate redundant inferences.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._completed_patterns: Set[Tuple[str, str, float, str]] = set()  # (text, voice, speed, lang)
        self._completed_stages: Set[WarmupStage] = set()
        self._stage_results: Dict[WarmupStage, Dict[str, Any]] = {}
        self._start_time: Optional[float] = None
        
    def should_warmup(self, text: str, voice: str = "af_heart", speed: float = 1.0, lang: str = "en-us") -> bool:
        """
        Check if a warmup pattern should be executed.
        
        @param text: Text to check
        @param voice: Voice to check
        @param speed: Speed to check
        @param lang: Language to check
        @returns: True if warmup should be executed, False if already done
        """
        pattern_key = (text, voice, speed, lang)
        with self._lock:
            return pattern_key not in self._completed_patterns
    
    def mark_warmup_complete(self, text: str, voice: str = "af_heart", speed: float = 1.0, lang: str = "en-us", 
                            stage: Optional[WarmupStage] = None, result: Optional[Any] = None) -> None:
        """
        Mark a warmup pattern as completed.
        
        @param text: Text that was warmed up
        @param voice: Voice used
        @param speed: Speed used
        @param lang: Language used
        @param stage: Optional warmup stage
        @param result: Optional warmup result
        """
        pattern_key = (text, voice, speed, lang)
        with self._lock:
            self._completed_patterns.add(pattern_key)
            if stage:
                self._completed_stages.add(stage)
                if stage not in self._stage_results:
                    self._stage_results[stage] = {}
                self._stage_results[stage][text] = {
                    "completed_at": time.time(),
                    "result": result
                }
    
    def mark_stage_complete(self, stage: WarmupStage, results: Optional[Dict[str, Any]] = None) -> None:
        """
        Mark an entire warmup stage as completed.
        
        @param stage: Warmup stage
        @param results: Optional stage results
        """
        with self._lock:
            self._completed_stages.add(stage)
            if results:
                self._stage_results[stage] = results
    
    def is_stage_complete(self, stage: WarmupStage) -> bool:
        """
        Check if a warmup stage is complete.
        
        @param stage: Warmup stage to check
        @returns: True if stage is complete
        """
        with self._lock:
            return stage in self._completed_stages
    
    def get_coordinated_warmup_patterns(self, stage: WarmupStage) -> list[Tuple[str, str, float, str]]:
        """
        Get warmup patterns for a stage, excluding already completed patterns.
        
        @param stage: Warmup stage
        @returns: List of (text, voice, speed, lang) tuples to warmup
        """
        with self._lock:
            # Define stage-specific patterns
            stage_patterns: Dict[WarmupStage, list[Tuple[str, str, float, str]]] = {
                WarmupStage.MINIMAL: [
                    ("Hi", "af_heart", 1.0, "en-us"),
                ],
                WarmupStage.EXTENDED: [
                    ("Hello world", "af_heart", 1.0, "en-us"),
                    ("This is a test sentence to warm up the model.", "af_heart", 1.0, "en-us"),
                    ("Hi there", "af_heart", 1.0, "en-us"),  # CPU model warmup
                    ("This is a longer test to warm up CoreML", "af_heart", 1.0, "en-us"),  # CoreML model warmup
                ],
                WarmupStage.DUAL_SESSION: [
                    ("Hi", "af_heart", 1.0, "en-us"),
                    ("This is a more complex sentence for testing.", "af_heart", 1.0, "en-us"),
                ],
                WarmupStage.COLD_START: [
                    ("Hello world.", "af_heart", 1.0, "en-us"),
                ],
            }
            
            # Get patterns for this stage
            patterns = stage_patterns.get(stage, [])
            
            # Filter out already completed patterns
            return [p for p in patterns if p not in self._completed_patterns]
    
    def execute_warmup(self, text: str, voice: str, speed: float, lang: str, 
                      warmup_func: Callable[[str, str, float, str], Any],
                      stage: Optional[WarmupStage] = None) -> Optional[Any]:
        """
        Execute a warmup inference if not already done.
        
        @param text: Text to warmup
        @param voice: Voice to use
        @param speed: Speed to use
        @param lang: Language to use
        @param warmup_func: Function to execute warmup (text, voice, speed, lang) -> result
        @param stage: Optional warmup stage
        @returns: Warmup result if executed, None if skipped
        """
        if not self.should_warmup(text, voice, speed, lang):
            logger.debug(f"Skipping duplicate warmup: '{text[:30]}...' (already completed)")
            return None
        
        try:
            result = warmup_func(text, voice, speed, lang)
            self.mark_warmup_complete(text, voice, speed, lang, stage, result)
            logger.debug(f"✅ Warmup completed: '{text[:30]}...' (stage={stage.value if stage else 'unknown'})")
            return result
        except Exception as e:
            logger.debug(f"Warmup failed for '{text[:30]}...': {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get warmup coordinator statistics.
        
        @returns: Dictionary with warmup statistics
        """
        with self._lock:
            return {
                "completed_patterns": len(self._completed_patterns),
                "completed_stages": [stage.value for stage in self._completed_stages],
                "stage_results": {
                    stage.value: results 
                    for stage, results in self._stage_results.items()
                }
            }


# Global warmup coordinator instance
_warmup_coordinator: Optional[WarmupCoordinator] = None
_coordinator_lock = threading.Lock()


def get_warmup_coordinator() -> WarmupCoordinator:
    """
    Get or create the global warmup coordinator instance.
    
    @returns: Warmup coordinator instance
    """
    global _warmup_coordinator
    with _coordinator_lock:
        if _warmup_coordinator is None:
            _warmup_coordinator = WarmupCoordinator()
        return _warmup_coordinator


def initialize_warmup_coordinator() -> WarmupCoordinator:
    """
    Initialize the warmup coordinator.
    
    @returns: Warmup coordinator instance
    """
    return get_warmup_coordinator()

