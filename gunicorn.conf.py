"""
Gunicorn configuration file for the Kokoro-ONNX TTS API.

This file defines worker lifecycle hooks to ensure that the ONNX model,
especially the fork-unsafe CoreML execution provider, is initialized
correctly in each worker process *after* it has been forked.

## Key Features:
- **`post_fork` Hook**: Initializes the TTS model in each worker process.
- **Environment Variable**: Sets `KOKORO_GUNICORN_WORKER=true` to signal to the
  FastAPI application that it's running in a Gunicorn worker, allowing it to
  skip the default model initialization in the `lifespan` manager.
"""
import os
import logging
import sys

# Add the project root to the Python path to ensure imports work correctly.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Get a logger instance
logger = logging.getLogger(__name__)

def post_fork(server, worker):
    """
    Gunicorn worker lifecycle hook executed after a worker process is forked.

    This is the ideal place to initialize resources that are not fork-safe,
    such as the ONNX Runtime session with the CoreML execution provider.

    Args:
        server: The Gunicorn server instance.
        worker: The worker instance.
    """
    # Set an environment variable to indicate that we are in a Gunicorn worker.
    # The FastAPI app's lifespan event will check for this to avoid initializing the model.
    os.environ["KOKORO_GUNICORN_WORKER"] = "true"
    
    worker.log.info("Gunicorn worker forked (PID: %s)", worker.pid)
    
    try:
        # Import the initializer function here, within the worker process.
        from api.model.loader import initialize_model
        
        worker.log.info("Initializing TTS model in Gunicorn worker...")
        initialize_model()
        worker.log.info("✅ Model initialized successfully in worker.")
        
    except Exception as e:
        worker.log.critical(
            "❌ Failed to initialize model in Gunicorn worker: %s", e, exc_info=True
        )
        # Exit the worker process if model initialization fails.
        # Gunicorn will automatically restart it.
        sys.exit(1) 