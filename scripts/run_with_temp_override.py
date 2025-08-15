#!/usr/bin/env python3
"""
ONNX Runtime Temp Directory Override Wrapper

This script provides process-level temp directory control by setting up
environment variables and monkey-patching Python's tempfile module 
BEFORE any other imports happen, including ONNX Runtime.

This is the most aggressive approach to ensure ONNX Runtime uses our
local temp directory instead of the system temp directory.
"""

import os
import sys
import tempfile
from pathlib import Path

def setup_aggressive_temp_override():
    """
    Set up aggressive temp directory override at the process level.
    
    This must be called before any ONNX Runtime imports to be effective.
    """
    # Get the project root (assume this script is in scripts/)
    project_root = Path(__file__).parent.parent
    cache_dir = project_root / ".cache"
    local_temp_dir = cache_dir / "coreml_temp"
    
    # Ensure directory exists with proper permissions
    local_temp_dir.mkdir(parents=True, exist_ok=True)
    local_temp_dir.chmod(0o755)
    
    # Clean any existing files
    try:
        for item in local_temp_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                import shutil
                shutil.rmtree(item)
    except Exception:
        pass  # Ignore cleanup errors
    
    local_temp_str = str(local_temp_dir.absolute())
    
    # Set ALL possible environment variables
    temp_vars = [
        'TMPDIR', 'TMP', 'TEMP', 'TEMPDIR',
        'COREML_TEMP_DIR', 'COREML_CACHE_DIR', 
        'ONNXRUNTIME_TEMP_DIR', 'ONNXRUNTIME_TEMP', 'ONNXRUNTIME_CACHE_DIR',
        'ML_TEMP_DIR', 'ML_CACHE_DIR',
        'PYTHONTEMPDIR', 'PYTHON_TEMP'
    ]
    
    for var in temp_vars:
        os.environ[var] = local_temp_str
    
    # Override Python's tempfile module IMMEDIATELY
    tempfile.tempdir = local_temp_str
    
    # Store original functions
    original_gettempdir = tempfile.gettempdir
    original_mkdtemp = tempfile.mkdtemp
    original_mkstemp = tempfile.mkstemp
    original_NamedTemporaryFile = tempfile.NamedTemporaryFile
    
    # Create override functions
    def override_gettempdir():
        return local_temp_str
        
    def override_mkdtemp(*args, **kwargs):
        kwargs['dir'] = local_temp_str
        return original_mkdtemp(*args, **kwargs)
        
    def override_mkstemp(*args, **kwargs):
        kwargs['dir'] = local_temp_str
        return original_mkstemp(*args, **kwargs)
    
    def override_NamedTemporaryFile(*args, **kwargs):
        kwargs['dir'] = local_temp_str
        return original_NamedTemporaryFile(*args, **kwargs)
    
    # Apply overrides
    tempfile.gettempdir = override_gettempdir
    tempfile.mkdtemp = override_mkdtemp
    tempfile.mkstemp = override_mkstemp
    tempfile.NamedTemporaryFile = override_NamedTemporaryFile
    
    print(f"✅ Aggressive temp override applied: {local_temp_str}")
    print(f"🔧 Overrode {len(temp_vars)} env vars + 4 tempfile functions")
    
    return local_temp_str

if __name__ == "__main__":
    # Set up temp override FIRST
    temp_dir = setup_aggressive_temp_override()
    
    # Now run the target script
    if len(sys.argv) < 2:
        print("Usage: python run_with_temp_override.py <script_to_run> [args...]")
        sys.exit(1)
    
    script_path = sys.argv[1]
    script_args = sys.argv[2:]
    
    # Change to project root
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    print(f"🚀 Running {script_path} with temp override...")
    
    # Import and run the target script
    sys.argv = [script_path] + script_args
    with open(script_path) as f:
        exec(f.read(), {"__name__": "__main__", "__file__": script_path})
