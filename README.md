# pytest-fastcollect

A high-performance pytest plugin that uses Rust to accelerate test collection. This plugin leverages `rustpython-parser` to parse Python test files in parallel, with incremental caching to skip unchanged files.

**Performance**: Up to **2.4x faster** collection on large projects (tested on Django's 1977 test files). Best for codebases with 200+ test files.

## Features

- 🦀 **Rust-Powered Parsing**: Uses `rustpython-parser` for blazing-fast Python AST parsing
- ⚡ **Parallel Processing**: Leverages Rayon for parallel file processing
- 💾 **Incremental Caching**: Caches parsed results with file modification tracking
- 🎯 **Smart Filtering**: Pre-filters test files before pytest's collection phase
- 🔧 **Drop-in Replacement**: Works as a pytest plugin with no code changes required
- 🎛️ **Configurable**: Enable/disable fast collection and caching with command-line flags
- 📈 **Scales with Size**: Performance improvements scale with project size (2-4x on 500+ files)

## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/yourusername/pytest-fastcollect.git
cd pytest-fastcollect

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install maturin and build
pip install maturin
maturin develop --release

# Or install in production mode
maturin build --release
pip install target/wheels/pytest_fastcollect-*.whl
```

### Requirements

- Python 3.8+
- Rust 1.70+
- pytest 7.0+

## Usage

Once installed, the plugin is automatically activated for all pytest runs:

```bash
# Run pytest as normal - fast collection is enabled by default
pytest

# Collect tests only (useful for benchmarking)
pytest --collect-only

# Disable fast collection
pytest --no-fast-collect

# Clear cache and reparse all files
pytest --fastcollect-clear-cache --collect-only

# Disable caching (always parse)
pytest --no-fastcollect-cache

# Experimental: Parallel module import (2.33x faster on pytest itself!)
pytest --parallel-import --parallel-workers=4

# Experimental: Collection Daemon (instant re-collection)
pytest --daemon-start tests/        # Start daemon
pytest --daemon-status              # Check status
pytest --daemon-stop                # Stop daemon

# Run benchmarks
python benchmark.py --synthetic
python benchmark_incremental.py  # Shows cache effectiveness
python benchmark_parallel.py     # Test parallel import performance
```

### Configuration Options

- `--use-fast-collect`: Enable Rust-based fast collection (default: True)
- `--no-fast-collect`: Disable fast collection and use standard pytest collection
- `--fastcollect-cache`: Enable incremental caching (default: True)
- `--no-fastcollect-cache`: Disable caching and parse all files
- `--fastcollect-clear-cache`: Clear the cache before collection
- `--benchmark-collect`: Benchmark collection time (fast vs standard)
- `--parallel-import`: **[Experimental]** Pre-import modules in parallel (default: False)
- `--parallel-workers=N`: Number of parallel import workers (default: CPU count)
- `--daemon-start`: **[Experimental]** Start collection daemon for instant re-collection
- `--daemon-stop`: Stop the collection daemon
- `--daemon-status`: Show daemon status (running/not running, PID, uptime, cached modules)

## Architecture

### How It Works

1. **Rust Collector (`FastCollector`)**:
   - Walks the directory tree to find Python test files
   - Uses `rustpython-parser` to parse each file's AST in parallel
   - Extracts file modification times for cache validation
   - Returns collected metadata to Python

2. **Incremental Caching**:
   - Caches parsed test data with file mtimes in `.pytest_cache/v/fastcollect/`
   - On subsequent runs, checks file mtimes
   - Only reparses files that have changed
   - Shows cache statistics (hits/misses) after collection

3. **pytest Plugin Integration**:
   - Hooks into pytest's `pytest_ignore_collect` to filter files
   - Uses cached data when available
   - Falls back to standard collection on errors

4. **File Detection**:
   - Test files: `test_*.py` or `*_test.py`
   - Ignored directories: `.git`, `__pycache__`, `.tox`, `.venv`, `venv`, `.eggs`, `*.egg-info`

### Components

```
pytest-fastcollect/
├── src/
│   └── lib.rs                    # Rust implementation (FastCollector)
├── pytest_fastcollect/
│   ├── __init__.py               # Python package init
│   ├── plugin.py                 # pytest plugin hooks
│   ├── cache.py                  # Incremental caching layer
│   ├── daemon.py                 # Collection daemon server
│   ├── daemon_client.py          # Daemon client communication
│   └── filter.py                 # Selective import filtering
├── tests/
│   └── sample_tests/             # Sample tests for validation
├── benchmark.py                  # Performance benchmarking
├── benchmark_incremental.py      # Cache effectiveness benchmark
├── benchmark_parallel.py         # Parallel import benchmarking
├── Cargo.toml                    # Rust dependencies
└── pyproject.toml                # Python package metadata
```

## Benchmarks

### v0.4.0 - Selective Import (Latest) ⭐

**THE BREAKTHROUGH**: Selective import based on `-k` and `-m` filters!

**How it works**:
1. Parse all test files with Rust (parallel, fast)
2. Extract test names and markers from AST
3. Apply `-k` and `-m` filters BEFORE importing modules
4. Only import files containing matching tests
5. Result: Massive speedups for filtered runs!

**Benchmark Results** (100 files, 10 tests/file):
```
Scenario                        Time      Speedup
Full collection (no filter)     0.98s     baseline
With -k filter (10% files)      0.57s     1.71x faster ⚡
With -m filter (20% files)      0.64s     1.55x faster ⚡
Combined filters                0.55s     1.78x faster ⚡
```

**Real-World Impact**:
```bash
# Before v0.4.0: imports ALL 100 test files
pytest -k test_user  # 0.98s

# With v0.4.0: imports only 10 matching files
pytest -k test_user  # 0.57s (1.71x faster!)
```

**When it helps most**:
- ✅ Running specific tests: `pytest -k test_user_login`
- ✅ Running marked tests: `pytest -m smoke`
- ✅ Development workflow (constantly filtering tests)
- ✅ CI/CD with test splits
- ✅ Large test suites with good organization

**Key Features**:
- Marker detection from decorators (`@pytest.mark.slow`)
- Keyword matching (function names, class names, file names)
- Supports `and`, `or`, `not` in expressions
- Shows file selection stats with `-v`
- Fully compatible with pytest's filter syntax

### Multi-Project Real-World Benchmarks 📊

Tested on **5 popular Python projects** to validate real-world performance:

| Project | Files | Baseline | FastCollect | Speedup | Grade |
|---------|-------|----------|-------------|---------|-------|
| **Django** | ~1977 | 10.85s | 4.49s | **2.42x** | ⚡⚡⚡ Excellent |
| **SQLAlchemy** | ~219 | 0.68s | 0.63s | **1.07x** | ✓ Minor |
| **Pytest** | ~108 | 2.40s | 2.54s | **0.94x** | ⚠️ Overhead |
| **Requests** | ~9 | 0.61s | 0.54s | **1.13x** | ✓ Minor |
| **Flask** | ~22 | 0.55s | 0.55s | **1.00x** | → Neutral |

**Key Finding**: Performance scales with project size! 🚀

**Selective Import Performance** (additional speedup with `-k` filters):
- **Pytest**: Up to **2.75x faster** with specific filters (`-k test_basic`)
- **Django**: Additional **1.32x faster** with keyword filters
- **Small projects**: Minimal additional benefit

**Break-Even Analysis**:
- ✅ **Large projects (500+ files)**: **2-4x speedup** - highly recommended
- ⚠️ **Medium projects (100-300 files)**: **0.9-1.5x** - evaluate first
- → **Small projects (< 50 files)**: **~1.0x** - not necessary

**Bottom Line**: pytest-fastcollect is **ideal for large codebases** (200+ test files) where collection time becomes a bottleneck. For projects with < 50 files, the overhead roughly equals the benefit.

📄 See [REALWORLD_BENCHMARKS.md](REALWORLD_BENCHMARKS.md) for comprehensive analysis across all projects.

### Parallel Import (Experimental) ⚡⚡⚡

**NEW**: Pre-import test modules in parallel for additional speedup!

```bash
pytest --parallel-import --parallel-workers=4
```

**Benchmark Results** (with --parallel-import):

| Project | Baseline | With Parallel | Speedup | Grade |
|---------|----------|---------------|---------|-------|
| **Pytest** | 2.40s | 1.03s | **2.33x faster** | ⚡⚡⚡ Excellent |
| **SQLAlchemy** | 0.69s | 0.64s | **1.07x faster** | ✓ Minor |
| **Django** | 4.80s | 4.90s | **0.98x slower** | ⚠️ Overhead |

**Key Finding**: Parallel import works great for projects with **simple, independent test modules** (like pytest itself!), but can hurt projects with complex interdependent imports (like Django).

**When to use**:
- ✅ Medium projects (100-300 files) with simple imports → **2-2.5x speedup**
- ⚠️ Projects with complex imports → **Benchmark first**
- ❌ Small projects (< 100 files) → **Overhead not worth it**

**Optimal configuration**: 4 workers seems to be the sweet spot for most projects.

**ProcessPoolExecutor** (experimental):
```bash
# Bypass GIL with true process parallelism
pytest --parallel-import --use-processes --parallel-workers=4
```

**Results**: ProcessPoolExecutor tested but **not recommended**
- ❌ Slower than ThreadPoolExecutor in most cases (0.88-1.10x)
- Process overhead > GIL bypass benefit
- Must import twice (subprocess + main process)
- ThreadPoolExecutor remains the better choice

📄 See [PARALLEL_IMPORT_RESULTS.md](PARALLEL_IMPORT_RESULTS.md) for threading details.
📄 See [PROCESS_POOL_RESULTS.md](PROCESS_POOL_RESULTS.md) for process pool analysis.

### Collection Daemon (Experimental - Phase 1) 🚀

**NEW**: Long-running daemon process that keeps test modules imported in memory for instant re-collection!

```bash
# Start the daemon (imports all modules once)
pytest --daemon-start tests/

# Check daemon status
pytest --daemon-status

# Stop the daemon
pytest --daemon-stop
```

**Expected Performance** (Phase 2 - Full Integration):
- First run: ~10s (cold start, imports all modules)
- Subsequent runs: ~0.01s (instant! modules already in memory)
- **100-1000x speedup** on subsequent test runs

**Current Status (Phase 1 - MVP)**:
- ✅ Daemon server with Unix socket communication
- ✅ Module pre-importing and caching in memory
- ✅ Start/stop/status management commands
- ⏳ Full pytest collection integration (Phase 2)
- ⏳ File watching for auto-reload (Phase 2)

**Architecture**:
- Long-running Python process
- Unix socket IPC for client-daemon communication
- Keeps modules in `sys.modules` across pytest runs
- Background process management with forking
- Per-project daemon instances (separate socket per root)

**When to use**:
- 🎯 **TDD workflows**: Constantly re-running tests during development
- 🎯 **Watch mode**: Instant collection on file changes
- 🎯 **Large codebases**: Where collection time > 5 seconds
- ⚠️ **Not for CI/CD**: Designed for development, not one-shot runs

**Current Limitations**:
- Unix/Linux only (uses Unix domain sockets)
- Phase 1: Infrastructure only, not yet integrated with pytest collection
- Requires manual daemon management (start/stop)
- May require reload after significant code changes

📄 See [COLLECTION_DAEMON_PLAN.md](COLLECTION_DAEMON_PLAN.md) for full implementation roadmap.

### Django Real-World Benchmark 🚀

**The ultimate test**: Django's massive test suite with **~1977 Python test files**!

**Full Collection Performance**:
```
Scenario                        Time      Speedup
Baseline (no plugin)            36.59s    -
FastCollect                     9.16s     3.99x faster ⚡⚡⚡
```

**Selective Import Performance**:
```
Filter Type                     Time      Speedup vs Full
Full collection                 9.16s     baseline
-k test_get                     4.12s     2.22x faster ⚡⚡
-k test_forms                   3.80s     2.41x faster ⚡⚡
-k "test_view or test_model"    4.19s     2.19x faster ⚡⚡
```

**Combined Impact**: FastCollect + Selective Import = **9.6x faster** than baseline pytest!
- Baseline: 36.59s → FastCollect + filter: 3.80s

**Key Takeaways**:
- ✅ **4x faster** on full collection (real-world production codebase)
- ✅ **2-2.4x additional speedup** with keyword filters
- ✅ **Nearly 10x overall** when combining both optimizations
- ✅ **Production-ready** on Django's complex test infrastructure
- ✅ **Zero configuration** required - works out of the box

📄 See [DJANGO_BENCHMARK_RESULTS.md](DJANGO_BENCHMARK_RESULTS.md) for detailed analysis.

### v0.3.0 - Better Integration

**Architecture Improvements**:
```
Early initialization:             Collection happens in pytest_configure
File filtering:                   Simplified pytest_ignore_collect hook
Collection overhead:              Reduced hook call complexity
Code quality:                     Cleaner separation of concerns
```

**Performance** (comparable to v0.2.0):
- Maintains incremental caching benefits (~5% improvement on warm cache)
- No duplicate collection issues
- Cleaner initialization flow

**Key Changes**:
- Moved Rust collection from lazy (first `pytest_ignore_collect` call) to eager (in `pytest_configure`)
- Simplified `pytest_ignore_collect` to only use pre-collected data
- Removed custom collector class to avoid pytest hook conflicts
- More predictable and testable architecture

### v0.2.0 - Incremental Caching

**Incremental Collection Benchmark (500 files, 20 tests/file, 5 files modified)**:
```
Cold start (no cache):              3.34s  (baseline)
Warm cache (no changes):            3.18s  (1.05x faster)
Incremental (5 files changed):      3.50s  (cache + reparse 1%)

Cache effectiveness:
  - 100% cache hit rate on unchanged files
  - Only modified files are reparsed
  - ~5% improvement on warm cache
  - Persistent across pytest runs
```

**Cache Statistics** (displayed after collection with `-v`):
```
FastCollect Cache: 2 files from cache, 0 parsed (100.0% hit rate)
```

### v0.1.0 - File Filtering Only

**Synthetic Benchmarks**:
- **200 files, 50 tests/file**: ~1.01x speedup
- **500 files, 100 tests/file**: ~1.01x speedup

**Real-World (pandas, 969 test files)**:
- File filtering: 0.75x (slower due to overhead)

### Performance Analysis

**Why Limited Speedup in Pure Collection?**

1. **Pytest Import Bottleneck**: Even with caching, pytest must import Python modules to get actual function/class objects
2. **File Filtering Overhead**: The `pytest_ignore_collect` hook is called for every path
3. **Duplicate Work**: Both Rust (for discovery) and Python (for import) process files

**Where Caching Provides Real Value:**

1. ✅ **Incremental Workflows**: Only reparse modified files (5-10% improvement)
2. ✅ **Large Codebases**: Faster discovery in deep directory trees
3. ✅ **CI/CD Pipelines**: Cache persists across runs
4. ✅ **Development Workflow**: Repeated `pytest --collect-only` calls
5. ✅ **Watch Mode**: Quick re-collection when files change

### Recent Improvements (v0.2.0)

✅ **Incremental Caching** - Cache parsed results with file modification tracking
- Persists to `.pytest_cache/v/fastcollect/cache.json`
- Only reparses files that have changed
- Shows cache statistics after collection
- ~5% improvement on repeated runs

### Future Optimizations

To achieve even greater speedup:

1. **Direct Item Creation**: Create pytest `Item` objects directly from Rust (complex, see IMPLEMENTATION_NOTES.md)
2. **Lazy Loading**: Only parse files when their tests are actually executed
3. **Better Integration**: Use pytest's lower-level APIs to bypass standard collection
4. **Parallel Imports**: Import Python modules in parallel

## Technical Details

### Rust Dependencies

- `pyo3`: Python bindings for Rust
- `rustpython-parser`: Python AST parser in Rust
- `walkdir`: Recursive directory traversal
- `rayon`: Data parallelism library

### Python API

```python
from pytest_fastcollect import FastCollector

# Create a collector for a directory
collector = FastCollector("/path/to/tests")

# Collect all tests (basic mode)
results = collector.collect()
# Returns: {"file_path": [{"name": "test_foo", "line": 10, "type": "Function"}, ...]}

# Collect with metadata (includes file mtimes for caching)
metadata = collector.collect_with_metadata()
# Returns: {"file_path": {"mtime": 1234567890.0, "items": [...]}}
```

## Development

### Building from Source

```bash
# Development build (faster compilation, slower runtime)
maturin develop

# Release build (slower compilation, faster runtime)
maturin develop --release

# Build wheel
maturin build --release
```

### Running Tests

```bash
# Run sample tests
pytest tests/sample_tests -v

# Run with fast collection disabled
pytest tests/sample_tests --no-fast-collect -v

# Collect only (no execution)
pytest tests/sample_tests --collect-only

# View cache statistics
pytest tests/sample_tests --collect-only -v
```

### Running Benchmarks

```bash
# Synthetic benchmark with custom parameters
python benchmark.py --synthetic --num-files 200 --tests-per-file 100

# Incremental caching benchmark (shows cache effectiveness)
python benchmark_incremental.py

# Benchmark on a real project
python benchmark.py --project /path/to/project

# Run all benchmarks
python benchmark.py --all
```

### Cache Management

```bash
# Clear the cache
pytest --fastcollect-clear-cache --collect-only

# Disable caching for one run
pytest --no-fastcollect-cache

# View cache contents
cat .pytest_cache/v/fastcollect/cache.json
```

## Contributing

Contributions are welcome! Areas for improvement:

1. **Performance Optimization**: Implement direct `Item` creation from Rust data
2. **Advanced Caching**: Add file content hashing for more reliable cache validation
3. **Test Discovery**: Support more complex test patterns (fixtures, parameterization)
4. **Configuration**: Add support for custom test patterns and ignore rules
5. **Documentation**: Add more examples and use cases

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [PyO3](https://pyo3.rs/) for seamless Rust-Python integration
- Uses [RustPython Parser](https://github.com/RustPython/RustPython) for Python AST parsing
- Inspired by the need for faster test collection in large Python codebases

## Technical Notes

### Why Rust?

- **Speed**: Rust's zero-cost abstractions and lack of GIL make it ideal for CPU-intensive parsing
- **Parallelism**: Rayon makes it trivial to parse files in parallel
- **Safety**: Rust's type system ensures memory safety without garbage collection overhead

### Current Limitations

1. **Limited Pure Collection Speedup**: Pytest still needs to import modules (~5% improvement)
2. **Simple Test Detection**: Only detects `test_*` functions and `Test*` classes
3. **No Fixture Support**: Doesn't analyze pytest fixtures or dependencies
4. **No Parametrization**: Doesn't expand parametrized tests

### Changelog

#### v0.3.0 (Current)
- 🏗️ **Better Integration**: Refactored plugin architecture for cleaner code
- ⚡ Early initialization in `pytest_configure` instead of lazy loading
- 🔧 Simplified `pytest_ignore_collect` hook to only use cached data
- 🐛 Fixed duplicate collection issues from custom collector conflicts
- 📊 Maintains all caching benefits from v0.2.0
- 🧹 Cleaner separation of concerns and more predictable behavior

#### v0.2.0
- ✨ Added incremental caching with file modification tracking
- 💾 Cache persists to `.pytest_cache/v/fastcollect/cache.json`
- 📊 Shows cache statistics after collection
- 🚀 ~5% improvement on repeated runs with warm cache
- 📝 Added `benchmark_incremental.py` for cache effectiveness testing

#### v0.1.0
- 🎉 Initial release
- 🦀 Rust-based parallel AST parsing
- 🎯 File filtering via `pytest_ignore_collect` hook
- ⚡ Parallel processing with Rayon
- 📚 Comprehensive documentation

## Contact

For issues, questions, or contributions, please open an issue on GitHub.
