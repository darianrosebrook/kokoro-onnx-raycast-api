#!/usr/bin/env python3
"""
Temporary Files Cleanup Script

This script manages cleanup of temporary files, logs, and test artifacts
to keep the development environment clean and prevent disk space issues.

Features:
- Cleans up old log files (keeps latest 10)
- Removes test audio files older than 7 days
- Removes debug files older than 3 days
- Creates proper directory structure if missing
- Safe operation with confirmation prompts

Usage:
    python scripts/cleanup_temp_files.py [--dry-run] [--force] [--days N]
"""

import os
import sys
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta
import shutil


def setup_temp_directories():
    """Create temp directory structure if it doesn't exist."""
    base_dir = Path(".")
    temp_dirs = [
        "temp/logs",
        "temp/test-audio", 
        "temp/debug-files",
        "temp/reports"
    ]
    
    for temp_dir in temp_dirs:
        dir_path = base_dir / temp_dir
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Ensured directory exists: {temp_dir}")


def cleanup_old_files(directory, pattern, max_files=None, max_age_days=None, dry_run=False):
    """
    Clean up old files in a directory.
    
    Args:
        directory (Path): Directory to clean
        pattern (str): File pattern to match (glob pattern)
        max_files (int): Keep only this many newest files
        max_age_days (int): Remove files older than this many days
        dry_run (bool): If True, only show what would be removed
    """
    if not directory.exists():
        print(f"⚠️  Directory does not exist: {directory}")
        return
    
    files = list(directory.glob(pattern))
    if not files:
        print(f"📁 No files found matching {pattern} in {directory}")
        return
    
    # Sort by modification time (newest first)
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    
    to_remove = []
    
    # Apply max_files limit
    if max_files and len(files) > max_files:
        to_remove.extend(files[max_files:])
        print(f"📋 Found {len(files)} files, keeping newest {max_files}")
    
    # Apply age limit
    if max_age_days:
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        old_files = [f for f in files if f.stat().st_mtime < cutoff_time]
        to_remove.extend(old_files)
        print(f"⏰ Found {len(old_files)} files older than {max_age_days} days")
    
    # Remove duplicates
    to_remove = list(set(to_remove))
    
    if not to_remove:
        print(f"✅ No cleanup needed for {pattern} in {directory}")
        return
    
    total_size = sum(f.stat().st_size for f in to_remove)
    print(f"🗑️  Would remove {len(to_remove)} files ({total_size / 1024 / 1024:.1f} MB)")
    
    for file_path in to_remove:
        file_age = datetime.fromtimestamp(file_path.stat().st_mtime)
        file_size = file_path.stat().st_size / 1024  # KB
        
        if dry_run:
            print(f"   [DRY RUN] Would remove: {file_path.name} ({file_size:.1f} KB, {file_age.strftime('%Y-%m-%d %H:%M')})")
        else:
            try:
                file_path.unlink()
                print(f"   ✓ Removed: {file_path.name} ({file_size:.1f} KB)")
            except Exception as e:
                print(f"   ❌ Failed to remove {file_path.name}: {e}")


def move_loose_files_to_temp():
    """Move loose temporary files from root to temp directories."""
    base_dir = Path(".")
    moved_count = 0
    
    # Define file patterns and their target directories
    file_mappings = [
        ("*.log", "temp/logs"),
        ("test_*.pcm", "temp/test-audio"),
        ("test_*.wav", "temp/test-audio"), 
        ("test-*.txt", "temp/test-audio"),
        ("debug_*.py", "temp/debug-files"),
        ("server*.log", "temp/logs"),
    ]
    
    for pattern, target_dir in file_mappings:
        target_path = base_dir / target_dir
        target_path.mkdir(parents=True, exist_ok=True)
        
        for file_path in base_dir.glob(pattern):
            if file_path.is_file() and not str(file_path).startswith("temp/"):
                target_file = target_path / file_path.name
                try:
                    # If target exists, add timestamp to avoid conflicts
                    if target_file.exists():
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        stem = target_file.stem
                        suffix = target_file.suffix
                        target_file = target_path / f"{stem}_{timestamp}{suffix}"
                    
                    shutil.move(str(file_path), str(target_file))
                    print(f"📦 Moved: {file_path.name} → {target_dir}")
                    moved_count += 1
                except Exception as e:
                    print(f"❌ Failed to move {file_path.name}: {e}")
    
    if moved_count == 0:
        print("✅ No loose temporary files found to move")
    else:
        print(f"📦 Moved {moved_count} files to temp directories")


def main():
    parser = argparse.ArgumentParser(description="Clean up temporary files and logs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without actually removing")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts")
    parser.add_argument("--log-days", type=int, default=7, help="Remove log files older than N days (default: 7)")
    parser.add_argument("--test-days", type=int, default=3, help="Remove test files older than N days (default: 3)")
    parser.add_argument("--max-logs", type=int, default=10, help="Keep only N newest log files (default: 10)")
    
    args = parser.parse_args()
    
    print("🧹 Kokoro TTS Temporary Files Cleanup")
    print("=" * 40)
    
    # Setup directories
    setup_temp_directories()
    print()
    
    # Move loose files first
    print("📦 Moving loose temporary files...")
    move_loose_files_to_temp()
    print()
    
    # Define cleanup rules
    cleanup_rules = [
        {
            "directory": Path("temp/logs"),
            "pattern": "*.log",
            "max_files": args.max_logs,
            "max_age_days": args.log_days,
            "description": "Log files"
        },
        {
            "directory": Path("temp/test-audio"), 
            "pattern": "*.pcm",
            "max_age_days": args.test_days,
            "description": "Test PCM audio files"
        },
        {
            "directory": Path("temp/test-audio"),
            "pattern": "*.wav", 
            "max_age_days": args.test_days,
            "description": "Test WAV audio files"
        },
        {
            "directory": Path("temp/debug-files"),
            "pattern": "*.py",
            "max_age_days": args.test_days,
            "description": "Debug Python files"
        },
        {
            "directory": Path("logs"),
            "pattern": "*.log",
            "max_files": args.max_logs,
            "description": "Application logs"
        }
    ]
    
    # Show what will be cleaned
    print("🔍 Cleanup plan:")
    for rule in cleanup_rules:
        print(f"   📁 {rule['description']} in {rule['directory']}")
        if rule.get('max_files'):
            print(f"      • Keep newest {rule['max_files']} files")
        if rule.get('max_age_days'):
            print(f"      • Remove files older than {rule['max_age_days']} days")
    print()
    
    # Confirm unless forced or dry run
    if not args.force and not args.dry_run:
        response = input("Continue with cleanup? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            print("Cleanup cancelled.")
            return
    
    # Perform cleanup
    print("🧹 Starting cleanup...")
    for rule in cleanup_rules:
        print(f"\n📂 Cleaning {rule['description']}...")
        cleanup_old_files(
            directory=rule["directory"],
            pattern=rule["pattern"],
            max_files=rule.get("max_files"),
            max_age_days=rule.get("max_age_days"),
            dry_run=args.dry_run
        )
    
    print("\n✅ Cleanup completed!")
    
    if args.dry_run:
        print("🔍 This was a dry run. Run without --dry-run to actually remove files.")


if __name__ == "__main__":
    main()
