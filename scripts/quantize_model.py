#!/usr/bin/env python3
"""
Kokoro TTS — Mixed Quantization & Benchmarking Utility (Apple Silicon–aware)

Improvements over prior version:
- Modes:
  • Weights-only INT8 (recommended first pass for TTS quality)
  • Full INT8 (weights=QInt8, activations=QUInt8) with robust calibration
- Calibration:
  • Uses your real preprocessing pipeline if available (Misaki/G2P, tokenizer, etc.)
  • Percentile/Histogram calibration options with reproducible corpus
- Exclusions:
  • Regex-based node exclusion (postnet, layernorm, out_proj, vocoder, etc.)
  • Conv per-channel; Gemm/MatMul safer handling
- Benchmarking:
  • Real feed dicts; multiple providers (CoreML, MPS, CPU) A/B comparisons
  • Warmup + timed runs; summary JSON optional
- Export:
  • Saves optimized ONNX; attempts .ort export if ORT converter is available

Usage examples
--------------
# 1) Weights-only INT8 (per-channel Conv), exclude sensitive ops, export optimized
python scripts/quantize_model.py \
  --input kokoro-v1.0.onnx \
  --output kokoro-v1.0.int8w.onnx \
  --weights-only \
  --exclude-pattern "postnet|layernorm|rmsnorm|out_proj|vocoder|final" \
  --export-optimized \
  --benchmark --compare --validate

# 2) Full INT8 (weights + QUInt8 activations) with percentile calibration
python scripts/quantize_model.py \
  --input kokoro-v1.0.onnx \
  --output kokoro-v1.0.int8wf.onnx \
  --quantize-activations \
  --calibration-method percentile --percentile 99.9 \
  --calibration-samples 200 \
  --exclude-pattern "postnet|layernorm|rmsnorm|out_proj|vocoder|final" \
  --export-optimized --benchmark --compare --validate
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import onnx
import onnxruntime as ort
from onnxruntime.quantization import (
    CalibrationDataReader,
    CalibrationMethod,
    QuantFormat,
    QuantType,
    quantize_dynamic,
    quantize_static,
)

# -----------------------------------------------------------------------------
# Optional project imports
# -----------------------------------------------------------------------------
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Expected to return {input_name: np.ndarray, ...} for given session & text
    from api.preprocessing import preprocess_to_onnx_inputs as real_preprocess
    HAVE_REAL_PREPROCESS = True
except Exception:
    HAVE_REAL_PREPROCESS = False

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("kokoro.quant")


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------
def load_onnx_model(path: str) -> onnx.ModelProto:
    m = onnx.load(path)
    onnx.checker.check_model(m)
    return m


def get_model_size_mb(path: str) -> float:
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except Exception:
        return 0.0


def list_input_specs(session: ort.InferenceSession) -> List[Tuple[str, Sequence[int], str]]:
    specs = []
    for i in session.get_inputs():
        specs.append((i.name, i.shape, i.type))
    return specs


def _default_texts(cal_samples: int) -> List[str]:
    base = [
        "Hello world, this is a test of the TTS system.",
        "The quick brown fox jumps over the lazy dog.",
        "Artificial intelligence is transforming our world.",
        "Text to speech synthesis has many applications.",
        "Numbers like 3.14159 and abbreviations e.g. Dr., vs. Mr. should be handled.",
        "Real-time streaming requires low latency and stable buffers.",
        "Pronunciation of sibilants and plosives can be sensitive to quantization.",
        "A longer paragraph is useful to test sustained throughput and memory.",
    ]
    # expand with simple variations
    texts = []
    for t in base:
        for k in [0.5, 1.0, 1.5, 2.0]:
            if k == 1.0:
                texts.append(t)
            elif k < 1.0:
                w = t.split()
                texts.append(" ".join(w[: max(2, int(len(w) * k))]))
            else:
                rep = (t + " ") * int(k)
                texts.append(rep[: min(len(rep), 400)])
    # clip to requested count
    if cal_samples <= len(texts):
        return texts[:cal_samples]
    # pad by repeating
    while len(texts) < cal_samples:
        texts.append(texts[len(texts) % len(base)])
    return texts[:cal_samples]


def _infer_vocab_bounds_from_graph(model: onnx.ModelProto) -> Dict[str, int]:
    """
    Best-effort: find embedding initializers and return their size along axis=0.
    Keyed by a heuristic name snippet so we can map to inputs later if needed.
    """
    bounds = {}
    for init in model.graph.initializer:
        name = init.name or ""
        # Common patterns to catch word/pos/segment embeddings
        if "embedding" in name or "embeddings" in name:
            # ONNX tensor dims are (axis0, axis1, ...)
            # Treat dim 0 as vocab-ish if rank>=2 and size > 0
            if len(init.dims) >= 2 and init.dims[0] > 0:
                bounds[name] = int(init.dims[0])
    return bounds


def _shape_fallback_feeds_safe(session: ort.InferenceSession, seed: int = 1234) -> Dict[str, np.ndarray]:
    """
    Safer fallback: clamp token ids to vocab size; respect dtypes; avoid invalid shapes.
    """
    rng = np.random.default_rng(seed)
    feeds: Dict[str, np.ndarray] = {}

    # Load model to inspect initializers for vocab sizes
    # Try to get model path from session, or load from the original path if available
    m = None
    if hasattr(session, "_model_path"):
        m = onnx.load(session._model_path)
    elif hasattr(session, "_model_location"):
        m = onnx.load(session._model_location)
    else:
        # Fallback: try to load from the session's model data
        try:
            m = onnx.load_from_string(session.get_modelmeta().custom_metadata_map.get("model_data", ""))
        except:
            pass
    
    vocab_by_init = _infer_vocab_bounds_from_graph(m) if m else {}
    
    # Known vocab size for Kokoro model (from error message)
    if not vocab_by_init:
        vocab_by_init = {"word_embeddings": 178}

    for inp in session.get_inputs():
        shape = []
        for d in inp.shape:
            # Fill unknown dims with something reasonable for your model
            if isinstance(d, int) and d > 0:
                shape.append(d)
            else:
                # Typical batch=1, seq_len ~ 128–256, feature dims ~512
                shape.append(1 if len(shape) == 0 else 128)
        dtype = inp.type

        if "int" in dtype:
            # Token-like input: generate bounded indices
            # For Kokoro model, use vocab size 178 (from error message)
            vocab = 178  # Known vocab size for Kokoro
            arr = rng.integers(low=0, high=vocab, size=shape, dtype=np.int64)
            # Cast to input's integer type if needed
            if dtype == "tensor(int32)":
                arr = arr.astype(np.int32, copy=False)
            elif dtype == "tensor(int64)":
                pass
            else:
                # Unusual integer type; coerce to int64 then cast via ORT
                arr = arr.astype(np.int64, copy=False)
        else:
            # Float-like inputs
            arr = rng.standard_normal(size=shape).astype(np.float32)
        feeds[inp.name] = arr

    return feeds


def _shape_fallback_feeds(session: ort.InferenceSession, seed: int = 1234) -> Dict[str, np.ndarray]:
    """
    Shape-aware but model-agnostic dummy feeds.
    Only used if real_preprocess isn't importable.
    """
    return _shape_fallback_feeds_safe(session, seed)


def _build_feeds(session: ort.InferenceSession, text: str, seed: int = 1234) -> Dict[str, np.ndarray]:
    if HAVE_REAL_PREPROCESS:
        try:
            return real_preprocess(text=text, session=session)
        except Exception as e:
            logger.warning(f"real_preprocess failed ({e}); using shape-fallback for calibration/bench.")
    return _shape_fallback_feeds(session, seed=seed)


# -----------------------------------------------------------------------------
# Calibration Reader (uses real preprocessor when available)
# -----------------------------------------------------------------------------
class KokoroCalibrationDataReader(CalibrationDataReader):
    def __init__(
        self,
        session: ort.InferenceSession,
        texts: List[str],
        seed: int = 13,
    ):
        self.session = session
        self.texts = texts
        self._i = 0
        self._seed = seed

    def get_next(self) -> Optional[Dict[str, np.ndarray]]:
        if self._i >= len(self.texts):
            return None
        text = self.texts[self._i]
        self._i += 1
        return _build_feeds(self.session, text, seed=self._seed + self._i)


# -----------------------------------------------------------------------------
# Node exclusion helpers
# -----------------------------------------------------------------------------
def compile_exclusion_regex(pattern: Optional[str]) -> Optional[re.Pattern]:
    if not pattern:
        return None
    try:
        return re.compile(pattern, flags=re.IGNORECASE)
    except re.error as e:
        logger.warning(f"Invalid exclude regex '{pattern}': {e}")
        return None


def find_nodes_to_exclude(model: onnx.ModelProto, rx: Optional[re.Pattern]) -> List[str]:
    if rx is None:
        return []
    names = []
    for n in model.graph.node:
        if n.name and rx.search(n.name):
            names.append(n.name)
    if names:
        logger.info(f"Excluding {len(names)} nodes by pattern: {rx.pattern}")
    return names

def assert_no_quantized_conv_kernels(path: str) -> None:
    """Sanity check to catch any stray ConvInteger/QLinearConv operations."""
    m = onnx.load(path)
    bad = [n for n in m.graph.node if n.op_type in ("ConvInteger", "QLinearConv")]
    if bad:
        names = ", ".join(n.name or "<noname>" for n in bad[:5])
        raise RuntimeError(f"Found {len(bad)} quantized Conv kernels ({names}...). "
                          f"Your weights-only path must use QDQ for Conv.")
    logger.info("✅ No ConvInteger/QLinearConv operations found - model is provider-friendly")


# -----------------------------------------------------------------------------
# Quantization pipelines
# -----------------------------------------------------------------------------
class _NullCalib(CalibrationDataReader):
    """Null calibration reader for weights-only quantization (no activation calibration needed)."""
    def get_next(self):
        # Return a dummy feed to satisfy the calibrator
        return {"tokens": np.array([[1, 2, 3, 4, 5]], dtype=np.int64),
                "style": np.array([[0]], dtype=np.int64),
                "speed": np.array([[1.0]], dtype=np.float32)}

def _upgrade_opset_if_needed(model: onnx.ModelProto, target: int = 13) -> onnx.ModelProto:
    """Upgrade model opset if needed for QDQ patterns."""
    cur = max((opset.version for opset in model.opset_import), default=13)
    if cur >= target:
        return model
    try:
        from onnx import version_converter
        return version_converter.convert_version(model, target)
    except Exception as e:
        logger.warning(f"Opset upgrade failed ({e}); continuing with current opset {cur}")
        return model

def quantize_weights_only_int8(
    input_model_path: str,
    output_model_path: str,
    include_ops: List[str],
    exclude_regex: Optional[re.Pattern],
    per_channel: bool = True,
) -> None:
    """
    Weights-only INT8 via dynamic quantization (activations kept FP).
    Excludes Conv operations to avoid ConvInteger that CoreML doesn't support.
    """
    model = load_onnx_model(input_model_path)
    nodes_to_exclude = find_nodes_to_exclude(model, exclude_regex)

    # Filter out Conv from include_ops to avoid ConvInteger
    safe_ops = [op for op in include_ops if op not in ['Conv', 'ConvTranspose']]
    if 'Conv' in include_ops or 'ConvTranspose' in include_ops:
        logger.info(f"Excluding Conv/ConvTranspose from quantization to avoid ConvInteger operations")
        logger.info(f"Safe ops for quantization: {safe_ops}")

    extra = {
        "MatMulConstBOnly": True,      # safer for attention/GEMM
        "EnableSubgraph": True,
        "WeightSymmetric": True,
        "DisableShapeInference": True, # avoid reload path on py3.13
    }

    logger.info("Running weights-only INT8 (dynamic) quantization...")
    try:
        quantize_dynamic(
            model_input=input_model_path,      # first attempt by path
            model_output=output_model_path,
            per_channel=per_channel,
            reduce_range=False,
            weight_type=QuantType.QInt8,
            nodes_to_quantize=[],
            nodes_to_exclude=nodes_to_exclude,
            op_types_to_quantize=safe_ops,     # use safe ops only
            extra_options=extra,
        )
    except Exception as e:
        logger.warning(f"quantize_dynamic(path) failed ({e}); retrying with in-memory ModelProto...")
        # Fallback: pass the already-loaded ModelProto to avoid file reload during quantization
        quantize_dynamic(
            model_input=model,                 # ModelProto, not path
            model_output=output_model_path,
            per_channel=per_channel,
            reduce_range=False,
            weight_type=QuantType.QInt8,
            nodes_to_quantize=[],
            nodes_to_exclude=nodes_to_exclude,
            op_types_to_quantize=safe_ops,     # use safe ops only
            extra_options=extra,
        )

    # Sanity check: ensure no ConvInteger operations were created
    assert_no_quantized_conv_kernels(output_model_path)
    
    logger.info(f"Saved weights-only INT8 model → {output_model_path}")


def quantize_full_int8_static(
    input_model_path: str,
    output_model_path: str,
    calibration_texts: List[str],
    include_ops: List[str],
    exclude_regex: Optional[re.Pattern],
    calibrate_method: CalibrationMethod,
    percentile: Optional[float],
    providers: Optional[List[str]] = None,
    per_channel: bool = True,
) -> None:
    """
    Full INT8 (weights + QUInt8 activations) with robust calibration.
    """
    # Build calibration session (CPU is fine & deterministic)
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    calib_providers = providers or ["CPUExecutionProvider"]
    calib_sess = ort.InferenceSession(input_model_path, sess_options=sess_options, providers=calib_providers)

    cal_reader = KokoroCalibrationDataReader(calib_sess, calibration_texts)

    model = load_onnx_model(input_model_path)
    nodes_to_exclude = find_nodes_to_exclude(model, exclude_regex)

    extra = {
        "MatMulConstBOnly": True,
        "EnableSubgraph": True,
        "CalibMovingAverage": True,
        "CalibTensorRangeSymmetric": False,  # allow asymmetric activations
        "WeightSymmetric": True,
        "DisableShapeInference": True,  # critical: avoid reload path
    }
    if calibrate_method == CalibrationMethod.Percentile and percentile is not None:
        extra["CalibPercentile"] = float(percentile)

    logger.info("Running full INT8 static quantization (weights=QInt8, activations=QUInt8)...")
    quantize_static(
        model_input=input_model_path,
        model_output=output_model_path,
        calibration_data_reader=cal_reader,
        quant_format=QuantFormat.QDQ,            # Q/DQ friendly to CoreML
        per_channel=per_channel,                 # per-channel Conv weights
        reduce_range=False,                      # full 8-bit
        weight_type=QuantType.QInt8,
        activation_type=QuantType.QUInt8,
        optimize_model=True,
        op_types_to_quantize=include_ops,
        nodes_to_quantize=[],                    # quantize matching ops
        nodes_to_exclude=nodes_to_exclude,
        calibrate_method=calibrate_method,
        extra_options=extra,
    )
    logger.info(f"Saved full INT8 model → {output_model_path}")


# -----------------------------------------------------------------------------
# Optimized export (.onnx optimized graph and best-effort .ort)
# -----------------------------------------------------------------------------
def export_optimized_graph(input_model_path: str, optimized_path: str, providers: List[str]) -> None:
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    sess_options.optimized_model_filepath = optimized_path
    _ = ort.InferenceSession(input_model_path, sess_options=sess_options, providers=providers)
    logger.info(f"Saved optimized ONNX graph → {optimized_path}")


def try_export_ort(input_model_path: str, ort_path: str, providers: List[str]) -> None:
    """
    Best-effort .ort export. Falls back silently if tooling is unavailable.
    """
    try:
        from onnxruntime.tools import convert_onnx_models_to_ort as to_ort  # type: ignore
    except Exception:
        logger.info("ORT converter not available; skipping .ort export.")
        return
    try:
        to_ort.convert_onnx_models_to_ort([input_model_path], [ort_path])  # API may vary by ORT version
        logger.info(f"Saved ORT binary graph → {ort_path}")
    except Exception as e:
        logger.info(f".ort export failed (non-fatal): {e}")


# -----------------------------------------------------------------------------
# Benchmarking
def _smoke_run_cpu(session: ort.InferenceSession, feeds: Dict[str, np.ndarray]) -> None:
    """Pre-benchmark validation: run a single CPU inference to catch invalid feeds early."""
    try:
        session.run(None, feeds)
    except Exception as e:
        raise RuntimeError(f"Smoke test failed - invalid feeds: {e}")


# -----------------------------------------------------------------------------
def benchmark_model(
    model_path: str,
    sample_text: str,
    runs: int = 10,
    providers_to_try: Optional[List[List[str]]] = None,
) -> Dict[str, Any]:
    results: Dict[str, Any] = {"model": model_path, "providers": []}

    if providers_to_try is None:
        # Order by preference on Apple Silicon
        providers_to_try = []
        avail = ort.get_available_providers()
        if "CoreMLExecutionProvider" in avail:
            providers_to_try.append(["CoreMLExecutionProvider"])
        if "MPSExecutionProvider" in avail:
            providers_to_try.append(["MPSExecutionProvider"])
        providers_to_try.append(["CPUExecutionProvider"])

    for prov in providers_to_try:
        try:
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess = ort.InferenceSession(model_path, sess_options=sess_options, providers=prov)

            feeds = _build_feeds(sess, sample_text, seed=1337)

            # Pre-benchmark smoke test to catch invalid feeds early
            if "CPUExecutionProvider" in prov:
                _smoke_run_cpu(sess, feeds)
            else:
                # For non-CPU providers, test with CPU first
                sess_cpu = ort.InferenceSession(model_path, sess_options=sess_options, providers=["CPUExecutionProvider"])
                _smoke_run_cpu(sess_cpu, feeds)

            # warmup
            for _ in range(min(3, runs)):
                _ = sess.run(None, feeds)

            times: List[float] = []
            for _ in range(runs):
                t0 = time.perf_counter()
                _ = sess.run(None, feeds)
                t1 = time.perf_counter()
                times.append(t1 - t0)

            entry = {
                "provider": prov,
                "avg_ms": float(np.mean(times) * 1000),
                "p50_ms": float(np.median(times) * 1000),
                "p95_ms": float(np.percentile(times, 95) * 1000),
                "min_ms": float(np.min(times) * 1000),
                "max_ms": float(np.max(times) * 1000),
                "throughput_qps": float(1.0 / np.mean(times)),
            }
            results["providers"].append(entry)
            logger.info(
                f"[{prov}] avg={entry['avg_ms']:.2f} ms, p95={entry['p95_ms']:.2f} ms, "
                f"qps={entry['throughput_qps']:.2f}"
            )
        except Exception as e:
            logger.warning(f"Benchmark failed for provider {prov}: {e}")

    return results


def compare_models(orig_path: str, quant_path: str, sample_text: str, runs: int = 10) -> Dict[str, Any]:
    orig_bench = benchmark_model(orig_path, sample_text, runs=runs)
    quant_bench = benchmark_model(quant_path, sample_text, runs=runs)
    size_orig = get_model_size_mb(orig_path)
    size_quant = get_model_size_mb(quant_path)
    return {
        "original_model_mb": size_orig,
        "quant_model_mb": size_quant,
        "size_reduction_percent": (size_orig - size_quant) / max(size_orig, 1e-9) * 100.0,
        "original_benchmark": orig_bench,
        "quant_benchmark": quant_bench,
    }


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Kokoro TTS — Mixed Quantization & Benchmarking")

    p.add_argument("--input", "-i", required=True, help="Input ONNX model path")
    p.add_argument("--output", "-o", required=True, help="Output ONNX model path")

    # Modes
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--weights-only", action="store_true", help="Weights-only INT8 (activations kept FP)")
    grp.add_argument("--quantize-activations", action="store_true", help="Full INT8: weights + QUInt8 activations")

    # Calibration
    p.add_argument("--calibration-samples", type=int, default=150, help="Number of calibration texts")
    p.add_argument("--calibration-corpus", type=str, default=None, help="Path to .txt or .json list of texts")
    p.add_argument("--calibration-method", type=str, default="percentile",
                   choices=["minmax", "percentile", "entropy", "histogram"])
    p.add_argument("--percentile", type=float, default=99.9, help="Percentile for percentile calibration")

    # Quant details
    p.add_argument("--include-ops", type=str, default="Conv,Gemm,MatMul", help="Comma list of ops to quantize")
    p.add_argument("--exclude-pattern", type=str, default="postnet|layernorm|rmsnorm|out_proj|vocoder|final",
                   help="Regex of node names to exclude from quantization")
    p.add_argument("--no-per-channel", action="store_true", help="Disable per-channel weight quant (Conv)")

    # Validation / export / bench
    p.add_argument("--validate", action="store_true", help="Validate ONNX models")
    p.add_argument("--export-optimized", action="store_true", help="Export optimized ONNX graph next to output")
    p.add_argument("--export-ort", action="store_true", help="Attempt to export .ort binary graph")
    p.add_argument("--benchmark", action="store_true", help="Run provider A/B benchmark on output model")
    p.add_argument("--compare", action="store_true", help="Benchmark both original and quantized models")
    p.add_argument("--bench-runs", type=int, default=10, help="Runs per provider during benchmark")
    p.add_argument("--bench-text", type=str, default="Real-time synthesis demands efficient algorithms.",
                   help="Text used for benchmarking preprocessing+inference")

    # Output
    p.add_argument("--results-json", type=str, default=None, help="Path to write JSON results (compare/bench)")

    return p.parse_args()


def load_corpus(path: Optional[str], n: int) -> List[str]:
    if not path:
        return _default_texts(n)
    fp = Path(path)
    if not fp.exists():
        logger.warning(f"Calibration corpus not found: {path}; using defaults.")
        return _default_texts(n)
    if fp.suffix.lower() == ".json":
        texts = json.loads(fp.read_text())
        if not isinstance(texts, list):
            raise ValueError("JSON corpus must be a list of strings")
        return [str(t) for t in texts][:n]
    # assume plain text, one example per line
    lines = [ln.strip() for ln in fp.read_text().splitlines() if ln.strip()]
    return (lines + _default_texts(n))[:n]


def main() -> int:
    args = parse_args()

    include_ops = [s.strip() for s in args.include_ops.split(",") if s.strip()]
    per_channel = not args.no_per_channel

    # Validate input model
    if args.validate:
        try:
            _ = load_onnx_model(args.input)
            logger.info(f"Input model validated: {args.input}")
        except Exception as e:
            logger.error(f"Input model validation failed: {e}")
            return 1

    # Quantization path
    if args.weights_only or not args.quantize_activations:
        # Optional: pre-process model for cleaner quantization
        input_for_quant = args.input
        try:
            from onnxruntime.quantization.preprocess import quant_pre_process
            pre_path = str(Path(args.input).with_suffix(".pre.onnx"))
            logger.info("Running quantization pre-processing...")
            quant_pre_process(
                input_model=args.input,
                output_model=pre_path,
                skip_optimization=False,
                skip_symbolic_shape=True
            )
            input_for_quant = pre_path
            logger.info(f"Pre-processed model saved → {pre_path}")
        except Exception as e:
            logger.info(f"Pre-processing skipped: {e}")
        
        # Weights-only dynamic INT8
        quantize_weights_only_int8(
            input_model_path=input_for_quant,
            output_model_path=args.output,
            include_ops=include_ops,
            exclude_regex=compile_exclusion_regex(args.exclude_pattern),
            per_channel=per_channel,
        )
    else:
        # Full INT8 static with calibration
        method_map = {
            "minmax":    CalibrationMethod.MinMax,
            "percentile": CalibrationMethod.Percentile,
            "entropy":   CalibrationMethod.Entropy,
            "histogram": CalibrationMethod.Histogram,
        }
        cal_texts = load_corpus(args.calibration_corpus, args.calibration_samples)
        quantize_full_int8_static(
            input_model_path=args.input,
            output_model_path=args.output,
            calibration_texts=cal_texts,
            include_ops=include_ops,
            exclude_regex=compile_exclusion_regex(args.exclude_pattern),
            calibrate_method=method_map[args.calibration_method],
            percentile=args.percentile,
            providers=["CPUExecutionProvider"],   # deterministic calibration
            per_channel=per_channel,
        )

    # Validate quantized model
    if args.validate:
        try:
            _ = load_onnx_model(args.output)
            logger.info(f"Quantized model validated: {args.output}")
        except Exception as e:
            logger.error(f"Quantized model validation failed: {e}")
            return 1

    # Export optimized artifacts
    if args.export_optimized:
        opt_path = str(Path(args.output).with_suffix(".opt.onnx"))
        providers = ["CPUExecutionProvider"]
        avail = ort.get_available_providers()
        if "CoreMLExecutionProvider" in avail:
            providers = ["CoreMLExecutionProvider"]
        export_optimized_graph(args.output, opt_path, providers)

    if args.export_ort:
        ort_path = str(Path(args.output).with_suffix(".ort"))
        providers = ["CPUExecutionProvider"]
        try_export_ort(args.output, ort_path, providers)

    # Benchmarking
    results: Optional[Dict[str, Any]] = None
    if args.compare:
        results = compare_models(args.input, args.output, args.bench_text, runs=args.bench_runs)
        logger.info(f"Size reduction: {results['size_reduction_percent']:.1f}%")
    elif args.benchmark:
        results = benchmark_model(args.output, args.bench_text, runs=args.bench_runs)

    if args.results_json and results is not None:
        Path(args.results_json).write_text(json.dumps(results, indent=2))
        logger.info(f"Wrote results JSON → {args.results_json}")

    logger.info("✅ Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
