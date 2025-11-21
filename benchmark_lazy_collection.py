#!/usr/bin/env python3
"""
Benchmark script for lazy collection performance.

This script measures the impact of lazy collection by comparing:
1. Collection time with lazy collection enabled (default)
2. Collection time with lazy collection disabled (--no-fast-collect)
3. Collection time with standard pytest (plugin disabled)

The goal is to validate the 5-10x speedup hypothesis for the collection phase.
"""

import subprocess
import time
import statistics
import sys
from pathlib import Path
from typing import List, Tuple, Dict


def run_pytest_collect(args: List[str], runs: int = 5) -> Dict[str, float]:
    """
    Run pytest with --collect-only and measure collection time.

    Args:
        args: Additional pytest arguments
        runs: Number of times to run for averaging

    Returns:
        Dictionary with timing statistics
    """
    times = []

    import os
    env = os.environ.copy()
    env['PYTHONPATH'] = '/home/user/pytest-fastcollect:' + env.get('PYTHONPATH', '')

    for i in range(runs):
        start = time.perf_counter()
        result = subprocess.run(
            ["pytest", "--collect-only", "-q"] + args,
            capture_output=True,
            text=True,
            cwd="/home/user/pytest-fastcollect",
            env=env
        )
        elapsed = time.perf_counter() - start

        if result.returncode != 0:
            print(f"Warning: Run {i+1} failed with code {result.returncode}")
            print(result.stderr)
        else:
            times.append(elapsed)

    if not times:
        return {"mean": 0, "stdev": 0, "min": 0, "max": 0, "samples": []}

    return {
        "mean": statistics.mean(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
        "min": min(times),
        "max": max(times),
        "samples": times
    }


def print_results(name: str, stats: Dict[str, float]) -> None:
    """Print benchmark results in a formatted way."""
    print(f"\n{name}:")
    print(f"  Mean:   {stats['mean']:.3f}s")
    print(f"  StdDev: {stats['stdev']:.3f}s")
    print(f"  Min:    {stats['min']:.3f}s")
    print(f"  Max:    {stats['max']:.3f}s")
    print(f"  Samples: {[f'{t:.3f}' for t in stats['samples']]}")


def main():
    print("=" * 70)
    print("Lazy Collection Performance Benchmark")
    print("=" * 70)
    print("\nThis benchmark measures collection time only (--collect-only)")
    print("Running 5 iterations for each configuration...\n")

    # Scenario 1: Lazy collection ENABLED (default behavior)
    print("\n[1/3] Running with LAZY COLLECTION ENABLED (default)...")
    lazy_enabled = run_pytest_collect(["tests/"])
    print_results("Lazy Collection ENABLED", lazy_enabled)

    # Scenario 2: Lazy collection DISABLED (plugin still active, but using standard collection)
    print("\n[2/3] Running with LAZY COLLECTION DISABLED (--no-fast-collect)...")
    lazy_disabled = run_pytest_collect(["tests/", "--no-fast-collect"])
    print_results("Lazy Collection DISABLED", lazy_disabled)

    # Scenario 3: Plugin UNLOADED (baseline pytest)
    print("\n[3/3] Running with PLUGIN UNLOADED (baseline pytest)...")
    plugin_disabled = run_pytest_collect(["tests/", "-p", "no:pytest_fastcollect"])
    print_results("Plugin UNLOADED (baseline)", plugin_disabled)

    # Calculate speedups
    print("\n" + "=" * 70)
    print("PERFORMANCE COMPARISON")
    print("=" * 70)

    if lazy_disabled['mean'] > 0:
        speedup_vs_disabled = lazy_disabled['mean'] / lazy_enabled['mean']
        print(f"\nLazy Collection vs Standard Collection (plugin active):")
        print(f"  {speedup_vs_disabled:.2f}x speedup ({lazy_enabled['mean']:.3f}s vs {lazy_disabled['mean']:.3f}s)")

        improvement_pct = ((lazy_disabled['mean'] - lazy_enabled['mean']) / lazy_disabled['mean']) * 100
        print(f"  {improvement_pct:.1f}% improvement")

    if plugin_disabled['mean'] > 0:
        speedup_vs_baseline = plugin_disabled['mean'] / lazy_enabled['mean']
        print(f"\nLazy Collection vs Baseline Pytest:")
        print(f"  {speedup_vs_baseline:.2f}x speedup ({lazy_enabled['mean']:.3f}s vs {plugin_disabled['mean']:.3f}s)")

        improvement_pct = ((plugin_disabled['mean'] - lazy_enabled['mean']) / plugin_disabled['mean']) * 100
        print(f"  {improvement_pct:.1f}% improvement")

    # Analysis
    print("\n" + "=" * 70)
    print("ANALYSIS")
    print("=" * 70)

    print("\nFiles using lazy collection:")
    print("  ✅ tests/test_cache.py (31 tests)")
    print("  ✅ tests/test_filter.py (34 tests)")
    print("  ✅ tests/test_selective_import.py (21 tests)")
    print("  ✅ sample_tests/*.py (~20 tests)")
    print("  Total: ~106 tests using lazy collection")

    print("\nFiles using standard collection (skiplist):")
    print("  ⚠️  tests/test_daemon.py")
    print("  ⚠️  tests/test_daemon_client.py")
    print("  ⚠️  tests/test_property_based.py")
    print("  Total: ~76 tests using standard collection")

    print(f"\nLazy collection coverage: ~58% of tests (106/182)")

    print("\n" + "=" * 70)
    print("NOTES")
    print("=" * 70)
    print("""
1. This benchmark measures COLLECTION TIME only, not test execution
2. Lazy collection defers imports from collection to execution phase
3. The speedup should be more pronounced on larger test suites
4. Files with sys.path modifications are in skiplist (documented)
5. For full speedup potential, combine with selective import (-k/-m filters)
""")


if __name__ == "__main__":
    main()
