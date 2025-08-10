from __future__ import annotations

import os
import logging
import onnxruntime as ort
from typing import Dict, Any, Optional

from api.config import TTSConfig
# Use late import to avoid circular dependencies
def _lazy_get_dynamic_memory_manager():
    try:
        from api.model.loader import get_dynamic_memory_manager  # type: ignore
        return get_dynamic_memory_manager()
    except Exception:
        return None

logger = logging.getLogger(__name__)

_session_options_cache: Optional[ort.SessionOptions] = None
_provider_options_cache: Dict[str, Dict[str, Any]] = {}


def setup_coreml_temp_directory() -> str:
    local_temp_dir = os.path.join(os.getcwd(), ".cache", "coreml_temp")
    os.makedirs(local_temp_dir, exist_ok=True)
    os.chmod(local_temp_dir, 0o755)
    os.environ['TMPDIR'] = local_temp_dir
    os.environ['TMP'] = local_temp_dir
    os.environ['TEMP'] = local_temp_dir
    os.environ['COREML_TEMP_DIR'] = local_temp_dir
    os.environ['ONNXRUNTIME_TEMP_DIR'] = local_temp_dir
    return local_temp_dir


def cleanup_coreml_temp_directory() -> None:
    try:
        local_temp_dir = os.path.join(os.getcwd(), ".cache", "coreml_temp")
        if os.path.exists(local_temp_dir):
            import glob
            import time
            current_time = time.time()
            for file_path in glob.glob(os.path.join(local_temp_dir, "*")):
                try:
                    if os.path.isfile(file_path):
                        file_age = current_time - os.path.getmtime(file_path)
                        if file_age > 3600:
                            os.remove(file_path)
                except Exception:
                    pass
    except Exception:
        pass


def create_optimized_session_options(capabilities: Dict[str, Any]) -> ort.SessionOptions:
    global _session_options_cache
    if _session_options_cache is not None:
        return _session_options_cache

    session_options = ort.SessionOptions()

    local_temp_dir = os.path.join(os.getcwd(), ".cache", "coreml_temp")
    if os.path.exists(local_temp_dir):
        session_options.add_session_config_entry("session.use_env_allocators", "1")
        session_options.add_session_config_entry("session.temp_dir_path", local_temp_dir)

    # BASIC optimizations are best-balanced for TTS
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    session_options.use_deterministic_compute = False

    if capabilities.get('is_apple_silicon', False):
        ne = capabilities.get('neural_engine_cores', 0)
        if ne >= 32:
            session_options.intra_op_num_threads = 8
            session_options.inter_op_num_threads = 4
        elif ne >= 16:
            session_options.intra_op_num_threads = 6
            session_options.inter_op_num_threads = 2
        else:
            session_options.intra_op_num_threads = 4
            session_options.inter_op_num_threads = 2
    else:
        session_options.intra_op_num_threads = 2
        session_options.inter_op_num_threads = 1

    # Dynamic memory arena sizing
    dynamic_memory_manager = _lazy_get_dynamic_memory_manager()
    if dynamic_memory_manager is not None:
        try:
            optimal_mb = dynamic_memory_manager.calculate_optimal_arena_size()
            session_options.add_session_config_entry("arena_extend_strategy", "kSameAsRequested")
            session_options.add_session_config_entry("session.dynamic_arena_initial", str(optimal_mb))
        except Exception:
            pass

    _session_options_cache = session_options
    return session_options


def get_cached_provider_options(provider_name: str, capabilities: Dict[str, Any]) -> Dict[str, Any]:
    if provider_name in _provider_options_cache:
        return _provider_options_cache[provider_name]

    if provider_name == "CoreMLExecutionProvider":
        if capabilities.get('neural_engine_cores', 0) >= 32:
            provider_options = {
                "MLComputeUnits": "CPUAndNeuralEngine",
                "ModelFormat": "MLProgram",
                "AllowLowPrecisionAccumulationOnGPU": "1",
            }
        elif capabilities.get('neural_engine_cores', 0) >= 16:
            provider_options = {
                "MLComputeUnits": "CPUAndNeuralEngine",
                "ModelFormat": "MLProgram",
            }
        else:
            provider_options = {
                "MLComputeUnits": "CPUAndGPU",
            }
    elif provider_name == "CPUExecutionProvider":
        provider_options = {
            "intra_op_num_threads": min(4, capabilities.get("cpu_cores", 4)),
            "inter_op_num_threads": 1,
            "arena_extend_strategy": "kSameAsRequested",
            "enable_cpu_mem_arena": "1",
            "enable_mem_pattern": "1",
        }
    else:
        provider_options = {}

    _provider_options_cache[provider_name] = provider_options
    return provider_options


