# Phoneme Truncation Fix Implementation

> **Status:** Completed and tested
> **Date:** 2025-08-06
> **Author:** @darianrosebrook

## Problem

The TTS system was cutting off text during speech synthesis, specifically truncating the end of longer texts. The issue was identified in the phoneme processing pipeline where the `DEFAULT_MAX_PHONEME_LENGTH` was set to 256, which was insufficient for longer text segments.

From the logs:
```
2025-08-06 20:46:07,107 - INFO - [0] Segment processed in 12.2706s using DualSession-GPU (concurrent:0) [phonemes:260→256 (truncated)]
```

This showed that phonemes were being truncated from 260 to 256, causing the end of the text to be cut off.

## Implementation Changes

### 1. Increased Maximum Phoneme Length

- **File:** `api/tts/text_processing.py`
- **Change:** Increased `DEFAULT_MAX_PHONEME_LENGTH` from 256 to 512
- **Reason:** To accommodate longer text segments without truncation

### 2. Enhanced Truncation Logic

- **File:** `api/tts/text_processing.py`
- **Change:** Improved the smart truncation algorithm in `pad_phoneme_sequence()`
- **Improvements:**
  - Adaptive search range for word boundaries based on max length
  - Better logging of truncation events
  - Extended search range for cleaner word boundary detection

### 3. Updated Misaki Processing

- **File:** `api/tts/misaki_processing.py`
- **Change:** Updated default phoneme length and improved truncation logic
- **Improvements:**
  - Increased default phoneme length from 256 to 512
  - Added word boundary detection for cleaner truncation
  - Enhanced logging for truncation events

### 4. Improved Error Logging

- **File:** `api/tts/core.py`
- **Change:** Added detailed warning logs for truncation events
- **Improvements:**
  - Clear warning when truncation occurs
  - Suggestion to increase `DEFAULT_MAX_PHONEME_LENGTH` if needed

## Testing

A dedicated test script was created to verify the fix:
- **File:** `scripts/test_long_text_tts.py`
- **Purpose:** Verify that the problematic text is processed without truncation
- **Tests:**
  - Phoneme processing test to check for truncation
  - Text segmentation test to ensure proper handling

## Configuration

The maximum phoneme length is now configurable via an environment variable:

```bash
# Set maximum phoneme length to 768 (default is 512)
export KOKORO_MAX_PHONEME_LENGTH=768
```

This allows for easy adjustment based on your specific text requirements without code changes.

## Future Considerations

1. **Dynamic Phoneme Length:** Consider implementing dynamic phoneme length based on text complexity
2. **Adaptive Segmentation:** Improve text segmentation to better handle complex texts
3. **Performance Impact:** Monitor performance impact of increased phoneme length

## References

- [CoreML Tensor Shape Optimization](docs/ORT-optimization-guide.md)
- [TTS Processing Pipeline](docs/MISAKI_INTEGRATION_GUIDE.md)
