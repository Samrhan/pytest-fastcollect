"""pytest-fastcollect: High-performance test collection using Rust."""

__version__ = "0.4.0"

try:
    from .pytest_fastcollect import FastCollector, get_version
except ImportError:
    # Fallback when the Rust extension is not built
    FastCollector = None
    get_version = lambda: __version__

__all__ = ["FastCollector", "get_version", "__version__"]
