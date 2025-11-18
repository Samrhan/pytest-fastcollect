"""Pytest plugin that monkey-patches the collection mechanism with Rust implementation."""

import os
import sys
from pathlib import Path
from typing import List, Optional, Any
import pytest
from _pytest.python import Module, Class, Function
from _pytest.main import Session
from _pytest.config import Config
from _pytest.nodes import Collector

try:
    from .pytest_fastcollect import FastCollector
    from .cache import CollectionCache, CacheStats
    from .filter import get_files_with_matching_tests
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    FastCollector = None
    CollectionCache = None
    CacheStats = None
    get_files_with_matching_tests = None


def pytest_configure(config: Config):
    """Register the plugin."""
    global _test_files_cache, _collection_cache, _cache_stats, _collected_data

    if not RUST_AVAILABLE:
        if config.option.verbose > 0:
            print("Warning: pytest-fastcollect Rust extension not available, using standard collection",
                  file=sys.stderr)
        return

    # Check if fast collection is disabled
    if hasattr(config.option, 'use_fast_collect') and not config.option.use_fast_collect:
        return

    # Initialize the collector and cache early
    root_path = str(config.rootpath)
    fast_collector = FastCollector(root_path)
    use_cache = getattr(config.option, 'fastcollect_cache', True)

    # Clear cache if requested
    if hasattr(config.option, 'fastcollect_clear_cache') and config.option.fastcollect_clear_cache:
        cache_dir = _get_cache_dir(config)
        if CollectionCache:
            cache = CollectionCache(cache_dir)
            cache.clear()
            if config.option.verbose >= 0:
                print("FastCollect: Cache cleared", file=sys.stderr)

    # Pre-collect test files and cache them
    if use_cache:
        cache_dir = _get_cache_dir(config)
        _collection_cache = CollectionCache(cache_dir)
        rust_metadata = fast_collector.collect_with_metadata()
        collected_data, cache_updated = _collection_cache.merge_with_rust_data(rust_metadata)

        if cache_updated:
            _collection_cache.save_cache()

        _cache_stats = _collection_cache.stats
    else:
        collected_data = fast_collector.collect()
        _cache_stats = None

    _collected_data = collected_data

    # Apply selective import filtering based on -k and -m options
    keyword_expr = config.getoption("-k", default=None)
    marker_expr = config.getoption("-m", default=None)

    if keyword_expr or marker_expr:
        # Only include files with tests matching the filter
        _test_files_cache = get_files_with_matching_tests(
            collected_data,
            keyword_expr=keyword_expr,
            marker_expr=marker_expr
        )
        if config.option.verbose >= 1:
            total_files = len(collected_data)
            filtered_files = len(_test_files_cache)
            print(
                f"FastCollect: Selective import - {filtered_files}/{total_files} files match filter",
                file=sys.stderr
            )
    else:
        # No filtering, collect all files
        _test_files_cache = set(collected_data.keys())


def pytest_collection_modifyitems(session: Session, config: Config, items: list):
    """Modify collected items - this is called AFTER collection."""
    # This is called after collection, so it's too late to optimize
    pass




def pytest_addoption(parser):
    """Add command-line options."""
    group = parser.getgroup('fastcollect')
    group.addoption(
        '--use-fast-collect',
        action='store_true',
        default=True,
        help='Use Rust-based fast collection (default: True)'
    )
    group.addoption(
        '--no-fast-collect',
        dest='use_fast_collect',
        action='store_false',
        help='Disable fast collection and use standard pytest collection'
    )
    group.addoption(
        '--fastcollect-cache',
        action='store_true',
        default=True,
        help='Enable incremental caching (default: True)'
    )
    group.addoption(
        '--no-fastcollect-cache',
        dest='fastcollect_cache',
        action='store_false',
        help='Disable caching and parse all files'
    )
    group.addoption(
        '--fastcollect-clear-cache',
        action='store_true',
        default=False,
        help='Clear the fastcollect cache before collection'
    )
    group.addoption(
        '--benchmark-collect',
        action='store_true',
        default=False,
        help='Benchmark collection time (fast vs standard)'
    )


def pytest_report_header(config: Config):
    """Add information to the pytest header."""
    if RUST_AVAILABLE:
        from . import get_version
        return f"fastcollect: v{get_version()} (Rust-accelerated collection enabled)"
    else:
        return "fastcollect: Rust extension not available"


# Store test files cache and collection cache
_test_files_cache = None
_collection_cache = None
_cache_stats = None
_collected_data = None


def _get_cache_dir(config: Config) -> Path:
    """Get the cache directory for fastcollect."""
    # Use pytest's cache directory
    cache_dir = Path(config.cache._cachedir) / "v" / "fastcollect"
    return cache_dir


def pytest_ignore_collect(collection_path, config):
    """Called to determine whether to ignore a file/directory during collection.

    Uses Rust-parsed metadata from pytest_configure to efficiently filter files.
    """
    global _test_files_cache

    if not RUST_AVAILABLE:
        return None

    # Check if fast collection is disabled
    if hasattr(config.option, 'use_fast_collect') and not config.option.use_fast_collect:
        return None

    # If cache hasn't been initialized yet, don't filter
    # (pytest_configure should have initialized it)
    if _test_files_cache is None:
        return None

    # Only filter Python test files
    if collection_path.is_file() and collection_path.suffix == ".py":
        abs_path = str(collection_path.absolute())
        # Ignore files that don't have tests according to Rust parser
        should_ignore = abs_path not in _test_files_cache
        return should_ignore

    return None


def pytest_collection_finish(session: Session):
    """Called after collection has been performed and modified."""
    global _cache_stats

    # Display cache statistics if available and verbose
    if _cache_stats and session.config.option.verbose >= 0:
        print(f"\n{_cache_stats}", file=sys.stderr)
