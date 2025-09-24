"""
Model state management module.

This module handles global model state tracking and provides
state access functions for the initialization system.
"""

import logging


logger = logging.getLogger(__name__)


def get_active_provider() -> str:
    """
    Get the currently active provider name.
    
    This is a compatibility function that delegates to the sessions module
    where the actual state is managed.
    
    @returns: Active provider name or "unknown" if not available
    """
    try:
        from api.model.sessions import get_active_provider as _get_active_provider
        return _get_active_provider()
    except Exception as e:
        logger.debug(f"Error getting active provider: {e}")
        return "unknown"

