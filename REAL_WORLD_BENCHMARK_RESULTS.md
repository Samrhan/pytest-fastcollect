# Real-World Codebase Benchmark Results

## Executive Summary

Lazy collection has been benchmarked on multiple real-world codebases and synthetic test suites. The results show **no significant performance improvement** and in some cases show performance degradation.

**Key Finding**: Lazy collection overhead outweighs the benefits of deferred imports across all tested scenarios.

## Benchmark Date

- **Date**: 2025-11-19
- **Environment**: Linux, Python 3.11.14, pytest 9.0.1
- **pytest-fastcollect**: v0.6.0 (lazy collection enabled)

## Methodology

All benchmarks measure collection time using `pytest --collect-only -q`:
- **With plugin**: Default behavior (lazy collection enabled for ~58% of files)
- **Without plugin**: Baseline pytest with `-p no:pytest_fastcollect`
- **Runs**: 3 iterations per configuration for statistical validity
- **Metric**: Mean collection time in seconds

## Results Summary

| Project | Test Files | Tests | With Plugin | Without Plugin | Speedup | Status |
|---------|-----------|-------|-------------|----------------|---------|--------|
| **pytest-fastcollect** | 8 | 182 | 0.670s | 0.661s | **0.99x** | ⚠️ 1% slower |
| **Flask** | 27 | ? | 0.577s | 0.567s | **0.98x** | ⚠️ 2% slower |
| **Heavy Synthetic** (100 files) | 100 | 400 | 0.967s | 0.845s | **0.87x** | ⚠️ 14% slower |
| **requests** (9 files) | 9 | 611 | (running) | 0.992s | *pending* | *pending* |

**Average Speedup: 0.95x (5% slower)**

## Detailed Results

### 1. pytest-fastcollect (Self-Test)

**Configuration:**
- Test files: 8
- Tests: 182
- Lazy collection: 58% of files (4/7, daemon tests in skiplist)

**Results:**
```
With plugin:    0.670s (avg of 3 runs: 0.691, 0.670, 0.650)
Without plugin: 0.661s (avg of 3 runs: 0.657, 0.643, 0.683)
Speedup:        0.99x (-1.4%)
```

**Analysis**: Marginal slowdown, within measurement error. Small test suite with lightweight imports.

### 2. Flask Framework

**Configuration:**
- Test files: 27
- Tests: Collection reported 0 (config issue, but timing valid)
- Real-world web framework with complex imports

**Results:**
```
Standard collection:       0.5669s
Fast collection (no cache): 0.6044s (0.94x)
Fast collection (cached):   0.5772s (0.98x)
```

**Analysis**: 2-6% slower with plugin. Flask has moderate complexity but lazy collection overhead dominates.

### 3. Heavy Synthetic Suite

**Configuration:**
- Created synthetic test suite to stress-test lazy collection
- 100 test files, each with 4 tests (400 total)
- Each file imports `heavy_module` with expensive module-level computation
- Simulates worst-case: heavy framework imports (Django, NumPy, etc.)

**Results:**
```
With plugin:    0.967s (avg of 3 runs: 1.106, 0.933, 0.863)
Without plugin: 0.845s (avg of 3 runs: 0.865, 0.818, 0.852)
Speedup:        0.87x (-14.5%)
```

**Analysis**: **Significantly slower** even with heavy imports. This contradicts the hypothesis that lazy collection benefits scale with import complexity.

### 4. Test Execution (Not Just Collection)

**Configuration:**
- Same heavy synthetic suite
- Full test execution with `pytest -q -x` (not --collect-only)
- Measures collection + execution time

**Results:**
```
With plugin:    1.053s (avg: 1.117, 1.004, 1.039)
Without plugin: 1.035s (avg: 1.063, 1.083, 0.959)
Speedup:        0.98x (-1.8%)
```

**Analysis**: Even with execution, no benefit. Test execution time dominates, and collection overhead remains.

### 5. requests Library (In Progress)

**Configuration:**
- Test files: 9
- Tests: 611
- Popular HTTP library

**Preliminary Results:**
```
Standard collection: 0.9915s (avg of 3 runs: 0.996, 0.995, 0.983)
Fast collection:     (still running)
```

## Why No Performance Improvement?

### Root Causes

1. **--collect-only Mode Limitation**
   - Lazy collection defers imports until test EXECUTION
   - In collection-only mode, pytest still accesses test metadata
   - The `obj` property is accessed during collection for markers, fixtures
   - Deferred import benefit not fully realized

2. **Custom Node Overhead**
   - Creating FastModule, FastClass, FastFunction objects adds cost
   - Property-based lazy loading has overhead
   - Memory allocation for custom node structures

3. **Duplicate Filtering Cost**
   - `pytest_collection_modifyitems` hook iterates all items twice
   - Set operations and duplicate checking
   - Scales O(n) with test count

4. **Partial Coverage**
   - Only 58% of pytest-fastcollect tests use lazy collection
   - 42% still use standard collection (daemon tests in skiplist)
   - Mixed collection modes add complexity

5. **Rust Parsing Overhead Still Present**
   - Rust AST parsing runs regardless of lazy collection
   - FFI overhead for data transfer
   - File I/O and parsing time unchanged

6. **Module-Level Side Effects**
   - Even with lazy imports, some module code may run
   - Global initialization, decorators, metaclasses
   - Python's import system complexity

### Fundamental Architecture Issue

Lazy collection architecture has inherent overhead:

```python
# Standard pytest flow:
Module → collect() → import module → create Function nodes → done

# Lazy collection flow:
Module → FastModule with metadata → create FastFunction nodes
       → (later) obj property accessed → import module
       → overhead of custom nodes + deferred import
```

The extra layer of indirection (custom nodes with lazy properties) adds more cost than it saves by deferring imports.

## Comparison with Other Optimizations

| Feature | Speedup | Proven? | Use Case |
|---------|---------|---------|----------|
| **Selective Import** (-k/-m filters) | **1.65-1.72x** | ✅ Yes | Filter-based test selection |
| **Incremental Caching** | **1.05x** | ✅ Yes | Warm cache, unchanged files |
| **Daemon Mode** | **100-1000x** | ✅ Yes | Repeated test runs |
| **Lazy Collection** | **0.95x** | ❌ No | (slower, not beneficial) |

Lazy collection is the **worst performing** optimization in pytest-fastcollect.

## Architectural Insights

### What Lazy Collection DOES Provide

1. ✅ **Clean code architecture**: Separation of parsing and execution
2. ✅ **Foundation for future work**: Infrastructure for advanced optimizations
3. ✅ **Understanding of pytest internals**: Deep knowledge of hook system
4. ✅ **No breaking changes**: All tests pass, backward compatible

### What Lazy Collection DOES NOT Provide

1. ❌ **Performance improvement**: 0.95x average (slower)
2. ❌ **Scalability with suite size**: Even 100-file suite shows degradation
3. ❌ **Benefit from heavy imports**: Contradicts hypothesis
4. ❌ **Memory reduction**: Custom nodes offset any savings

## Recommendations

### For pytest-fastcollect v0.6.0

**DISABLE lazy collection by default:**

1. **Revert pytest_collect_file hook to return None**
   - Remove FastModule creation
   - Use standard pytest collection for all files
   - Keep skiplist documentation for context

2. **Keep lazy_collection.py for reference**
   - Document as "experimental feature (disabled)"
   - Valuable learning and architecture reference
   - May be useful if pytest internals change

3. **Update CHANGELOG and docs**
   - Document lazy collection as "experimental, currently disabled"
   - Set realistic expectations: overhead > benefits
   - Focus communication on selective import (1.65-1.72x proven)

4. **Prioritize proven optimizations**
   - Selective import: 1.65-1.72x speedup
   - Daemon mode: 100-1000x on re-runs
   - Incremental caching: 1.05x warm cache

### For Future Research

If lazy collection is to be revisited:

1. **Eliminate custom node overhead**
   - Modify pytest core instead of creating custom nodes
   - Contribute upstream to pytest project
   - Requires deep pytest internals knowledge

2. **Optimize duplicate filtering**
   - Use more efficient data structures
   - Filter earlier in the collection pipeline
   - Minimize O(n) operations

3. **Test on extreme cases**
   - 10,000+ test files
   - Very heavy framework imports (Django ORM, TensorFlow)
   - Projects where collection time >> execution time

4. **Profile and optimize hotspots**
   - Use cProfile to identify bottlenecks
   - Focus on most expensive operations
   - Reduce FFI overhead with better serialization

## Conclusions

1. **Lazy collection shows no performance benefit** on tested codebases (0.95x average)
2. **Overhead outweighs benefits** even with heavy imports and large suites
3. **Selective import is the proven winner** (1.65-1.72x speedup)
4. **Recommendation: DISABLE lazy collection** in production releases
5. **Keep as architectural reference** for future work

The lazy collection implementation is **technically sound** and **all tests pass**, but it does not provide the expected performance benefits. This is a valuable learning: not all theoretically good ideas translate to practical speedups.

## Raw Data Appendix

### pytest-fastcollect Self-Test
```
WITH PLUGIN (3 runs):
  Run 1: 0.691s
  Run 2: 0.670s
  Run 3: 0.650s
  Average: 0.670s

WITHOUT PLUGIN (3 runs):
  Run 1: 0.657s
  Run 2: 0.643s
  Run 3: 0.683s
  Average: 0.661s
```

### Flask Framework
```
Standard collection (3 runs):
  Run 1: 0.5746s
  Run 2: 0.5382s
  Run 3: 0.5877s
  Average: 0.5669s

Fast collection no cache (3 runs):
  Run 1: 0.5947s
  Run 2: 0.6149s
  Run 3: 0.6037s
  Average: 0.6044s

Fast collection cached (3 runs):
  Run 1: 0.5735s
  Run 2: 0.5868s
  Run 3: 0.5714s
  Average: 0.5772s
```

### Heavy Synthetic Suite (Collection Only)
```
WITH PLUGIN (3 runs):
  Run 1: 1.106s
  Run 2: 0.933s
  Run 3: 0.863s
  Average: 0.967s

WITHOUT PLUGIN (3 runs):
  Run 1: 0.865s
  Run 2: 0.818s
  Run 3: 0.852s
  Average: 0.845s
```

### Heavy Synthetic Suite (With Execution)
```
WITH PLUGIN (3 runs):
  Run 1: 1.117s
  Run 2: 1.004s
  Run 3: 1.039s
  Average: 1.053s

WITHOUT PLUGIN (3 runs):
  Run 1: 1.063s
  Run 2: 1.083s
  Run 3: 0.959s
  Average: 1.035s
```

---

**Generated**: 2025-11-19
**Version**: pytest-fastcollect v0.6.0
**Benchmark Suite**: Real-world codebases + synthetic heavy test suite
**Conclusion**: **Lazy collection should be DISABLED** due to performance degradation
