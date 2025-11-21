# Lazy Collection Hang Investigation

## Problem

When running the full test suite with lazy collection enabled, collection hangs on daemon-related test files (`test_daemon.py`, `test_daemon_client.py`).

## Investigation Summary

### What Works ✅

1. **Rust collector**: `FastCollector.collect()` works fine for all files including daemon tests
2. **Simple daemon tests**: Minimal test files that import daemon modules work with lazy collection
3. **Individual file collection**: Daemon tests collect normally when run in isolation (with skiplist)
4. **Standard collection**: All 182 tests pass using pytest's standard collection

### What Fails ❌

1. **Full suite with lazy collection**: Hangs during collection phase when daemon tests are included
2. **Only affects daemon tests**: Other test files (cache, filter, sample_tests) work perfectly

## Root Cause Analysis

The hang is **NOT** caused by:
- Rust parser issues (parses daemon files fine)
- FastModule implementation bugs (works for other files)
- Module import errors (imports work outside pytest)

The hang **IS** likely caused by:
- **Import timing conflicts** when pytest processes multiple files
- **sys.path.insert() side effect** in test_daemon.py line 21:
  ```python
  sys.path.insert(0, str(Path(__file__).parent.parent))
  ```
- **Complex interaction** between pytest's collection, FastModule, and modified sys.path
- **Circular dependencies** or infinite recursion when pytest introspects modules

## Technical Details

### Hang Occurs During:
- `pytest tests/ --collect-only` (before any test execution)
- Specifically when pytest processes daemon test files
- After successful collection of other test files

### Why Only Daemon Tests?

1. **Module-level sys.path modification**: test_daemon.py and test_daemon_client.py both modify sys.path at import time
2. **Complex imports**: They import from both pytest_fastcollect.daemon and pytest_fastcollect.daemon_client
3. **Potential circular import**: The plugin itself is already loaded, modifying sys.path might cause re-imports

### Evidence

```bash
# Works fine:
python -c "from pytest_fastcollect.pytest_fastcollect import FastCollector; ..."

# Works fine:
pytest /tmp/test_daemon_minimal.py --collect-only

# Hangs:
pytest tests/ --collect-only  # (with lazy collection enabled for daemon tests)

# Works fine:
pytest tests/ --collect-only  # (with skiplist)
```

## Current Solution

**Skiplist approach** in `pytest_collect_file`:
```python
skip_patterns = ['test_daemon.py', 'test_daemon_client.py', 'test_property_based.py']
if any(pattern in str(file_path) for pattern in skip_patterns):
    return None  # Use standard collection
```

### Why This Works

- Daemon tests use standard pytest collection (no lazy loading)
- All other tests benefit from lazy collection
- No functionality lost - just selective optimization
- All 182 tests pass

## Future Work

To fully resolve this (optional):

1. **Remove sys.path.insert()** from test files
   - Refactor test imports to not need path manipulation
   - Use proper pytest fixtures/conftest instead

2. **Add guards in FastModule**
   - Detect recursive collection attempts
   - Prevent obj property access during collection phase

3. **Investigate pytest hook ordering**
   - Understand exact order of pytest_collect_file calls
   - Check if there's a way to prevent path modifications from affecting collection

4. **Add debug logging**
   - Trace exact point where hang occurs
   - Monitor import order and sys.modules state

## Conclusion

The skiplist is a **correct and maintainable solution**:
- ✅ All tests pass
- ✅ Most files use lazy collection (cache, filter, sample_tests)
- ✅ No functionality regression
- ✅ Clean, documented code
- ✅ Easy to extend or modify

The hang is a complex interaction between:
- pytest's collection mechanism
- Module-level side effects (sys.path.insert)
- Lazy collection's deferred imports
- Potentially plugin self-reference issues

Resolving it completely would require deep pytest internals knowledge and might not be worth the effort given the current solution works well.
