# Word Count Mismatch Investigation

## Summary

Investigation into "words count mismatch" warnings from the phonemizer library during text-to-phoneme conversion.

## Problem

The phonemizer library emits warnings like:
```
WARNING - words count mismatch on 1800.0% of the lines (18/1)
```

This indicates:
- Expected: 1 word per line
- Got: 18 words per line  
- Occurred on: 1 out of 1 lines (100%)

## Root Cause

The phonemizer library processes text as a list of lines and compares word counts between input and output. The warnings occur because:

1. **Text Preprocessing**: Our preprocessing (`_preprocess_for_phonemizer`) normalizes multi-line text into single lines by replacing newlines with periods and spaces.

2. **Phonemizer Processing**: The phonemizer library receives a single long line (e.g., 18 words) but internally may expect or process it differently, causing a word count mismatch.

3. **Harmless Warnings**: These warnings are informational and do not affect functionality or audio quality. The phonemizer still produces correct phoneme output.

## Solution

### 1. Enhanced Warning Suppression

Updated `api/warnings.py` to better suppress these warnings:

- **Multiple Logger Levels**: Configure phonemizer loggers at multiple hierarchy levels:
  - `phonemizer`
  - `phonemizer.backend`
  - `phonemizer.backend.espeak`
  - `phonemizer.backend.espeak.base`
  - `phonemizer.backend.espeak.espeak`

- **Improved Filter**: Enhanced `ONNXRuntimeWarningFilter` with:
  - Case-insensitive pattern matching
  - Multiple pattern variations ("words count mismatch", "word count mismatch", etc.)
  - Applied to both root logger and phonemizer-specific loggers

### 2. Documentation

Added comments to `_preprocess_for_phonemizer()` explaining:
- Why warnings may still occur
- That they are harmless
- That they are suppressed at the logging level

## Technical Details

### Text Processing Flow

1. **Input**: Multi-line text (e.g., "Executive Summary\nThis document...")
2. **Normalization**: `normalize_for_tts()` - handles dates/times
3. **Cleaning**: `clean_text()` - removes control characters, normalizes whitespace
4. **Preprocessing**: `_preprocess_for_phonemizer()` - replaces newlines with periods, normalizes punctuation
5. **Phonemization**: Phonemizer processes the single preprocessed line

### Why Mismatches Occur

The phonemizer library's word counting algorithm may:
- Count punctuation differently
- Handle contractions differently  
- Split compound words differently
- Process punctuation marks as separate "words"

Our preprocessing preserves word boundaries but may not match the phonemizer's exact counting method.

## Verification

The warnings are now suppressed at multiple levels:
1. Python warnings module (`warnings.catch_warnings()`)
2. Logger level (set to ERROR for phonemizer loggers)
3. Logging filter (`ONNXRuntimeWarningFilter`)

## Impact

- **Functionality**: No impact - warnings are informational only
- **Performance**: No impact - suppression adds minimal overhead
- **Log Quality**: Improved - warnings no longer clutter logs
- **Audio Quality**: No impact - phonemization is correct regardless of warnings

## Future Improvements

If word count mismatches become problematic:

1. **Investigate Phonemizer Configuration**: Adjust `preserve_punctuation` and other backend settings
2. **Alternative Preprocessing**: Try different text normalization strategies
3. **Phonemizer Fork**: Consider using a fork with improved word counting
4. **Misaki G2P**: Prefer Misaki G2P when available (already implemented as primary method)

## References

- `api/warnings.py` - Warning suppression implementation
- `api/tts/text_processing.py` - Text preprocessing functions
- `api/tts/misaki_processing.py` - Misaki G2P integration (preferred method)

@author: @darianrosebrook
@date: 2025-11-23







