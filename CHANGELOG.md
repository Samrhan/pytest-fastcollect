# Changelog

All notable changes to pytest-fastcollect will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.2] - 2025-01-19

### Added
- 🧪 **Property-Based Testing**: Added comprehensive property-based tests using Hypothesis
  - 11 new property-based tests for filter logic and cache behavior
  - Tests filter commutivity, double negation, cache persistence, and more
  - Automatically generates hundreds of test cases to find edge cases
  - Total test count: 182 → 193 tests
- 📚 **Documentation Overhaul**: Improved architecture documentation
  - Added ASCII art system architecture diagram
  - Better visual representation of data flow
  - Updated Python version requirements (3.9-3.14)
  - Clearer component interaction documentation
- 🔍 **Stricter Type Checking**: Enhanced mypy configuration for better type safety
  - Enabled `disallow_untyped_defs` for all production code
  - Enabled `disallow_incomplete_defs` for complete type coverage
  - Added `strict_optional` for better None handling
  - Type annotations now enforced for all new code
- 📦 **Python 3.13 & 3.14 Support**: Added support for latest Python versions
  - CI now tests on Python 3.9, 3.10, 3.11, 3.12, 3.13, and 3.14
  - Updated black and tool configurations for new Python versions
  - Added PyPI classifiers for Python 3.13 and 3.14
- 📋 **Constants Module**: Extracted magic numbers to centralized constants
  - Created `pytest_fastcollect/constants.py` for all configuration values
  - Daemon, client, cache, and performance constants now centralized
  - Easier tuning and better maintainability
- 🔧 **Hypothesis Dev Dependency**: Added hypothesis>=6.0.0 to dev dependencies

### Fixed
- 🐛 **Filter Bug**: Fixed crash when test class is None in filter logic
  - `filter.py:59` now checks `class is not None` before adding to search text
  - Prevents `TypeError: expected str instance, NoneType found`
  - Discovered by property-based tests!
- 🪟 **Windows Daemon Support**: Fixed daemon failing on Windows with `AttributeError: module 'os' has no attribute 'fork'`
  - Added cross-platform daemon launching
  - Unix/Linux/macOS: Uses double-fork technique (existing behavior)
  - Windows: Uses subprocess with CREATE_NEW_PROCESS_GROUP and DETACHED_PROCESS flags
  - Daemon now works on all platforms

### Changed
- ⬆️ **Python 3.9+ Required**: Dropped Python 3.8 support, now requires Python 3.9+
  - Python 3.8 reached end-of-life
  - Allows use of `hashlib.md5(usedforsecurity=False)` without version checks
  - Simplified codebase by removing compatibility workarounds
- 📊 **Test Suite**: Expanded from 182 to 193 tests (6% increase)
  - Added 11 property-based tests
  - Improved edge case coverage
  - Better confidence in filter and cache correctness

### Technical Details
- Property-based tests generate random inputs to validate:
  - Filter keyword matching and substring behavior
  - Marker AND/OR/NOT expression logic
  - Cache hit/miss behavior with various mtimes
  - Cache persistence across instances
  - Expression commutativity and double negation properties
- Mypy configuration improvements:
  - `disallow_untyped_defs = true`
  - `disallow_incomplete_defs = true`
  - `strict_optional = true`
  - Special overrides for test files and complex modules
- Constants extracted from 5 modules:
  - 18 daemon configuration constants
  - 12 client configuration constants
  - 6 performance tuning constants
  - 4 cache configuration constants

## [0.5.1] - 2025-01-18

### Added
- Comprehensive test suite for cache.py (31 tests, 100% coverage)
- Comprehensive test suite for filter.py (34 tests, 100% coverage)
- SECURITY.md with vulnerability reporting process
- CONTRIBUTING.md with detailed contribution guidelines
- Development tooling configuration (black, isort, ruff, mypy)
- Pre-commit hooks configuration for automated code quality checks
- Pytest markers configuration in pyproject.toml

### Fixed
- Duplicate FastCollector initialization in plugin.py (line 127)
- Test compatibility issues in CI environments (proper mocking for error handling)

### Changed
- Test coverage increased from ~35% to ~60%
- Total test count: 61 → 182 tests

## [0.5.0] - 2025-01-15

### Added
- 🚀 **Production-Ready Daemon**: Collection daemon upgraded from experimental to production-ready
- 🔒 **Security**: Comprehensive input validation and path checking to prevent attacks
- 📊 **Monitoring**: Health checks, metrics tracking, and detailed diagnostics
- 📝 **Logging**: Structured logging with automatic rotation (10MB files, 5 backups)
- 🔄 **Reliability**: Automatic retries with exponential backoff
- 🛡️ **Error Handling**: Comprehensive error handling and recovery mechanisms
- 🔗 **Connection Management**: Rate limiting, timeouts, and proper resource cleanup
- ✅ **Testing**: Comprehensive unit and integration tests for daemon
- 📚 **Documentation**: Complete troubleshooting guide and best practices
- 🎯 **Health Endpoint**: New `--daemon-health` command for diagnostics
- 📏 **Benchmark Tool**: New `--benchmark-collect` to test if plugin is beneficial for your project

### Changed
- Daemon now uses Unix domain sockets (local only, no network exposure)
- Each project gets isolated daemon instance
- Socket files created with 0600 permissions for security
- Improved daemon lifecycle management

## [0.4.0] - 2024-12-20

### Added
- ⚡ **Selective Import**: Major performance breakthrough!
  - Parse all test files with Rust (parallel, fast)
  - Extract test names and markers from AST
  - Apply `-k` and `-m` filters BEFORE importing modules
  - Only import files containing matching tests
  - **Result**: 1.55-1.78x speedup for filtered runs
- Marker detection from decorators (`@pytest.mark.slow`)
- Keyword matching (function names, class names, file names)
- Support for `and`, `or`, `not` in filter expressions
- File selection stats with `-v` flag
- Fully compatible with pytest's filter syntax

### Performance
- **Full collection**: 0.98s (baseline)
- **With -k filter (10% files)**: 0.57s (1.71x faster ⚡)
- **With -m filter (20% files)**: 0.64s (1.55x faster ⚡)
- **Combined filters**: 0.55s (1.78x faster ⚡)

### Real-World Impact
- Django (1977 files): **2.22-2.41x faster** with keyword filters
- Pytest (108 files): Up to **2.75x faster** with selective import
- Best for: Running specific tests, marked tests, development workflow, CI/CD with test splits

## [0.3.0] - 2024-11-15

### Changed
- 🏗️ **Better Integration**: Refactored plugin architecture for cleaner code
- ⚡ Early initialization in `pytest_configure` instead of lazy loading
- 🔧 Simplified `pytest_ignore_collect` hook to only use cached data
- 🐛 Fixed duplicate collection issues from custom collector conflicts
- 📊 Maintains all caching benefits from v0.2.0
- 🧹 Cleaner separation of concerns and more predictable behavior

### Fixed
- Duplicate collection issues
- Hook call complexity

### Performance
- Comparable to v0.2.0
- ~5% improvement on warm cache
- No regression in collection speed

## [0.2.0] - 2024-10-01

### Added
- ✨ **Incremental Caching**: Cache parsed results with file modification tracking
  - Persists to `.pytest_cache/v/fastcollect/cache.json`
  - Only reparses files that have changed
  - Shows cache statistics after collection
  - ~5% improvement on repeated runs
- Cache statistics display with verbose mode
- `--fastcollect-clear-cache` option

### Performance
- **Cold start (no cache)**: 3.34s (baseline)
- **Warm cache (no changes)**: 3.18s (1.05x faster)
- **Incremental (5 files changed)**: 3.50s (cache + reparse 1%)

### Changed
- Cache hit rate: 100% on unchanged files
- Persistent cache across pytest runs

## [0.1.0] - 2024-09-01

### Added
- 🎉 Initial release
- 🦀 Rust-based parallel AST parsing
- 🎯 File filtering via `pytest_ignore_collect` hook
- ⚡ Parallel processing with Rayon
- 📚 Comprehensive documentation

### Performance
- **200 files, 50 tests/file**: ~1.01x speedup
- **500 files, 100 tests/file**: ~1.01x speedup

### Features
- Automatic pytest plugin registration
- Command-line options:
  - `--use-fast-collect` / `--no-fast-collect`
  - `--fastcollect-cache` / `--no-fastcollect-cache`
- Test file patterns: `test_*.py` and `*_test.py`
- Ignores: `.git`, `__pycache__`, `.tox`, `.venv`, `venv`, `.eggs`, `*.egg-info`

## Version History Summary

| Version | Date | Key Feature | Performance |
|---------|------|-------------|-------------|
| 0.5.2 | 2025-01 | Property-Based Tests, Python 3.13/3.14, Stricter Types | Quality & Robustness |
| 0.5.1 | 2025-01 | Comprehensive Test Suite, Security | 182 tests, 60% coverage |
| 0.5.0 | 2025-01 | Production-Ready Daemon | 100-1000x on re-runs |
| 0.4.0 | 2024-12 | Selective Import | 1.55-2.75x with filters |
| 0.3.0 | 2024-11 | Better Integration | ~5% improvement |
| 0.2.0 | 2024-10 | Incremental Caching | 1.05x on warm cache |
| 0.1.0 | 2024-09 | Initial Release | 1.01x baseline |

## Upgrade Guide

### From 0.5.1 to 0.5.2
**Breaking Change**: Python 3.8 is no longer supported. Python 3.9+ is required.

```bash
pip install --upgrade pytest-fastcollect
```

Benefits:
- Property-based tests ensure better correctness
- Support for Python 3.13 and 3.14
- Fixed filter bug discovered by property-based testing
- Better type safety with stricter mypy checks

### From 0.5.0 to 0.5.1
No breaking changes. Simply upgrade:
```bash
pip install --upgrade pytest-fastcollect
```

### From 0.4.x to 0.5.0
No breaking changes. Simply upgrade:
```bash
pip install --upgrade pytest-fastcollect
```

New features available:
- `pytest --daemon-start` - Start collection daemon
- `pytest --daemon-status` - Check daemon status
- `pytest --daemon-health` - Health diagnostics
- `pytest --benchmark-collect` - Test if plugin helps your project

### From 0.3.x to 0.4.0
No breaking changes. Selective import is automatically applied when using `-k` or `-m` filters.

### From 0.2.x to 0.3.0
No breaking changes. Cache format remains compatible.

### From 0.1.x to 0.2.0
Cache files will be created in `.pytest_cache/v/fastcollect/`. Old cache directories can be safely deleted.

## Links

- **GitHub**: https://github.com/Samrhan/pytest-fastcollect
- **PyPI**: https://pypi.org/project/pytest-fastcollect/
- **Documentation**: See README.md
- **Issues**: https://github.com/Samrhan/pytest-fastcollect/issues
- **Security**: See SECURITY.md
- **Contributing**: See CONTRIBUTING.md

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
