"""Caching layer for pytest-fastcollect to enable incremental collection."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class CacheStats:
    """Statistics about cache usage."""
    cache_hits: int = 0
    cache_misses: int = 0
    files_parsed: int = 0
    files_from_cache: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.cache_hits + self.cache_misses
        return self.cache_hits / total if total > 0 else 0.0

    def __str__(self) -> str:
        return (f"FastCollect Cache: {self.files_from_cache} files from cache, "
                f"{self.files_parsed} parsed ({self.hit_rate:.1%} hit rate)")


class CollectionCache:
    """Manages persistent cache of parsed test data with file modification times."""

    CACHE_VERSION = "1.0"

    def __init__(self, cache_dir: Path):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory to store cache (typically .pytest_cache/v/fastcollect)
        """
        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "cache.json"
        self.cache_data: Dict[str, Dict[str, Any]] = {}
        self.stats = CacheStats()
        self._load_cache()

    def _load_cache(self):
        """Load cache from disk if it exists."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)

                    # Check cache version
                    if data.get('version') == self.CACHE_VERSION:
                        self.cache_data = data.get('entries', {})
                    else:
                        # Cache version mismatch, start fresh
                        self.cache_data = {}
            except (json.JSONDecodeError, IOError):
                # Corrupted cache, start fresh
                self.cache_data = {}

    def save_cache(self):
        """Save cache to disk."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        cache_structure = {
            'version': self.CACHE_VERSION,
            'entries': self.cache_data
        }

        try:
            with open(self.cache_file, 'w') as f:
                json.dump(cache_structure, f, indent=2)
        except IOError:
            # Silently fail if we can't write cache
            pass

    def get_cached_data(self, file_path: str, current_mtime: float) -> Optional[Dict[str, Any]]:
        """
        Get cached data for a file if it's still valid.

        Args:
            file_path: Absolute path to the file
            current_mtime: Current modification time of the file

        Returns:
            Cached test data if valid, None otherwise
        """
        if file_path not in self.cache_data:
            self.stats.cache_misses += 1
            return None

        cached_entry = self.cache_data[file_path]
        cached_mtime = cached_entry.get('mtime', 0)

        # Check if file has been modified
        if abs(cached_mtime - current_mtime) < 0.01:  # Allow small floating point difference
            self.stats.cache_hits += 1
            self.stats.files_from_cache += 1
            return cached_entry.get('items', [])
        else:
            self.stats.cache_misses += 1
            return None

    def update_cache(self, file_path: str, mtime: float, items: list):
        """
        Update cache with newly parsed data.

        Args:
            file_path: Absolute path to the file
            mtime: Modification time of the file
            items: List of test items found in the file
        """
        self.cache_data[file_path] = {
            'mtime': mtime,
            'items': items
        }
        self.stats.files_parsed += 1

    def merge_with_rust_data(self, rust_metadata: Dict[str, Dict[str, Any]]) -> Tuple[Dict[str, list], bool]:
        """
        Merge Rust-collected metadata with cache.

        Args:
            rust_metadata: Dictionary from Rust collector with {file_path: {mtime: float, items: list}}

        Returns:
            Tuple of (merged data dict, cache_updated flag)
        """
        merged_data = {}
        cache_updated = False

        for file_path, metadata in rust_metadata.items():
            current_mtime = metadata['mtime']
            rust_items = metadata['items']

            # Try to use cached data
            cached_items = self.get_cached_data(file_path, current_mtime)

            if cached_items is not None:
                # Use cached data
                merged_data[file_path] = cached_items
            else:
                # Use newly parsed data and update cache
                merged_data[file_path] = rust_items
                self.update_cache(file_path, current_mtime, rust_items)
                cache_updated = True

        # Remove deleted files from cache
        current_files = set(rust_metadata.keys())
        cached_files = set(self.cache_data.keys())
        deleted_files = cached_files - current_files

        if deleted_files:
            for file_path in deleted_files:
                del self.cache_data[file_path]
            cache_updated = True

        return merged_data, cache_updated

    def clear(self):
        """Clear the entire cache."""
        self.cache_data = {}
        self.stats = CacheStats()
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
            except IOError:
                pass
