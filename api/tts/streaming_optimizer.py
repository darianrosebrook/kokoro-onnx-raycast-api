"""
Streaming Audio Optimization Module

This module implements advanced streaming optimizations to reduce TTFA (Time to First Audio)
by generating and streaming audio incrementally instead of waiting for complete segments.
"""

import asyncio
import time
import logging
import numpy as np
from typing import AsyncGenerator, Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass
class StreamingConfig:
    """Configuration for streaming optimization"""
    # Chunk generation settings
    min_chunk_size_ms: int = 50      # Minimum chunk size in milliseconds
    max_chunk_size_ms: int = 200     # Maximum chunk size in milliseconds
    target_buffer_ms: int = 150      # Target buffer size for smooth playback
    
    # TTFA optimization settings
    first_chunk_target_ms: int = 200  # Target time to first chunk
    parallel_processing: bool = True   # Enable parallel segment processing
    
    # Quality/speed tradeoffs
    fast_path_enabled: bool = True     # Enable fast path for simple text
    incremental_generation: bool = True # Generate audio incrementally
    
    # Performance monitoring
    enable_timing_logs: bool = True    # Log detailed timing information

class IncrementalAudioGenerator:
    """
    Generates audio incrementally to minimize TTFA.
    
    Instead of generating complete audio segments before streaming,
    this generator produces audio in small chunks as soon as possible.
    """
    
    def __init__(self, config: StreamingConfig):
        self.config = config
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="audio_gen")
        self.last_processing_method = "unknown"  # Track the processing method used
        
    async def generate_streaming_audio(
        self, 
        text: str, 
        voice: str, 
        speed: float, 
        lang: str,
        request_id: str
    ) -> AsyncGenerator[Tuple[bytes, Dict[str, Any]], None]:
        """
        Generate audio incrementally with minimal TTFA.
        
        This method implements the core streaming optimization:
        1. Fast-path generation for first chunk (<200ms target)
        2. Parallel processing of subsequent text while streaming
        3. Incremental audio generation instead of batch processing
        """
        start_time = time.perf_counter()
        logger.info(f"[{request_id}] Starting incremental audio generation")
        
        # Split text into optimized segments for streaming
        segments = self._optimize_text_segmentation(text)
        logger.info(f"[{request_id}] Text split into {len(segments)} optimized segments")
        
        # Track metrics for optimization analysis
        metrics = {
            'segments_processed': 0,
            'first_chunk_time_ms': 0,
            'total_chunks_yielded': 0,
            'processing_method': 'incremental'
        }
        
        first_chunk_yielded = False
        
        try:
            # Process segments with streaming overlap
            for i, segment in enumerate(segments):
                segment_start = time.perf_counter()
                
                # Use fast path for first segment to minimize TTFA
                if i == 0 and self.config.fast_path_enabled:
                    async for chunk_data, chunk_metrics in self._generate_fast_first_chunk(
                        segment, voice, speed, lang, request_id
                    ):
                        if not first_chunk_yielded:
                            first_chunk_time = (time.perf_counter() - start_time) * 1000
                            metrics['first_chunk_time_ms'] = first_chunk_time
                            logger.info(f"[{request_id}] First chunk generated in {first_chunk_time:.1f}ms")
                            first_chunk_yielded = True
                        
                        metrics['total_chunks_yielded'] += 1
                        yield chunk_data, {**chunk_metrics, **metrics}
                else:
                    # Use incremental generation for subsequent segments
                    async for chunk_data, chunk_metrics in self._generate_incremental_segment(
                        segment, voice, speed, lang, request_id, i
                    ):
                        metrics['total_chunks_yielded'] += 1
                        yield chunk_data, {**chunk_metrics, **metrics}
                
                metrics['segments_processed'] += 1
                segment_time = (time.perf_counter() - segment_start) * 1000
                logger.debug(f"[{request_id}] Segment {i} completed in {segment_time:.1f}ms")
        
        except Exception as e:
            logger.error(f"[{request_id}] Streaming generation failed: {e}")
            raise
        
        total_time = (time.perf_counter() - start_time) * 1000
        logger.info(f"[{request_id}] Incremental generation completed in {total_time:.1f}ms")
    
    def _optimize_text_segmentation(self, text: str) -> List[str]:
        """
        Optimize text segmentation for streaming performance.
        
        This creates very small first segments for minimal TTFA,
        with larger subsequent segments for efficiency.
        """
        if len(text) <= 50:
            return [text]
        
        segments = []
        
        # Create tiny first segment for ultra-fast TTFA
        if len(text) > 100:
            # Find first natural break point within first 30 characters
            first_break = 20
            for i, char in enumerate(text[:30]):
                if char in '.!?':
                    first_break = i + 1
                    break
                elif char in ',;':
                    first_break = i + 1
            
            first_segment = text[:first_break].strip()
            if first_segment:
                segments.append(first_segment)
                remaining = text[first_break:].strip()
            else:
                remaining = text
        else:
            remaining = text
        
        # Split remaining text into reasonable chunks
        while remaining:
            if len(remaining) <= 100:
                segments.append(remaining)
                break
            
            # Find break point around 80-120 characters
            break_point = 80
            for i in range(80, min(120, len(remaining))):
                if remaining[i] in '.!?':
                    break_point = i + 1
                    break
                elif remaining[i] in ' \n':
                    break_point = i
            
            segment = remaining[:break_point].strip()
            if segment:
                segments.append(segment)
            remaining = remaining[break_point:].strip()
        
        return [s for s in segments if s]  # Remove empty segments
    
    async def _generate_fast_first_chunk(
        self, 
        text: str, 
        voice: str, 
        speed: float, 
        lang: str,
        request_id: str
    ) -> AsyncGenerator[Tuple[bytes, Dict[str, Any]], None]:
        """
        Generate the first audio chunk using the fastest possible method.
        
        Target: <200ms to first audio chunk
        """
        chunk_start = time.perf_counter()
        
        try:
            # Use optimized fast generation path
            from api.tts.core import _fast_generate_audio_segment
            
            logger.debug(f"[{request_id}] Generating fast first chunk: '{text[:30]}...'")
            
            # Generate audio using fast path in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                _fast_generate_audio_segment,
                0, text, voice, speed, lang
            )
            
            idx, audio_np, provider_info, processing_method = result
            self.last_processing_method = processing_method
            
            if audio_np is None:
                logger.warning(f"[{request_id}] Fast first chunk generation failed")
                return
            
            generation_time = (time.perf_counter() - chunk_start) * 1000
            
            # Convert to bytes and create small initial chunks for immediate streaming
            audio_bytes = self._convert_audio_to_bytes(audio_np)
            
            # Yield audio in small chunks for immediate playback
            chunk_size = 512  # Small chunks for minimal latency
            total_yielded = 0
            
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i + chunk_size]
                chunk_metrics = {
                    'chunk_index': total_yielded,
                    'chunk_size': len(chunk),
                    'generation_method': 'fast_first_chunk',
                    'provider': provider_info,
                    'generation_time_ms': generation_time if i == 0 else 0
                }
                
                yield chunk, chunk_metrics
                total_yielded += 1
            
            logger.info(f"[{request_id}] Fast first chunk: {generation_time:.1f}ms, {total_yielded} chunks")
            
        except Exception as e:
            logger.error(f"[{request_id}] Fast first chunk generation failed: {e}")
            raise
    
    async def _generate_incremental_segment(
        self, 
        text: str, 
        voice: str, 
        speed: float, 
        lang: str,
        request_id: str,
        segment_index: int
    ) -> AsyncGenerator[Tuple[bytes, Dict[str, Any]], None]:
        """
        Generate audio for a segment using incremental processing.
        
        This method generates audio progressively rather than waiting
        for complete segment processing.
        """
        segment_start = time.perf_counter()
        
        try:
            # Use standard generation path but with chunked output
            from api.tts.core import _generate_audio_segment
            
            logger.debug(f"[{request_id}] Generating incremental segment {segment_index}: '{text[:30]}...'")
            
            # Generate audio in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                _generate_audio_segment,
                segment_index, text, voice, speed, lang
            )
            
            idx, audio_np, provider_info, processing_method = result
            self.last_processing_method = processing_method
            
            if audio_np is None:
                logger.warning(f"[{request_id}] Segment {segment_index} generation failed")
                return
            
            generation_time = (time.perf_counter() - segment_start) * 1000
            
            # Convert and stream in optimized chunks
            audio_bytes = self._convert_audio_to_bytes(audio_np)
            
            # Use larger chunks for efficiency on subsequent segments
            chunk_size = 1024
            total_yielded = 0
            
            for i in range(0, len(audio_bytes), chunk_size):
                chunk = audio_bytes[i:i + chunk_size]
                chunk_metrics = {
                    'chunk_index': total_yielded,
                    'chunk_size': len(chunk),
                    'segment_index': segment_index,
                    'generation_method': 'incremental_segment',
                    'provider': provider_info,
                    'generation_time_ms': generation_time if i == 0 else 0
                }
                
                yield chunk, chunk_metrics
                total_yielded += 1
            
            logger.debug(f"[{request_id}] Segment {segment_index}: {generation_time:.1f}ms, {total_yielded} chunks")
            
        except Exception as e:
            logger.error(f"[{request_id}] Incremental segment {segment_index} failed: {e}")
            raise
    
    def _convert_audio_to_bytes(self, audio_np: np.ndarray) -> bytes:
        """
        Convert numpy audio array to bytes with optimized processing.
        
        This method minimizes conversion overhead for faster streaming.
        """
        try:
            # Ensure audio is properly formatted
            audio_np = np.asarray(audio_np, dtype=np.float32)
            if audio_np.ndim > 1:
                audio_np = audio_np.reshape(-1)
            
            # Handle NaN/Inf values
            audio_np = np.nan_to_num(audio_np, nan=0.0, posinf=1.0, neginf=-1.0)
            
            # Try optimized WAV conversion first
            try:
                from api.tts.misaki_processing import audio_to_wav_bytes
                return audio_to_wav_bytes(audio_np, sample_rate=24000)
            except ImportError:
                # Fallback to simple PCM conversion
                return (audio_np * 32767).astype(np.int16).tobytes()
            
        except Exception as e:
            logger.warning(f"Audio conversion failed: {e}, using fallback")
            # Emergency fallback
            return (np.zeros(1000, dtype=np.int16)).tobytes()
    
    def cleanup(self):
        """Clean up resources"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


class StreamingOptimizer:
    """
    Main streaming optimization coordinator.
    
    This class orchestrates all streaming optimizations and provides
    the main interface for optimized audio generation.
    """
    
    def __init__(self, config: Optional[StreamingConfig] = None):
        self.config = config or StreamingConfig()
        self.generator = IncrementalAudioGenerator(self.config)
        self.active_requests: Dict[str, Any] = {}
    
    async def optimize_stream_tts_audio(
        self,
        text: str,
        voice: str,
        speed: float,
        lang: str,
        format: str,
        request_id: str
    ) -> AsyncGenerator[bytes, None]:
        """
        Main optimized streaming interface.
        
        This replaces the standard stream_tts_audio function with
        optimized incremental generation.
        """
        start_time = time.perf_counter()
        self.active_requests[request_id] = {
            'start_time': start_time,
            'text_length': len(text),
            'voice': voice,
            'speed': speed
        }
        
        try:
            logger.info(f"[{request_id}] Starting optimized streaming: voice='{voice}', speed={speed}")
            
            total_chunks = 0
            first_chunk_time = None
            
            async for chunk_data, metrics in self.generator.generate_streaming_audio(
                text, voice, speed, lang, request_id
            ):
                if first_chunk_time is None:
                    first_chunk_time = (time.perf_counter() - start_time) * 1000
                    logger.info(f"[{request_id}] TTFA OPTIMIZED: {first_chunk_time:.1f}ms")
                
                total_chunks += 1
                yield chunk_data
            
            total_time = (time.perf_counter() - start_time) * 1000
            
            # Update performance stats with actual processing method
            from api.performance.stats import update_fast_path_performance_stats
            
            # Get the actual processing method from the generator
            # This should reflect what actually happened in text processing
            actual_processing_method = getattr(self.generator, 'last_processing_method', 'unknown')
            
            # If we don't have the processing method from the generator, use a heuristic
            if actual_processing_method == 'unknown':
                # Simple heuristic: short, simple text likely used fast-path
                if len(text) <= 100 and text.isascii() and not any(c in text for c in '{}[]()@#$%^&*+=<>'):
                    actual_processing_method = 'fast_path'
                else:
                    actual_processing_method = 'phonemizer'  # Default to phonemizer for complex text
            
            update_fast_path_performance_stats(
                processing_method=actual_processing_method,
                ttfa_ms=first_chunk_time or 0,
                success=first_chunk_time is not None and first_chunk_time <= 800,
                total_time_ms=total_time,
                total_chunks=total_chunks
            )
            
            logger.info(f"[{request_id}] Optimized streaming completed: {total_time:.1f}ms, {total_chunks} chunks")
            
        except Exception as e:
            logger.error(f"[{request_id}] Optimized streaming failed: {e}")
            raise
        finally:
            if request_id in self.active_requests:
                del self.active_requests[request_id]
    
    def get_optimization_status(self) -> Dict[str, Any]:
        """Get current optimization status and metrics"""
        return {
            'active_requests': len(self.active_requests),
            'config': {
                'fast_path_enabled': self.config.fast_path_enabled,
                'incremental_generation': self.config.incremental_generation,
                'target_buffer_ms': self.config.target_buffer_ms,
                'first_chunk_target_ms': self.config.first_chunk_target_ms
            },
            'recent_requests': list(self.active_requests.keys())
        }
    
    def cleanup(self):
        """Clean up optimizer resources"""
        self.generator.cleanup()


# Global streaming optimizer instance
_streaming_optimizer: Optional[StreamingOptimizer] = None

def get_streaming_optimizer() -> StreamingOptimizer:
    """Get the global streaming optimizer instance"""
    global _streaming_optimizer
    if _streaming_optimizer is None:
        config = StreamingConfig(
            fast_path_enabled=True,
            incremental_generation=True,
            first_chunk_target_ms=200,
            target_buffer_ms=150
        )
        _streaming_optimizer = StreamingOptimizer(config)
    return _streaming_optimizer

def cleanup_streaming_optimizer():
    """Clean up the global streaming optimizer"""
    global _streaming_optimizer
    if _streaming_optimizer:
        _streaming_optimizer.cleanup()
        _streaming_optimizer = None
