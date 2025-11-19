"""Property-based tests using Hypothesis for pytest-fastcollect.

These tests generate random inputs to test edge cases and invariants.
"""

import pytest

# Try to import hypothesis, skip all tests if not available
try:
    from hypothesis import given, strategies as st, assume
    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    # Create dummy decorators for when hypothesis is not available
    def given(*args, **kwargs):
        return pytest.mark.skip(reason="hypothesis not installed")
    st = None
    assume = None

from pathlib import Path
import tempfile
import json

from pytest_fastcollect.filter import TestFilter, filter_collected_data
from pytest_fastcollect.cache import CollectionCache, CacheStats


# Skip all tests in this module if hypothesis is not available
pytestmark = pytest.mark.skipif(
    not HYPOTHESIS_AVAILABLE,
    reason="hypothesis not installed (install with: pip install hypothesis)"
)


# ============================================================================
# Filter Property-Based Tests
# ============================================================================


@pytest.mark.unit
class TestFilterProperties:
    """Property-based tests for filter logic."""

    @given(
        test_name=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
            min_size=1,
            max_size=50
        ),
        keyword=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
            min_size=1,
            max_size=20
        )
    )
    def test_keyword_filter_matches_substring(self, test_name, keyword):
        """Property: if keyword is substring of test name, filter should match."""
        assume(len(keyword) > 0)
        assume(len(test_name) > 0)

        # Create test data with keyword in name
        test_item = {
            "name": f"{test_name}_{keyword}_test",
            "class": None,
            "markers": []
        }

        filter_obj = TestFilter(keyword_expr=keyword)
        assert filter_obj.matches(test_item) is True

    @given(
        test_names=st.lists(
            st.text(
                alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
                min_size=1,
                max_size=30
            ),
            min_size=1,
            max_size=20
        )
    )
    def test_no_filter_matches_all(self, test_names):
        """Property: with no filters, all tests should match."""
        collected_data = {
            f"test_{i}.py": [
                {"name": name, "class": None, "markers": []}
                for name in test_names
            ]
            for i in range(len(test_names))
        }

        result = filter_collected_data(collected_data)
        assert len(result) == len(collected_data)

        # All original tests should be present
        for file_path, tests in collected_data.items():
            assert file_path in result
            assert len(result[file_path]) == len(tests)

    @given(
        marker1=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz",
            min_size=1,
            max_size=15
        ),
        marker2=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz",
            min_size=1,
            max_size=15
        )
    )
    def test_marker_and_expression(self, marker1, marker2):
        """Property: AND expression requires both markers."""
        assume(marker1 != marker2)

        # Test with both markers
        test_with_both = {
            "name": "test_both",
            "class": None,
            "markers": [marker1, marker2]
        }

        # Test with only first marker
        test_with_first = {
            "name": "test_first",
            "class": None,
            "markers": [marker1]
        }

        filter_obj = TestFilter(marker_expr=f"{marker1} and {marker2}")

        assert filter_obj.matches(test_with_both) is True
        assert filter_obj.matches(test_with_first) is False

    @given(
        keyword=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ",
            min_size=1,
            max_size=20
        )
    )
    def test_not_expression_inverts_match(self, keyword):
        """Property: NOT expression should invert the match."""
        assume(len(keyword) > 0)

        test_with_keyword = {
            "name": f"test_{keyword}",
            "class": None,
            "markers": []
        }

        # Create test name that definitely doesn't contain keyword
        # Use numbers to avoid any letter overlap
        test_without_keyword = {
            "name": "test_1234567890",
            "class": None,
            "markers": []
        }

        filter_obj = TestFilter(keyword_expr=f"not {keyword}")
        filter_normal = TestFilter(keyword_expr=keyword)

        # Test with keyword should NOT match "not" expression
        # but SHOULD match normal expression
        assert filter_obj.matches(test_with_keyword) is False
        assert filter_normal.matches(test_with_keyword) is True

        # Test without keyword should match "not" expression
        # but should NOT match normal expression (if keyword not in name)
        if keyword.lower() not in test_without_keyword["name"].lower():
            assert filter_obj.matches(test_without_keyword) is True
            assert filter_normal.matches(test_without_keyword) is False


# ============================================================================
# Cache Property-Based Tests
# ============================================================================


@pytest.mark.unit
class TestCacheProperties:
    """Property-based tests for cache behavior."""

    @given(
        mtime=st.floats(min_value=1000000000.0, max_value=9999999999.0),
        items_count=st.integers(min_value=0, max_value=100)
    )
    def test_cache_hit_on_same_mtime(self, mtime, items_count):
        """Property: cache should hit when mtime hasn't changed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CollectionCache(Path(tmpdir))

            file_path = "/fake/test.py"
            items = [{"name": f"test_{i}"} for i in range(items_count)]

            # Update cache
            cache.update_cache(file_path, mtime, items)

            # Retrieve with same mtime should hit
            result = cache.get_cached_data(file_path, mtime)
            assert result == items
            assert cache.stats.cache_hits == 1
            assert cache.stats.cache_misses == 0

    @given(
        mtime1=st.floats(min_value=1000000000.0, max_value=5000000000.0),
        mtime2=st.floats(min_value=5000000001.0, max_value=9999999999.0),
    )
    def test_cache_miss_on_different_mtime(self, mtime1, mtime2):
        """Property: cache should miss when mtime changes significantly."""
        assume(abs(mtime2 - mtime1) > 0.1)  # Significant difference

        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CollectionCache(Path(tmpdir))

            file_path = "/fake/test.py"
            items = [{"name": "test_1"}]

            # Update cache with mtime1
            cache.update_cache(file_path, mtime1, items)

            # Retrieve with mtime2 should miss
            result = cache.get_cached_data(file_path, mtime2)
            assert result is None
            assert cache.stats.cache_misses == 1

    @given(
        num_files=st.integers(min_value=1, max_value=20),
        num_items_per_file=st.integers(min_value=0, max_value=10)
    )
    def test_cache_persistence(self, num_files, num_items_per_file):
        """Property: cache should persist across instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir)

            # First instance - write data
            cache1 = CollectionCache(cache_dir)
            for i in range(num_files):
                file_path = f"/fake/test_{i}.py"
                items = [{"name": f"test_{j}"} for j in range(num_items_per_file)]
                cache1.update_cache(file_path, 1234567890.0 + i, items)
            cache1.save_cache()

            # Second instance - read data
            cache2 = CollectionCache(cache_dir)
            for i in range(num_files):
                file_path = f"/fake/test_{i}.py"
                result = cache2.get_cached_data(file_path, 1234567890.0 + i)
                assert result is not None
                assert len(result) == num_items_per_file

    @given(
        num_operations=st.integers(min_value=1, max_value=50)
    )
    def test_cache_stats_accuracy(self, num_operations):
        """Property: cache stats should accurately track hits and misses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CollectionCache(Path(tmpdir))

            hits = 0
            misses = 0

            for i in range(num_operations):
                file_path = f"/fake/test_{i % 10}.py"  # Reuse some paths
                mtime = 1234567890.0 + (i % 5)  # Reuse some mtimes

                result = cache.get_cached_data(file_path, mtime)

                if result is None:
                    misses += 1
                    # Add to cache
                    cache.update_cache(file_path, mtime, [{"name": f"test_{i}"}])
                else:
                    hits += 1

            assert cache.stats.cache_hits == hits
            assert cache.stats.cache_misses == misses

    @given(
        items=st.lists(
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.one_of(st.text(max_size=50), st.integers(), st.booleans(), st.none())
            ),
            min_size=0,
            max_size=50
        )
    )
    def test_cache_handles_various_item_structures(self, items):
        """Property: cache should handle various item structures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = CollectionCache(Path(tmpdir))

            file_path = "/fake/test.py"
            mtime = 1234567890.0

            # Update cache with random items
            cache.update_cache(file_path, mtime, items)
            cache.save_cache()

            # Reload and verify
            cache2 = CollectionCache(Path(tmpdir))
            result = cache2.get_cached_data(file_path, mtime)

            assert result == items


# ============================================================================
# String Expression Property-Based Tests
# ============================================================================


@pytest.mark.unit
class TestExpressionProperties:
    """Property-based tests for expression parsing and evaluation."""

    @given(
        word1=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz",
            min_size=1,
            max_size=10
        ),
        word2=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz",
            min_size=1,
            max_size=10
        )
    )
    def test_or_expression_commutative(self, word1, word2):
        """Property: OR expression should be commutative (A or B == B or A)."""
        assume(word1 != word2)

        test_item = {
            "name": f"test_{word1}",
            "class": None,
            "markers": []
        }

        filter1 = TestFilter(keyword_expr=f"{word1} or {word2}")
        filter2 = TestFilter(keyword_expr=f"{word2} or {word1}")

        assert filter1.matches(test_item) == filter2.matches(test_item)

    @given(
        word=st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz",
            min_size=1,
            max_size=15
        )
    )
    def test_double_negation(self, word):
        """Property: NOT NOT should cancel out (NOT NOT A == A)."""
        test_with_word = {
            "name": f"test_{word}",
            "class": None,
            "markers": []
        }

        filter_normal = TestFilter(keyword_expr=word)
        filter_double_not = TestFilter(keyword_expr=f"not not {word}")

        # Both should match the same
        assert filter_normal.matches(test_with_word) == filter_double_not.matches(test_with_word)
