"""
Common pattern optimization for TTS pipeline.

This module provides optimized patterns for common text, phoneme,
and voice combinations to improve inference performance.
"""

import logging
from typing import List, Dict, Any, Tuple


def get_common_text_patterns() -> List[str]:
    """
    Get list of common text patterns for warm-up and optimization.
    
    @returns List[str]: Common text patterns for precompilation
    """
    return [
        # Primer-like short texts to precompile early fast path
        "Primer:",
        "Hello world.",
        "Starting stream.",
        
        # Short natural sentences
        "How are you today?",
        "Welcome to our service.",
        "Thank you for waiting.",
        "Please hold on.",
        "Processing your request.",
        
        # Medium sentences to heat up graphs
        "This is a test of the text to speech system.",
        "The quick brown fox jumps over the lazy dog.",
        "Please wait while we process your request.",
        "Your request is being processed, please wait.",
        
        # Longer sentence to match typical usage
        "This is a longer sentence intended to demonstrate early primer streaming behavior, enabling the client to begin playback while the remainder is prepared and streamed in order.",
        
        # Technical and complex patterns
        "The system configuration has been updated successfully.",
        "Authentication failed. Please check your credentials and try again.",
        "Data processing completed with 99.5% accuracy in 2.3 seconds.",
        
        # Numbers and special characters
        "Your order number is 12345.",
        "The temperature is 72.5 degrees Fahrenheit.",
        "Meeting scheduled for 3:30 PM on January 15th, 2024."
    ]


def get_common_voice_patterns() -> List[str]:
    """
    Get list of common voice patterns for optimization.
    
    @returns List[str]: Common voice identifiers
    """
    return [
        # Primary AF voices
        "af_bella", "af_nicole", "af_sarah", "af_sky",
        
        # English voices (if available)
        "en_jane", "en_adam", "en_john", "en_maria",
        
        # Additional AF voices
        "af_voice", "af_heart", "af_default"
    ]


def get_phoneme_test_patterns() -> List[List[str]]:
    """
    Get phoneme patterns for shape precompilation and testing.
    
    @returns List[List[str]]: Phoneme patterns of various lengths
    """
    return [
        # Short patterns (good for quick warm-up)
        ["h", "e", "l", "o"] + ["_"] * 252,
        ["t", "e", "s", "t"] + ["_"] * 252,
        ["h", "i"] + ["_"] * 254,
        
        # Medium patterns
        ["h", "e", "l", "o", " ", "w", "ɝ", "l", "d"] + ["_"] * 247,
        ["t", "e", "s", "t", " ", "m", "e", "s", "ɪ", "ʤ"] + ["_"] * 246,
        
        # Complex patterns with various phonemes
        ["ð", "ə", " ", "k", "w", "ɪ", "k", " ", "b", "r",
         "aʊ", "n", " ", "f", "ɑ", "k", "s"] + ["_"] * 239,
        
        # Very complex pattern with difficult sounds
        ["k", "ɑ", "m", "p", "l", "ɛ", "k", "s", " ", "f", "o", "n", "i", "m", 
         "ɪ", "k", " ", "p", "æ", "t", "ɝ", "n", "z"] + ["_"] * 233,
        
        # Full length pattern (stress test)
        ["a"] * 256,  # Maximum length pattern
        
        # Varied difficulty pattern
        ["s", "ɪ", "m", "p", "l", " ", "æ", "n", "d", " ", "k", "ɑ", "m", "p", "l", "ɛ", "k", "s", " ",
         "f", "o", "n", "i", "m", " ", "p", "æ", "t", "ɝ", "n", "z", " ", "f", "ɔ", "r", " ",
         "t", "ɛ", "s", "t", "ɪ", "ŋ"] + ["_"] * 214
    ]


def get_complexity_test_patterns() -> List[Tuple[str, float]]:
    """
    Get text patterns with expected complexity scores for testing.
    
    @returns List[Tuple[str, float]]: (text, expected_complexity) pairs
    """
    return [
        # Very low complexity
        ("Hi", 0.1),
        ("Hello", 0.15),
        ("Test", 0.15),
        
        # Low complexity
        ("Hello world", 0.25),
        ("How are you?", 0.3),
        ("Thank you", 0.2),
        
        # Medium complexity  
        ("This is a test sentence", 0.5),
        ("Please wait while processing", 0.55),
        ("The quick brown fox jumps", 0.6),
        
        # High complexity
        ("Complex technical terminology with specialized vocabulary", 0.8),
        ("Sophisticated phonological patterns with consonant clusters", 0.85),
        ("Authentication and authorization protocols for secure communication", 0.75),
        
        # Very high complexity
        ("Extraordinarily sophisticated and multifaceted computational algorithms", 0.9),
        ("Very long and complex sentence with multiple subordinate clauses and technical terminology", 0.95),
        ("Pneumonoultramicroscopicsilicovolcanoconiosisrepresentsanextremelylongmedicalterm", 0.98)
    ]


def get_language_specific_patterns() -> Dict[str, List[str]]:
    """
    Get language-specific text patterns for optimization.
    
    @returns Dict[str, List[str]]: Language code to patterns mapping
    """
    return {
        "en-us": [
            "Hello, how are you doing today?",
            "The weather is nice outside.",
            "I'll be right back in a moment.",
            "Thank you for your patience.",
            "Processing your request now."
        ],
        "en-gb": [
            "Cheerio, how are you getting on?",
            "The weather's quite lovely today.",
            "I shall return presently.",
            "Thank you for your patience.",
            "Processing your enquiry now."
        ]
    }


def get_voice_optimization_patterns() -> Dict[str, List[str]]:
    """
    Get voice-specific optimization patterns.
    
    @returns Dict[str, List[str]]: Voice ID to optimized patterns mapping
    """
    return {
        "af_bella": [
            "Welcome to our service.",
            "How can I help you today?",
            "Your request is being processed.",
            "Thank you for choosing us."
        ],
        "af_nicole": [
            "Hello and welcome.",
            "I'm here to assist you.",
            "Please wait a moment.",
            "Have a wonderful day."
        ],
        "af_sarah": [
            "Good morning, good afternoon.",
            "Let me help you with that.",
            "Processing your information.",
            "Thank you for waiting."
        ],
        "af_sky": [
            "Hi there, how are you?",
            "I'll take care of that for you.",
            "Just a moment please.",
            "Is there anything else I can help with?"
        ]
    }


def get_performance_test_patterns() -> List[Dict[str, Any]]:
    """
    Get patterns specifically designed for performance testing.
    
    @returns List[Dict[str, Any]]: Performance test configurations
    """
    return [
        {
            "name": "quick_warmup",
            "texts": ["Hi", "Hello", "Test"],
            "voices": ["af_bella"],
            "purpose": "Fast initial warm-up"
        },
        {
            "name": "standard_patterns",
            "texts": [
                "Hello world",
                "How are you today?",
                "This is a test of the speech system"
            ],
            "voices": ["af_bella", "af_nicole"],
            "purpose": "Standard performance validation"
        },
        {
            "name": "complex_patterns",
            "texts": [
                "The quick brown fox jumps over the lazy dog",
                "Complex technical terminology with specialized vocabulary",
                "Very long sentence with multiple clauses and technical terms"
            ],
            "voices": ["af_bella", "af_sarah", "af_sky"],
            "purpose": "Stress testing and optimization validation"
        },
        {
            "name": "shape_diversity",
            "texts": [
                "A",  # Very short
                "Medium length sentence for testing",  # Medium
                "This is a very long sentence designed to test the maximum capabilities of the text-to-speech system with complex phonological patterns"  # Long
            ],
            "voices": ["af_bella"],
            "purpose": "Shape specialization testing"
        }
    ]


def optimize_patterns_for_session(session_type: str) -> List[str]:
    """
    Get optimized patterns for specific session types.
    
    @param session_type: Session type ('ane', 'gpu', 'cpu')
    @returns List[str]: Optimized patterns for the session
    """
    base_patterns = get_common_text_patterns()
    
    if session_type == "ane":
        # Neural Engine works well with complex patterns
        return [
            "Complex technical terminology with specialized vocabulary",
            "Sophisticated phonological patterns require advanced processing",
            "The quick brown fox jumps over the lazy dog repeatedly",
            "Authentication and authorization protocols for secure communication"
        ] + base_patterns[:5]
    
    elif session_type == "gpu":
        # GPU good for medium complexity
        return [
            "This is a test of the text to speech system",
            "Please wait while we process your request carefully",
            "The weather is nice outside today, isn't it?",
            "Welcome to our advanced speech synthesis service"
        ] + base_patterns[:5]
    
    elif session_type == "cpu":
        # CPU better for simpler patterns
        return [
            "Hello world",
            "How are you?",
            "Thank you",
            "Please wait",
            "Welcome"
        ] + base_patterns[:3]
    
    else:
        return base_patterns


def get_cache_optimization_patterns() -> Dict[str, Any]:
    """
    Get patterns optimized for caching strategies.
    
    @returns Dict[str, Any]: Cache optimization configuration
    """
    return {
        "high_frequency": [
            "Hello",
            "Thank you",
            "Please wait",
            "Welcome",
            "How are you?"
        ],
        "medium_frequency": [
            "This is a test",
            "Processing your request",
            "Have a nice day",
            "Is there anything else?",
            "Please hold on"
        ],
        "specialized": [
            "Authentication required",
            "Processing complete",
            "Error occurred",
            "Connection established",
            "System ready"
        ],
        "cache_strategy": {
            "high_frequency": {
                "cache_duration": 3600,  # 1 hour
                "preload": True,
                "priority": "high"
            },
            "medium_frequency": {
                "cache_duration": 1800,  # 30 minutes
                "preload": False,
                "priority": "medium"
            },
            "specialized": {
                "cache_duration": 900,   # 15 minutes
                "preload": False,
                "priority": "low"
            }
        }
    }


def generate_benchmark_patterns(complexity_levels: List[str] = None) -> List[Dict[str, Any]]:
    """
    Generate patterns for benchmarking different complexity levels.
    
    @param complexity_levels: List of complexity levels to generate
    @returns List[Dict[str, Any]]: Benchmark pattern configurations
    """
    if complexity_levels is None:
        complexity_levels = ["low", "medium", "high"]
    
    patterns = []
    
    complexity_patterns = {
        "low": {
            "texts": ["Hi", "Hello", "Test", "Thanks", "Welcome"],
            "expected_time_ms": 100,
            "memory_usage": "low"
        },
        "medium": {
            "texts": [
                "How are you today?",
                "This is a test sentence",
                "Please wait while processing",
                "The weather is nice outside"
            ],
            "expected_time_ms": 300,
            "memory_usage": "medium"
        },
        "high": {
            "texts": [
                "Complex technical terminology with specialized vocabulary",
                "The quick brown fox jumps over the lazy dog repeatedly",
                "Very long sentence with multiple subordinate clauses and technical terminology"
            ],
            "expected_time_ms": 800,
            "memory_usage": "high"
        }
    }
    
    for level in complexity_levels:
        if level in complexity_patterns:
            patterns.append({
                "complexity_level": level,
                **complexity_patterns[level]
            })
    
    return patterns

