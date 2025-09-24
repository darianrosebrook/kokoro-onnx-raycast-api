"""
Startup Profiler Utilities

Lightweight helpers for recording startup step durations so that we can
surface concise, high-signal timings in `/status` without verbose logs.

Author: @darianrosebrook
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Dict

_timings: Dict[str, float] = {}


def record_step(name: str, duration_seconds: float) -> None:
    """Record a named startup step duration in seconds."""
    # Keep the last measurement for each step name
    _timings[name] = float(max(0.0, duration_seconds))


def get_timings() -> Dict[str, float]:
    """Return a copy of recorded startup step timings."""
    return dict(_timings)


def reset_timings() -> None:
    """Clear recorded timings (useful between reloads)."""
    _timings.clear()


@contextmanager
def step_timer(name: str):
    """Context manager that measures and records a step's duration."""
    start = time.perf_counter()
    try:
        yield
    finally:
        record_step(name, time.perf_counter() - start)


