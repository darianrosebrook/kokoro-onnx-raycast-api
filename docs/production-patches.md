# Production Patches and Safety Guards

This document details the production-ready monkey-patches applied at runtime to ensure the stability and performance of the Kokoro-ONNX TTS API, especially when using CoreML on Apple Silicon.

## Why Patch?

The CoreML Execution Provider for ONNX Runtime can be sensitive. It sometimes emits verbose, non-critical warnings or can become unstable if it competes for Neural Engine resources with other processes. Our patches are designed to be **idempotent** (safe to apply multiple times) and **resilient** (they only apply if needed).

## Core Patches (`api/model/patch.py`)

### 1. Spurious Warning Suppression

-   **Problem**: CoreML may log verbose warnings about missing model metadata that are harmless but create noise in production logs.
-   **Solution**: We patch the `onnxruntime.InferenceSession` to intercept and suppress these specific, known-benign warnings, keeping logs clean.

### 2. CoreML Initialization Fallback

-   **Problem**: If the Apple Neural Engine is under heavy load or contended by another application, attempting to initialize a CoreML session can fail or hang.
-   **Solution**: We wrap the CoreML session provider initialization in a `try...except` block. If initialization fails, it gracefully falls back to the `CPUExecutionProvider`. This ensures the TTS service remains available, even if hardware acceleration is temporarily unavailable.

### Verification

The status of these patches can be checked via the API's `/status` endpoint, which provides a `patch_status` object detailing which patches were applied and whether any errors occurred.

```bash
# Verify patches applied successfully
curl http://localhost:8000/status | jq '.patch_status'
```

This approach ensures maximum performance when available, with a safety net to maintain reliability under all system conditions. 