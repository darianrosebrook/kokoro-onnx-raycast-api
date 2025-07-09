#!/usr/bin/env python3
"""
Benchmark Cache Management Utility

This script provides comprehensive tools for managing the TTS benchmark cache,
allowing users to clear cache, force benchmarking, inspect cache status, and
manually trigger benchmarks when needed.

## Features

### Cache Management
- **Clear Cache**: Remove cached benchmark results to force re-benchmarking
- **Inspect Cache**: View detailed cache status and expiration information
- **Force Benchmark**: Manually trigger benchmarking regardless of cache status
- **Validate Cache**: Check if cache is valid and up-to-date

### Cache Analysis
- **Cache Age**: Shows how long cache has been valid
- **Expiration Time**: When cache will expire based on frequency setting
- **Provider History**: Historical provider recommendations
- **Performance Trends**: Analysis of benchmark performance over time

### Manual Control
- **Expert Mode**: For users who prefer manual control over automatic benchmarking
- **Testing**: Force benchmarking for testing and comparison purposes
- **Debugging**: Detailed cache inspection for troubleshooting

## Usage

```bash
# Show cache status
python scripts/manage_benchmark_cache.py --status

# Clear cache to force re-benchmark
python scripts/manage_benchmark_cache.py --clear

# Force benchmark now (ignores cache)
python scripts/manage_benchmark_cache.py --force-benchmark

# Inspect cache contents
python scripts/manage_benchmark_cache.py --inspect
```

@author: @darianrosebrook
@date: 2025-07-09
@version: 1.0.0
@license: MIT
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import TTSConfig
from api.model.loader import benchmark_providers, initialize_model, get_model_status


def get_cache_file_path() -> str:
    """Get the path to the benchmark cache file."""
    return os.path.join(".cache", "coreml_config.json")


def load_cache_data() -> Optional[Dict[str, Any]]:
    """
    Load benchmark cache data from file.
    
    @returns Optional[Dict]: Cache data or None if not found/invalid
    """
    cache_file = get_cache_file_path()
    
    if not os.path.exists(cache_file):
        return None
    
    try:
        with open(cache_file, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️ Error reading cache file: {e}")
        return None


def save_cache_data(data: Dict[str, Any]) -> bool:
    """
    Save benchmark cache data to file.
    
    @param data: Cache data to save
    @returns bool: True if saved successfully
    """
    cache_file = get_cache_file_path()
    
    try:
        # Ensure cache directory exists
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        print(f"❌ Error saving cache file: {e}")
        return False


def clear_cache() -> bool:
    """
    Clear the benchmark cache to force re-benchmarking.
    
    @returns bool: True if cleared successfully
    """
    cache_file = get_cache_file_path()
    
    if not os.path.exists(cache_file):
        print("ℹ️  No cache file found - already cleared")
        return True
    
    try:
        os.remove(cache_file)
        print("✅ Benchmark cache cleared successfully")
        print("   • Next startup will perform fresh benchmarking")
        print("   • This will add 20-30 seconds to startup time")
        return True
    except IOError as e:
        print(f"❌ Error clearing cache: {e}")
        return False


def show_cache_status() -> None:
    """Display comprehensive cache status information."""
    print("\n" + "="*70)
    print("📊 BENCHMARK CACHE STATUS")
    print("="*70)
    
    # Show current configuration
    frequency = TTSConfig.BENCHMARK_FREQUENCY
    cache_duration = TTSConfig.get_benchmark_cache_duration()
    
    print(f"Configuration:")
    print(f"  • Benchmark Frequency: {frequency}")
    print(f"  • Cache Duration: {cache_duration/3600:.1f} hours ({cache_duration/86400:.1f} days)")
    print(f"  • Development Mode: {'Yes' if TTSConfig.DEVELOPMENT_MODE else 'No'}")
    print(f"  • Fast Startup: {'Yes' if TTSConfig.FAST_STARTUP else 'No'}")
    print()
    
    # Load cache data
    cache_data = load_cache_data()
    
    if not cache_data:
        print("Cache Status: ❌ No cache file found")
        print("  • Next startup will benchmark hardware")
        print("  • Expected startup delay: 20-30 seconds")
        print("  • This is normal for first-time setup")
        return
    
    # Analyze cache data
    benchmark_date = cache_data.get("benchmark_date", 0)
    cache_age = time.time() - benchmark_date
    cache_age_hours = cache_age / 3600
    cache_age_days = cache_age / 86400
    
    recommended_provider = cache_data.get("recommended_provider", "Unknown")
    current_provider = cache_data.get("current_provider", "Unknown")
    benchmark_results = cache_data.get("benchmark_results", {})
    
    # Check if cache is valid
    is_valid = cache_age < cache_duration
    expires_in = (cache_duration - cache_age) / 3600
    
    print(f"Cache Status: {'✅ Valid' if is_valid else '⏰ Expired'}")
    print(f"  • Cache Age: {cache_age_hours:.1f} hours ({cache_age_days:.1f} days)")
    print(f"  • Benchmark Date: {datetime.fromtimestamp(benchmark_date).strftime('%Y-%m-%d %H:%M:%S')}")
    
    if is_valid:
        print(f"  • Expires In: {expires_in:.1f} hours")
        print(f"  • Next Benchmark: {(datetime.now() + timedelta(seconds=cache_duration - cache_age)).strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"  • Expired: {abs(expires_in):.1f} hours ago")
        print(f"  • Next startup will re-benchmark")
    
    print()
    print(f"Provider Information:")
    print(f"  • Recommended Provider: {recommended_provider}")
    print(f"  • Current Provider: {current_provider}")
    
    # Show benchmark results if available
    if benchmark_results:
        print(f"  • Benchmark Results:")
        for provider, time_taken in benchmark_results.items():
            print(f"    - {provider}: {time_taken:.3f}s")
    
    print()
    
    # Show recommendations
    if not is_valid:
        print("💡 Recommendations:")
        print("  • Cache is expired - next startup will benchmark")
        print("  • Consider using 'weekly' or 'monthly' frequency for less frequent benchmarking")
        print("  • Use --clear to force immediate re-benchmarking")
    elif frequency == "manually":
        print("💡 Manual Mode:")
        print("  • Cache will not expire automatically")
        print("  • Use --force-benchmark to run benchmarks when needed")
        print("  • Use --clear to reset cache")
    else:
        print("💡 Status:")
        print("  • Cache is valid and will be used")
        print("  • No benchmarking needed until expiration")


def inspect_cache() -> None:
    """Display detailed cache inspection information."""
    print("\n" + "="*70)
    print("🔍 DETAILED CACHE INSPECTION")
    print("="*70)
    
    cache_file = get_cache_file_path()
    
    if not os.path.exists(cache_file):
        print("❌ No cache file found")
        return
    
    try:
        # File system information
        stat = os.stat(cache_file)
        file_size = stat.st_size
        modified_time = datetime.fromtimestamp(stat.st_mtime)
        
        print(f"File Information:")
        print(f"  • Path: {cache_file}")
        print(f"  • Size: {file_size} bytes")
        print(f"  • Modified: {modified_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Cache content
        cache_data = load_cache_data()
        if cache_data:
            print("Cache Contents:")
            for key, value in cache_data.items():
                if key == "benchmark_date":
                    # Convert timestamp to readable format
                    readable_date = datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
                    print(f"  • {key}: {value} ({readable_date})")
                elif key == "benchmark_results" and isinstance(value, dict):
                    print(f"  • {key}:")
                    for provider, time_taken in value.items():
                        print(f"    - {provider}: {time_taken:.3f}s")
                else:
                    print(f"  • {key}: {value}")
        
    except Exception as e:
        print(f"❌ Error inspecting cache: {e}")


def force_benchmark() -> bool:
    """
    Force benchmark execution regardless of cache status.
    
    @returns bool: True if benchmarking succeeded
    """
    print("\n" + "="*70)
    print("🔬 FORCING BENCHMARK EXECUTION")
    print("="*70)
    print()
    print("This will benchmark your hardware to determine optimal provider...")
    print("Expected time: 20-30 seconds")
    print()
    
    # Initialize model if needed
    if not get_model_status():
        print("🔄 Initializing model for benchmarking...")
        try:
            initialize_model()
            print("✅ Model initialized successfully")
        except Exception as e:
            print(f"❌ Model initialization failed: {e}")
            return False
    
    # Run benchmark
    try:
        print("🔬 Running benchmark...")
        optimal_provider, benchmark_results = benchmark_providers()
        
        if not benchmark_results:
            print("⚠️ No benchmark results obtained")
            return False
        
        # Save results to cache
        cache_data = {
            "recommended_provider": optimal_provider,
            "benchmark_date": time.time(),
            "current_provider": optimal_provider,
            "benchmark_results": benchmark_results
        }
        
        if save_cache_data(cache_data):
            print("✅ Benchmark completed successfully")
            print(f"   • Optimal Provider: {optimal_provider}")
            print(f"   • Results cached for {TTSConfig.get_benchmark_cache_duration()/3600:.1f} hours")
            
            # Show performance comparison
            if len(benchmark_results) > 1:
                sorted_results = sorted(benchmark_results.items(), key=lambda x: x[1])
                fastest = sorted_results[0]
                slowest = sorted_results[-1]
                improvement = ((slowest[1] - fastest[1]) / slowest[1]) * 100
                
                print(f"   • Performance Improvement: {improvement:.1f}%")
                print(f"   • Fastest: {fastest[0]} ({fastest[1]:.3f}s)")
                print(f"   • Slowest: {slowest[0]} ({slowest[1]:.3f}s)")
            
            return True
        else:
            print("❌ Failed to save benchmark results")
            return False
            
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        return False


def main():
    """Main entry point for benchmark cache management."""
    parser = argparse.ArgumentParser(
        description="Manage TTS benchmark cache",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/manage_benchmark_cache.py --status           # Show cache status
  python scripts/manage_benchmark_cache.py --clear            # Clear cache
  python scripts/manage_benchmark_cache.py --force-benchmark  # Force benchmark
  python scripts/manage_benchmark_cache.py --inspect          # Inspect cache
        """
    )
    
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show benchmark cache status"
    )
    
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear benchmark cache to force re-benchmarking"
    )
    
    parser.add_argument(
        "--force-benchmark",
        action="store_true",
        help="Force benchmark execution regardless of cache status"
    )
    
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Inspect detailed cache contents"
    )
    
    args = parser.parse_args()
    
    # Default to showing status if no arguments provided
    if not any([args.status, args.clear, args.force_benchmark, args.inspect]):
        args.status = True
    
    # Execute requested operations
    if args.status:
        show_cache_status()
    
    if args.clear:
        clear_cache()
    
    if args.force_benchmark:
        if not force_benchmark():
            sys.exit(1)
    
    if args.inspect:
        inspect_cache()


if __name__ == "__main__":
    main() 