#!/usr/bin/env python3
"""
Kokoro TTS – Comprehensive Benchmark Harness

Measures:
  • TTFA (time to first audio byte) on streaming
  • Stream cadence/jitter and underrun risk (max inter-chunk gap, gap>threshold counts)
  • RTF (processing_time / audio_duration) on non-streaming or streamed-to-file
  • Memory/CPU envelopes over time (psutil)
  • LUFS/dBTP audio quality gates (optional: pyloudnorm + soundfile)
  • Soak drift (latency and RSS over many iterations)
Artifacts:
  • JSON summary, per-trial JSON, per-trial audio files, per-trial chunk traces (CSV)
Inputs:
  • expected_bands.json / baselines.json (optional; if missing, gates are disabled)
Endpoint:
  • OpenAI-compatible /v1/audio/speech (JSON body). Supports payload/header overrides.

Author: @darianrosebrook (edited)
Date: 2025-08-16
Version: 2.0.0
"""

import argparse
import asyncio
import aiohttp
import json
import logging
import os
import sys
import time
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# project root on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Optional deps
try:
    import psutil
    HAVE_PSUTIL = True
except Exception:
    HAVE_PSUTIL = False

try:
    import soundfile as sf  # reads wav/flac/ogg reliably
    HAVE_SF = True
except Exception:
    HAVE_SF = False

try:
    import pyloudnorm as pyln  # LUFS if available
    HAVE_PYLN = True
except Exception:
    HAVE_PYLN = False

import wave
import numpy as np

# ------------------------- Logging -------------------------------------------
def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )

# ------------------------- Config loaders ------------------------------------
def load_json_file(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def load_expected_bands() -> Optional[Dict[str, Any]]:
    return load_json_file(Path("docs/perf/expected_bands.json"))

def load_baselines() -> Optional[Dict[str, Any]]:
    return load_json_file(Path("docs/perf/baselines.json"))

# ------------------------- Audio helpers -------------------------------------
def parse_audio_duration_sec(data: bytes) -> Optional[float]:
    """Return signal duration in seconds if parsable from container, else None."""
    # Try soundfile first (broad container support)
    if HAVE_SF:
        try:
            with sf.SoundFile(io.BytesIO(data)) as f:
                return len(f) / float(f.samplerate)
        except Exception:
            pass
    # Fallback to wave (WAV only)
    try:
        with wave.open(io.BytesIO(data), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return None

def audio_lufs_dbtp(data: bytes) -> Optional[Dict[str, float]]:
    """Compute LUFS integrated and dBTP (true peak approximate) if deps are present."""
    if not (HAVE_SF and HAVE_PYLN):
        return None
    try:
        y, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=False)
        if y.ndim > 1:
            y = np.mean(y, axis=1)
        meter = pyln.Meter(sr)  # EBU R128
        lufs = meter.integrated_loudness(y)
        # dBTP rough: 20*log10(max|oversampled|)
        # simple 4x oversample w/ zero-stuffing + lowpass (very approximate)
        x = y
        for _ in range(2):
            # naive upsample by 2
            z = np.zeros(x.size * 2, dtype=x.dtype)
            z[::2] = x
            x = z  # skip lowpass for speed; overestimates slightly
        peak = np.max(np.abs(x)) + 1e-12
        dbtp = 20.0 * np.log10(peak)
        return {"lufs": float(lufs), "dbtp": float(dbtp)}
    except Exception:
        return None

# ------------------------- HTTP helpers --------------------------------------
class TTSClient:
    def __init__(self, url: str, headers: Dict[str, str], request_base: Dict[str, Any], timeout: int):
        self.url = url
        self.headers = headers
        self.request_base = request_base
        self.timeout = timeout

    async def synthesize_stream(self, session: aiohttp.ClientSession, text: str) -> Dict[str, Any]:
        """
        Streaming: return TTFA, chunk trace, full_bytes (if reconstructed), and status.
        We measure TTFA as time to first byte (server bytes observed).
        """
        payload = dict(self.request_base)
        payload.update({"text": text, "stream": True})
        t0 = time.perf_counter()
        chunks: List[Tuple[float, int]] = []  # (arrival_time_since_start, len)
        buf = io.BytesIO()
        ttfa_ms: Optional[float] = None
        try:
            async with session.post(self.url, json=payload, headers=self.headers, timeout=self.timeout) as resp:
                resp.raise_for_status()
                async for chunk in resp.content.iter_chunked(8192):
                    now = time.perf_counter()
                    if chunk and ttfa_ms is None:
                        ttfa_ms = (now - t0) * 1000.0
                    if chunk:
                        buf.write(chunk)
                        chunks.append(((now - t0) * 1000.0, len(chunk)))
        except Exception as e:
            return {"ok": False, "error": str(e), "ttfa_ms": ttfa_ms, "chunks": chunks, "audio_bytes": b""}
        return {"ok": True, "error": None, "ttfa_ms": ttfa_ms, "chunks": chunks, "audio_bytes": buf.getvalue()}

    async def synthesize_nonstream(self, session: aiohttp.ClientSession, text: str) -> Dict[str, Any]:
        """Non-streaming: return total_time_ms and audio bytes."""
        payload = dict(self.request_base)
        payload.update({"text": text, "stream": False})
        t0 = time.perf_counter()
        try:
            async with session.post(self.url, json=payload, headers=self.headers, timeout=self.timeout) as resp:
                resp.raise_for_status()
                data = await resp.read()
                t_total_ms = (time.perf_counter() - t0) * 1000.0
                return {"ok": True, "error": None, "total_ms": t_total_ms, "audio_bytes": data}
        except Exception as e:
            return {"ok": False, "error": str(e), "total_ms": None, "audio_bytes": b""}

# ------------------------- Metrics & gates -----------------------------------
def percentile(vals: List[float], p: float) -> float:
    if not vals:
        return float("nan")
    arr = np.array(sorted(vals), dtype=float)
    idx = int(np.clip(np.ceil(p * len(arr)) - 1, 0, len(arr) - 1))
    return float(arr[idx])

def stream_cadence_stats(chunks: List[Tuple[float, int]]) -> Dict[str, Any]:
    # chunks: [(ms_since_start, size_bytes), ...]
    if len(chunks) < 2:
        return {"num_chunks": len(chunks), "max_gap_ms": None, "median_gap_ms": None, "underrun_suspected": False}
    times = [t for (t, _) in chunks]
    gaps = [t2 - t1 for t1, t2 in zip(times[:-1], times[1:])]
    med = float(np.median(gaps))
    mx = float(np.max(gaps))
    # Heuristic underrun: any gap > 2.0 * median gap (configurable)
    underrun = any(g > 2.0 * med and g > 30.0 for g in gaps)  # also ensure >30ms to avoid trivial med~0
    return {
        "num_chunks": len(chunks),
        "median_gap_ms": med,
        "p95_gap_ms": percentile(gaps, 0.95),
        "max_gap_ms": mx,
        "underrun_suspected": bool(underrun),
    }

def compute_rtf(total_ms: float, audio_sec: Optional[float], fallback_chars: int = 0) -> Optional[float]:
    if audio_sec is None:
        # heuristic fallback ~50ms per char (configurable)
        if fallback_chars <= 0:
            return None
        audio_sec = 0.05 * fallback_chars
    return (total_ms / 1000.0) / max(audio_sec, 1e-6)

# ------------------------- Benchmark runner ----------------------------------
class BenchmarkRunner:
    def __init__(
        self,
        url: str,
        headers: Dict[str, str],
        base_payload: Dict[str, Any],
        trials: int,
        stream: bool,
        preset: str,
        timeout: int,
        save_audio: bool,
        verbose: bool,
        providers: Optional[List[str]] = None,
        expected_bands: Optional[Dict[str, Any]] = None,
        baselines: Optional[Dict[str, Any]] = None,
        profile_interval_s: float = 0.5,
        concurrency: int = 1,
        soak_iterations: int = 0,
    ):
        self.url = url
        self.headers = headers
        self.base_payload = base_payload
        self.trials = max(trials, 3)
        self.stream = stream
        self.preset = preset
        self.timeout = timeout
        self.save_audio = save_audio
        self.verbose = verbose
        self.providers = providers or []
        self.expected_bands = expected_bands
        self.baselines = baselines
        self.profile_interval_s = max(0.25, profile_interval_s)
        self.concurrency = max(1, concurrency)
        self.soak_iterations = max(0, soak_iterations)

        self.logger = logging.getLogger("bench")
        timestamp = datetime.now().strftime("%Y-%m-%d")
        self.artifacts_dir = Path(f"artifacts/bench/{timestamp}")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

        self.test_texts = {
            "short": "This is a short test sentence for TTFA and streaming cadence.",
            "medium": "This is a medium length paragraph used to benchmark real-time factor and end-to-end latency across providers and modes in a reproducible way.",
            "long": (
                "This is a long paragraph intended to exercise sustained synthesis performance, "
                "including punctuation, numerals such as 123 and 456, abbreviations like Dr. and St., "
                "and varied phonetic content. It should be long enough to measure RTF reliably."
            ),
        }

    async def _monitor_process(self, pid: int, samples: List[Dict[str, Any]], stop_evt: asyncio.Event):
        if not HAVE_PSUTIL:
            return
        p = psutil.Process(pid)
        # Prime CPU percent
        try:
            p.cpu_percent(interval=None)
        except Exception:
            pass
        while not stop_evt.is_set():
            try:
                rss = p.memory_info().rss / (1024 ** 2)
                cpu = p.cpu_percent(interval=None)  # percentage since last call
                samples.append({"t": time.time(), "rss_mb": rss, "cpu_pct": cpu})
            except Exception:
                break
            await asyncio.sleep(self.profile_interval_s)

    def _gate(self, key: str, value: float) -> Tuple[bool, Optional[float]]:
        """
        Compare 'value' to expected_bands threshold if present.
        Returns (passes, threshold_or_None).
        """
        if not self.expected_bands:
            return (True, None)
        gates = self.expected_bands.get("performance_gates", {})
        # Map common keys
        if key == "ttfa_p95_ms":
            thr = gates.get("ttfa", {}).get("threshold_p95_ms")
            return ((value <= thr) if thr is not None else True, thr)
        if key == "rtf_long_p95":
            thr = gates.get("rtf", {}).get("long_paragraph_threshold_p95")
            return ((value <= thr) if thr is not None else True, thr)
        if key == "rss_range_mb":
            thr = gates.get("memory", {}).get("rss_envelope_mb")
            return ((value <= thr) if thr is not None else True, thr)
        if key == "lufs_target":
            # expect |LUFS - target| <= tolerance
            aq = gates.get("audio_quality", {})
            tol = aq.get("lufs_tolerance")
            tgt = aq.get("lufs_target")
            if tgt is None or tol is None:
                return (True, None)
            return (abs(value - tgt) <= tol, tgt)
        if key == "dbtp_ceiling":
            aq = gates.get("audio_quality", {})
            ceil = aq.get("dbtp_ceiling")
            return ((value <= ceil) if ceil is not None else True, ceil)
        return (True, None)

    def _artifact_path(self, stem: str, ext: str) -> Path:
        ts = datetime.now().strftime("%H%M%S")
        return self.artifacts_dir / f"{stem}_{ts}.{ext}"

    async def run(self) -> Dict[str, Any]:
        """
        Run configured benchmarks:
          • TTFA + cadence if streaming
          • RTF if non-streaming (or computed from streamed full bytes)
          • Memory/CPU sampling
          • Soak (optional)
        """
        text = self.test_texts[self.preset]
        client = TTSClient(self.url, self.headers, self.base_payload, self.timeout)

        pid = os.getpid()
        mem_samples: List[Dict[str, Any]] = []
        stop_evt = asyncio.Event()
        mon_task = asyncio.create_task(self._monitor_process(pid, mem_samples, stop_evt))

        async with aiohttp.ClientSession() as session:
            # Single pass (TTFA/RTF)
            ttfa_list: List[float] = []
            rtf_list: List[float] = []
            cadence_list: List[Dict[str, Any]] = []
            lufs_list: List[float] = []
            dbtp_list: List[float] = []
            trial_artifacts: List[Dict[str, Any]] = []

            async def run_one(trial_idx: int):
                nonlocal client, session, text
                trial_prefix = f"trial{trial_idx:02d}_{self.preset}"
                self.logger.info(f"Trial {trial_idx+1}/{self.trials} ({'stream' if self.stream else 'non-stream'})")

                if self.stream:
                    res = await client.synthesize_stream(session, text)
                    if not res["ok"]:
                        self.logger.warning(f"Stream trial failed: {res['error']}")
                        return

                    ttfa = res["ttfa_ms"] or float("inf")
                    ttfa_list.append(ttfa)

                    # cadence stats
                    cadence = stream_cadence_stats(res["chunks"])
                    cadence_list.append(cadence)

                    # Persist chunk trace
                    if res["chunks"]:
                        trace_path = self._artifact_path(trial_prefix + "_chunks", "csv")
                        with open(trace_path, "w") as f:
                            f.write("ms_since_start,bytes\n")
                            for (t_ms, n) in res["chunks"]:
                                f.write(f"{t_ms:.3f},{n}\n")

                    audio_bytes = res["audio_bytes"]
                    dur = parse_audio_duration_sec(audio_bytes)
                    # non-stream RTF is cleaner, but compute if containerized stream is provided
                    if dur is not None:
                        total_ms = (res["chunks"][-1][0]) if res["chunks"] else None
                        if total_ms is not None:
                            rtf = compute_rtf(total_ms, dur)
                            if rtf is not None:
                                rtf_list.append(rtf)

                    if self.save_audio and audio_bytes:
                        wav_path = self._artifact_path(trial_prefix, "wav")
                        with open(wav_path, "wb") as f:
                            f.write(audio_bytes)

                    if audio_bytes:
                        aq = audio_lufs_dbtp(audio_bytes)
                        if aq:
                            lufs_list.append(aq["lufs"])
                            dbtp_list.append(aq["dbtp"])

                    trial_artifacts.append({
                        "ttfa_ms": ttfa,
                        "cadence": cadence,
                        "audio_duration_s": dur,
                    })

                else:
                    res = await client.synthesize_nonstream(session, text)
                    if not res["ok"]:
                        self.logger.warning(f"Non-stream trial failed: {res['error']}")
                        return
                    total_ms = res["total_ms"] or float("inf")
                    audio_bytes = res["audio_bytes"]
                    dur = parse_audio_duration_sec(audio_bytes)
                    rtf = compute_rtf(total_ms, dur, fallback_chars=len(text))
                    if rtf is not None:
                        rtf_list.append(rtf)

                    if self.save_audio and audio_bytes:
                        wav_path = self._artifact_path(trial_prefix, "wav")
                        with open(wav_path, "wb") as f:
                            f.write(audio_bytes)

                    aq = audio_lufs_dbtp(audio_bytes) if audio_bytes else None
                    if aq:
                        lufs_list.append(aq["lufs"])
                        dbtp_list.append(aq["dbtp"])

                    trial_artifacts.append({
                        "total_ms": total_ms,
                        "audio_duration_s": dur,
                        "rtf": rtf,
                    })

            # Run N trials
            for i in range(self.trials):
                await run_one(i)

            # Optional soak (concurrency supported)
            soak_metrics: List[Dict[str, Any]] = []
            async def soak_once(iter_idx: int):
                # For soak, use streaming to stress cadence, else non-stream latency
                if self.stream:
                    res = await client.synthesize_stream(session, text)
                    if res["ok"]:
                        cadence = stream_cadence_stats(res["chunks"])
                        return {"ttfa_ms": res["ttfa_ms"], "max_gap_ms": cadence.get("max_gap_ms")}
                    return {"error": res["error"]}
                else:
                    res = await client.synthesize_nonstream(session, text)
                    if res["ok"]:
                        return {"total_ms": res["total_ms"]}
                    return {"error": res["error"]}

            if self.soak_iterations > 0:
                self.logger.info(f"Starting soak: {self.soak_iterations} iterations, concurrency={self.concurrency}")
                try:
                    for batch_start in range(0, self.soak_iterations, self.concurrency):
                        # Progress log every batch; denser every ~25 batches
                        if batch_start % max(1, 25 * self.concurrency) == 0:
                            self.logger.info(f"Soak progress: {batch_start}/{self.soak_iterations}")

                        batch = [
                            asyncio.create_task(soak_once(iter_idx))
                            for iter_idx in range(batch_start, min(batch_start + self.concurrency, self.soak_iterations))
                        ]
                        done = await asyncio.gather(*batch, return_exceptions=False)
                        soak_metrics.extend(done)
                except KeyboardInterrupt:
                    self.logger.warning("Soak interrupted by user; saving partial results so far…")
                except asyncio.CancelledError:
                    self.logger.warning("Soak task cancelled; saving partial results so far…")

            # Stop monitor
            stop_evt.set()
            await mon_task

        # Summarize
        def summarize(vals: List[float]) -> Dict[str, float]:
            if not vals:
                return {}
            return {
                "count": len(vals),
                "mean": float(np.mean(vals)),
                "p50": percentile(vals, 0.50),
                "p95": percentile(vals, 0.95),
                "min": float(np.min(vals)),
                "max": float(np.max(vals)),
            }

        mem_summary = {}
        if mem_samples:
            rss_vals = [s["rss_mb"] for s in mem_samples]
            mem_summary = {
                "rss_min_mb": float(np.min(rss_vals)),
                "rss_max_mb": float(np.max(rss_vals)),
                "rss_range_mb": float(np.max(rss_vals) - np.min(rss_vals)),
            }

        ttfa_summary = summarize(ttfa_list) if self.stream else {}
        rtf_summary = summarize(rtf_list)
        max_gap_ms = None
        p95_gap_ms = None
        if cadence_list:
            g = [c["max_gap_ms"] for c in cadence_list if c.get("max_gap_ms") is not None]
            p = [c["p95_gap_ms"] for c in cadence_list if c.get("p95_gap_ms") is not None]
            max_gap_ms = float(np.max(g)) if g else None
            p95_gap_ms = float(np.max(p)) if p else None

        lufs_summary = summarize(lufs_list) if lufs_list else {}
        dbtp_summary = summarize(dbtp_list) if dbtp_list else {}

        results: Dict[str, Any] = {
            "config": {
                "url": self.url,
                "headers": self.headers,
                "base_payload": self.base_payload,
                "trials": self.trials,
                "stream": self.stream,
                "preset": self.preset,
                "timeout_s": self.timeout,
                "concurrency": self.concurrency,
                "soak_iterations": self.soak_iterations,
            },
            "measurements": {
                "ttfa_ms": ttfa_list,
                "rtf": rtf_list,
                "lufs": lufs_list,
                "dbtp": dbtp_list,
                "mem_samples": mem_samples,  # raw
                "trial_artifacts": trial_artifacts,
                "cadence": cadence_list,
                "soak_metrics": soak_metrics if self.soak_iterations > 0 else [],
            },
            "summary": {
                "ttfa": ttfa_summary,
                "rtf": rtf_summary,
                "lufs": lufs_summary,
                "dbtp": dbtp_summary,
                "mem": mem_summary,
                "stream_max_gap_ms": max_gap_ms,
                "stream_p95_gap_ms": p95_gap_ms,
            },
            "gates": {},
        }

        # Gate checks
        if self.expected_bands:
            if self.stream and "p95" in ttfa_summary:
                passes, thr = self._gate("ttfa_p95_ms", ttfa_summary["p95"])
                results["gates"]["ttfa_p95_ms"] = {"value": ttfa_summary["p95"], "threshold": thr, "pass": passes}
            if "p95" in rtf_summary and self.preset == "long":
                passes, thr = self._gate("rtf_long_p95", rtf_summary["p95"])
                results["gates"]["rtf_long_p95"] = {"value": rtf_summary["p95"], "threshold": thr, "pass": passes}
            if mem_summary:
                passes, thr = self._gate("rss_range_mb", mem_summary["rss_range_mb"])
                results["gates"]["rss_range_mb"] = {"value": mem_summary["rss_range_mb"], "threshold": thr, "pass": passes}
            if lufs_summary and "mean" in lufs_summary:
                passes, tgt = self._gate("lufs_target", lufs_summary["mean"])
                results["gates"]["lufs_target"] = {"value": lufs_summary["mean"], "target": tgt, "pass": passes}
            if dbtp_summary and "max" in dbtp_summary:
                passes, ceil = self._gate("dbtp_ceiling", dbtp_summary["max"])
                results["gates"]["dbtp_ceiling"] = {"value": dbtp_summary["max"], "ceiling": ceil, "pass": passes}

        # Save consolidated JSON
        out_json = self._artifact_path(f"bench_{'stream' if self.stream else 'nonstream'}_{self.preset}", "json")
        out_json.write_text(json.dumps(results, indent=2, default=str))
        self.logger.info(f"✅ Results saved: {out_json}")
        return results

# ------------------------- CLI ------------------------------------------------
def parse_headers(header_list: List[str]) -> Dict[str, str]:
    h = {}
    for item in header_list:
        if ":" in item:
            k, v = item.split(":", 1)
            h[k.strip()] = v.strip()
    return h

def parse_payload_extra(extra: Optional[str]) -> Dict[str, Any]:
    if not extra:
        return {}
    try:
        return json.loads(extra)
    except Exception:
        raise ValueError("--payload-extra must be a JSON object string")

async def main():
    ap = argparse.ArgumentParser(
        description="Kokoro TTS Comprehensive Benchmark",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Stream TTFA + cadence on short preset
  scripts/run_bench.py --preset short --stream --trials 5

  # Non-stream RTF on long preset, save audio artifacts
  scripts/run_bench.py --preset long --trials 3 --save-audio

  # Soak test 100 iterations with concurrency 3
  scripts/run_bench.py --preset medium --stream --soak-iterations 100 --concurrency 3

  # Pass provider hints via payload extras and custom headers
  scripts/run_bench.py --preset short --stream --payload-extra '{"provider":"coreml","device_type":"ALL"}' \\
                       --header 'X-Provider: coreml-ALL'
        """
    )
    ap.add_argument("--url", default="http://localhost:8000/v1/audio/speech", help="TTS endpoint URL")
    ap.add_argument("--voice", default="af_heart", help="Voice id/name")
    ap.add_argument("--lang", default="en-us", help="Language code")
    ap.add_argument("--speed", type=float, default=1.0, help="Playback speed")
    ap.add_argument("--preset", choices=["short", "medium", "long"], default="short")
    ap.add_argument("--stream", action="store_true", help="Test streaming mode")
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--save-audio", action="store_true")
    ap.add_argument("--verbose", action="store_true")

    ap.add_argument("--header", action="append", default=[], help="Extra header 'Key: Value' (repeatable)")
    ap.add_argument("--payload-extra", type=str, default=None, help="JSON string merged into request payload")

    ap.add_argument("--profile-interval", type=float, default=0.5, help="Seconds between RSS/CPU samples")
    ap.add_argument("--concurrency", type=int, default=1, help="Concurrent requests for soak")
    ap.add_argument("--soak-iterations", type=int, default=0, help="Iterations for soak; 0 disables")

    args = ap.parse_args()
    setup_logging(args.verbose)
    log = logging.getLogger("main")

    expected_bands = load_expected_bands()
    if expected_bands is None:
        log.warning("expected_bands.json not found; gate checks disabled.")
    baselines = load_baselines()
    if baselines is None:
        log.warning("baselines.json not found; baseline references disabled.")

    headers = parse_headers(args.header)
    payload_extra = parse_payload_extra(args.payload_extra)

    base_payload = {
        "voice": args.voice,
        "speed": args.speed,
        "lang": args.lang,
        # align with OpenAI-compatible schema
        # add format if your server expects {"format":"wav"}
        "format": "wav",
    }
    base_payload.update(payload_extra)

    runner = BenchmarkRunner(
        url=args.url,
        headers=headers,
        base_payload=base_payload,
        trials=args.trials,
        stream=args.stream,
        preset=args.preset,
        timeout=args.timeout,
        save_audio=args.save_audio,
        verbose=args.verbose,
        providers=None,
        expected_bands=expected_bands,
        baselines=baselines,
        profile_interval_s=args.profile_interval,
        concurrency=args.concurrency,
        soak_iterations=args.soak_iterations,
    )

    try:
        results = await runner.run()
        # Pretty summary
        log.info("=" * 64)
        log.info("📊 BENCHMARK SUMMARY")
        log.info("=" * 64)
        s = results["summary"]
        if args.stream and s.get("ttfa"):
            ttfa = s["ttfa"]
            log.info(f"TTFA p95: {ttfa.get('p95', float('nan')):.1f} ms")
        if s.get("rtf"):
            rtf = s["rtf"]
            log.info(f"RTF p95:  {rtf.get('p95', float('nan')):.3f}")
        if s.get("mem"):
            log.info(f"RSS range: {s['mem'].get('rss_range_mb', float('nan')):.1f} MB")
        if s.get("stream_max_gap_ms") is not None:
            log.info(f"Stream gaps: max={s['stream_max_gap_ms']:.1f} ms, p95={s.get('stream_p95_gap_ms', float('nan')):.1f} ms")
        if s.get("lufs"):
            log.info(f"LUFS mean: {s['lufs'].get('mean', float('nan')):.2f} (dBTP max: {s.get('dbtp',{}).get('max', float('nan')):.2f})")
        gates = results.get("gates", {})
        if gates:
            log.info("-" * 64)
            for k, v in gates.items():
                status = "PASS" if v.get("pass", True) else "FAIL"
                th = v.get("threshold") or v.get("target") or v.get("ceiling")
                log.info(f"{k}: {v['value']:.3f} vs {th}  [{status}]")
        log.info("=" * 64)
        return 0
    except Exception as e:
        log.error(f"❌ Benchmark failed: {e}", exc_info=args.verbose)
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
