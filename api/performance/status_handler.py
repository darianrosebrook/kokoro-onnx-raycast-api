"""
Status Update Handler for Long-Running Operations

This module provides comprehensive status update handling for long-running
TTS operations, including progress tracking, real-time synchronization,
and enterprise-grade status management.

@sign: @darianrosebrook
"""

import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Any, Callable, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class OperationStatus(Enum):
    """Status of long-running operations."""
    PENDING = "pending"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    STREAMING = "streaming"
    COMPLETING = "completing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StatusUpdateType(Enum):
    """Types of status updates."""
    PROGRESS = "progress"
    METRICS = "metrics"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    COMPLETION = "completion"


@dataclass
class StatusUpdate:
    """A status update message."""
    operation_id: str
    update_type: StatusUpdateType
    status: OperationStatus
    timestamp: float = field(default_factory=time.time)
    progress_percent: Optional[float] = None
    message: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    error_details: Optional[str] = None


@dataclass
class OperationProgress:
    """Progress tracking for long-running operations."""
    operation_id: str
    operation_type: str  # "tts_streaming", "tts_batch", etc.
    status: OperationStatus = OperationStatus.PENDING
    start_time: float = field(default_factory=time.time)
    last_update_time: float = field(default_factory=time.time)
    progress_percent: float = 0.0
    estimated_completion_time: Optional[float] = None
    total_items: Optional[int] = None
    completed_items: int = 0
    current_item: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        """Duration of the operation in seconds."""
        return time.time() - self.start_time

    @property
    def is_complete(self) -> bool:
        """Check if operation is complete."""
        return self.status in [OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.CANCELLED]

    def update_progress(self, completed: int, total: Optional[int] = None, item: Optional[str] = None):
        """Update progress counters."""
        self.completed_items = completed
        if total is not None:
            self.total_items = total
            self.progress_percent = (completed / total) * 100.0 if total > 0 else 0.0
        if item:
            self.current_item = item
        self.last_update_time = time.time()

    def add_metric(self, key: str, value: Any):
        """Add a metric to the operation."""
        self.metrics[key] = value

    def add_warning(self, warning: str):
        """Add a warning to the operation."""
        self.warnings.append(warning)

    def add_error(self, error: str):
        """Add an error to the operation."""
        self.errors.append(error)


class StatusUpdateHandler:
    """
    Handles status updates for long-running operations.

    Provides real-time status synchronization, progress tracking,
    and enterprise-grade status management.
    """

    def __init__(self):
        self.operations: Dict[str, OperationProgress] = {}
        self.status_listeners: Dict[str, List[Callable]] = {}
        self.update_queues: Dict[str, asyncio.Queue] = {}
        self.lock = threading.RLock()

        # Cleanup settings
        self.max_operation_age_hours = 24
        self.cleanup_interval_seconds = 3600  # 1 hour

        # Start cleanup task
        self.cleanup_task = None
        self._start_cleanup_task()

        logger.info("📊 Status update handler initialized")

    def start_operation(
        self,
        operation_id: str,
        operation_type: str,
        total_items: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> OperationProgress:
        """
        Start tracking a new operation.

        @param operation_id: Unique operation identifier
        @param operation_type: Type of operation ("tts_streaming", etc.)
        @param total_items: Total number of items to process
        @param metadata: Additional metadata for the operation
        @returns OperationProgress: Progress tracking object
        """
        with self.lock:
            if operation_id in self.operations:
                logger.warning(f"Operation {operation_id} already exists, overwriting")

            operation = OperationProgress(
                operation_id=operation_id,
                operation_type=operation_type,
                total_items=total_items,
                status=OperationStatus.INITIALIZING
            )

            if metadata:
                operation.metrics.update(metadata)

            self.operations[operation_id] = operation
            self.update_queues[operation_id] = asyncio.Queue()

            # Emit initial status update
            self._emit_status_update(operation_id, StatusUpdateType.INFO, OperationStatus.INITIALIZING,
                                   message=f"Started {operation_type} operation")

            logger.info(f"📊 Started tracking operation: {operation_id} ({operation_type})")
            return operation

    def update_operation_status(
        self,
        operation_id: str,
        status: OperationStatus,
        progress_percent: Optional[float] = None,
        message: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None
    ):
        """
        Update the status of an operation.

        @param operation_id: Operation identifier
        @param status: New operation status
        @param progress_percent: Progress percentage (0-100)
        @param message: Status message
        @param metrics: Additional metrics
        """
        with self.lock:
            if operation_id not in self.operations:
                logger.warning(f"Operation {operation_id} not found for status update")
                return

            operation = self.operations[operation_id]
            operation.status = status
            operation.last_update_time = time.time()

            if progress_percent is not None:
                operation.progress_percent = progress_percent

            if metrics:
                operation.metrics.update(metrics)

            # Determine update type based on status
            if status == OperationStatus.FAILED:
                update_type = StatusUpdateType.ERROR
            elif status == OperationStatus.COMPLETED:
                update_type = StatusUpdateType.COMPLETION
            elif any(word in (message or "").lower() for word in ["error", "fail", "exception"]):
                update_type = StatusUpdateType.ERROR
            elif any(word in (message or "").lower() for word in ["warn", "warning"]):
                update_type = StatusUpdateType.WARNING
            else:
                update_type = StatusUpdateType.PROGRESS

            self._emit_status_update(operation_id, update_type, status,
                                   progress_percent, message, metrics)

    def update_operation_progress(
        self,
        operation_id: str,
        completed_items: int,
        total_items: Optional[int] = None,
        current_item: Optional[str] = None
    ):
        """
        Update operation progress counters.

        @param operation_id: Operation identifier
        @param completed_items: Number of completed items
        @param total_items: Total number of items (optional)
        @param current_item: Currently processing item (optional)
        """
        with self.lock:
            if operation_id not in self.operations:
                return

            operation = self.operations[operation_id]
            operation.update_progress(completed_items, total_items, current_item)

            # Calculate estimated completion time
            if operation.completed_items > 0 and operation.total_items:
                progress_ratio = operation.completed_items / operation.total_items
                if progress_ratio > 0.1:  # Need some progress to estimate
                    elapsed = operation.duration_seconds
                    estimated_total = elapsed / progress_ratio
                    remaining = estimated_total - elapsed
                    operation.estimated_completion_time = time.time() + remaining

            progress_msg = f"Progress: {operation.completed_items}"
            if operation.total_items:
                progress_msg += f"/{operation.total_items}"
            if current_item:
                progress_msg += f" ({current_item})"

            self._emit_status_update(operation_id, StatusUpdateType.PROGRESS, operation.status,
                                   operation.progress_percent, progress_msg)

    def add_operation_metric(self, operation_id: str, key: str, value: Any):
        """Add a metric to an operation."""
        with self.lock:
            if operation_id in self.operations:
                self.operations[operation_id].add_metric(key, value)

    def add_operation_warning(self, operation_id: str, warning: str):
        """Add a warning to an operation."""
        with self.lock:
            if operation_id in self.operations:
                self.operations[operation_id].add_warning(warning)
                self._emit_status_update(operation_id, StatusUpdateType.WARNING, self.operations[operation_id].status,
                                       message=f"Warning: {warning}")

    def add_operation_error(self, operation_id: str, error: str):
        """Add an error to an operation."""
        with self.lock:
            if operation_id in self.operations:
                self.operations[operation_id].add_error(error)
                self._emit_status_update(operation_id, StatusUpdateType.ERROR, self.operations[operation_id].status,
                                       message=f"Error: {error}")

    def complete_operation(self, operation_id: str, success: bool = True, final_message: Optional[str] = None):
        """
        Mark an operation as completed.

        @param operation_id: Operation identifier
        @param success: Whether operation completed successfully
        @param final_message: Final status message
        """
        with self.lock:
            if operation_id not in self.operations:
                return

            operation = self.operations[operation_id]
            operation.status = OperationStatus.COMPLETED if success else OperationStatus.FAILED
            operation.progress_percent = 100.0 if success else operation.progress_percent

            message = final_message or f"Operation {'completed successfully' if success else 'failed'}"
            update_type = StatusUpdateType.COMPLETION if success else StatusUpdateType.ERROR

            self._emit_status_update(operation_id, update_type, operation.status,
                                   operation.progress_percent, message)

            logger.info(f"📊 Operation {operation_id} completed: {'success' if success else 'failure'}")

    def get_operation_status(self, operation_id: str) -> Optional[OperationProgress]:
        """Get the current status of an operation."""
        with self.lock:
            return self.operations.get(operation_id)

    def list_operations(self, status_filter: Optional[OperationStatus] = None) -> List[OperationProgress]:
        """List all operations, optionally filtered by status."""
        with self.lock:
            operations = list(self.operations.values())
            if status_filter:
                operations = [op for op in operations if op.status == status_filter]
            return operations

    def cancel_operation(self, operation_id: str, reason: Optional[str] = None):
        """Cancel an operation."""
        with self.lock:
            if operation_id in self.operations:
                operation = self.operations[operation_id]
                operation.status = OperationStatus.CANCELLED

                message = f"Operation cancelled{f': {reason}' if reason else ''}"
                self._emit_status_update(operation_id, StatusUpdateType.INFO, OperationStatus.CANCELLED,
                                       message=message)

                logger.info(f"📊 Operation {operation_id} cancelled")

    async def stream_operation_updates(self, operation_id: str) -> AsyncGenerator[StatusUpdate, None]:
        """
        Stream real-time status updates for an operation.

        @param operation_id: Operation identifier
        @yields StatusUpdate: Real-time status updates
        """
        queue = self.update_queues.get(operation_id)
        if not queue:
            return

        try:
            while True:
                update = await queue.get()
                yield update

                # End stream when operation is complete
                if update.status in [OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.CANCELLED]:
                    break

        except Exception as e:
            logger.error(f"Error streaming updates for operation {operation_id}: {e}")

    def add_status_listener(self, operation_id: str, listener: Callable[[StatusUpdate], None]):
        """Add a listener for status updates."""
        with self.lock:
            if operation_id not in self.status_listeners:
                self.status_listeners[operation_id] = []
            self.status_listeners[operation_id].append(listener)

    def remove_status_listener(self, operation_id: str, listener: Callable[[StatusUpdate], None]):
        """Remove a status update listener."""
        with self.lock:
            if operation_id in self.status_listeners:
                try:
                    self.status_listeners[operation_id].remove(listener)
                except ValueError:
                    pass

    def _emit_status_update(
        self,
        operation_id: str,
        update_type: StatusUpdateType,
        status: OperationStatus,
        progress_percent: Optional[float] = None,
        message: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        error_details: Optional[str] = None
    ):
        """Emit a status update to all listeners and queues."""
        update = StatusUpdate(
            operation_id=operation_id,
            update_type=update_type,
            status=status,
            progress_percent=progress_percent,
            message=message,
            metrics=metrics,
            error_details=error_details
        )

        # Send to async queue for streaming
        queue = self.update_queues.get(operation_id)
        if queue:
            try:
                # Use non-blocking put to avoid deadlocks
                queue.put_nowait(update)
            except asyncio.QueueFull:
                logger.warning(f"Status update queue full for operation {operation_id}")

        # Send to listeners
        listeners = self.status_listeners.get(operation_id, [])
        for listener in listeners:
            try:
                listener(update)
            except Exception as e:
                logger.error(f"Status listener failed for operation {operation_id}: {e}")

    def _start_cleanup_task(self):
        """Start the background cleanup task."""
        def cleanup_worker():
            while True:
                try:
                    self._cleanup_old_operations()
                    time.sleep(self.cleanup_interval_seconds)
                except Exception as e:
                    logger.error(f"Status cleanup task failed: {e}")
                    time.sleep(60)  # Wait before retry

        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True, name="status_cleanup")
        cleanup_thread.start()

    def _cleanup_old_operations(self):
        """Clean up old completed operations."""
        cutoff_time = time.time() - (self.max_operation_age_hours * 3600)

        with self.lock:
            to_remove = []
            for operation_id, operation in self.operations.items():
                if operation.is_complete and operation.last_update_time < cutoff_time:
                    to_remove.append(operation_id)

            for operation_id in to_remove:
                del self.operations[operation_id]
                self.update_queues.pop(operation_id, None)
                self.status_listeners.pop(operation_id, None)

            if to_remove:
                logger.info(f"🧹 Cleaned up {len(to_remove)} old operations")


# Global status handler instance
_status_handler = None

def get_status_handler() -> StatusUpdateHandler:
    """Get the global status update handler instance."""
    global _status_handler
    if _status_handler is None:
        _status_handler = StatusUpdateHandler()
    return _status_handler


# Convenience functions for TTS operations
def start_tts_operation(operation_id: str, text_length: int, is_streaming: bool = False) -> OperationProgress:
    """Start tracking a TTS operation."""
    handler = get_status_handler()
    operation_type = "tts_streaming" if is_streaming else "tts_single"

    return handler.start_operation(
        operation_id=operation_id,
        operation_type=operation_type,
        total_items=text_length if not is_streaming else None,  # For non-streaming, track by characters
        metadata={"text_length": text_length, "streaming": is_streaming}
    )

def update_tts_progress(operation_id: str, completed_chars: int, total_chars: int, current_segment: Optional[str] = None):
    """Update TTS operation progress."""
    handler = get_status_handler()
    handler.update_operation_progress(operation_id, completed_chars, total_chars, current_segment)

def complete_tts_operation(operation_id: str, success: bool = True, final_metrics: Optional[Dict[str, Any]] = None):
    """Complete a TTS operation."""
    handler = get_status_handler()
    if final_metrics:
        for key, value in final_metrics.items():
            handler.add_operation_metric(operation_id, key, value)
    handler.complete_operation(operation_id, success)
