# Logging Deduplication Plan

> **Status:** In Progress

## Goal
To reduce log verbosity and eliminate duplicate messages during application startup, making the logs cleaner and easier to read, especially in production environments.

---
## Problems Identified
1.  **Duplicate Session Initialization:** Multiple, redundant messages for "Initializing dual session manager" and "✅ Dual session manager initialized".
2.  **Verbose Session Creation:** Redundant messages for "Creating optimized ONNX Runtime session options..."
3.  **Repetitive Hardware Detection:** Apple Silicon hardware detection and thread configurations are logged multiple times.
4.  **CoreML Warning Spam:** The "Context leak detected, msgtracer returned -1" warning floods the logs despite a warning management system being in place.
5.  **Redundant Provider Fallback:** The same `EP Error` for `PhonemeBasedPadding` is logged twice.

---
## Implementation and Refactor plan
### 1. Consolidate Session Initialization Logging
- [ ] Modify `api/model/loader.py` to consolidate session initialization messages.
- [ ] Create a single, comprehensive log message that summarizes all initialized sessions (e.g., ANE, GPU, CPU).
- [ ] Move detailed, individual session success messages to `DEBUG` level.

### 2. Cache Hardware Detection Logging
- [ ] Implement a caching mechanism or a flag in `api/model/loader.py` to ensure hardware capabilities are detected and logged only once.
- [ ] Refactor the hardware detection logic to check the flag before logging.

### 3. Improve Warning Suppression
- [ ] Investigate why "Context leak detected" messages are bypassing the existing suppression in `api/warnings.py`.
- [ ] Strengthen the pattern matching in `StderrInterceptor` to more effectively catch and suppress these warnings.
- [ ] Ensure that the performance tracking for these warnings is not compromised.

### 4. Reduce Provider Fallback Verbosity
- [ ] In `api/model/loader.py`, modify the error handling for `EP Error` to prevent logging the same fallback event multiple times.
- [ ] Consolidate the fallback messages to a single, clear log entry.

---
## Code References
- **Model Loader:** `api/model/loader.py` (for session initialization and hardware detection)
- **Warning Handler:** `api/warnings.py` (for CoreML context leak suppression) 