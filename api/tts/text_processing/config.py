"""
Configuration management for text processing pipeline.

This module centralizes all configuration options for the text processing
system, providing type-safe configuration with validation and defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum


class PhonemizerBackend(Enum):
    """Available phonemizer backends in priority order."""
    MISAKI = "misaki"
    ESPEAK = "espeak"
    CHARACTER = "character"


class NormalizationLevel(Enum):
    """Text normalization levels."""
    MINIMAL = "minimal"      # Basic cleaning only
    STANDARD = "standard"    # Standard normalization
    AGGRESSIVE = "aggressive" # Maximum normalization


@dataclass
class CacheConfig:
    """Configuration for caching behavior."""
    enabled: bool = True
    max_size: int = 1000
    ttl_seconds: int = 3600  # 1 hour
    eviction_policy: str = "lru"  # lru, fifo, random
    
    def __post_init__(self):
        """Validate cache configuration."""
        if self.max_size < 1:
            raise ValueError("Cache max_size must be positive")
        if self.ttl_seconds < 0:
            raise ValueError("Cache TTL must be non-negative")


@dataclass 
class NormalizationConfig:
    """Configuration for text normalization."""
    level: NormalizationLevel = NormalizationLevel.STANDARD
    
    # Number processing
    expand_numbers: bool = True
    expand_ordinals: bool = True
    expand_decimals: bool = True
    expand_fractions: bool = True
    
    # Date and time processing
    expand_dates: bool = True
    expand_times: bool = True
    date_format: str = "natural"  # natural, iso, us
    
    # Abbreviation processing
    expand_abbreviations: bool = True
    expand_units: bool = True
    expand_currency: bool = True
    
    # Text cleaning
    normalize_whitespace: bool = True
    remove_control_chars: bool = True
    normalize_punctuation: bool = True
    normalize_quotes: bool = True
    
    # Case handling
    preserve_case: bool = True
    normalize_case: str = "none"  # none, lower, upper, title
    
    # Custom patterns
    custom_replacements: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate normalization configuration."""
        if self.normalize_case not in ["none", "lower", "upper", "title"]:
            raise ValueError("Invalid normalize_case value")


@dataclass
class PhonemizerConfig:
    """Configuration for phonemization."""
    preferred_backends: List[PhonemizerBackend] = field(
        default_factory=lambda: [
            PhonemizerBackend.MISAKI,
            PhonemizerBackend.ESPEAK,
            PhonemizerBackend.CHARACTER
        ]
    )
    
    # Misaki-specific settings
    misaki_enabled: bool = True
    misaki_use_transformer: bool = False
    misaki_british_english: bool = False
    
    # eSpeak-specific settings
    espeak_language: str = "en-us"
    espeak_preserve_punctuation: bool = True
    espeak_with_stress: bool = False
    
    # Quality settings
    fallback_on_error: bool = True
    quality_threshold: float = 0.8
    confidence_threshold: float = 0.7
    
    # Performance settings
    parallel_processing: bool = False
    max_workers: int = 2
    timeout_seconds: int = 30


@dataclass
class SegmentationConfig:
    """Configuration for text segmentation."""
    max_segment_length: int = 200
    min_segment_length: int = 10
    
    # Segmentation strategy
    respect_sentence_boundaries: bool = True
    respect_clause_boundaries: bool = True
    respect_word_boundaries: bool = True
    
    # Advanced segmentation
    use_linguistic_segmentation: bool = True
    balance_segment_lengths: bool = True
    overlap_segments: bool = False
    overlap_size: int = 0
    
    # Fallback behavior
    force_split_long_words: bool = True
    max_word_length: int = 50


@dataclass
class PaddingConfig:
    """Configuration for phoneme padding."""
    max_phoneme_length: int = 256
    padding_token: str = "_"
    truncation_strategy: str = "smart"  # smart, end, middle
    preserve_word_boundaries: bool = True


@dataclass
class PerformanceConfig:
    """Configuration for performance optimization."""
    lazy_loading: bool = True
    parallel_processing: bool = False
    max_workers: int = 2
    
    # Memory management
    gc_frequency: int = 100  # Run GC every N requests
    max_memory_mb: int = 500
    
    # Monitoring
    enable_metrics: bool = True
    metrics_sample_rate: float = 1.0


@dataclass
class ProcessingConfig:
    """
    Master configuration for the text processing pipeline.
    
    This class aggregates all configuration options for the various
    components of the text processing system, providing a single
    point of configuration management.
    """
    # Component configurations
    cache: CacheConfig = field(default_factory=CacheConfig)
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    phonemizer: PhonemizerConfig = field(default_factory=PhonemizerConfig)
    segmentation: SegmentationConfig = field(default_factory=SegmentationConfig)
    padding: PaddingConfig = field(default_factory=PaddingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    
    # Global settings
    language: str = "en"
    debug_mode: bool = False
    
    # Legacy compatibility
    enable_misaki: bool = True
    max_phoneme_length: int = 256
    
    def __post_init__(self):
        """Sync legacy settings with new configuration structure."""
        # Sync legacy settings
        self.phonemizer.misaki_enabled = self.enable_misaki
        self.padding.max_phoneme_length = self.max_phoneme_length
        
        # Validate configuration
        self._validate()
    
    def _validate(self):
        """Validate the complete configuration."""
        if self.padding.max_phoneme_length < 1:
            raise ValueError("max_phoneme_length must be positive")
        
        if self.language not in ["en"]:  # Extend as more languages are supported
            raise ValueError(f"Unsupported language: {self.language}")
        
        if self.segmentation.max_segment_length < self.segmentation.min_segment_length:
            raise ValueError("max_segment_length must be >= min_segment_length")
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ProcessingConfig':
        """
        Create configuration from dictionary.
        
        Args:
            config_dict: Dictionary containing configuration values
            
        Returns:
            ProcessingConfig instance
        """
        # Handle nested configuration
        cache_config = CacheConfig(**config_dict.get('cache', {}))
        normalization_config = NormalizationConfig(**config_dict.get('normalization', {}))
        phonemizer_config = PhonemizerConfig(**config_dict.get('phonemizer', {}))
        segmentation_config = SegmentationConfig(**config_dict.get('segmentation', {}))
        padding_config = PaddingConfig(**config_dict.get('padding', {}))
        performance_config = PerformanceConfig(**config_dict.get('performance', {}))
        
        # Extract top-level settings
        top_level = {k: v for k, v in config_dict.items() 
                    if k not in ['cache', 'normalization', 'phonemizer', 'segmentation', 'padding', 'performance']}
        
        return cls(
            cache=cache_config,
            normalization=normalization_config,
            phonemizer=phonemizer_config,
            segmentation=segmentation_config,
            padding=padding_config,
            performance=performance_config,
            **top_level
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert configuration to dictionary.
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            'cache': self.cache.__dict__,
            'normalization': self.normalization.__dict__,
            'phonemizer': self.phonemizer.__dict__,
            'segmentation': self.segmentation.__dict__,
            'padding': self.padding.__dict__,
            'performance': self.performance.__dict__,
            'language': self.language,
            'debug_mode': self.debug_mode,
            'enable_misaki': self.enable_misaki,
            'max_phoneme_length': self.max_phoneme_length
        }
    
    @classmethod
    def from_env(cls, prefix: str = "KOKORO_") -> 'ProcessingConfig':
        """
        Create configuration from environment variables.
        
        Args:
            prefix: Environment variable prefix
            
        Returns:
            ProcessingConfig instance with values from environment
        """
        config = cls()
        
        # Global settings
        if env_lang := os.getenv(f"{prefix}LANGUAGE"):
            config.language = env_lang
        
        if env_debug := os.getenv(f"{prefix}DEBUG_MODE"):
            config.debug_mode = env_debug.lower() in ("true", "1", "yes")
        
        # Misaki settings
        if env_misaki := os.getenv(f"{prefix}MISAKI_ENABLED"):
            config.enable_misaki = env_misaki.lower() in ("true", "1", "yes")
            config.phonemizer.misaki_enabled = config.enable_misaki
        
        # Phoneme length
        if env_max_len := os.getenv(f"{prefix}MAX_PHONEME_LENGTH"):
            try:
                config.max_phoneme_length = int(env_max_len)
                config.padding.max_phoneme_length = config.max_phoneme_length
            except ValueError:
                pass
        
        # Cache settings
        if env_cache_size := os.getenv(f"{prefix}CACHE_SIZE"):
            try:
                config.cache.max_size = int(env_cache_size)
            except ValueError:
                pass
        
        return config


# Default configuration instance
DEFAULT_CONFIG = ProcessingConfig()

# Environment-based configuration
ENV_CONFIG = ProcessingConfig.from_env()

# Export commonly used configurations
FAST_CONFIG = ProcessingConfig(
    normalization=NormalizationConfig(level=NormalizationLevel.MINIMAL),
    cache=CacheConfig(max_size=500),
    performance=PerformanceConfig(parallel_processing=True)
)

QUALITY_CONFIG = ProcessingConfig(
    normalization=NormalizationConfig(level=NormalizationLevel.AGGRESSIVE),
    phonemizer=PhonemizerConfig(quality_threshold=0.9),
    cache=CacheConfig(max_size=2000),
    performance=PerformanceConfig(enable_metrics=True)
)

STREAMING_CONFIG = ProcessingConfig(
    normalization=NormalizationConfig(level=NormalizationLevel.MINIMAL),
    cache=CacheConfig(max_size=200, ttl_seconds=300),
    segmentation=SegmentationConfig(max_segment_length=100),
    performance=PerformanceConfig(
        parallel_processing=False,  # Avoid threading overhead for streaming
        gc_frequency=50
    )
)
