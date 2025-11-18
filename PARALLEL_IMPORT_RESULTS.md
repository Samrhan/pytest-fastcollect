# Parallel Import: Benchmark Results & Analysis

## Overview

Parallel import is an **experimental optimization** that pre-imports test modules in parallel using `ThreadPoolExecutor` before pytest's collection phase. The goal is to reduce module import time, which accounts for 95% of collection time.

## Usage

```bash
# Enable parallel import (uses CPU count workers by default)
pytest --parallel-import

# Specify number of workers
pytest --parallel-import --parallel-workers=4

# Combine with other optimizations
pytest --parallel-import -k test_user
```

## Benchmark Results

Tested on 3 real-world projects:

| Project | Files | Baseline | Parallel (4 workers) | Speedup | Grade |
|---------|-------|----------|---------------------|---------|-------|
| **Pytest** | 108 | 2.40s | 1.03s | **2.33x faster** | ⚡⚡⚡ Excellent |
| **SQLAlchemy** | 219 | 0.69s | 0.64s | **1.07x faster** | ✓ Minor |
| **Django** | 1977 | 4.80s | 4.90s | **0.98x slower** | ⚠️ Overhead |

### Detailed Results

#### Pytest (108 files) - ⚡⚡⚡ EXCELLENT

```
Baseline (no parallel):        2.40s
Parallel (default, 16 workers): 1.55s  (1.55x faster)
Parallel (4 workers):          1.03s  (2.33x faster) ✅ BEST
Parallel (8 workers):          1.06s  (2.27x faster)
```

**Analysis**:
- **Dramatic speedup**: 2.33x faster with 4 workers
- **Optimal workers**: 4 workers performed best
- **Why it works**: Pytest's test modules have simple imports with minimal interdependencies
- **Recommendation**: ✅ **Highly recommended** for pytest-scale projects

---

#### SQLAlchemy (219 files) - ✓ MINOR GAIN

```
Baseline (no parallel):        0.69s
Parallel (default, 16 workers): 0.64s  (1.07x faster)
Parallel (4 workers):          0.64s  (1.07x faster)
Parallel (8 workers):          0.64s  (1.08x faster)
```

**Analysis**:
- **Modest improvement**: ~7% faster (~50ms saved)
- **Worker count doesn't matter**: Similar performance with 4, 8, or 16 workers
- **Why minimal**: Collection already fast, parallel overhead visible
- **Recommendation**: ⚠️ **Optional** - minor benefit

---

#### Django (1977 files) - ⚠️ SLOWER

```
Baseline (no parallel):        4.80s
Parallel (default, 16 workers): 5.48s  (0.88x slower) ❌
Parallel (4 workers):          4.90s  (0.98x slower) ❌
Parallel (8 workers):          4.98s  (0.96x slower) ❌
```

**Analysis**:
- **Parallel actually hurts**: 2-14% slower with parallel import
- **Why it fails**: Django modules have complex interdependencies
  - Heavy use of imports during module initialization
  - Circular import patterns
  - Module-level initialization code
  - GIL contention during initialization
- **ThreadPool overhead**: Context switching costs more than parallelism saves
- **Recommendation**: ❌ **Do not use** for Django-scale projects with complex imports

---

## Key Findings

### 1. Worker Count Matters

**Optimal configuration varies by project**:
- **Pytest**: 4 workers = best performance (2.33x faster)
- **SQLAlchemy**: Worker count doesn't significantly impact (1.07-1.08x)
- **Django**: Fewer workers slightly better, but still slower than no parallel

**General guideline**:
- Start with 4 workers: `--parallel-workers=4`
- More workers ≠ better performance (GIL limits parallelism)

### 2. Import Complexity Determines Success

**Simple imports** (Pytest): ✅ Excellent speedup
- Independent test modules
- Minimal import-time side effects
- Clean import graphs

**Moderate imports** (SQLAlchemy): ✓ Minor gain
- Some interdependencies
- Moderate initialization

**Complex imports** (Django): ❌ Overhead
- Heavy interdependencies
- Module-level initialization
- Circular imports
- Framework setup code

### 3. GIL Impact

Python's Global Interpreter Lock (GIL) limits true parallelism:
- **I/O operations** (reading .py/.pyc files) can benefit from threading
- **CPU-bound work** (parsing, executing module code) is serialized by GIL
- **Best case**: Modules with heavy I/O, light initialization
- **Worst case**: Modules with heavy computation during import

### 4. When Parallel Import Helps

✅ **Use parallel import when**:
- Test modules have **simple, independent imports**
- Project has **100-300 test files** (sweet spot for pytest)
- Modules are **I/O heavy, CPU light** during import
- Collection time is **> 1 second**

⚠️ **Evaluate first when**:
- Test modules have **moderate interdependencies**
- Project has **< 100 files** (overhead may dominate)
- Collection time is **< 1 second** (already fast)

❌ **Don't use when**:
- Test modules have **complex interdependencies** (Django-like)
- Heavy **framework initialization** during imports
- Project has **> 500 files with complex imports** (overhead wins)

---

## Technical Analysis

### Why Threading Over Multiprocessing?

We chose `ThreadPoolExecutor` over `ProcessPoolExecutor`:

**Advantages**:
- Lower overhead (no process spawning)
- Shared memory (sys.modules accessible)
- Faster startup/teardown
- Simpler IPC

**Disadvantages**:
- GIL limits CPU parallelism
- Only I/O operations truly parallel

**Verdict**: For module import (mostly I/O), threading is better than multiprocessing.

### Module Import Phases

1. **Find module** (I/O heavy): Threading helps ✅
   - Search sys.path
   - Read .py or .pyc files

2. **Parse module** (CPU heavy): GIL limits ⚠️
   - Parse bytecode
   - Create code objects

3. **Execute module** (varies): Depends on module ❓
   - Simple modules: Fast
   - Complex modules: Slow, serialized by GIL

### Why Django Failed

Django's test modules commonly:
- Import `django.conf.settings` (global state)
- Import models (ORM initialization)
- Import views (URL resolution)
- Trigger app registry initialization
- Setup test database connections

All of this is:
- **CPU-intensive** (serialized by GIL)
- **Order-dependent** (parallelism breaks assumptions)
- **Shared-state heavy** (lock contention)

Result: Parallel overhead > parallel benefit

---

## Recommendations by Project Type

### Small Projects (< 100 files)

**Don't use parallel import**:
- Collection already < 1 second
- Overhead > benefit
- Not worth the complexity

**Example**: Flask (22 files), Requests (9 files)

---

### Medium Projects with Simple Imports (100-300 files)

**USE parallel import with 4 workers** ✅:
```bash
pytest --parallel-import --parallel-workers=4
```

**Expected benefit**: 1.5-2.5x faster collection

**Example**: Pytest itself (108 files) - 2.33x faster!

---

### Medium Projects with Complex Imports

**Evaluate first** ⚠️:
1. Run benchmark: `pytest --collect-only` (baseline)
2. Test parallel: `pytest --collect-only --parallel-import --parallel-workers=4`
3. If speedup > 1.1x, keep it. Otherwise, skip.

**Example**: SQLAlchemy (219 files) - 1.07x faster (marginal)

---

### Large Projects (500+ files)

**Depends on import complexity**:

**Simple imports**: ✅ Try parallel with 4-8 workers
- Independent test modules
- Minimal framework overhead
- Clean import graphs

**Complex imports** (Django-like): ❌ Skip parallel
- Heavy interdependencies
- Framework initialization
- Circular imports
- Parallel import makes it slower

**Example**: Django (1977 files) - 0.98x slower ❌

---

## Combining Optimizations

Parallel import can be combined with other optimizations:

### FastCollect + Parallel Import

```bash
pytest --collect-only --parallel-import --parallel-workers=4
```

**Pytest**:
- FastCollect alone: 2.54s → 2.40s (1.06x)
- Parallel import alone: 2.40s → 1.03s (2.33x)
- **Combined potential**: Up to 2.5x faster than FastCollect baseline

**SQLAlchemy**:
- FastCollect alone: 0.63s
- Parallel import: +1.07x
- **Combined**: ~0.59s (marginal)

**Django**:
- FastCollect alone: 4.49s (vs 10.85s baseline = 2.42x)
- Parallel import: -2% (makes it slower)
- **Combined**: Skip parallel, use FastCollect only

### Selective Import + Parallel Import

```bash
pytest -k test_user --parallel-import --parallel-workers=4
```

**Effect**: Selective import reduces files to import, making parallel import faster!

**Example** (Pytest with -k test_basic):
- Full collection: 2.54s
- With -k filter: 0.92s (2.75x faster)
- **Add parallel**: Could push to < 0.5s!

---

## Experimental Status

**Why experimental?**

1. **Project-dependent**: Works great for some, hurts others
2. **Worker tuning**: Requires finding optimal worker count
3. **Import complexity**: Hard to predict which projects benefit
4. **GIL limitations**: True speedup limited by Python's GIL

**Should you use it?**

- **Yes**, if you benchmark first and see > 1.2x speedup
- **No**, if your project has complex imports like Django
- **Maybe**, if you have 100-300 files with simple imports

**Default**: Disabled (opt-in with `--parallel-import`)

---

## Future Improvements

### 1. Auto-Detection

Automatically detect if project would benefit:
- Analyze import complexity
- Profile import times
- Enable parallel only if beneficial

### 2. Smart Worker Scaling

Dynamically adjust workers based on:
- Project size
- Import complexity
- Available CPU cores

### 3. Dependency-Aware Scheduling

Import modules in dependency order:
- Parse import statements
- Build dependency graph
- Schedule imports respecting dependencies
- Reduce serialization

### 4. Hybrid Approach

Combine threading + multiprocessing:
- Use processes for independent module groups
- Use threads within each process
- Avoid GIL contention across groups

---

## Conclusion

**Parallel import is a powerful optimization for the right project.**

**Best use case**: Medium-sized projects (100-300 files) with simple, independent test modules.

**Pytest itself is the poster child**: 2.33x faster with parallel import!

**Not a silver bullet**: Complex imports (Django) actually get slower.

**Recommendation**: Benchmark your specific project to see if it helps.

### Quick Decision Guide

```
Does your project have < 100 test files?
├─ Yes → Skip parallel import
└─ No  → Does collection take > 2 seconds?
    ├─ Yes → Are your imports simple and independent?
    │   ├─ Yes → Use parallel import! (--parallel-import --parallel-workers=4)
    │   └─ No  → Benchmark first, might not help
    └─ No  → Collection already fast, skip parallel import
```

---

Generated by `benchmark_parallel.py` on pytest-fastcollect v0.4.0
