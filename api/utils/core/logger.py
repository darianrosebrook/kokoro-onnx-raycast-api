# Logging utility.

import logging

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the given name."""
    return logging.getLogger(name)

logger = logging.getLogger(__name__)

