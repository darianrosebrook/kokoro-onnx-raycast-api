"""
Cache Cleanup Utility - Smart Storage Management for Temporary Files

This module provides intelligent cache cleanup mechanisms to prevent storage bloat
from temporary files, CoreML compilation artifacts, and other cache-based operations.
It includes automatic cleanup policies, storage monitoring, and safe file removal.

## Features

### Automatic Cleanup Policies
- **Age-based cleanup**: Remove files older than configurable thresholds
- **Size-based cleanup**: Remove oldest files when cache exceeds size limits
- **Pattern-based cleanup**: Remove specific file types and patterns
- **Safe removal**: Validate files before deletion with error handling

### Storage Monitoring
- **Cache size tracking**: Monitor total cache directory size
- **File count limits**: Prevent excessive file accumulation
- **Performance impact**: Minimal overhead during cleanup operations

### Integration Points
- **Startup cleanup**: Automatic cleanup during application startup
- **Periodic cleanup**: Background cleanup during operation
- **Manual cleanup**: On-demand cleanup via API or CLI

@author @darianrosebrook
@version 1.0.0
@since 2025-07-09
@license MIT
"""
import os
import shutil
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import tempfile
import glob

logger = logging.getLogger(__name__)

class CacheCleanupManager:
    """
    Intelligent cache cleanup manager with configurable policies.
    
    This class provides comprehensive cache management including age-based cleanup,
    size-based limits, and pattern-based file removal with safety checks.
    """
    
    def __init__(self, cache_dir: str = ".cache"):
        """
        Initialize cache cleanup manager.
        
        @param cache_dir: Path to cache directory relative to project root
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Default cleanup policies
        self.policies = {
            'max_age_hours': 24,           # Remove files older than 24 hours
            'max_size_mb': 500,            # Max cache size in MB
            'max_temp_dirs': 10,           # Max temporary directories
            'max_log_files': 20,           # Max log files to keep
            'cleanup_patterns': [          # Patterns to clean up
                'tmp*',
                '*.tmp',
                '*.log.*',
                'benchmark_*.log',
                'coreml_context_*'
            ]
        }
        
    def get_cache_stats(self) -> Dict[str, any]:
        """
        Get comprehensive cache statistics.
        
        @returns Dictionary with cache size, file counts, and other metrics
        """
        try:
            total_size = 0
            file_count = 0
            dir_count = 0
            temp_dirs = 0
            
            for item in self.cache_dir.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
                elif item.is_dir():
                    dir_count += 1
                    if item.name.startswith('tmp'):
                        temp_dirs += 1
            
            return {
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count,
                'dir_count': dir_count,
                'temp_dirs': temp_dirs,
                'cache_path': str(self.cache_dir.absolute()),
                'needs_cleanup': self._needs_cleanup(total_size, temp_dirs)
            }
        except Exception as e:
            logger.error(f"❌ Error getting cache stats: {e}")
            return {'error': str(e)}
    
    def _needs_cleanup(self, total_size: int, temp_dirs: int) -> bool:
        """Check if cache needs cleanup based on policies."""
        size_mb = total_size / (1024 * 1024)
        return (
            size_mb > self.policies['max_size_mb'] or
            temp_dirs > self.policies['max_temp_dirs']
        )
    
    def cleanup_by_age(self, max_age_hours: Optional[int] = None) -> Dict[str, any]:
        """
        Remove files older than specified age.
        
        @param max_age_hours: Maximum age in hours (uses policy default if None)
        @returns Cleanup statistics
        """
        max_age = max_age_hours or self.policies['max_age_hours']
        cutoff_time = time.time() - (max_age * 3600)
        
        removed_files = 0
        removed_dirs = 0
        freed_space = 0
        errors = []
        
        try:
            for item in self.cache_dir.rglob('*'):
                try:
                    if item.stat().st_mtime < cutoff_time:
                        if item.is_file():
                            freed_space += item.stat().st_size
                            item.unlink()
                            removed_files += 1
                        elif item.is_dir() and not any(item.iterdir()):
                            # Remove empty directories
                            item.rmdir()
                            removed_dirs += 1
                except Exception as e:
                    errors.append(f"Error removing {item}: {e}")
                    continue
                    
        except Exception as e:
            errors.append(f"Error during age cleanup: {e}")
        
        logger.info(f"🧹 Age cleanup: removed {removed_files} files, {removed_dirs} dirs, freed {freed_space/1024/1024:.1f}MB")
        
        return {
            'removed_files': removed_files,
            'removed_dirs': removed_dirs,
            'freed_space_mb': round(freed_space / (1024 * 1024), 2),
            'errors': errors
        }
    
    def cleanup_temp_dirs(self) -> Dict[str, any]:
        """
        Remove temporary directories (tmp* pattern).
        
        @returns Cleanup statistics
        """
        removed_dirs = 0
        freed_space = 0
        errors = []
        
        try:
            temp_dirs = list(self.cache_dir.glob('tmp*'))
            
            # Keep only the most recent temp directories
            if len(temp_dirs) > self.policies['max_temp_dirs']:
                # Sort by modification time, keep newest
                temp_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                dirs_to_remove = temp_dirs[self.policies['max_temp_dirs']:]
                
                for temp_dir in dirs_to_remove:
                    try:
                        # Calculate size before removal
                        dir_size = sum(f.stat().st_size for f in temp_dir.rglob('*') if f.is_file())
                        
                        shutil.rmtree(temp_dir)
                        removed_dirs += 1
                        freed_space += dir_size
                        
                    except Exception as e:
                        errors.append(f"Error removing temp dir {temp_dir}: {e}")
                        continue
                        
        except Exception as e:
            errors.append(f"Error during temp dir cleanup: {e}")
        
        logger.info(f"🧹 Temp dir cleanup: removed {removed_dirs} dirs, freed {freed_space/1024/1024:.1f}MB")
        
        return {
            'removed_dirs': removed_dirs,
            'freed_space_mb': round(freed_space / (1024 * 1024), 2),
            'errors': errors
        }
    
    def cleanup_by_size(self) -> Dict[str, any]:
        """
        Remove oldest files when cache exceeds size limit.
        
        @returns Cleanup statistics
        """
        stats = self.get_cache_stats()
        
        if stats.get('total_size_mb', 0) <= self.policies['max_size_mb']:
            return {
                'removed_files': 0,
                'freed_space_mb': 0,
                'message': 'Cache size within limits'
            }
        
        # Get all files sorted by age (oldest first)
        files_by_age = []
        try:
            for item in self.cache_dir.rglob('*'):
                if item.is_file():
                    files_by_age.append((item.stat().st_mtime, item))
        except Exception as e:
            logger.error(f"❌ Error collecting files for size cleanup: {e}")
            return {'error': str(e)}
        
        files_by_age.sort()  # Oldest first
        
        removed_files = 0
        freed_space = 0
        current_size = stats['total_size_mb']
        target_size = self.policies['max_size_mb'] * 0.8  # Clean to 80% of limit
        
        for mtime, file_path in files_by_age:
            if current_size <= target_size:
                break
                
            try:
                file_size = file_path.stat().st_size
                file_path.unlink()
                
                removed_files += 1
                freed_space += file_size
                current_size -= file_size / (1024 * 1024)
                
            except Exception as e:
                logger.warning(f"⚠️ Error removing file {file_path}: {e}")
                continue
        
        logger.info(f"🧹 Size cleanup: removed {removed_files} files, freed {freed_space/1024/1024:.1f}MB")
        
        return {
            'removed_files': removed_files,
            'freed_space_mb': round(freed_space / (1024 * 1024), 2),
            'target_size_mb': target_size,
            'current_size_mb': current_size
        }
    
    def cleanup_patterns(self, patterns: Optional[List[str]] = None) -> Dict[str, any]:
        """
        Remove files matching specific patterns.
        
        @param patterns: List of glob patterns to match (uses policy defaults if None)
        @returns Cleanup statistics
        """
        patterns = patterns or self.policies['cleanup_patterns']
        
        removed_files = 0
        freed_space = 0
        errors = []
        
        for pattern in patterns:
            try:
                for item in self.cache_dir.rglob(pattern):
                    try:
                        if item.is_file():
                            freed_space += item.stat().st_size
                            item.unlink()
                            removed_files += 1
                        elif item.is_dir() and not any(item.iterdir()):
                            # Remove empty directories
                            item.rmdir()
                            
                    except Exception as e:
                        errors.append(f"Error removing {item}: {e}")
                        continue
                        
            except Exception as e:
                errors.append(f"Error processing pattern {pattern}: {e}")
                continue
        
        logger.info(f"🧹 Pattern cleanup: removed {removed_files} files, freed {freed_space/1024/1024:.1f}MB")
        
        return {
            'removed_files': removed_files,
            'freed_space_mb': round(freed_space / (1024 * 1024), 2),
            'patterns_processed': len(patterns),
            'errors': errors
        }
    
    def full_cleanup(self) -> Dict[str, any]:
        """
        Perform comprehensive cache cleanup using all policies.
        
        @returns Combined cleanup statistics
        """
        logger.info("🧹 Starting comprehensive cache cleanup...")
        
        initial_stats = self.get_cache_stats()
        
        # Run all cleanup methods
        age_result = self.cleanup_by_age()
        temp_result = self.cleanup_temp_dirs()
        size_result = self.cleanup_by_size()
        pattern_result = self.cleanup_patterns()
        
        # Clean up empty directories
        self._cleanup_empty_dirs()
        
        final_stats = self.get_cache_stats()
        
        total_freed = (
            age_result.get('freed_space_mb', 0) +
            temp_result.get('freed_space_mb', 0) +
            size_result.get('freed_space_mb', 0) +
            pattern_result.get('freed_space_mb', 0)
        )
        
        logger.info(f"🎉 Cache cleanup completed: freed {total_freed:.1f}MB")
        
        return {
            'initial_size_mb': initial_stats.get('total_size_mb', 0),
            'final_size_mb': final_stats.get('total_size_mb', 0),
            'total_freed_mb': total_freed,
            'cleanup_results': {
                'age': age_result,
                'temp_dirs': temp_result,
                'size': size_result,
                'patterns': pattern_result
            }
        }
    
    def _cleanup_empty_dirs(self):
        """Remove empty directories in cache."""
        try:
            # Get all directories, sorted by depth (deepest first)
            dirs = []
            for item in self.cache_dir.rglob('*'):
                if item.is_dir():
                    dirs.append(item)
            
            # Sort by depth (deepest first) to remove empty subdirs first
            dirs.sort(key=lambda x: len(x.parts), reverse=True)
            
            for dir_path in dirs:
                try:
                    if dir_path.exists() and not any(dir_path.iterdir()):
                        dir_path.rmdir()
                except Exception:
                    # Ignore errors for non-empty or protected directories
                    pass
                    
        except Exception as e:
            logger.debug(f"⚠️ Error during empty dir cleanup: {e}")

# Global instance for easy access
cache_manager = CacheCleanupManager()

def cleanup_cache(aggressive: bool = False) -> Dict[str, any]:
    """
    Convenient function to perform cache cleanup.
    
    @param aggressive: If True, uses more aggressive cleanup policies
    @returns Cleanup statistics
    """
    if aggressive:
        # More aggressive cleanup for storage-critical situations
        original_policies = cache_manager.policies.copy()
        cache_manager.policies.update({
            'max_age_hours': 12,      # 12 hours instead of 24
            'max_size_mb': 250,       # 250MB instead of 500MB
            'max_temp_dirs': 5,       # 5 temp dirs instead of 10
        })
        
        result = cache_manager.full_cleanup()
        
        # Restore original policies
        cache_manager.policies = original_policies
        
        return result
    else:
        return cache_manager.full_cleanup()

def get_cache_info() -> Dict[str, any]:
    """
    Get current cache information.
    
    @returns Cache statistics and status
    """
    return cache_manager.get_cache_stats() 