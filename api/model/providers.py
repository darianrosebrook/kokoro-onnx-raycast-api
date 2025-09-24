"""
DEPRECATED: This module has been moved to a package structure.

For backward compatibility, this file re-exports functions from the new
api.model.providers package. Please update imports to use the package directly.

Example:
    # Old
    from api.model.providers import create_optimized_session_options
    
    # New (preferred)
    from api.model.providers import create_optimized_session_options
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "api.model.providers module has been restructured. "
    "Please update imports to use the package structure for better organization.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export all functions from the new package structure for backward compatibility
from .providers import *  # noqa: F403, F401


