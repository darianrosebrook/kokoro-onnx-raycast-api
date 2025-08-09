# DualSessionManager Fix - Missing Complexity Analysis Methods

**Date:** 2025-08-08  
**Author:** @darianrosebrook  
**Status:** Resolved  

## Problem Description

The Kokoro TTS system was failing with the following error when processing text:

```
WARNING - [0] Fast dual session failed: 'DualSessionManager' object has no attribute '_analyze_character_complexity'
ERROR - [0] Error processing segment 0: 'DualSessionManager' object has no attribute '_analyze_character_complexity'
```

This error occurred in the `DualSessionManager.calculate_segment_complexity()` method when it tried to call `self._analyze_character_complexity()` and `self._analyze_linguistic_complexity()` methods that were not implemented in the class.

## Root Cause

The `DualSessionManager` class in `api/model/loader.py` was calling two methods that didn't exist:

1. `_analyze_character_complexity()` - for analyzing character distribution complexity
2. `_analyze_linguistic_complexity()` - for analyzing linguistic complexity patterns

These methods were referenced in the `_calculate_complexity_impl()` method but were never implemented in the `DualSessionManager` class, even though similar methods existed in the `TextComplexityAnalyzer` class.

## Solution

Added the missing complexity analysis methods to the `DualSessionManager` class:

### 1. `_analyze_character_complexity()` Method

```python
def _analyze_character_complexity(self, text: str) -> float:
    """
    Analyze character distribution complexity.
    
    @param text: Text to analyze
    @returns: Character complexity score (0.0 to 1.0)
    """
    if not text:
        return 0.0

    char_counts = {
        'letters': 0,
        'digits': 0,
        'punctuation': 0,
        'special': 0,
        'unicode': 0
    }

    for char in text:
        if char.isalpha():
            char_counts['letters'] += 1
        elif char.isdigit():
            char_counts['digits'] += 1
        elif char in '.,!?;:':
            char_counts['punctuation'] += 1
        elif ord(char) > 127:
            char_counts['unicode'] += 1
        else:
            char_counts['special'] += 1

    # Calculate weighted complexity
    total_chars = len(text)
    complexity = 0.0

    # Character complexity weights
    char_weights = {
        'letters': 1.0,
        'digits': 1.1,
        'punctuation': 1.2,
        'special': 1.5,
        'unicode': 2.0
    }

    for char_type, count in char_counts.items():
        if total_chars > 0:
            ratio = count / total_chars
            complexity += ratio * char_weights[char_type]

    return complexity / 2.0  # Normalize to reasonable range
```

### 2. `_analyze_linguistic_complexity()` Method

```python
def _analyze_linguistic_complexity(self, text: str) -> float:
    """
    Analyze linguistic complexity patterns.
    
    @param text: Text to analyze
    @returns: Linguistic complexity score (0.0 to 1.0)
    """
    if not text:
        return 0.0

    # Simple heuristic-based linguistic analysis
    complexity = 0.0

    # Count difficult patterns
    difficult_patterns = [
        'tion', 'sion', 'ough', 'augh', 'eigh',
        'ph', 'gh', 'ch', 'sh', 'th', 'wh',
        'qu', 'x', 'z'
    ]

    pattern_count = 0
    for pattern in difficult_patterns:
        pattern_count += text.lower().count(pattern)

    # Calculate complexity based on pattern density
    if len(text) > 0:
        complexity = min(1.0, pattern_count / len(text) * 10)

    return complexity
```

## Testing

The fix was verified by testing with the exact text that was causing the original error:

```python
test_text = "The Kokoro TTS system is now fully functional and ready for use with the Raycast extension. The \"speak selected text\" feature should work smoothly without any tuple errors or streaming issues."
```

**Test Results:**
- ✅ Request completed successfully (HTTP 200)
- ✅ Audio generated: 483,328 bytes
- ✅ Processing time: ~17 seconds
- ✅ No more `_analyze_character_complexity` errors

## Impact

This fix resolves the critical error that was preventing the TTS system from processing text through the dual session manager. The system can now:

1. Properly calculate text complexity for optimal session routing
2. Route segments to appropriate hardware (ANE, GPU, CPU) based on complexity
3. Process text without the missing method errors
4. Generate audio successfully for the Raycast extension

## Files Modified

- `api/model/loader.py` - Added missing complexity analysis methods to `DualSessionManager` class

## Related Components

- `DualSessionManager` - Session management for concurrent processing
- `TextComplexityAnalyzer` - Similar complexity analysis (used as reference)
- `WorkloadAnalyzer` - Workload profiling and analysis
- TTS Core Processing - Audio generation pipeline
