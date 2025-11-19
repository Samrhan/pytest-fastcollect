#!/usr/bin/env python3
"""
Benchmark Rust-side filtering vs baseline.

This tests the performance improvement from filtering tests in Rust
during parallel collection, avoiding Python object creation for filtered-out tests.
"""

import subprocess
import time
import os
import statistics

def run_benchmark(label, args, runs=5):
    """Run pytest collection and measure time."""
    times = []

    env = os.environ.copy()
    env['PYTHONPATH'] = '/home/user/pytest-fastcollect:' + env.get('PYTHONPATH', '')

    for i in range(runs):
        start = time.perf_counter()
        result = subprocess.run(
            ["pytest", "--collect-only", "-q"] + args,
            cwd="/home/user/pytest-fastcollect",
            env=env,
            capture_output=True,
            text=True,
            timeout=60
        )
        elapsed = time.perf_counter() - start

        if result.returncode in [0, 5]:  # 0 = success, 5 = no tests
            times.append(elapsed)
            # Extract collected/deselected counts
            for line in result.stdout.split('\n'):
                if 'collected' in line.lower() and i == 0:
                    print(f"  {line.strip()}")
        else:
            print(f"  Run {i+1} failed with code {result.returncode}")

    if not times:
        return 0, 0, 0

    mean = statistics.mean(times)
    stddev = statistics.stdev(times) if len(times) > 1 else 0

    print(f"  Mean:   {mean:.3f}s ± {stddev:.3f}s")
    print(f"  Samples: {[f'{t:.3f}' for t in times]}")

    return mean, stddev, times

print("="*70)
print("Rust-Side Filtering Benchmark (Phase 1 Complete)")
print("="*70)
print("\nComparing Rust-side filtering vs baseline pytest")
print("Running 5 iterations per scenario...\n")

scenarios = [
    {
        "name": "Full Collection (no filters)",
        "args_rust": ["tests/"],
        "args_baseline": ["tests/", "-p", "no:pytest_fastcollect"],
    },
    {
        "name": "Keyword Filter (-k slow)",
        "args_rust": ["tests/", "-k", "slow"],
        "args_baseline": ["tests/", "-k", "slow", "-p", "no:pytest_fastcollect"],
    },
    {
        "name": "Keyword Filter (-k cache)",
        "args_rust": ["tests/", "-k", "cache"],
        "args_baseline": ["tests/", "-k", "cache", "-p", "no:pytest_fastcollect"],
    },
    {
        "name": "Marker Filter (-m slow)",
        "args_rust": ["tests/", "-m", "slow"],
        "args_baseline": ["tests/", "-m", "slow", "-p", "no:pytest_fastcollect"],
    },
    {
        "name": "Complex Filter (-k 'test and not daemon')",
        "args_rust": ["tests/", "-k", "test and not daemon"],
        "args_baseline": ["tests/", "-k", "test and not daemon", "-p", "no:pytest_fastcollect"],
    },
]

results = []

for i, scenario in enumerate(scenarios, 1):
    print(f"\n{'='*70}")
    print(f"[{i}/{len(scenarios)}] {scenario['name']}")
    print(f"{'='*70}")

    # Run with Rust-side filtering
    print(f"\nWith RUST-SIDE FILTERING (filter during parallel collection):")
    rust_mean, rust_std, rust_times = run_benchmark("Rust filtering", scenario['args_rust'])

    # Run with baseline pytest
    print(f"\nWith BASELINE PYTEST (no filtering during collection):")
    baseline_mean, baseline_std, baseline_times = run_benchmark("Baseline", scenario['args_baseline'])

    # Calculate speedup
    if baseline_mean > 0 and rust_mean > 0:
        speedup = baseline_mean / rust_mean
        improvement = ((baseline_mean - rust_mean) / baseline_mean) * 100

        symbol = "✅" if speedup >= 1.05 else ("➖" if speedup >= 0.95 else "⚠️")
        print(f"\n  Speedup: {speedup:.2f}x ({improvement:+.1f}%) {symbol}")

        results.append({
            "name": scenario['name'],
            "rust": rust_mean,
            "baseline": baseline_mean,
            "speedup": speedup,
            "improvement": improvement
        })

# Summary
print("\n" + "="*70)
print("SUMMARY - Rust-Side Filtering Performance")
print("="*70)
print(f"\n{'Scenario':<45} {'Rust':>8} {'Baseline':>8} {'Speedup':>8}")
print("-"*70)

for result in results:
    speedup_str = f"{result['speedup']:.2f}x"
    symbol = "✅" if result['speedup'] >= 1.05 else ("➖" if result['speedup'] >= 0.95 else "⚠️")
    print(f"{result['name']:<45} {result['rust']:>7.3f}s {result['baseline']:>7.3f}s {speedup_str:>8} {symbol}")

avg_speedup = sum(r['speedup'] for r in results) / len(results)
print("-"*70)
print(f"{'AVERAGE':<45} {'':<8} {'':<8} {avg_speedup:>7.2f}x")

# Analysis
print("\n" + "="*70)
print("ANALYSIS")
print("="*70)

if avg_speedup >= 1.2:
    print(f"\n✅ MAJOR WIN: Rust-side filtering shows {avg_speedup:.2f}x average speedup!")
    print("   Filtering during parallel collection eliminates Python object overhead.")
elif avg_speedup >= 1.05:
    print(f"\n✅ SUCCESS: Rust-side filtering shows {avg_speedup:.2f}x average speedup")
    print("   Modest but consistent improvement.")
elif avg_speedup >= 0.95:
    print(f"\n➖ NEUTRAL: Rust-side filtering shows {avg_speedup:.2f}x (comparable)")
else:
    print(f"\n⚠️  REGRESSION: Rust-side filtering shows {avg_speedup:.2f}x (slower)")

print("\nKey Benefits of Rust-Side Filtering:")
print("  1. No Python object creation for filtered-out tests")
print("  2. Filter evaluation happens in parallel with rayon")
print("  3. Reduced FFI overhead (only matching tests cross boundary)")
print("  4. Memory efficient (never allocate Python objects for non-matches)")

print("\n" + "="*70)
print("NEXT STEPS (Phase 2)")
print("="*70)
print("""
Now that filtering is in Rust, next optimizations:
  1. Move caching to Rust (eliminate JSON deserialization overhead)
  2. Fix pytest hook usage (avoid double collection)
  3. Optimize rayon parallelism
  4. Auto-start daemon mode

Expected cumulative improvements:
  - Phase 1 (Rust filtering): ~1.1-1.5x
  - Phase 2 (Rust caching):   ~1.2-1.8x
  - Phase 3 (Fix hooks):      ~1.3-2.0x
  - Phase 4 (Daemon):         ~100-1000x (re-runs)
""")

print(f"\nBenchmark complete! Rust-side filtering is {avg_speedup:.2f}x vs baseline.")
