#!/usr/bin/env python3
"""
Predictive Caching System for Kokoro TTS API.

This script analyzes usage patterns and pre-generates audio for common phrases,
improving response times for frequently requested content.
"""
import asyncio
import aiohttp
import json
import time
import hashlib
import sqlite3
import statistics
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
from collections import defaultdict, Counter

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PhraseUsage:
    """Phrase usage statistics."""
    phrase: str
    count: int
    last_used: float
    avg_response_time: float
    voice: str
    speed: float
    lang: str

@dataclass
class CacheEntry:
    """Cache entry for pre-generated audio."""
    phrase_hash: str
    phrase: str
    voice: str
    speed: float
    lang: str
    audio_data: bytes
    created_at: float
    access_count: int
    last_accessed: float

@dataclass
class CacheStats:
    """Cache statistics."""
    total_entries: int
    hit_rate: float
    miss_rate: float
    total_hits: int
    total_misses: int
    cache_size_mb: float
    most_requested: List[Tuple[str, int]]

class PredictiveCache:
    """Predictive caching system for TTS phrases."""
    
    def __init__(self, db_path: str = "predictive_cache.db", api_url: str = "http://localhost:8000"):
        self.db_path = db_path
        self.api_url = api_url
        self.usage_stats: Dict[str, PhraseUsage] = {}
        self.cache_entries: Dict[str, CacheEntry] = {}
        self.phrase_patterns: Dict[str, int] = defaultdict(int)
        
        # Cache configuration
        self.max_cache_size_mb = 100  # 100MB cache limit
        self.min_usage_count = 3  # Minimum usage count to cache
        self.cache_ttl_hours = 24  # Cache TTL in hours
        self.batch_size = 10  # Number of phrases to pre-generate per batch
        
        # Initialize database
        self._init_database()
        self._load_cache()
    
    def _init_database(self):
        """Initialize SQLite database for usage tracking."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create usage tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS phrase_usage (
                phrase_hash TEXT PRIMARY KEY,
                phrase TEXT NOT NULL,
                voice TEXT NOT NULL,
                speed REAL NOT NULL,
                lang TEXT NOT NULL,
                count INTEGER DEFAULT 1,
                last_used REAL NOT NULL,
                avg_response_time REAL DEFAULT 0.0,
                created_at REAL DEFAULT (julianday('now'))
            )
        ''')
        
        # Create cache entries table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache_entries (
                phrase_hash TEXT PRIMARY KEY,
                phrase TEXT NOT NULL,
                voice TEXT NOT NULL,
                speed REAL NOT NULL,
                lang TEXT NOT NULL,
                audio_data BLOB NOT NULL,
                created_at REAL NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed REAL NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _load_cache(self):
        """Load cache entries from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Load usage statistics
        cursor.execute('SELECT * FROM phrase_usage')
        for row in cursor.fetchall():
            phrase_hash, phrase, voice, speed, lang, count, last_used, avg_response_time, created_at = row
            self.usage_stats[phrase_hash] = PhraseUsage(
                phrase=phrase,
                count=count,
                last_used=last_used,
                avg_response_time=avg_response_time,
                voice=voice,
                speed=speed,
                lang=lang
            )
        
        # Load cache entries
        cursor.execute('SELECT * FROM cache_entries')
        for row in cursor.fetchall():
            phrase_hash, phrase, voice, speed, lang, audio_data, created_at, access_count, last_accessed = row
            self.cache_entries[phrase_hash] = CacheEntry(
                phrase_hash=phrase_hash,
                phrase=phrase,
                voice=voice,
                speed=speed,
                lang=lang,
                audio_data=audio_data,
                created_at=created_at,
                access_count=access_count,
                last_accessed=last_accessed
            )
        
        conn.close()
        logger.info(f"Loaded {len(self.usage_stats)} usage stats and {len(self.cache_entries)} cache entries")
    
    def _generate_phrase_hash(self, phrase: str, voice: str, speed: float, lang: str) -> str:
        """Generate hash for phrase with parameters."""
        content = f"{phrase}|{voice}|{speed}|{lang}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def record_usage(self, phrase: str, voice: str, speed: float, lang: str, response_time: float):
        """Record phrase usage for analysis."""
        phrase_hash = self._generate_phrase_hash(phrase, voice, speed, lang)
        current_time = time.time()
        
        if phrase_hash in self.usage_stats:
            # Update existing usage
            usage = self.usage_stats[phrase_hash]
            usage.count += 1
            usage.last_used = current_time
            # Update average response time
            usage.avg_response_time = (usage.avg_response_time * (usage.count - 1) + response_time) / usage.count
        else:
            # Create new usage record
            self.usage_stats[phrase_hash] = PhraseUsage(
                phrase=phrase,
                count=1,
                last_used=current_time,
                avg_response_time=response_time,
                voice=voice,
                speed=speed,
                lang=lang
            )
        
        # Update database
        self._update_usage_database(phrase_hash, self.usage_stats[phrase_hash])
        
        # Track phrase patterns for analysis
        self.phrase_patterns[phrase] += 1
    
    def _update_usage_database(self, phrase_hash: str, usage: PhraseUsage):
        """Update usage statistics in database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO phrase_usage 
            (phrase_hash, phrase, voice, speed, lang, count, last_used, avg_response_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (phrase_hash, usage.phrase, usage.voice, usage.speed, usage.lang, 
              usage.count, usage.last_used, usage.avg_response_time))
        
        conn.commit()
        conn.close()
    
    def get_cached_audio(self, phrase: str, voice: str, speed: float, lang: str) -> Optional[bytes]:
        """Get cached audio for phrase."""
        phrase_hash = self._generate_phrase_hash(phrase, voice, speed, lang)
        
        if phrase_hash in self.cache_entries:
            entry = self.cache_entries[phrase_hash]
            
            # Check TTL
            if time.time() - entry.created_at > self.cache_ttl_hours * 3600:
                # Expired, remove from cache
                del self.cache_entries[phrase_hash]
                self._remove_cache_entry(phrase_hash)
                return None
            
            # Update access statistics
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._update_cache_entry(entry)
            
            return entry.audio_data
        
        return None
    
    def cache_audio(self, phrase: str, voice: str, speed: float, lang: str, audio_data: bytes):
        """Cache audio data for phrase."""
        phrase_hash = self._generate_phrase_hash(phrase, voice, speed, lang)
        current_time = time.time()
        
        entry = CacheEntry(
            phrase_hash=phrase_hash,
            phrase=phrase,
            voice=voice,
            speed=speed,
            lang=lang,
            audio_data=audio_data,
            created_at=current_time,
            access_count=0,
            last_accessed=current_time
        )
        
        self.cache_entries[phrase_hash] = entry
        self._save_cache_entry(entry)
        
        # Check cache size limit
        self._enforce_cache_size_limit()
    
    def _save_cache_entry(self, entry: CacheEntry):
        """Save cache entry to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO cache_entries 
            (phrase_hash, phrase, voice, speed, lang, audio_data, created_at, access_count, last_accessed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (entry.phrase_hash, entry.phrase, entry.voice, entry.speed, entry.lang,
              entry.audio_data, entry.created_at, entry.access_count, entry.last_accessed))
        
        conn.commit()
        conn.close()
    
    def _update_cache_entry(self, entry: CacheEntry):
        """Update cache entry access statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE cache_entries 
            SET access_count = ?, last_accessed = ?
            WHERE phrase_hash = ?
        ''', (entry.access_count, entry.last_accessed, entry.phrase_hash))
        
        conn.commit()
        conn.close()
    
    def _remove_cache_entry(self, phrase_hash: str):
        """Remove cache entry from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM cache_entries WHERE phrase_hash = ?', (phrase_hash,))
        
        conn.commit()
        conn.close()
    
    def _enforce_cache_size_limit(self):
        """Enforce cache size limit by removing least recently used entries."""
        current_size_mb = sum(len(entry.audio_data) for entry in self.cache_entries.values()) / (1024 * 1024)
        
        if current_size_mb > self.max_cache_size_mb:
            # Sort by last accessed time (LRU)
            sorted_entries = sorted(self.cache_entries.items(), key=lambda x: x[1].last_accessed)
            
            # Remove entries until under limit
            for phrase_hash, entry in sorted_entries:
                del self.cache_entries[phrase_hash]
                self._remove_cache_entry(phrase_hash)
                
                current_size_mb = sum(len(e.audio_data) for e in self.cache_entries.values()) / (1024 * 1024)
                if current_size_mb <= self.max_cache_size_mb * 0.8:  # Remove to 80% of limit
                    break
    
    def get_phrases_to_cache(self) -> List[Tuple[str, str, float, str]]:
        """Get list of phrases that should be cached based on usage patterns."""
        candidates = []
        
        for phrase_hash, usage in self.usage_stats.items():
            # Check if phrase meets caching criteria
            if (usage.count >= self.min_usage_count and 
                phrase_hash not in self.cache_entries and
                time.time() - usage.last_used < 7 * 24 * 3600):  # Used within last week
                
                # Calculate caching priority (higher count = higher priority)
                priority = usage.count * (1.0 / (usage.avg_response_time + 1.0))  # Faster responses get higher priority
                candidates.append((usage.phrase, usage.voice, usage.speed, usage.lang, priority))
        
        # Sort by priority and return top candidates
        candidates.sort(key=lambda x: x[4], reverse=True)
        return [(phrase, voice, speed, lang) for phrase, voice, speed, lang, _ in candidates[:self.batch_size]]
    
    async def pre_generate_audio(self, phrases: List[Tuple[str, str, float, str]]) -> int:
        """Pre-generate audio for phrases."""
        generated_count = 0
        
        async with aiohttp.ClientSession() as session:
            for phrase, voice, speed, lang in phrases:
                try:
                    request_data = {
                        "text": phrase,
                        "voice": voice,
                        "speed": speed,
                        "lang": lang,
                        "stream": False,
                        "format": "wav"
                    }
                    
                    start_time = time.time()
                    async with session.post(f"{self.api_url}/v1/audio/speech", json=request_data) as response:
                        if response.status == 200:
                            audio_data = await response.read()
                            self.cache_audio(phrase, voice, speed, lang, audio_data)
                            generated_count += 1
                            logger.info(f"Pre-generated audio for: '{phrase[:50]}...'")
                        else:
                            logger.warning(f"Failed to pre-generate audio for '{phrase[:50]}...': {response.status}")
                
                except Exception as e:
                    logger.error(f"Error pre-generating audio for '{phrase[:50]}...': {e}")
        
        return generated_count
    
    async def run_predictive_caching(self):
        """Run predictive caching process."""
        logger.info("Starting predictive caching process...")
        
        # Get phrases to cache
        phrases_to_cache = self.get_phrases_to_cache()
        
        if not phrases_to_cache:
            logger.info("No phrases need caching")
            return
        
        logger.info(f"Found {len(phrases_to_cache)} phrases to cache")
        
        # Pre-generate audio
        generated_count = await self.pre_generate_audio(phrases_to_cache)
        
        logger.info(f"Pre-generated {generated_count} audio files")
    
    def get_cache_stats(self) -> CacheStats:
        """Get cache statistics."""
        total_hits = sum(entry.access_count for entry in self.cache_entries.values())
        total_misses = len(self.usage_stats) - len(self.cache_entries)
        total_requests = total_hits + total_misses
        
        hit_rate = total_hits / total_requests if total_requests > 0 else 0.0
        miss_rate = 1.0 - hit_rate
        
        cache_size_mb = sum(len(entry.audio_data) for entry in self.cache_entries.values()) / (1024 * 1024)
        
        # Most requested phrases
        most_requested = sorted(
            [(usage.phrase, usage.count) for usage in self.usage_stats.values()],
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return CacheStats(
            total_entries=len(self.cache_entries),
            hit_rate=hit_rate,
            miss_rate=miss_rate,
            total_hits=total_hits,
            total_misses=total_misses,
            cache_size_mb=cache_size_mb,
            most_requested=most_requested
        )
    
    def analyze_usage_patterns(self) -> Dict[str, Any]:
        """Analyze usage patterns for insights."""
        if not self.usage_stats:
            return {"error": "No usage data available"}
        
        # Analyze phrase lengths
        phrase_lengths = [len(usage.phrase) for usage in self.usage_stats.values()]
        
        # Analyze voice usage
        voice_usage = Counter(usage.voice for usage in self.usage_stats.values())
        
        # Analyze speed usage
        speed_usage = Counter(usage.speed for usage in self.usage_stats.values())
        
        # Analyze language usage
        lang_usage = Counter(usage.lang for usage in self.usage_stats.values())
        
        # Analyze response times
        response_times = [usage.avg_response_time for usage in self.usage_stats.values()]
        
        return {
            "total_phrases": len(self.usage_stats),
            "phrase_length_stats": {
                "min": min(phrase_lengths),
                "max": max(phrase_lengths),
                "avg": statistics.mean(phrase_lengths),
                "median": statistics.median(phrase_lengths)
            },
            "voice_usage": dict(voice_usage.most_common()),
            "speed_usage": dict(speed_usage.most_common()),
            "language_usage": dict(lang_usage.most_common()),
            "response_time_stats": {
                "min": min(response_times),
                "max": max(response_times),
                "avg": statistics.mean(response_times),
                "median": statistics.median(response_times)
            }
        }

async def main():
    """Main predictive caching function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Predictive Caching System")
    parser.add_argument("--url", default="http://localhost:8000", help="TTS API base URL")
    parser.add_argument("--db", default="predictive_cache.db", help="Database file path")
    parser.add_argument("--run", action="store_true", help="Run predictive caching process")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--analyze", action="store_true", help="Analyze usage patterns")
    parser.add_argument("--max-size", type=int, default=100, help="Maximum cache size in MB")
    parser.add_argument("--min-usage", type=int, default=3, help="Minimum usage count to cache")
    
    args = parser.parse_args()
    
    # Create cache system
    cache = PredictiveCache(args.db, args.url)
    cache.max_cache_size_mb = args.max_size
    cache.min_usage_count = args.min_usage
    
    if args.stats:
        # Show cache statistics
        stats = cache.get_cache_stats()
        print(f"📊 Cache Statistics:")
        print(f"  Total entries: {stats.total_entries}")
        print(f"  Hit rate: {stats.hit_rate:.2%}")
        print(f"  Miss rate: {stats.miss_rate:.2%}")
        print(f"  Total hits: {stats.total_hits}")
        print(f"  Total misses: {stats.total_misses}")
        print(f"  Cache size: {stats.cache_size_mb:.2f} MB")
        print(f"  Most requested phrases:")
        for phrase, count in stats.most_requested[:5]:
            print(f"    '{phrase[:50]}...': {count} requests")
    
    if args.analyze:
        # Analyze usage patterns
        analysis = cache.analyze_usage_patterns()
        if "error" in analysis:
            print(f"❌ {analysis['error']}")
        else:
            print(f"📈 Usage Pattern Analysis:")
            print(f"  Total phrases: {analysis['total_phrases']}")
            print(f"  Phrase length: {analysis['phrase_length_stats']['avg']:.1f} chars avg")
            print(f"  Most used voice: {max(analysis['voice_usage'].items(), key=lambda x: x[1])}")
            print(f"  Most used speed: {max(analysis['speed_usage'].items(), key=lambda x: x[1])}")
            print(f"  Most used language: {max(analysis['language_usage'].items(), key=lambda x: x[1])}")
            print(f"  Avg response time: {analysis['response_time_stats']['avg']:.2f}ms")
    
    if args.run:
        # Run predictive caching
        await cache.run_predictive_caching()

if __name__ == "__main__":
    asyncio.run(main())
