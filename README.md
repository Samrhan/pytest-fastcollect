# pytest-fastcollect

A high-performance pytest plugin that uses Rust to accelerate test collection. This plugin leverages `rustpython-parser` to parse Python test files in parallel, identifying test functions and classes much faster than pure Python implementations.

## Features

- 🦀 **Rust-Powered Parsing**: Uses `rustpython-parser` for blazing-fast Python AST parsing
- ⚡ **Parallel Processing**: Leverages Rayon for parallel file processing
- 🎯 **Smart Filtering**: Pre-filters test files before pytest's collection phase
- 🔧 **Drop-in Replacement**: Works as a pytest plugin with no code changes required
- 🎛️ **Configurable**: Enable/disable fast collection with command-line flags

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

# Run benchmarks
python benchmark.py --synthetic
python benchmark.py --project /path/to/your/project
```

### Configuration Options

- `--use-fast-collect`: Enable Rust-based fast collection (default: True)
- `--no-fast-collect`: Disable fast collection and use standard pytest collection
- `--benchmark-collect`: Benchmark collection time (fast vs standard)

## Architecture

### How It Works

1. **Rust Collector (`FastCollector`)**:
   - Walks the directory tree to find Python test files
   - Uses `rustpython-parser` to parse each file's AST in parallel
   - Identifies test functions (starting with `test_`) and test classes (starting with `Test`)
   - Returns collected metadata to Python

2. **pytest Plugin Integration**:
   - Hooks into pytest's `pytest_ignore_collect` to filter files
   - Caches the list of files containing tests
   - Allows pytest to skip files that don't contain tests
   - Falls back to standard collection on errors

3. **File Detection**:
   - Test files: `test_*.py` or `*_test.py`
   - Ignored directories: `.git`, `__pycache__`, `.tox`, `.venv`, `venv`, `.eggs`, `*.egg-info`

### Components

```
pytest-fastcollect/
├── src/
│   └── lib.rs              # Rust implementation (FastCollector)
├── pytest_fastcollect/
│   ├── __init__.py         # Python package init
│   └── plugin.py           # pytest plugin hooks
├── tests/
│   └── sample_tests/       # Sample tests for validation
├── benchmark.py            # Benchmarking script
├── Cargo.toml              # Rust dependencies
└── pyproject.toml          # Python package metadata
```

## Benchmarks

### Synthetic Benchmarks

**100 files, 50 tests each (5,000 total tests)**:
```
Fast collection average:     1.8621s
Standard collection average: 1.7949s
Speedup:                     0.96x
```

**500 files, 100 tests each (50,000 total tests)**:
```
Fast collection average:     15.0391s
Standard collection average: 15.2124s
Speedup:                     1.01x
```

### Real-World Benchmarks

**pandas (969 test files)**:
```
Fast collection average:     1.6822s
Standard collection average: 1.2606s
Speedup:                     0.75x
```

### Performance Analysis

The current implementation shows marginal or negative performance improvement because:

1. **File Filtering Only**: The plugin currently only filters which files to collect, but pytest still parses each file
2. **Overhead**: The Rust collector adds overhead for file scanning and parsing
3. **Duplicate Work**: Both Rust and pytest parse the files (Rust for filtering, pytest for collection)

### Future Optimizations

To achieve significant speedup, the plugin needs to:

1. **Skip pytest Parsing**: Create pytest `Item` objects directly from Rust-parsed data
2. **Incremental Collection**: Cache parsing results and only re-parse modified files
3. **Lazy Loading**: Only parse files when their tests are actually executed
4. **Better Integration**: Use pytest's lower-level APIs to bypass standard collection

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

# Collect all tests
results = collector.collect()
# Returns: {"file_path": [{"name": "test_foo", "line": 10, "type": "Function"}, ...]}

# Collect from a specific file
results = collector.collect_file("/path/to/test_foo.py")
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
```

### Running Benchmarks

```bash
# Synthetic benchmark with custom parameters
python benchmark.py --synthetic --num-files 200 --tests-per-file 100

# Benchmark on a real project
python benchmark.py --project /path/to/project

# Run all benchmarks
python benchmark.py --all
```

## Contributing

Contributions are welcome! Areas for improvement:

1. **Performance Optimization**: Implement direct `Item` creation from Rust data
2. **Incremental Collection**: Add file modification tracking and caching
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

1. **No Speedup Yet**: Current implementation adds overhead; needs architectural improvements
2. **Limited Test Detection**: Only detects `test_*` functions and `Test*` classes
3. **No Fixture Support**: Doesn't analyze pytest fixtures or dependencies
4. **No Parametrization**: Doesn't expand parametrized tests

### Future Roadmap

- [ ] Direct pytest Item creation from Rust
- [ ] Incremental collection with file watching
- [ ] Support for pytest markers and fixtures
- [ ] Parallel test execution hints
- [ ] Integration with pytest-xdist
- [ ] Configuration file support (`.pytest-fastcollect.toml`)
- [ ] VS Code and PyCharm integration

## Contact

For issues, questions, or contributions, please open an issue on GitHub.
