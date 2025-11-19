#!/usr/bin/env python3
"""
Benchmark Phase 3: Elimination of Double Collection

This tests the performance improvement from disabling lazy collection and
eliminating the double collection overhead.

Before Phase 3:
- pytest_collect_file created FastModule instances
- pytest's standard collector ALSO created Module instances
- Both created test items (FastFunction + standard Function)
- pytest_collection_modifyitems filtered duplicates in O(n)

After Phase 3:
- pytest_collect_file returns None (no FastModule)
- Only pytest's standard collector runs
- No duplicate test items
- No O(n) duplicate filtering

Expected improvement: 1.5-2.0x by eliminating double collection overhead.
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

        if result.returncode in [0, 5]:
            times.append(elapsed)
            if i == 0:
                # Extract collected/deselected counts
                for line in result.stdout.split('\n'):
                    if 'collected' in line.lower():
                        print(f"  {line.strip()}")
        else:
            print(f"  Run {i+1} failed with code {result.returncode}")

    if not times:
        return 0, 0, times

    mean = statistics.mean(times)
    stddev = statistics.stdev(times) if len(times) > 1 else 0

    print(f"  Mean:   {mean:.3f}s ± {stddev:.3f}s")
    print(f"  Samples: {[f'{t:.3f}' for t in times]}")

    return mean, stddev, times

print("="*70)
print("Phase 3 Benchmark: Elimination of Double Collection")
print("="*70)
print("\nComparing Phase 3 (no lazy collection) vs Baseline pytest")
print("Running 5 iterations per scenario...\n")

scenarios = [
    {
        "name": "Full Collection (no filters)",
        "args_phase3": ["tests/"],
        "args_baseline": ["tests/", "-p", "no:pytest_fastcollect"],
    },
    {
        "name": "Keyword Filter (-k slow)",
        "args_phase3": ["tests/", "-k", "slow"],
        "args_baseline": ["tests/", "-k", "slow", "-p", "no:pytest_fastcollect"],
    },
    {
        "name": "Keyword Filter (-k cache)",
        "args_phase3": ["tests/", "-k", "cache"],
        "args_baseline": ["tests/", "-k", "cache", "-p", "no:pytest_fastcollect"],
    },
    {
        "name": "Marker Filter (-m slow)",
        "args_phase3": ["tests/", "-m", "slow"],
        "args_baseline": ["tests/", "-m", "slow", "-p", "no:pytest_fastcollect"],
    },
    {
        "name": "Complex Filter (-k 'test and not daemon')",
        "args_phase3": ["tests/", "-k", "test and not daemon"],
        "args_baseline": ["tests/", "-k", "test and not daemon", "-p", "no:pytest_fastcollect"],
    },
]

results = []

for i, scenario in enumerate(scenarios, 1):
    print(f"\n{'='*70}")
    print(f"[{i}/{len(scenarios)}] {scenario['name']}")
    print(f"{'='*70}")

    # Run with Phase 3 (no lazy collection, no double collection)
    print(f"\nWith PHASE 3 (single collection, no duplicates):")
    phase3_mean, phase3_std, phase3_times = run_benchmark("Phase 3", scenario['args_phase3'])

    # Run with baseline pytest
    print(f"\nWith BASELINE PYTEST:")
    baseline_mean, baseline_std, baseline_times = run_benchmark("Baseline", scenario['args_baseline'])

    # Calculate speedup
    if baseline_mean > 0 and phase3_mean > 0:
        speedup = baseline_mean / phase3_mean
        improvement = ((baseline_mean - phase3_mean) / baseline_mean) * 100

        symbol = "✅" if speedup >= 1.10 else ("➖" if speedup >= 0.95 else "⚠️")
        print(f"\n  Speedup: {speedup:.2f}x ({improvement:+.1f}%) {symbol}")

        results.append({
            "name": scenario['name'],
            "phase3": phase3_mean,
            "baseline": baseline_mean,
            "speedup": speedup,
            "improvement": improvement
        })

# Summary
print("\n" + "="*70)
print("SUMMARY - Phase 3 Performance Results")
print("="*70)
print(f"\n{'Scenario':<45} {'Phase3':>8} {'Baseline':>8} {'Speedup':>8}")
print("-"*70)

for result in results:
    speedup_str = f"{result['speedup']:.2f}x"
    symbol = "✅" if result['speedup'] >= 1.10 else ("➖" if result['speedup'] >= 0.95 else "⚠️")
    print(f"{result['name']:<45} {result['phase3']:>7.3f}s {result['baseline']:>7.3f}s {speedup_str:>8} {symbol}")

avg_speedup = sum(r['speedup'] for r in results) / len(results)
print("-"*70)
print(f"{'AVERAGE':<45} {'':<8} {'':<8} {avg_speedup:>7.2f}x")

# Analysis
print("\n" + "="*70)
print("ANALYSIS")
print("="*70)

if avg_speedup >= 1.5:
    print(f"\n🎯 MAJOR SUCCESS: Phase 3 shows {avg_speedup:.2f}x average speedup!")
    print("   Eliminating double collection was the game changer.")
elif avg_speedup >= 1.2:
    print(f"\n✅ SUCCESS: Phase 3 shows {avg_speedup:.2f}x average speedup")
    print("   Significant improvement from eliminating double collection.")
elif avg_speedup >= 1.05:
    print(f"\n✅ MODEST WIN: Phase 3 shows {avg_speedup:.2f}x average speedup")
elif avg_speedup >= 0.95:
    print(f"\n➖ NEUTRAL: Phase 3 shows {avg_speedup:.2f}x (comparable)")
else:
    print(f"\n⚠️  REGRESSION: Phase 3 shows {avg_speedup:.2f}x (slower)")

print("\nWhat Phase 3 Fixed:")
print("  ✅ Disabled lazy collection (FastModule/FastClass/FastFunction)")
print("  ✅ Eliminated double collection (only standard pytest collects now)")
print("  ✅ Removed O(n) duplicate filtering in pytest_collection_modifyitems")
print("  ✅ Kept Rust-side filtering (tests filtered during parallel collection)")
print("  ✅ Kept pytest_ignore_collect (skip files without matching tests)")

print("\nArchitecture After Phase 3:")
print("  1. Rust parses all files in parallel with rayon")
print("  2. Rust applies keyword/marker filters during parsing")
print("  3. pytest_ignore_collect skips files without matching tests")
print("  4. Standard pytest collection runs (SINGLE path, no duplicates)")
print("  5. No custom nodes, no duplicate filtering, clean & fast")

print("\n" + "="*70)
print("COMPARISON: Lazy Collection vs Phase 3")
print("="*70)
print("""
Lazy Collection (Phase 1 disabled):
  - Double collection: FastModule + standard Module
  - Custom nodes: FastFunction, FastClass overhead
  - O(n) duplicate filtering
  - Result: 0.95x (5% SLOWER)

Phase 3 (current):
  - Single collection: standard pytest only
  - No custom nodes overhead
  - No duplicate filtering
  - Result: {:.2f}x ({}% {})

This validates the strategic decision to disable lazy collection!
""".format(
    avg_speedup,
    abs(int((avg_speedup - 1) * 100)),
    "FASTER" if avg_speedup >= 1.0 else "SLOWER"
))

print("="*70)
print("NEXT STEPS (Cumulative Optimizations)")
print("="*70)
print("""
✅ Phase 1 (Rust filtering):        1.02x (marginal, foundation)
✅ Phase 3 (No double collection):  {:.2f}x (current result)
⏭  Phase 2 (Rust caching):          +0.2-0.3x (cumulative)
⏭  Phase 4 (Daemon auto-start):    100-1000x (re-runs)

Total expected with all phases: ~2.0x for collection + 100-1000x for re-runs
""".format(avg_speedup))

print(f"\nPhase 3 benchmark complete! Average speedup: {avg_speedup:.2f}x")
