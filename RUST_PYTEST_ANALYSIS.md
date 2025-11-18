# Rebuilding pytest in Rust - Feasibility Analysis

## The Question

What would it cost to rebuild pytest in Rust with API compatibility?

## TL;DR

**Short answer**: Extremely expensive (12-24 person-months), limited benefit because **Python module import remains unavoidable**.

**Better approach**: Hybrid Rust/Python runner that handles orchestration in Rust but delegates to Python for execution.

## Why the Bottleneck Persists Even in Rust

The fundamental issue is **not pytest's implementation language**, it's **Python's import semantics**:

```
┌─────────────────────────────────────┐
│  Rust pytest (hypothetical)        │
├─────────────────────────────────────┤
│  1. Parse test files (Rust) ✅ FAST│
│  2. Collect metadata (Rust) ✅ FAST │
│  3. Import Python modules ❌ SLOW   │  ← UNAVOIDABLE
│  4. Execute tests (Python) ❌ SLOW  │  ← MUST USE PYTHON
└─────────────────────────────────────┘
```

**Why you MUST import Python modules**:
- Tests are Python code that must execute in a Python interpreter
- Fixtures are Python functions with complex scoping and dependency injection
- Setup/teardown code runs in Python
- Test assertions use Python's runtime

**What Rust can't do**:
- Run Python code without CPython
- Access Python objects without importing
- Execute test logic without the Python runtime

## Full Pytest Reimplementation - Cost Analysis

### Core Components to Reimplement

#### 1. Collection System (~3-4 months)
**Lines of code**: ~5,000
**Complexity**: Medium-High

Components:
- Session management
- Path traversal and filtering
- pytest_collect_file/directory hooks
- Collector node hierarchy
- Item creation

**Challenge**: Must maintain exact pytest semantics for compatibility

#### 2. Fixture System (~6-8 months)
**Lines of code**: ~8,000
**Complexity**: VERY HIGH

Components:
- Fixture registration and lookup
- Scope management (function, class, module, session, package)
- Dependency resolution (fixture dependencies on other fixtures)
- Autouse fixtures
- Fixture parametrization
- Fixture caching per scope
- Teardown/cleanup handling
- Request object with complex APIs

**Challenge**: This is the most complex part of pytest. The fixture system is incredibly sophisticated with:
- Dynamic fixture discovery
- Circular dependency detection
- Fixture factories
- Yield fixtures with cleanup
- Fixture finalization order
- tmpdir, capsys, monkeypatch built-ins

**Reality check**: This alone could take a senior engineer 6+ months

#### 3. Plugin System (~2-3 months)
**Lines of code**: ~3,000 (using pluggy)
**Complexity**: High

Components:
- Hook specification
- Hook implementation
- Plugin registration
- Hook call ordering (tryfirst, trylast, hookwrapper)
- Plugin compatibility layer

**Challenge**: Need to maintain compatibility with existing Python plugins (impossible in pure Rust)

#### 4. Assertion Rewriting (~1-2 months)
**Lines of code**: ~2,000
**Complexity**: High

Components:
- AST rewriting for better assertion messages
- Import hooks
- Bytecode manipulation

**Challenge**: Requires deep integration with Python's import system

#### 5. Parametrization (~2-3 months)
**Lines of code**: ~2,500
**Complexity**: Medium-High

Components:
- @pytest.mark.parametrize
- pytest_generate_tests hook
- Indirect parametrization
- ID generation
- Parametrize with fixtures

#### 6. Marks System (~1 month)
**Lines of code**: ~1,500
**Complexity**: Medium

Components:
- Mark registration
- Mark application
- Mark inheritance
- Built-in marks (skip, xfail, parametrize, etc.)

#### 7. Test Execution (~2-3 months)
**Lines of code**: ~4,000
**Complexity**: High

Components:
- Setup/teardown execution
- Exception handling
- Timeout support
- Test outcome tracking
- Reporting

**Critical**: Must use CPython to actually run tests

#### 8. Output/Reporting (~1-2 months)
**Lines of code**: ~3,000
**Complexity**: Medium

Components:
- Terminal output
- Progress reporting
- JUnit XML
- HTML reports
- JSON reports
- Live logging

#### 9. Configuration (~1 month)
**Lines of code**: ~2,000
**Complexity**: Medium

Components:
- pytest.ini/pyproject.toml parsing
- Command-line options
- Config ini options
- rootdir detection

### Total Estimated Effort

**Conservative estimate**: 18-24 person-months
**Lines of code**: ~30,000+ (pytest itself is ~40k LOC)
**Team size**: 2-3 experienced developers
**Timeline**: 9-12 months for MVP, 18-24 months for production-ready

### What You'd Gain

**Performance improvements**:
- Collection: 10-20% faster (we already achieve this with current plugin)
- Execution orchestration: 5-10% faster
- Memory usage: Potentially lower
- **Overall speedup**: ~15-30% for full test runs

**What you WOULDN'T gain**:
- ❌ Faster module import (still need CPython)
- ❌ Faster test execution (still running Python code)
- ❌ Python plugin compatibility (would break ecosystem)

### Major Risks

1. **Plugin Ecosystem**: 1000+ pytest plugins would be incompatible
2. **Edge Cases**: Years of bug fixes and edge case handling
3. **Maintenance**: Keeping up with pytest development
4. **Adoption**: Users won't switch without huge benefits
5. **Python-Rust Bridge**: Overhead of FFI calls

## Better Alternative: Hybrid Architecture

Instead of full reimplementation, build a **Rust Test Orchestrator** that:

### Architecture

```
┌──────────────────────────────────────────┐
│  Rust Test Orchestrator                  │
├──────────────────────────────────────────┤
│  ✅ File discovery (parallel)            │
│  ✅ Test parsing (Rust AST)              │
│  ✅ Test filtering (-k, -m)               │
│  ✅ Test scheduling (parallel execution) │
│  ✅ Result aggregation                    │
├──────────────────────────────────────────┤
│  Python Execution Workers (pool)         │
│    - Import modules                       │
│    - Run fixtures                         │
│    - Execute tests                        │
│    - Report results back to Rust         │
└──────────────────────────────────────────┘
```

### What This Achieves

**Speedups**:
- ✅ Parallel test execution (2-8x on multi-core)
- ✅ Fast test filtering
- ✅ Efficient scheduling
- ✅ Lower overhead per test

**Compatibility**:
- ✅ Uses pytest for actual test execution
- ✅ Plugin compatibility maintained
- ✅ Fixture system works as-is

**Effort**: 3-6 months (vs 18-24 for full rewrite)

### Similar to Existing Tools

This is similar to:
- **pytest-xdist**: Parallel execution (but in Python)
- **cargo test**: Rust's parallel test runner
- **bazel test**: Build system test runner

## Recommended Approach: Selective Import (v0.4.0)

Given the analysis, the most practical path is our **Option B** from PYTEST_ANALYSIS.md:

### Selective Import Implementation

**Effort**: 2-4 weeks
**Impact**: 20-80% faster for filtered runs (common workflow)

```rust
// In Rust: Parse all files, extract test names
let all_tests = parse_all_test_files_parallel();

// Apply filters before importing
let filtered_tests = apply_filters(all_tests, k_expr, markers);

// Only these files get imported
let files_to_import: Vec<Path> = filtered_tests
    .iter()
    .map(|t| t.file_path)
    .unique()
    .collect();
```

**Benefits**:
- ✅ Works with existing pytest
- ✅ Real speedup for `pytest -k test_foo`
- ✅ No breaking changes
- ✅ Low complexity

**Example speedup**:
```
# Full run: 100 files, 1000 tests
pytest                           # 10s

# Filtered run: 5 matching files, 50 tests
pytest -k test_user              # 10s (imports all files)
pytest -k test_user (with v0.4)  # 2s (imports only 5 files) ← 5x faster
```

## Conclusion

**Full Rust pytest reimplementation**:
- Cost: 18-24 person-months, $300k-500k
- Benefit: 15-30% speedup
- Risk: High (plugin incompatibility, edge cases)
- **Verdict**: ❌ Not worth it

**Hybrid Rust orchestrator**:
- Cost: 3-6 months
- Benefit: 2-8x for parallel execution
- Risk: Medium
- **Verdict**: 🤔 Interesting but complex

**Selective import (v0.4.0)**:
- Cost: 2-4 weeks
- Benefit: 2-10x for filtered runs
- Risk: Low
- **Verdict**: ✅ Best ROI

## The Real Innovation Opportunity

The true innovation isn't reimplementing pytest in Rust—it's **changing how we think about test collection**:

### Lazy Evaluation Model

Instead of:
```
collect_all() → filter() → run()
```

Do:
```
parse_all() → filter() → collect_filtered() → run()
```

This is what **selective import** achieves, and it's the key insight that makes Rust valuable here.

## References

- pytest source: ~40,000 LOC Python
- pluggy: ~3,000 LOC Python
- RustPython: Full Python interpreter in Rust (huge project)
- Ruff: Python linter in Rust (doesn't need to execute code)
- uv: Python package manager in Rust (doesn't need to run Python)

**Key difference**: Test runners MUST execute Python code, so Rust has limited advantage compared to tools like ruff/uv that only analyze code.
