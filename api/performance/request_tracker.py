"""
Server-side Performance Request Tracking

This module provides server-side performance tracking that coordinates with
client-side tracking to provide end-to-end performance monitoring from
text input to audio generation.

@author: @darianrosebrook
@date: 2025-08-18
@version: 1.0.0
"""

import time
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ServerPerformanceEvent:
    """Server-side performance event"""
    request_id: str
    stage: str
    timestamp: float
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ServerRequestFlow:
    """Server-side request flow tracking"""
    request_id: str
    start_time: float
    events: List[ServerPerformanceEvent] = field(default_factory=list)
    text: str = ""
    voice: str = ""
    speed: float = 1.0
    completed: bool = False
    total_duration_ms: Optional[float] = None

@dataclass
class ServerPerformanceMetrics:
    """Server-side performance metrics"""
    # Core timing metrics
    request_received_to_processing_start: float = 0.0
    text_processing_time_ms: float = 0.0
    phoneme_generation_time_ms: float = 0.0
    model_inference_time_ms: float = 0.0
    audio_generation_time_ms: float = 0.0
    first_chunk_generated_time_ms: float = 0.0
    total_server_processing_time_ms: float = 0.0
    
    # Quality metrics
    provider_used: str = "unknown"
    cache_hit: bool = False
    text_length: int = 0
    phoneme_count: int = 0
    audio_chunks_generated: int = 0
    
    # Error tracking
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

class ServerPerformanceTracker:
    """Server-side performance tracking system"""
    
    def __init__(self):
        self.active_flows: Dict[str, ServerRequestFlow] = {}
        self.completed_flows: List[ServerRequestFlow] = []
        self._lock = None  # Will be set to threading.Lock() if needed
        
    def start_request(self, request_id: str, text: str, voice: str, speed: float) -> None:
        """Start tracking a new request"""
        flow = ServerRequestFlow(
            request_id=request_id,
            start_time=time.perf_counter(),
            text=text,
            voice=voice,
            speed=speed
        )
        
        self.active_flows[request_id] = flow
        
        self.log_event(request_id, "REQUEST_RECEIVED", {
            "text_length": len(text),
            "voice": voice,
            "speed": speed
        })
        
    def log_event(self, request_id: str, stage: str, metadata: Dict[str, Any] = None) -> None:
        """Log a performance event"""
        if request_id not in self.active_flows:
            logger.warning(f"ServerPerformanceTracker: No active flow for request {request_id}")
            return
            
        flow = self.active_flows[request_id]
        event = ServerPerformanceEvent(
            request_id=request_id,
            stage=stage,
            timestamp=time.perf_counter(),
            metadata=metadata or {}
        )
        
        flow.events.append(event)
        
        # Log with consistent format
        logger.info(f"[SERVER_PERF:{request_id}] {stage}", extra={
            "timestamp": datetime.now().isoformat(),
            "stage": stage,
            **(metadata or {})
        })
        
    def complete_request(self, request_id: str) -> Optional[ServerPerformanceMetrics]:
        """Complete a request and calculate final metrics"""
        if request_id not in self.active_flows:
            logger.warning(f"ServerPerformanceTracker: No active flow for request {request_id}")
            return None
            
        flow = self.active_flows[request_id]
        flow.completed = True
        flow.total_duration_ms = (time.perf_counter() - flow.start_time) * 1000
        
        metrics = self._calculate_metrics(flow)
        
        # Move to completed flows
        del self.active_flows[request_id]
        self.completed_flows.append(flow)
        
        # Log final summary
        self._log_final_summary(request_id, metrics)
        
        return metrics
        
    def _calculate_metrics(self, flow: ServerRequestFlow) -> ServerPerformanceMetrics:
        """Calculate performance metrics from flow events"""
        events = flow.events
        start_time = flow.start_time
        
        # Find key timing events
        request_received = events[0] if events else None
        processing_start = self._find_event(events, "PROCESSING_START")
        text_processing_complete = self._find_event(events, "TEXT_PROCESSING_COMPLETE")
        phoneme_generation_complete = self._find_event(events, "PHONEME_GENERATION_COMPLETE")
        inference_start = self._find_event(events, "INFERENCE_START")
        inference_complete = self._find_event(events, "INFERENCE_COMPLETE")
        first_chunk_generated = self._find_event(events, "FIRST_CHUNK_GENERATED")
        audio_generation_complete = self._find_event(events, "AUDIO_GENERATION_COMPLETE")
        
        # Calculate timing metrics
        request_received_to_processing_start = (
            (processing_start.timestamp - start_time) * 1000 
            if processing_start else 0
        )
        
        text_processing_time_ms = (
            (text_processing_complete.timestamp - processing_start.timestamp) * 1000
            if text_processing_complete and processing_start else 0
        )
        
        phoneme_generation_time_ms = (
            (phoneme_generation_complete.timestamp - text_processing_complete.timestamp) * 1000
            if phoneme_generation_complete and text_processing_complete else 0
        )
        
        model_inference_time_ms = (
            (inference_complete.timestamp - inference_start.timestamp) * 1000
            if inference_complete and inference_start else 0
        )
        
        first_chunk_generated_time_ms = (
            (first_chunk_generated.timestamp - start_time) * 1000
            if first_chunk_generated else 0
        )
        
        total_server_processing_time_ms = (
            (audio_generation_complete.timestamp - start_time) * 1000
            if audio_generation_complete else 0
        )
        
        # Extract metadata
        provider_used = inference_start.metadata.get("provider", "unknown") if inference_start else "unknown"
        cache_hit = any(e.stage == "CACHE_HIT" for e in events)
        text_length = len(flow.text)
        phoneme_count = text_processing_complete.metadata.get("phoneme_count", 0) if text_processing_complete else 0
        audio_chunks_generated = len([e for e in events if e.stage == "AUDIO_CHUNK_GENERATED"])
        
        # Collect errors and warnings
        errors = [e.metadata.get("error", "") for e in events if e.stage == "ERROR"]
        warnings = [e.metadata.get("warning", "") for e in events if e.stage == "WARNING"]
        
        return ServerPerformanceMetrics(
            request_received_to_processing_start=request_received_to_processing_start,
            text_processing_time_ms=text_processing_time_ms,
            phoneme_generation_time_ms=phoneme_generation_time_ms,
            model_inference_time_ms=model_inference_time_ms,
            audio_generation_time_ms=total_server_processing_time_ms,
            first_chunk_generated_time_ms=first_chunk_generated_time_ms,
            total_server_processing_time_ms=total_server_processing_time_ms,
            provider_used=provider_used,
            cache_hit=cache_hit,
            text_length=text_length,
            phoneme_count=phoneme_count,
            audio_chunks_generated=audio_chunks_generated,
            errors=errors,
            warnings=warnings
        )
        
    def _find_event(self, events: List[ServerPerformanceEvent], stage: str) -> Optional[ServerPerformanceEvent]:
        """Find the first event with the given stage"""
        for event in events:
            if event.stage == stage:
                return event
        return None
        
    def _log_final_summary(self, request_id: str, metrics: ServerPerformanceMetrics) -> None:
        """Log final performance summary"""
        status = "✅ PASS" if metrics.first_chunk_generated_time_ms <= 800 else "❌ FAIL"
        
        logger.info(f"[SERVER_PERF:{request_id}] FINAL_SUMMARY", extra={
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "metrics": {
                "first_chunk_generated_ms": f"{metrics.first_chunk_generated_time_ms:.2f}",
                "total_processing_ms": f"{metrics.total_server_processing_time_ms:.2f}",
                "text_processing_ms": f"{metrics.text_processing_time_ms:.2f}",
                "inference_ms": f"{metrics.model_inference_time_ms:.2f}",
                "provider_used": metrics.provider_used,
                "cache_hit": metrics.cache_hit,
                "chunks_generated": metrics.audio_chunks_generated
            },
            "errors": metrics.errors if metrics.errors else None,
            "warnings": metrics.warnings if metrics.warnings else None
        })
        
    def get_completed_flows(self) -> List[ServerRequestFlow]:
        """Get all completed flows for analysis"""
        return self.completed_flows.copy()
        
    def clear_completed_flows(self) -> None:
        """Clear completed flows for memory management"""
        self.completed_flows.clear()

# Global instance
server_tracker = ServerPerformanceTracker()
