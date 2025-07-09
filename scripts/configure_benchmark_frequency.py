#!/usr/bin/env python3
"""
Interactive Benchmark Frequency Configuration

This script provides an interactive interface for users to configure how often
the TTS system should benchmark their hardware to determine the optimal provider.
It creates environment configuration and provides clear explanations about the
impact of different benchmark frequencies.

## Features

### Interactive Configuration
- **Clear Explanations**: Detailed descriptions of each frequency option
- **Hardware Context**: Explains why hardware doesn't change frequently
- **Performance Impact**: Shows impact on startup time and battery life
- **Recommendation Engine**: Suggests optimal settings based on usage patterns

### Configuration Options
- **Daily**: 24-hour cache for users who want frequent optimization
- **Weekly**: 7-day cache for most users (recommended)
- **Monthly**: 30-day cache for stable systems
- **Manual**: User-controlled benchmarking only

### Environment Integration
- **Environment Variables**: Sets KOKORO_BENCHMARK_FREQUENCY
- **Persistent Configuration**: Saves settings to .env file
- **Validation**: Ensures configuration is valid and well-formed

## Usage

```bash
# Interactive configuration
python scripts/configure_benchmark_frequency.py

# Non-interactive with preset
python scripts/configure_benchmark_frequency.py --frequency weekly

# Show current configuration
python scripts/configure_benchmark_frequency.py --show-current
```

@author: @darianrosebrook
@date: 2025-07-09
@version: 1.0.0
@license: MIT
"""

import argparse
import os
import sys
from typing import Dict, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import TTSConfig


def get_frequency_descriptions() -> Dict[str, Dict[str, str]]:
    """
    Get detailed descriptions of each benchmark frequency option.
    
    @returns Dict mapping frequency names to description dictionaries
    """
    return {
        "daily": {
            "name": "Daily",
            "duration": "24 hours",
            "description": "Benchmark every day for frequent optimization",
            "best_for": "Development, frequent system changes, or maximum performance",
            "startup_impact": "Occasional 20-30 second delays during startup",
            "battery_impact": "Minimal - benchmarking is infrequent",
            "recommendation": "Good for developers or users who frequently change system settings"
        },
        "weekly": {
            "name": "Weekly", 
            "duration": "7 days",
            "description": "Benchmark once per week for balanced optimization",
            "best_for": "Most users with stable systems",
            "startup_impact": "Rare 20-30 second delays (once per week)",
            "battery_impact": "Very minimal - benchmarking is rare",
            "recommendation": "⭐ RECOMMENDED for most users"
        },
        "monthly": {
            "name": "Monthly",
            "duration": "30 days", 
            "description": "Benchmark once per month for stable systems",
            "best_for": "Stable production systems, battery-conscious users",
            "startup_impact": "Very rare delays (once per month)",
            "battery_impact": "Negligible - benchmarking is very rare",
            "recommendation": "Good for production servers or laptop users"
        },
        "manually": {
            "name": "Manual",
            "duration": "Only when explicitly requested",
            "description": "Never benchmark automatically - user controls when to benchmark",
            "best_for": "Expert users who want complete control",
            "startup_impact": "Never - always uses cached results",
            "battery_impact": "None - no automatic benchmarking",
            "recommendation": "For expert users who understand provider optimization"
        }
    }


def display_frequency_options() -> None:
    """Display all available benchmark frequency options with detailed descriptions."""
    print("\n" + "="*80)
    print("🔧 BENCHMARK FREQUENCY CONFIGURATION")
    print("="*80)
    print()
    print("The TTS system benchmarks your hardware to determine the optimal provider")
    print("(CoreML vs CPU) for best performance. Since hardware doesn't change frequently,")
    print("you can cache these results to speed up startup times.")
    print()
    print("Available Options:")
    print("-" * 80)
    
    descriptions = get_frequency_descriptions()
    
    for i, (freq, info) in enumerate(descriptions.items(), 1):
        print(f"\n{i}. {info['name']} ({info['duration']})")
        print(f"   Description: {info['description']}")
        print(f"   Best for: {info['best_for']}")
        print(f"   Startup impact: {info['startup_impact']}")
        print(f"   Battery impact: {info['battery_impact']}")
        print(f"   {info['recommendation']}")


def get_current_configuration() -> Dict[str, str]:
    """
    Get the current benchmark frequency configuration.
    
    @returns Dict containing current configuration details
    """
    current_freq = TTSConfig.BENCHMARK_FREQUENCY
    cache_duration = TTSConfig.get_benchmark_cache_duration()
    descriptions = get_frequency_descriptions()
    
    return {
        "frequency": current_freq,
        "cache_duration_hours": cache_duration / 3600,
        "cache_duration_days": cache_duration / 86400,
        "description": descriptions.get(current_freq, {}).get("description", "Unknown"),
        "env_var": os.environ.get("KOKORO_BENCHMARK_FREQUENCY", "Not set")
    }


def save_configuration(frequency: str) -> bool:
    """
    Save the benchmark frequency configuration to environment.
    
    @param frequency: The benchmark frequency to save
    @returns bool: True if saved successfully, False otherwise
    """
    try:
        # Create or update .env file
        env_file = ".env"
        env_lines = []
        
        # Read existing .env file if it exists
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                env_lines = f.readlines()
        
        # Remove existing KOKORO_BENCHMARK_FREQUENCY line
        env_lines = [line for line in env_lines if not line.strip().startswith("KOKORO_BENCHMARK_FREQUENCY=")]
        
        # Add new configuration
        env_lines.append(f"KOKORO_BENCHMARK_FREQUENCY={frequency}\n")
        
        # Write updated .env file
        with open(env_file, 'w') as f:
            f.writelines(env_lines)
        
        # Set environment variable for current session
        os.environ["KOKORO_BENCHMARK_FREQUENCY"] = frequency
        
        return True
        
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")
        return False


def interactive_configuration() -> Optional[str]:
    """
    Run interactive configuration to get user's preferred benchmark frequency.
    
    @returns Optional[str]: Selected frequency or None if cancelled
    """
    display_frequency_options()
    
    print("\n" + "="*80)
    print("🤔 HARDWARE CONTEXT")
    print("="*80)
    print()
    print("Why cache benchmark results?")
    print("• Hardware capabilities don't change frequently")
    print("• OS/software updates that affect Metal/CoreML are infrequent")
    print("• Benchmarking takes 20-30 seconds and affects startup time")
    print("• Longer cache periods = faster startup times")
    print("• You can always clear the cache manually if needed")
    print()
    
    frequency_options = ["daily", "weekly", "monthly", "manually"]
    
    while True:
        try:
            print("Please choose your preferred benchmark frequency:")
            for i, freq in enumerate(frequency_options, 1):
                descriptions = get_frequency_descriptions()
                name = descriptions[freq]["name"]
                duration = descriptions[freq]["duration"]
                print(f"  {i}. {name} ({duration})")
            
            print(f"  0. Cancel")
            print()
            
            choice = input("Enter your choice (0-4): ").strip()
            
            if choice == "0":
                print("Configuration cancelled.")
                return None
            
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(frequency_options):
                selected_freq = frequency_options[choice_idx]
                descriptions = get_frequency_descriptions()
                
                # Show confirmation
                print(f"\n✅ You selected: {descriptions[selected_freq]['name']}")
                print(f"   {descriptions[selected_freq]['description']}")
                print(f"   Cache duration: {descriptions[selected_freq]['duration']}")
                print()
                
                confirm = input("Is this correct? (y/n): ").strip().lower()
                if confirm in ['y', 'yes']:
                    return selected_freq
                else:
                    print("Let's try again...\n")
                    continue
            else:
                print("Invalid choice. Please enter a number between 0 and 4.")
                
        except (ValueError, KeyboardInterrupt):
            print("\nConfiguration cancelled.")
            return None


def show_current_configuration() -> None:
    """Display the current benchmark frequency configuration."""
    config = get_current_configuration()
    
    print("\n" + "="*60)
    print("📊 CURRENT BENCHMARK FREQUENCY CONFIGURATION")
    print("="*60)
    print()
    print(f"Current Setting: {config['frequency']}")
    print(f"Description: {config['description']}")
    print(f"Cache Duration: {config['cache_duration_hours']:.1f} hours ({config['cache_duration_days']:.1f} days)")
    print(f"Environment Variable: {config['env_var']}")
    print()
    
    # Show cache file status
    cache_file = ".cache/coreml_config.json"
    if os.path.exists(cache_file):
        import json
        import time
        
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            
            cache_age = time.time() - cache_data.get("benchmark_date", 0)
            cache_age_hours = cache_age / 3600
            
            print(f"Cache File: {cache_file}")
            print(f"Cache Age: {cache_age_hours:.1f} hours")
            print(f"Cached Provider: {cache_data.get('recommended_provider', 'Unknown')}")
            
            if cache_age < config['cache_duration_hours'] * 3600:
                print("Status: ✅ Cache is valid and will be used")
            else:
                print("Status: ⏰ Cache is expired - will benchmark on next startup")
                
        except Exception as e:
            print(f"Cache File: {cache_file} (error reading: {e})")
    else:
        print("Cache File: No cache file found - will benchmark on next startup")


def main():
    """Main entry point for benchmark frequency configuration."""
    parser = argparse.ArgumentParser(
        description="Configure TTS benchmark frequency",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--frequency",
        choices=["daily", "weekly", "monthly", "manually"],
        help="Set benchmark frequency non-interactively"
    )
    
    parser.add_argument(
        "--show-current",
        action="store_true",
        help="Show current configuration and exit"
    )
    
    args = parser.parse_args()
    
    # Show current configuration if requested
    if args.show_current:
        show_current_configuration()
        return
    
    # Non-interactive mode
    if args.frequency:
        if save_configuration(args.frequency):
            descriptions = get_frequency_descriptions()
            print(f"✅ Benchmark frequency set to: {descriptions[args.frequency]['name']}")
            print(f"   Cache duration: {descriptions[args.frequency]['duration']}")
            print(f"   Configuration saved to .env file")
        else:
            print("❌ Failed to save configuration")
            sys.exit(1)
        return
    
    # Interactive mode
    print("🔧 Kokoro TTS Benchmark Frequency Configuration")
    print("This tool helps you configure how often the system should benchmark your hardware.")
    
    selected_frequency = interactive_configuration()
    
    if selected_frequency:
        if save_configuration(selected_frequency):
            descriptions = get_frequency_descriptions()
            print(f"\n✅ Configuration saved successfully!")
            print(f"   Benchmark frequency: {descriptions[selected_frequency]['name']}")
            print(f"   Cache duration: {descriptions[selected_frequency]['duration']}")
            print(f"   Configuration saved to .env file")
            print()
            print("🚀 Next steps:")
            print("   • Restart the TTS server to apply the new settings")
            print("   • The system will use cached results until the next benchmark")
            print("   • You can run this script again anytime to change settings")
        else:
            print("❌ Failed to save configuration")
            sys.exit(1)


if __name__ == "__main__":
    main() 