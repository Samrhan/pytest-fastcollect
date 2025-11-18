"""Pytest plugin that monkey-patches the collection mechanism with Rust implementation."""

import os
import sys
import importlib.util
from pathlib import Path
from typing import List, Optional, Any, Set
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
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

    # Parallel import optimization (if enabled)
    if hasattr(config.option, 'parallel_import') and config.option.parallel_import:
        _parallel_import_modules(_test_files_cache, config)


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
    group.addoption(
        '--parallel-import',
        action='store_true',
        default=False,
        help='Pre-import test modules in parallel (experimental)'
    )
    group.addoption(
        '--parallel-workers',
        type=int,
        default=None,
        help='Number of parallel import workers (default: CPU count)'
    )
    group.addoption(
        '--use-processes',
        action='store_true',
        default=False,
        help='Use ProcessPoolExecutor instead of ThreadPoolExecutor (bypasses GIL)'
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


def _import_test_module(file_path: str, root_path: str) -> tuple:
    """Import a single test module.

    Returns: (file_path, success, error_message)
    """
    try:
        # Convert file path to module name
        path_obj = Path(file_path)
        root_obj = Path(root_path)

        # Get relative path from root
        try:
            rel_path = path_obj.relative_to(root_obj)
        except ValueError:
            # If file is not under root, use absolute path
            rel_path = path_obj

        # Convert path to module name (remove .py and replace / with .)
        module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

        # Check if already imported
        if module_name in sys.modules:
            return (file_path, True, None)

        # Import the module using importlib
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            return (file_path, True, None)
        else:
            return (file_path, False, "Could not create module spec")

    except Exception as e:
        return (file_path, False, str(e))


def _import_test_module_process(file_path: str, root_path: str) -> tuple:
    """Import a single test module in a subprocess (for ProcessPoolExecutor).

    This runs in a separate process, so it can't populate the main process's
    sys.modules. Instead, it ensures the .pyc file is compiled and cached.

    Returns: (file_path, success, error_message)
    """
    try:
        # Convert file path to module name
        path_obj = Path(file_path)
        root_obj = Path(root_path)

        # Get relative path from root
        try:
            rel_path = path_obj.relative_to(root_obj)
        except ValueError:
            rel_path = path_obj

        # Convert path to module name (remove .py and replace / with .)
        module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

        # Import the module to compile .pyc
        # This happens in subprocess, but .pyc file is written to disk
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            # Don't add to sys.modules in subprocess - it won't help main process
            spec.loader.exec_module(module)
            return (file_path, True, None)
        else:
            return (file_path, False, "Could not create module spec")

    except Exception as e:
        return (file_path, False, str(e))


def _parallel_import_modules(file_paths: Set[str], config: Config):
    """Pre-import test modules in parallel to warm the cache.

    Uses either ThreadPoolExecutor (shares sys.modules, limited by GIL)
    or ProcessPoolExecutor (true parallelism, compiles .pyc in parallel).
    """
    import time

    if not file_paths:
        return

    # Get number of workers
    workers = getattr(config.option, 'parallel_workers', None)
    if workers is None:
        workers = os.cpu_count() or 4

    # Check if using processes or threads
    use_processes = getattr(config.option, 'use_processes', False)

    root_path = str(config.rootpath)

    executor_type = "processes" if use_processes else "threads"
    if config.option.verbose >= 1:
        print(f"\nFastCollect: Parallel import ({workers} {executor_type}) - importing {len(file_paths)} modules...",
              file=sys.stderr, end=" ", flush=True)

    start_time = time.time()
    success_count = 0
    error_count = 0

    # Choose executor type
    if use_processes:
        # ProcessPoolExecutor: True parallelism, bypasses GIL
        # Each process compiles .pyc independently
        # Main process benefits from cached .pyc files
        executor_class = ProcessPoolExecutor
        import_func = _import_test_module_process
    else:
        # ThreadPoolExecutor: Limited by GIL, but shares sys.modules
        # Imports stay in main process's sys.modules
        executor_class = ThreadPoolExecutor
        import_func = _import_test_module

    with executor_class(max_workers=workers) as executor:
        # Submit all import tasks
        future_to_path = {
            executor.submit(import_func, file_path, root_path): file_path
            for file_path in file_paths
        }

        # Collect results
        for future in as_completed(future_to_path):
            file_path, success, error = future.result()
            if success:
                success_count += 1
            else:
                error_count += 1
                if config.option.verbose >= 2:
                    print(f"\n  Warning: Failed to import {file_path}: {error}",
                          file=sys.stderr)

    elapsed = time.time() - start_time

    if config.option.verbose >= 1:
        print(f"Done ({elapsed:.2f}s)", file=sys.stderr)
        if error_count > 0:
            print(f"  Imported: {success_count}/{len(file_paths)} modules ({error_count} errors)",
                  file=sys.stderr)

    # If using processes, need to import in main process to populate sys.modules
    # The .pyc files are now cached, so this should be much faster
    if use_processes and success_count > 0:
        if config.option.verbose >= 1:
            print(f"FastCollect: Loading modules into main process...", file=sys.stderr, end=" ", flush=True)

        start_reload = time.time()
        reload_count = 0

        # Import in main process (fast now due to cached .pyc)
        for file_path in file_paths:
            try:
                path_obj = Path(file_path)
                root_obj = Path(root_path)
                try:
                    rel_path = path_obj.relative_to(root_obj)
                except ValueError:
                    rel_path = path_obj

                module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')

                if module_name not in sys.modules:
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)
                        reload_count += 1
            except Exception:
                pass  # Ignore errors in main process import

        reload_elapsed = time.time() - start_reload
        if config.option.verbose >= 1:
            print(f"Done ({reload_elapsed:.2f}s, {reload_count} modules)", file=sys.stderr)


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
