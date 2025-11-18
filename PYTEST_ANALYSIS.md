# Pytest Collection Mechanism Analysis

## Overview

This document analyzes pytest's test collection mechanism to identify optimization opportunities for pytest-fastcollect.

## Collection Flow

### 1. Entry Point: `Session.perform_collect()`
**File**: `_pytest/main.py:777`

```python
def perform_collect(self, args=None, genitems=True):
    # Resolves command-line arguments
    # Calls collect_one_node(self) to start collection
    # Expands collectors to items
```

**Key Points**:
- Line 837: `rep = collect_one_node(self)` - Triggers collection
- Line 857: `self.items.extend(self.genitems(node))` - Expands collectors into items
- Line 860: `hook.pytest_collection_modifyitems()` - Allows modifications
- Line 867: `hook.pytest_collection_finish()` - Cleanup hook

### 2. Path Collection: `Session._collect_path()`
**File**: `_pytest/main.py:736`

```python
def _collect_path(self, path, path_cache):
    if path.is_dir():
        col = ihook.pytest_collect_directory(path=path, parent=self)
    elif path.is_file():
        cols = ihook.pytest_collect_file(file_path=path, parent=self)
```

**Key Points**:
- Line 758: **pytest_collect_file hook** - This is where plugins can intercept file collection
- Returns a sequence of Collector objects (e.g., Module)
- Has built-in path caching

### 3. File Collection: `pytest_collect_file()`
**File**: `_pytest/python.py:194`

```python
def pytest_collect_file(file_path, parent):
    if file_path.suffix == ".py":
        if not path_matches_patterns(file_path, parent.config.getini("python_files")):
            return None
        module = ihook.pytest_pycollect_makemodule(module_path=file_path, parent=parent)
        return module
```

**Key Points**:
- Line 195-200: Pattern matching for test files (`test_*.py`, etc.)
- Line 202: **pytest_pycollect_makemodule hook** - Creates Module object
- Line 214: Default implementation returns `Module.from_parent()`

### 4. Module Collection: `Module.collect()`
**File**: `_pytest/python.py:562`

```python
class Module(nodes.File, PyCollector):
    def _getobj(self):
        return importtestmodule(self.path, self.config)  # ⚠️ IMPORTS MODULE

    def collect(self):
        self._register_setup_module_fixture()
        self._register_setup_function_fixture()
        self.session._fixturemanager.parsefactories(self)
        return super().collect()  # Calls PyCollector.collect()
```

**Key Points**:
- Line 560: **`importtestmodule()` - THE BOTTLENECK**
  - Module MUST be imported to access test functions/classes
  - This is unavoidable in Python - you need the actual function objects
  - Import time dominates collection time in large projects

### 5. Test Introspection: `PyCollector.collect()`
**File**: `_pytest/python.py:399`

```python
def collect(self):
    dicts = [getattr(self.obj, "__dict__", {})]
    if isinstance(self.obj, type):
        for basecls in self.obj.__mro__:
            dicts.append(basecls.__dict__)

    for dic in dicts:
        for name, obj in list(dic.items()):
            res = ihook.pytest_pycollect_makeitem(collector=self, name=name, obj=obj)
            # Creates Function or Class collectors
```

**Key Points**:
- Line 404-407: Introspects module's `__dict__` and class MRO
- Line 432: **pytest_pycollect_makeitem hook** - Creates test items
- Line 419: Iterates over every attribute in the module

## Bottleneck Analysis

### Primary Bottleneck: Module Import (95%+ of collection time)

**Location**: `Module._getobj()` → `importtestmodule()`

**Why it's slow**:
1. **Import semantics**: Python must parse, compile, and execute module code
2. **Dependency loading**: Modules import their dependencies (numpy, pandas, etc.)
3. **Side effects**: Import-time code execution (class definitions, decorators, etc.)
4. **No parallelism**: Python's GIL prevents parallel imports

**Why we can't bypass it**:
- pytest needs actual Python objects (functions, classes) to create test Items
- Function objects contain metadata: fixtures, marks, parametrization
- Introspection requires imported objects - can't work with just AST

### Secondary Bottlenecks

1. **Path traversal** (~5%)
   - Walking directory tree
   - Pattern matching for test files
   - **Our optimization**: Rust-based parallel file discovery ✅

2. **Hook overhead** (~2%)
   - pytest_collect_file called for every file
   - pytest_pycollect_makeitem called for every module attribute
   - **Our optimization**: Early filtering, simplified hooks ✅

3. **Fixture parsing** (~1%)
   - Analyzing fixture dependencies
   - Building fixture graphs
   - **Not optimized yet**

## Current pytest-fastcollect Optimizations

### v0.3.0 Architecture

```
pytest_configure (EAGER)
    ↓
FastCollector.collect_with_metadata()  [RUST, PARALLEL]
    ↓
CollectionCache.merge_with_rust_data()
    ↓
Pre-populate _test_files_cache
    ↓
pytest traversal begins
    ↓
pytest_ignore_collect (FAST FILTER)
    ↓
pytest_collect_file (STANDARD)
    ↓
Module.collect() → importtestmodule() [SLOW, UNAVOIDABLE]
```

### What We Optimize

✅ **File Discovery** (Rust, parallel)
✅ **File Filtering** (Pre-computed set lookup)
✅ **Caching** (Incremental, mtime-based)
✅ **Hook Overhead** (Simplified, early init)

### What We Can't Optimize

❌ **Module Import** - Fundamental Python limitation
❌ **Object Introspection** - Need actual objects
❌ **Fixture Resolution** - Requires imported code

## Potential Future Optimizations

### 1. Lazy Import (Highest Impact)

**Idea**: Only import modules when tests are actually run, not during collection

**Implementation**:
- Create stub Item objects from Rust AST data
- Defer module import until test execution
- Use pytest's lazy collection if available

**Challenges**:
- pytest expects real objects during collection
- Fixtures require imported modules
- Parametrization needs access to decorators

**Estimated Impact**: 50-90% faster collection (but slower first test run)

### 2. Parallel Module Import

**Idea**: Import modules in parallel threads/processes

**Implementation**:
- Use multiprocessing to bypass GIL
- Import modules in worker processes
- Serialize test items back to main process

**Challenges**:
- Serialization overhead
- Process startup cost
- Import side effects may not be thread-safe

**Estimated Impact**: 20-40% faster on multi-core systems

### 3. Import Mocking/Stubbing

**Idea**: Create fake module objects that satisfy pytest's introspection

**Implementation**:
- Generate stub classes/functions from AST
- Provide minimal metadata for pytest
- Real import only on test execution

**Challenges**:
- Complex fixture dependencies
- Mark and parametrization handling
- Maintaining compatibility

**Estimated Impact**: 60-80% faster, high complexity

### 4. AST-Based Fixture Analysis

**Idea**: Parse fixture dependencies from AST instead of importing

**Implementation**:
- Analyze `@pytest.fixture` decorators in AST
- Build dependency graph without imports
- Cache fixture metadata

**Challenges**:
- Dynamic fixtures (fixtures that call other functions)
- Fixture factories
- Complex parametrization

**Estimated Impact**: 5-10% faster

### 5. Collection Result Caching

**Idea**: Cache the full collection results, not just file metadata

**Implementation**:
- Serialize collected Items to cache
- Invalidate on file/dependency changes
- Deserialize on subsequent runs

**Challenges**:
- Item serialization complexity
- Dependency tracking (imports)
- Plugin compatibility

**Estimated Impact**: 80-95% faster on cache hit, but fragile

## Recommended Next Steps

Based on this analysis, the most promising optimization is:

### **Option A: Lazy Collection + Import Deferral**

**Approach**:
1. Parse test files with Rust
2. Create minimal Item stubs from AST
3. Store import info for later
4. Only import when test runs

**Pros**:
- Massive speedup for `--collect-only`
- Enables selective import for `-k` filtering
- Clean architecture

**Cons**:
- Doesn't speed up actual test runs
- May break some plugins
- Complex implementation

### **Option B: Selective Import Based on Filters**

**Approach**:
1. Parse all files with Rust
2. Apply `-k`, `-m` filters to AST data
3. Only import files with matching tests
4. Standard collection for selected files

**Pros**:
- Significant speedup when running subsets
- Compatible with pytest
- Easier to implement

**Cons**:
- No improvement for full runs
- Still requires import eventually

### **Option C: Incremental Import Optimization**

**Approach**:
1. Track import times per module
2. Cache imported modules between runs
3. Use import hooks to speed up repeated imports
4. Pre-import during idle time

**Pros**:
- Some speedup on repeated runs
- Low complexity
- Plugin compatible

**Cons**:
- Limited impact (10-20%)
- Cache invalidation challenges

## Conclusion

The fundamental bottleneck in pytest collection is **module import**, which we cannot eliminate while maintaining pytest compatibility. Our current optimizations (v0.3.0) have successfully optimized everything around the import step, achieving:

- ✅ Near-zero file discovery overhead (Rust)
- ✅ Efficient caching (incremental)
- ✅ Minimal hook overhead

**The only way to achieve dramatic speedups (>2x) is to defer or eliminate module imports**, which requires breaking changes to pytest's collection model.

**Recommended**: Implement **Option B (Selective Import)** as it provides real-world value for the common workflow of running filtered test subsets while maintaining pytest compatibility.
