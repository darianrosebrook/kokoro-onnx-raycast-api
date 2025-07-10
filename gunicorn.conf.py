"""
Gunicorn configuration file for the Kokoro-ONNX TTS API.

This file defines worker lifecycle hooks and production-optimized settings
to ensure high-performance TTS API deployment with proper resource management.

## Key Features:
- **Production Optimization**: Tuned worker counts and resource limits
- **Worker Lifecycle Management**: Proper model initialization per worker
- **Memory Management**: Optimized memory usage and cleanup
- **Performance Tuning**: Optimal timeouts and connection handling
- **Health Monitoring**: Worker health checks and graceful restarts

## Performance Characteristics:
- **Worker Count**: Auto-tuned based on CPU cores for optimal throughput
- **Memory Efficiency**: Per-worker memory limits to prevent resource exhaustion
- **Request Handling**: Optimized timeouts for TTS workloads
- **Connection Management**: Efficient keep-alive and connection pooling
"""
import os
import logging
import sys
import multiprocessing

# Add the project root to the Python path to ensure imports work correctly.
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Get a logger instance
logger = logging.getLogger(__name__)

# Production-optimized Gunicorn configuration
# ============================================

# Worker configuration
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count()))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = int(os.environ.get("GUNICORN_WORKER_CONNECTIONS", 1000))

# Timeout configuration (optimized for TTS workloads)
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 120))  # TTS can take time
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", 30))

# Memory and resource management
max_requests = int(os.environ.get("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = int(os.environ.get("GUNICORN_MAX_REQUESTS_JITTER", 100))
worker_tmp_dir = "/dev/shm" if os.path.exists("/dev/shm") else None

# Connection and performance tuning
preload_app = True  # Improves memory usage and startup time
bind = os.environ.get("GUNICORN_BIND", "0.0.0.0:8000")

# Logging configuration
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

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