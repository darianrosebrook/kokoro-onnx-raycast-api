#!/usr/bin/env python3
"""
Cache Cleanup Command Line Utility

A standalone utility for cleaning up cache files, temporary directories,
and other storage-consuming artifacts created during TTS operations.

Usage:
    python scripts/cleanup_cache.py [options]

Options:
    --aggressive    Use aggressive cleanup policies
    --stats         Show cache statistics only
    --help          Show this help message

@author @darianrosebrook
@version 1.0.0
@since 2025-07-09
"""
import sys
import os
import argparse
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api.utils.cache_cleanup import cleanup_cache, get_cache_info

def main():
    parser = argparse.ArgumentParser(
        description="Cache cleanup utility for Kokoro TTS API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/cleanup_cache.py --stats
    python scripts/cleanup_cache.py --aggressive
    python scripts/cleanup_cache.py
        """
    )
    
    parser.add_argument(
        '--aggressive', 
        action='store_true',
        help='Use aggressive cleanup policies (smaller limits, shorter retention)'
    )
    
    parser.add_argument(
        '--stats', 
        action='store_true',
        help='Show cache statistics only, without cleanup'
    )
    
    parser.add_argument(
        '--json', 
        action='store_true',
        help='Output results in JSON format'
    )
    
    args = parser.parse_args()
    
    try:
        # Get cache statistics
        cache_info = get_cache_info()
        
        if args.stats:
            # Show statistics only
            if args.json:
                print(json.dumps(cache_info, indent=2))
            else:
                print("\n🗂️  Cache Statistics:")
                print(f"   Total Size: {cache_info.get('total_size_mb', 0):.1f} MB")
                print(f"   File Count: {cache_info.get('file_count', 0):,}")
                print(f"   Directory Count: {cache_info.get('dir_count', 0):,}")
                print(f"   Temp Directories: {cache_info.get('temp_dirs', 0)}")
                print(f"   Cache Path: {cache_info.get('cache_path', 'Unknown')}")
                print(f"   Needs Cleanup: {'Yes' if cache_info.get('needs_cleanup', False) else 'No'}")
                
                if cache_info.get('needs_cleanup', False):
                    print(f"\n⚠️  Cleanup recommended!")
                    print(f"   Run: python scripts/cleanup_cache.py")
                else:
                    print(f"\n✅ Cache size is within acceptable limits")
                    
        else:
            # Perform cleanup
            print(f"\n🧹 Starting cache cleanup...")
            
            if args.aggressive:
                print("   Using aggressive cleanup policies")
            
            cleanup_result = cleanup_cache(aggressive=args.aggressive)
            
            if args.json:
                print(json.dumps(cleanup_result, indent=2))
            else:
                print(f"\n🎉 Cache cleanup completed!")
                print(f"   Initial Size: {cleanup_result.get('initial_size_mb', 0):.1f} MB")
                print(f"   Final Size: {cleanup_result.get('final_size_mb', 0):.1f} MB")
                print(f"   Total Freed: {cleanup_result.get('total_freed_mb', 0):.1f} MB")
                
                # Show detailed results
                results = cleanup_result.get('cleanup_results', {})
                if results:
                    print(f"\n📊 Cleanup Details:")
                    for method, result in results.items():
                        if isinstance(result, dict):
                            freed = result.get('freed_space_mb', 0)
                            if freed > 0:
                                print(f"   {method.title()}: {freed:.1f} MB freed")
                                
                print(f"\n✅ Cache cleanup successful!")
                
    except Exception as e:
        if args.json:
            print(json.dumps({"error": str(e)}, indent=2))
        else:
            print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 