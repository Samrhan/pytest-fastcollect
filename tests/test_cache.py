"""
Comprehensive test suite for cache.py module.

Tests the CollectionCache class and CacheStats dataclass with:
- Unit tests for all methods
- Edge cases and error handling
- Cache invalidation logic
- File operations and persistence
"""

import json
import tempfile
import pytest
from pathlib import Path
import time

from pytest_fastcollect.cache import CollectionCache, CacheStats


class TestCacheStats:
    """Test CacheStats dataclass."""

    @pytest.mark.unit
    def test_cache_stats_initialization(self):
        """Test CacheStats initializes with zeros."""
        stats = CacheStats()
        assert stats.cache_hits == 0
        assert stats.cache_misses == 0
        assert stats.files_parsed == 0
        assert stats.files_from_cache == 0

    @pytest.mark.unit
    def test_cache_stats_hit_rate_empty(self):
        """Test hit rate calculation with no data."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    @pytest.mark.unit
    def test_cache_stats_hit_rate_all_hits(self):
        """Test hit rate with all cache hits."""
        stats = CacheStats(cache_hits=10, cache_misses=0)
        assert stats.hit_rate == 1.0

    @pytest.mark.unit
    def test_cache_stats_hit_rate_all_misses(self):
        """Test hit rate with all cache misses."""
        stats = CacheStats(cache_hits=0, cache_misses=10)
        assert stats.hit_rate == 0.0

    @pytest.mark.unit
    def test_cache_stats_hit_rate_mixed(self):
        """Test hit rate with mixed hits and misses."""
        stats = CacheStats(cache_hits=7, cache_misses=3)
        assert stats.hit_rate == 0.7

    @pytest.mark.unit
    def test_cache_stats_string_representation(self):
        """Test string representation of cache stats."""
        stats = CacheStats(
            cache_hits=7,
            cache_misses=3,
            files_parsed=3,
            files_from_cache=7
        )
        result = str(stats)
        assert "7 files from cache" in result
        assert "3 parsed" in result
        assert "70.0% hit rate" in result


class TestCollectionCacheInitialization:
    """Test CollectionCache initialization and setup."""

    @pytest.mark.unit
    def test_cache_initialization(self):
        """Test cache initializes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            assert cache.cache_dir == cache_dir
            assert cache.cache_file == cache_dir / "cache.json"
            assert isinstance(cache.cache_data, dict)
            assert isinstance(cache.stats, CacheStats)

    @pytest.mark.unit
    def test_cache_initialization_creates_empty_cache(self):
        """Test cache starts empty if no cache file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            assert len(cache.cache_data) == 0

    @pytest.mark.unit
    def test_cache_loads_existing_cache(self):
        """Test cache loads existing cache file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_file = cache_dir / "cache.json"

            # Create a cache file
            cache_content = {
                "version": "1.0",
                "entries": {
                    "/path/to/test.py": {
                        "mtime": 1234567890.0,
                        "items": [{"name": "test_foo"}]
                    }
                }
            }
            cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(cache_content, f)

            # Load cache
            cache = CollectionCache(cache_dir)

            assert len(cache.cache_data) == 1
            assert "/path/to/test.py" in cache.cache_data

    @pytest.mark.unit
    def test_cache_ignores_wrong_version(self):
        """Test cache ignores cache file with wrong version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_file = cache_dir / "cache.json"

            # Create a cache file with wrong version
            cache_content = {
                "version": "99.0",
                "entries": {
                    "/path/to/test.py": {
                        "mtime": 1234567890.0,
                        "items": [{"name": "test_foo"}]
                    }
                }
            }
            cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(cache_content, f)

            # Load cache
            cache = CollectionCache(cache_dir)

            # Should start with empty cache
            assert len(cache.cache_data) == 0

    @pytest.mark.unit
    def test_cache_handles_corrupted_json(self):
        """Test cache handles corrupted JSON gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache_file = cache_dir / "cache.json"

            # Create a corrupted cache file
            cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_file, 'w') as f:
                f.write("{ this is not valid json }")

            # Load cache - should not crash
            cache = CollectionCache(cache_dir)

            # Should start with empty cache
            assert len(cache.cache_data) == 0


class TestCollectionCacheSave:
    """Test cache saving functionality."""

    @pytest.mark.unit
    def test_save_cache_creates_directory(self):
        """Test save_cache creates directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "subdir" / "cache"
            cache = CollectionCache(cache_dir)

            # Add some data
            cache.cache_data["/test.py"] = {
                "mtime": 1234567890.0,
                "items": []
            }

            # Save cache
            cache.save_cache()

            # Directory should be created
            assert cache_dir.exists()
            assert cache.cache_file.exists()

    @pytest.mark.unit
    def test_save_cache_writes_correct_format(self):
        """Test save_cache writes correct JSON format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Add test data
            cache.cache_data["/test.py"] = {
                "mtime": 1234567890.0,
                "items": [{"name": "test_foo", "line": 10}]
            }

            # Save cache
            cache.save_cache()

            # Read back and verify
            with open(cache.cache_file, 'r') as f:
                data = json.load(f)

            assert data["version"] == "1.0"
            assert "/test.py" in data["entries"]
            assert data["entries"]["/test.py"]["mtime"] == 1234567890.0

    @pytest.mark.unit
    def test_save_cache_handles_write_errors(self):
        """Test save_cache handles write errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use a path that can't be written to
            cache_dir = Path("/nonexistent/invalid/path")
            cache = CollectionCache(cache_dir)

            # Should not crash
            cache.save_cache()


class TestCollectionCacheGetData:
    """Test cache data retrieval."""

    @pytest.mark.unit
    def test_get_cached_data_miss(self):
        """Test get_cached_data returns None on cache miss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            result = cache.get_cached_data("/nonexistent.py", 1234567890.0)

            assert result is None
            assert cache.stats.cache_misses == 1
            assert cache.stats.cache_hits == 0

    @pytest.mark.unit
    def test_get_cached_data_hit(self):
        """Test get_cached_data returns data on cache hit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Add data to cache
            test_items = [{"name": "test_foo", "line": 10}]
            cache.cache_data["/test.py"] = {
                "mtime": 1234567890.0,
                "items": test_items
            }

            # Get cached data with same mtime
            result = cache.get_cached_data("/test.py", 1234567890.0)

            assert result == test_items
            assert cache.stats.cache_hits == 1
            assert cache.stats.cache_misses == 0
            assert cache.stats.files_from_cache == 1

    @pytest.mark.unit
    def test_get_cached_data_stale(self):
        """Test get_cached_data returns None for stale cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Add data to cache with old mtime
            cache.cache_data["/test.py"] = {
                "mtime": 1234567890.0,
                "items": [{"name": "test_foo"}]
            }

            # Get with newer mtime (file was modified)
            result = cache.get_cached_data("/test.py", 1234567899.0)

            assert result is None
            assert cache.stats.cache_misses == 1
            assert cache.stats.cache_hits == 0

    @pytest.mark.unit
    def test_get_cached_data_mtime_tolerance(self):
        """Test get_cached_data allows small mtime differences."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Add data to cache
            test_items = [{"name": "test_foo"}]
            cache.cache_data["/test.py"] = {
                "mtime": 1234567890.0,
                "items": test_items
            }

            # Get with slightly different mtime (within 0.01s tolerance)
            result = cache.get_cached_data("/test.py", 1234567890.005)

            # Should still be a cache hit
            assert result == test_items
            assert cache.stats.cache_hits == 1


class TestCollectionCacheUpdate:
    """Test cache update functionality."""

    @pytest.mark.unit
    def test_update_cache_adds_new_entry(self):
        """Test update_cache adds new cache entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            test_items = [{"name": "test_foo"}]
            cache.update_cache("/test.py", 1234567890.0, test_items)

            assert "/test.py" in cache.cache_data
            assert cache.cache_data["/test.py"]["mtime"] == 1234567890.0
            assert cache.cache_data["/test.py"]["items"] == test_items
            assert cache.stats.files_parsed == 1

    @pytest.mark.unit
    def test_update_cache_overwrites_existing(self):
        """Test update_cache overwrites existing entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Add initial data
            cache.cache_data["/test.py"] = {
                "mtime": 1234567890.0,
                "items": [{"name": "old_test"}]
            }

            # Update with new data
            new_items = [{"name": "new_test"}]
            cache.update_cache("/test.py", 1234567899.0, new_items)

            assert cache.cache_data["/test.py"]["mtime"] == 1234567899.0
            assert cache.cache_data["/test.py"]["items"] == new_items


class TestCollectionCacheMerge:
    """Test merge_with_rust_data functionality."""

    @pytest.mark.unit
    def test_merge_with_empty_cache(self):
        """Test merging with empty cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            rust_metadata = {
                "/test1.py": {
                    "mtime": 1234567890.0,
                    "items": [{"name": "test_foo"}]
                },
                "/test2.py": {
                    "mtime": 1234567891.0,
                    "items": [{"name": "test_bar"}]
                }
            }

            merged_data, cache_updated = cache.merge_with_rust_data(rust_metadata)

            assert len(merged_data) == 2
            assert cache_updated is True
            assert cache.stats.files_parsed == 2
            assert cache.stats.files_from_cache == 0

    @pytest.mark.unit
    def test_merge_with_existing_cache_all_fresh(self):
        """Test merging when all files are cached and fresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Pre-populate cache
            cache.cache_data["/test1.py"] = {
                "mtime": 1234567890.0,
                "items": [{"name": "cached_test"}]
            }

            rust_metadata = {
                "/test1.py": {
                    "mtime": 1234567890.0,
                    "items": [{"name": "new_test"}]  # Won't be used
                }
            }

            merged_data, cache_updated = cache.merge_with_rust_data(rust_metadata)

            # Should use cached data
            assert merged_data["/test1.py"] == [{"name": "cached_test"}]
            assert cache_updated is False
            assert cache.stats.cache_hits == 1
            assert cache.stats.files_parsed == 0

    @pytest.mark.unit
    def test_merge_with_existing_cache_some_stale(self):
        """Test merging when some cached files are stale."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Pre-populate cache
            cache.cache_data["/test1.py"] = {
                "mtime": 1234567890.0,
                "items": [{"name": "old_test"}]
            }

            rust_metadata = {
                "/test1.py": {
                    "mtime": 1234567899.0,  # File was modified
                    "items": [{"name": "new_test"}]
                }
            }

            merged_data, cache_updated = cache.merge_with_rust_data(rust_metadata)

            # Should use new data
            assert merged_data["/test1.py"] == [{"name": "new_test"}]
            assert cache_updated is True
            assert cache.stats.cache_misses == 1
            assert cache.stats.files_parsed == 1

    @pytest.mark.unit
    def test_merge_removes_deleted_files(self):
        """Test merge removes files that no longer exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Pre-populate cache with files
            cache.cache_data["/test1.py"] = {
                "mtime": 1234567890.0,
                "items": [{"name": "test1"}]
            }
            cache.cache_data["/test2.py"] = {
                "mtime": 1234567891.0,
                "items": [{"name": "test2"}]
            }
            cache.cache_data["/deleted.py"] = {
                "mtime": 1234567892.0,
                "items": [{"name": "deleted_test"}]
            }

            # Rust only reports test1 and test2 (deleted.py was removed)
            rust_metadata = {
                "/test1.py": {
                    "mtime": 1234567890.0,
                    "items": [{"name": "test1"}]
                },
                "/test2.py": {
                    "mtime": 1234567891.0,
                    "items": [{"name": "test2"}]
                }
            }

            merged_data, cache_updated = cache.merge_with_rust_data(rust_metadata)

            # deleted.py should be removed from cache
            assert "/deleted.py" not in cache.cache_data
            assert len(cache.cache_data) == 2
            assert cache_updated is True


class TestCollectionCacheClear:
    """Test cache clearing functionality."""

    @pytest.mark.unit
    def test_clear_cache_removes_all_data(self):
        """Test clear removes all cache data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Add data
            cache.cache_data["/test.py"] = {
                "mtime": 1234567890.0,
                "items": [{"name": "test_foo"}]
            }
            cache.stats.cache_hits = 5
            cache.stats.files_parsed = 10

            # Save to disk
            cache.save_cache()
            assert cache.cache_file.exists()

            # Clear
            cache.clear()

            # Everything should be cleared
            assert len(cache.cache_data) == 0
            assert cache.stats.cache_hits == 0
            assert cache.stats.files_parsed == 0
            assert not cache.cache_file.exists()

    @pytest.mark.unit
    def test_clear_cache_handles_missing_file(self):
        """Test clear handles missing cache file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Clear without creating cache file first
            cache.clear()

            # Should not crash
            assert len(cache.cache_data) == 0


class TestCollectionCacheEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.unit
    def test_cache_with_empty_items(self):
        """Test caching files with no test items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            cache.update_cache("/empty.py", 1234567890.0, [])

            assert "/empty.py" in cache.cache_data
            assert cache.cache_data["/empty.py"]["items"] == []

    @pytest.mark.unit
    def test_cache_with_unicode_paths(self):
        """Test caching with unicode file paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            unicode_path = "/path/to/测试_test.py"
            test_items = [{"name": "test_unicode"}]

            cache.update_cache(unicode_path, 1234567890.0, test_items)
            cache.save_cache()

            # Load and verify
            cache2 = CollectionCache(cache_dir)
            assert unicode_path in cache2.cache_data

    @pytest.mark.unit
    def test_cache_with_very_large_data(self):
        """Test caching with large number of items."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Create large list of items
            large_items = [{"name": f"test_{i}", "line": i} for i in range(10000)]

            cache.update_cache("/large.py", 1234567890.0, large_items)
            cache.save_cache()

            # Load and verify
            cache2 = CollectionCache(cache_dir)
            assert len(cache2.cache_data["/large.py"]["items"]) == 10000

    @pytest.mark.unit
    def test_cache_stats_persistence(self):
        """Test that cache stats are reset on reload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            # Generate some stats
            cache.update_cache("/test.py", 1234567890.0, [])
            cache.stats.cache_hits = 10
            cache.save_cache()

            # Load new cache instance
            cache2 = CollectionCache(cache_dir)

            # Stats should be reset (they're not persisted)
            assert cache2.stats.cache_hits == 0
            assert cache2.stats.files_parsed == 0

    @pytest.mark.unit
    def test_concurrent_cache_access(self):
        """Test basic thread safety (basic test only)."""
        import threading

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)
            cache = CollectionCache(cache_dir)

            def update_cache(i):
                cache.update_cache(f"/test{i}.py", 1234567890.0 + i, [])

            # Create multiple threads updating cache
            threads = [threading.Thread(target=update_cache, args=(i,)) for i in range(10)]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All updates should be present
            assert len(cache.cache_data) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
