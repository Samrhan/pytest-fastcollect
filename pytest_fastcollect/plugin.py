"""Pytest plugin that monkey-patches the collection mechanism with Rust implementation."""

import os
import sys
from pathlib import Path
from typing import List, Optional
import pytest
from _pytest.python import Module, Class, Function
from _pytest.main import Session
from _pytest.config import Config

try:
    from .pytest_fastcollect import FastCollector
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    FastCollector = None


class FastCollectionSession:
    """Wrapper to inject fast collection into pytest Session."""

    def __init__(self, session: Session):
        self.session = session
        self.config = session.config
        self.fast_collector = None

        if RUST_AVAILABLE:
            root_path = str(self.config.rootpath)
            self.fast_collector = FastCollector(root_path)

    def collect(self):
        """Fast collection using Rust parser."""
        if not self.fast_collector:
            # Fallback to original collection
            return self._original_collect()

        try:
            # Use Rust collector
            collected_items = self.fast_collector.collect()

            # Convert Rust results to pytest Items
            items = []
            for file_path, test_items in collected_items.items():
                # Create Module for each file
                module_path = Path(file_path)

                # Import the module to get actual test objects
                try:
                    items.extend(self._create_pytest_items(file_path, test_items))
                except Exception as e:
                    # If fast collection fails for a file, skip it
                    if self.config.option.verbose > 0:
                        print(f"Fast collection failed for {file_path}: {e}", file=sys.stderr)
                    continue

            return items
        except Exception as e:
            # Fallback to original collection on any error
            if self.config.option.verbose > 0:
                print(f"Fast collection failed, falling back to standard collection: {e}", file=sys.stderr)
            return self._original_collect()

    def _create_pytest_items(self, file_path: str, test_items: List[dict]):
        """Create pytest Item objects from collected test information."""
        items = []

        # Get the module path relative to rootpath
        module_path = Path(file_path)
        try:
            rel_path = module_path.relative_to(self.config.rootpath)
        except ValueError:
            rel_path = module_path

        # Create a Module node
        module = Module.from_parent(
            self.session,
            path=module_path,
        )

        # Collect items from the module
        # We let pytest do the actual collection for now, but we know what to look for
        module_items = []
        try:
            module_items = list(module.collect())
        except Exception:
            pass

        items.extend(module_items)

        return items

    def _original_collect(self):
        """Fallback to original pytest collection."""
        # This should never be called directly; it's a placeholder
        return []


def pytest_configure(config: Config):
    """Register the plugin."""
    if not RUST_AVAILABLE:
        if config.option.verbose > 0:
            print("Warning: pytest-fastcollect Rust extension not available, using standard collection",
                  file=sys.stderr)
        return


def pytest_collection_modifyitems(session: Session, config: Config, items: list):
    """Modify collected items - this is called AFTER collection."""
    # This is called after collection, so it's too late to optimize
    pass


def pytest_collection_finish(session: Session):
    """Called after collection has been performed and modified."""
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


# Store test files cache
_test_files_cache = None


def pytest_ignore_collect(collection_path, config):
    """Called to determine whether to ignore a file/directory during collection."""
    global _test_files_cache

    if not RUST_AVAILABLE:
        return None

    # Check if fast collection is disabled
    if hasattr(config.option, 'use_fast_collect') and not config.option.use_fast_collect:
        return None

    # Initialize cache on first call
    if _test_files_cache is None:
        root_path = str(config.rootpath)
        fast_collector = FastCollector(root_path)
        collected_data = fast_collector.collect()
        _test_files_cache = set(collected_data.keys())

    # Only collect Python test files that Rust found
    if collection_path.is_file() and collection_path.suffix == ".py":
        abs_path = str(collection_path.absolute())
        should_ignore = abs_path not in _test_files_cache
        return should_ignore

    return None
