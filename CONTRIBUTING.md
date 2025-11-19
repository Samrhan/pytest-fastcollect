# Contributing to pytest-fastcollect

Thank you for your interest in contributing to pytest-fastcollect! We welcome contributions from the community and appreciate your help in making this project better.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Enhancements](#suggesting-enhancements)
- [Documentation](#documentation)
- [Community](#community)

## Code of Conduct

This project adheres to a Code of Conduct that we expect all contributors to follow. By participating, you are expected to:

- Be respectful and inclusive
- Welcome newcomers and help them get started
- Focus on what is best for the community
- Show empathy towards other community members
- Accept constructive criticism gracefully

## Getting Started

### Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.8+** (Python 3.11+ recommended)
- **Rust 1.70+** (for building the extension)
- **Git** (for version control)
- **maturin** (for building Python-Rust packages)

### Quick Start

```bash
# Fork the repository on GitHub first

# Clone your fork
git clone https://github.com/YOUR_USERNAME/pytest-fastcollect.git
cd pytest-fastcollect

# Add upstream remote
git remote add upstream https://github.com/Samrhan/pytest-fastcollect.git

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install maturin pytest pytest-benchmark

# Build and install in development mode
maturin develop --release

# Run tests to ensure everything works
python -m pytest tests/ -v
```

## Development Setup

### Installing Development Dependencies

```bash
# Install all development tools
pip install -e ".[dev]"
pip install black isort mypy ruff bandit safety

# Install pre-commit hooks (coming soon)
# pre-commit install
```

### IDE Setup

#### VS Code (Recommended)

The repository includes a `.devcontainer` configuration for VS Code:

```bash
# Open in container
code .
# VS Code will prompt to reopen in container
```

Recommended extensions:
- Python (ms-python.python)
- Rust Analyzer (rust-lang.rust-analyzer)
- Pytest (littlefoxteam.vscode-python-test-adapter)

#### PyCharm

1. Open project in PyCharm
2. Configure Python interpreter to use virtual environment
3. Enable pytest as test runner
4. Install Rust plugin for Rust code editing

## Development Workflow

### Creating a Feature Branch

```bash
# Update your fork
git fetch upstream
git checkout main
git merge upstream/main

# Create a feature branch
git checkout -b feature/my-awesome-feature

# Or for bug fixes
git checkout -b fix/issue-123
```

### Making Changes

1. **Write Code**: Make your changes following our [Code Style](#code-style)
2. **Write Tests**: Add tests for your changes (see [Testing](#testing))
3. **Update Docs**: Update documentation if needed
4. **Test Locally**: Run tests and linters before committing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_cache.py -v

# Run with coverage
python -m pytest tests/ --cov=pytest_fastcollect --cov-report=html

# Run linters (when configured)
black pytest_fastcollect/
isort pytest_fastcollect/
mypy pytest_fastcollect/
ruff check pytest_fastcollect/
```

### Committing Changes

Follow conventional commits format:

```bash
# Format: <type>(<scope>): <subject>

git commit -m "feat(cache): add TTL support for cache entries"
git commit -m "fix(daemon): handle connection timeout correctly"
git commit -m "docs(readme): update installation instructions"
git commit -m "test(filter): add edge case tests for expression parsing"
git commit -m "refactor(plugin): extract magic numbers to constants"
```

**Commit Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding or updating tests
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `style`: Code style changes (formatting, etc.)
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

## Testing

### Test Structure

```
tests/
├── test_cache.py          # Cache module tests
├── test_filter.py         # Filter module tests
├── test_daemon.py         # Daemon tests
├── test_selective_import.py  # Integration tests
└── sample_tests/          # Sample test files for testing
```

### Writing Tests

```python
import pytest

class TestMyFeature:
    """Test my awesome feature."""

    @pytest.mark.unit
    def test_basic_functionality(self):
        """Test basic functionality."""
        result = my_function()
        assert result == expected_value

    @pytest.mark.integration
    def test_integration_with_daemon(self):
        """Test integration with daemon."""
        # Integration test code
        pass

    @pytest.mark.slow
    def test_performance(self):
        """Test performance characteristics."""
        # Performance test code
        pass
```

### Test Markers

Use appropriate markers for tests:
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Slow tests (>1 second)
- `@pytest.mark.smoke` - Smoke tests (quick validation)
- `@pytest.mark.regression` - Regression tests

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test class
python -m pytest tests/test_cache.py::TestCacheStats

# Run specific test
python -m pytest tests/test_cache.py::TestCacheStats::test_hit_rate

# Run with markers
python -m pytest -m "unit and not slow"

# Run with coverage
python -m pytest --cov=pytest_fastcollect --cov-report=html
```

### Test Coverage Goals

- **Overall**: 80%+ coverage
- **Critical Modules** (cache, filter, daemon): 90%+
- **New Features**: 100% coverage required
- **Bug Fixes**: Add regression test

## Code Style

### Python Code Style

We follow **PEP 8** with some modifications:

```python
# Use Black for formatting (line length: 100)
black --line-length 100 pytest_fastcollect/

# Use isort for import sorting
isort pytest_fastcollect/

# Use type hints for all functions
def parse_file(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """Parse a Python file and extract test items.

    Args:
        file_path: Path to the file to parse
        encoding: File encoding (default: utf-8)

    Returns:
        Dictionary mapping test names to metadata
    """
    pass
```

### Rust Code Style

Follow Rust standard conventions:

```bash
# Format Rust code
cargo fmt

# Run clippy linter
cargo clippy -- -D warnings

# Check code
cargo check
```

### Docstrings

Use Google-style docstrings:

```python
def my_function(arg1: str, arg2: int = 0) -> bool:
    """Short one-line description.

    Longer description explaining what the function does,
    when to use it, and any important details.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2 (default: 0)

    Returns:
        True if successful, False otherwise

    Raises:
        ValueError: If arg1 is empty
        RuntimeError: If operation fails

    Examples:
        >>> my_function("test", 42)
        True
    """
    pass
```

## Pull Request Process

### Before Submitting

- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation is updated
- [ ] CHANGELOG.md is updated (for significant changes)
- [ ] Commit messages follow conventional format
- [ ] Branch is up to date with main

### Submitting a PR

1. **Push to Your Fork**
   ```bash
   git push origin feature/my-awesome-feature
   ```

2. **Create Pull Request**
   - Go to GitHub and create a pull request
   - Use the PR template (will be auto-populated)
   - Link related issues (e.g., "Fixes #123")
   - Add appropriate labels

3. **PR Title Format**
   ```
   feat(cache): add TTL support for cache entries
   fix(daemon): handle connection timeout correctly
   ```

4. **PR Description Should Include:**
   - What changed and why
   - How to test the changes
   - Screenshots/examples (if applicable)
   - Breaking changes (if any)
   - Related issues

### Review Process

1. **Automated Checks**: CI/CD will run tests and linters
2. **Code Review**: Maintainers will review your code
3. **Feedback**: Address any comments or requested changes
4. **Approval**: Once approved, maintainers will merge

### After Merging

- Delete your feature branch
- Update your fork's main branch
- Thank you for contributing! 🎉

## Reporting Bugs

### Before Reporting

- Check if the bug has already been reported
- Try the latest version of pytest-fastcollect
- Collect relevant information

### Bug Report Template

Use the GitHub issue template or include:

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Run pytest with '...'
2. Click on '....'
3. See error

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Environment:**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.11.4]
- pytest-fastcollect version: [e.g., 0.5.0]
- pytest version: [e.g., 8.0.0]

**Additional context**
Any other context about the problem.

**Logs**
```
Paste relevant logs here
```
```

## Suggesting Enhancements

### Enhancement Proposal Template

```markdown
**Is your feature request related to a problem?**
A clear description of the problem.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Other solutions or features you've considered.

**Additional context**
Any other context, mockups, or examples.
```

### Feature Acceptance Criteria

Features should:
- Align with project goals (performance, usability)
- Have clear use cases and benefits
- Not significantly increase complexity
- Include tests and documentation
- Maintain backward compatibility (or have clear migration path)

## Documentation

### Types of Documentation

1. **Code Comments**: Explain complex logic
2. **Docstrings**: Document all public APIs
3. **README.md**: User-facing documentation
4. **CHANGELOG.md**: Track changes between versions
5. **Guides**: Tutorial-style documentation

### Building Documentation

```bash
# Install documentation dependencies (when available)
pip install sphinx sphinx-rtd-theme

# Build documentation
cd docs
make html

# View documentation
open _build/html/index.html
```

## Community

### Getting Help

- 💬 **Discussions**: Use GitHub Discussions for questions
- 🐛 **Issues**: Report bugs via GitHub Issues
- 📧 **Email**: Contact maintainers for private matters

### Communication Guidelines

- Be respectful and professional
- Provide context and examples
- Search before asking (your question may be answered)
- Help others when you can

### Recognition

Contributors are recognized in:
- CHANGELOG.md (for significant contributions)
- README.md (major contributors)
- GitHub contributors page

## Development Tips

### Performance Testing

```bash
# Run benchmarks
python benchmark.py --synthetic --num-files 500

# Benchmark specific feature
python benchmark_incremental.py

# Profile code
python -m cProfile -o output.prof benchmark.py
python -m pstats output.prof
```

### Debugging

```bash
# Run with verbose output
python -m pytest tests/ -vv

# Run single test with debugging
python -m pytest tests/test_cache.py::test_name -vv -s --pdb

# Check daemon logs
tail -f /tmp/pytest-fastcollect-*/daemon.log
```

### Rust Development

```bash
# Build in debug mode (faster compilation)
maturin develop

# Build in release mode (faster runtime)
maturin develop --release

# Run Rust tests
cargo test

# Check for issues
cargo clippy
```

## License

By contributing to pytest-fastcollect, you agree that your contributions will be licensed under the MIT License.

## Questions?

If you have questions about contributing:
1. Check this guide thoroughly
2. Search existing issues and discussions
3. Open a new discussion on GitHub
4. Contact the maintainers

---

**Thank you for contributing to pytest-fastcollect!** 🚀

Your contributions make this project better for everyone.
