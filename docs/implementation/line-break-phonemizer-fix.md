# Line Break Handling in Phonemizer Fix

> **Status:** Completed and tested
> **Date:** 2025-08-06
> **Author:** @darianrosebrook

## Problem

The TTS system was cutting off text during speech synthesis when processing multi-line text. Specifically, the text was being truncated after the phrase "Warm or Hot water temperature" in washing machine instructions text. The issue was identified in the phonemizer processing pipeline where line breaks were causing word count mismatches and incomplete phoneme sequences.

From the logs:
```
2025-08-06 21:11:10,738 - WARNING - words count mismatch on 100.0% of the lines (1/1)
```

This warning indicated that the phonemizer was having trouble correctly aligning words in the input text with their phoneme representations, which was causing truncation in the TTS output.

## Root Cause Analysis

1. **Line Break Handling**: The phonemizer was not properly handling line breaks in the input text, causing it to process only part of the text.

2. **Word Count Mismatches**: The phonemizer was reporting word count mismatches, indicating that it wasn't correctly processing all words in the text.

3. **Incomplete Phoneme Sequences**: Testing showed that phrases like "water temperature" and "appropriate for your" were missing from the phoneme output, explaining why the TTS stopped at that point.

4. **Verification**: The phoneme length (348) was well within our limit (512), confirming that the truncation was not due to the phoneme length limit.

## Implementation Changes

### 1. Improved Line Break Handling

- **Files:** `api/tts/text_processing.py` and `api/tts/misaki_processing.py`
- **Change:** Added special handling for line breaks in text
- **Improvements:**
  - Replace line breaks with periods to maintain sentence structure
  - Clean up any double periods that might be created
  - Ensure proper spacing around sentence boundaries

### 2. Enhanced Preprocessing for Phonemizer

- **File:** `api/tts/text_processing.py`
- **Change:** Updated `_preprocess_for_phonemizer()` function
- **Improvements:**
  - Added line break handling as a first preprocessing step
  - Added period at the end of text if missing to improve phonemizer behavior
  - Added debug logging for preprocessed text

### 3. Updated Misaki G2P Integration

- **File:** `api/tts/misaki_processing.py`
- **Change:** Added line break handling to `text_to_phonemes_misaki()`
- **Improvements:**
  - Process multi-line text before passing to Misaki G2P
  - Maintain consistent line break handling across all phonemization methods

### 4. Added Verification and Testing

- **File:** `scripts/verify_washing_fix.py`
- **Purpose:** Verify the fix works correctly with the problematic text
- **Tests:**
  - Preprocessing test to ensure problematic parts are preserved
  - Phoneme conversion test to ensure complete phoneme output
  - Misaki G2P test to ensure consistent behavior

## Testing Results

The verification tests confirmed that our fix successfully addresses the issue:

1. **Preprocessing**: The problematic phrases "water temperature" and "appropriate for your" are now preserved in the preprocessed text.

2. **Phoneme Conversion**: The phoneme output now includes the entire text, with a length of 358 phonemes.

3. **Misaki G2P**: The Misaki G2P engine also correctly processes the entire text with consistent results.

## Future Considerations

1. **Word Count Mismatch Handling**: While we've improved the handling of line breaks, the phonemizer still reports word count mismatches. Consider implementing more sophisticated word alignment algorithms to further reduce these warnings.

2. **Line Break Preservation**: The current implementation replaces line breaks with periods. Consider alternative approaches that better preserve the original text structure while ensuring complete phonemization.

3. **Performance Impact**: Monitor the performance impact of the enhanced preprocessing steps, especially for very long texts.

4. **Configuration Options**: Consider making line break handling configurable via environment variables for specific use cases.

## References

- [Phonemizer Documentation](https://github.com/bootphon/phonemizer)
- [Misaki G2P Integration Guide](docs/MISAKI_INTEGRATION_GUIDE.md)
- [TTS Processing Pipeline](docs/implementation/misaki-future-enhancements.md)

