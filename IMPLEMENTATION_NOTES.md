# pytest-fastcollect Implementation Notes

## Current Status (v0.1.0)

### ✅ What's Working

1. **Rust-based Test Discovery**
   - Fast parallel parsing of Python test files using `rustpython-parser`
   - Identifies test functions (`test_*`) and classes (`Test*`)
   - File traversal with smart ignore patterns
   - Returns structured test metadata to Python

2. **pytest Plugin Integration**
   - Registers as pytest plugin via entry points
   - Uses `pytest_ignore_collect` hook to filter files
   - Caches discovered test files to avoid redundant scanning
   - Command-line options: `--use-fast-collect` / `--no-fast-collect`

3. **Benchmarking Infrastructure**
   - Synthetic test generation (configurable size)
   - Real-world project benchmarking
   - Statistical analysis with multiple runs
   - Tested on pandas (969 test files)

### 📊 Performance Results

**Current Implementation (File Filtering Only)**:
- Synthetic (500 files, 50K tests): ~1.01x speedup
- pandas (969 files): 0.75x (slower due to overhead)

**Why Limited Performance?**
1. **Double Parsing**: Rust parses for discovery, pytest parses for collection
2. **Hook Overhead**: `pytest_ignore_collect` called for every file/directory
3. **No Direct Item Creation**: pytest still does all the heavy lifting

##Direct Item Creation Attempt

### Challenge: pytest's Collection Architecture

Attempted to create pytest `Item` objects directly from Rust data to bypass pytest's parser entirely. This proved complex due to:

1. **Module Loading Required**
   - Need actual Python function/class objects, not just names
   - Must use `importlib` to load modules anyway
   - Negates parsing speedup

2. **pytest's Collection Protocol**
   - Multiple hooks with specific call order
   - `pytest_collect_file` returns Collectors, not Items
   - `pytest_collection` is notification-only, doesn't return items
   - Custom Collectors require complex `from_parent()` patterns

3. **Item Creation Requirements**
   - Items need parent collectors (Module -> Class -> Function)
   - Must maintain pytest's node hierarchy
   - Parametrized tests expand at collection time
   - Fixtures analyzed during collection

### Code Attempts Made

1. **pytest_collection Hook** - Tried modifying `session.items` directly
   - Items created but not shown (timing issue)

2. **Custom Collector Class** - Subclassed `PyCollector`
   - Complex `from_parent()` requirements
   - Missing required parameters (name, path, etc.)

3. **pytest_collect_file Hook** - Return custom Module
   - Closer to working, but module loading still required

## Path Forward

### Option 1: Incremental Collection (Most Promising)
- Cache Rust parsing results with file mtimes
- Only reparse files that changed
- Skip unchanged files entirely
- **Estimated speedup**: 5-10x on repeated runs

### Option 2: Lazy Loading
- Parse files on-demand when tests execute
- Works well with `pytest -k` filtering
- Reduces upfront collection time
- **Estimated speedup**: 2-5x for filtered runs

### Option 3: Better Integration
- Deep integration with pytest's Collector protocol
- Replace Module.collect() method
- Handle parametrization in Rust
- **Complexity**: High, requires pytest internals expertise

### Option 4: Hybrid Approach (Recommended)
1. Use Rust for file discovery (current)
2. Add incremental caching
3. Let pytest handle module loading and item creation
4. Optimize for the 90% use case (repeated test runs)

## Technical Details

### Rust Components (`src/lib.rs`)

```rust
struct FastCollector {
    root_path: PathBuf,
    test_patterns: Vec<String>,      // "test_*.py", "*_test.py"
    ignore_patterns: Vec<String>,     // .git, __pycache__, etc.
}

struct TestItem {
    file_path: String,
    name: String,
    line_number: usize,
    item_type: TestItemType,         // Function, Class, Method
    class_name: Option<String>,
}
```

### Python Plugin (`pytest_fastcollect/plugin.py`)

```python
def pytest_ignore_collect(collection_path, config):
    """Filter files based on Rust discovery."""
    # Initialize cache on first call
    if cache is None:
        collector = FastCollector(root_path)
        cache = set(collector.collect().keys())

    # Ignore files not in cache
    return abs_path not in cache
```

## Lessons Learned

1. **pytest's Architecture is Complex**
   - Collection happens in multiple phases
   - Hooks have specific purposes and limitations
   - Direct item creation requires deep integration

2. **Module Loading is Unavoidable**
   - Need actual Python objects for pytest Items
   - Can't avoid importing modules
   - Parsing alone isn't enough

3. **The 80/20 Rule Applies**
   - 80% of speedup comes from simpler optimizations
   - Caching and incremental updates are easier wins
   - Full replacement is diminishing returns

4. **Benchmarking is Essential**
   - Early benchmarks showed overhead issues
   - Guided decision to focus elsewhere
   - Real-world testing (pandas) was valuable

## Recommendations

### For v0.2.0 (Quick Wins)
1. Add file modification time caching
2. Skip unchanged files
3. Persist cache to disk (`.pytest_cache/fast collect.json`)
4. **Expected**: 5x speedup on repeated runs

### For v0.3.0 (Incremental)
1. Lazy loading for filtered runs
2. Integration with pytest-xdist
3. Watch mode support
4. **Expected**: 2-3x additional speedup

### For v1.0 (Advanced)
1. Deep pytest integration
2. Parametrization handling in Rust
3. Fixture dependency analysis
4. **Expected**: 10x+ speedup potential

## Conclusion

The pytest-fastcollect plugin **successfully demonstrates** Rust-Python integration for test discovery. While direct item creation proved complex, the foundation is solid for incremental improvements.

The biggest wins will come from:
- **Caching** (avoid redundant work)
- **Incremental updates** (only reparse changed files)
- **Lazy loading** (defer work until needed)

Rather than fighting pytest's architecture, work with it.

## References

- [pytest Collection Protocol](https://docs.pytest.org/en/stable/reference/reference.html#collection)
- [PyO3 Documentation](https://pyo3.rs/)
- [RustPython Parser](https://github.com/RustPython/Parser)
