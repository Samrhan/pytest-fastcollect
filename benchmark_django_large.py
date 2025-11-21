#!/usr/bin/env python3
"""
Benchmark pytest-fastcollect on Django (Large Real-World Codebase)

Django has ~1977 test files and is a perfect benchmark for:
1. Testing scalability hypothesis (does overhead amortize on large suites?)
2. Validating Rust parallelism wins at scale
3. Measuring selective import effectiveness

Expected results:
- Small suite (183 tests): 0.96x (overhead dominates)
- Large suite (Django): 1.3-2.0x (Rust parallelism wins)
"""

import subprocess
import time
import os
import statistics
import sys
from pathlib import Path
import tempfile
import shutil

def run_benchmark(label, args, cwd, runs=3):
    """Run pytest collection and measure time."""
    times = []

    env = os.environ.copy()
    env['PYTHONPATH'] = '/home/user/pytest-fastcollect:' + env.get('PYTHONPATH', '')

    print(f"\n{label}:")
    for i in range(runs):
        start = time.perf_counter()
        result = subprocess.run(
            ["pytest", "--collect-only", "-q"] + args,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for large suites
        )
        elapsed = time.perf_counter() - start

        if result.returncode in [0, 4, 5]:  # 0=success, 4=collection errors, 5=no tests
            times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.3f}s", end="")

            # Extract test count from first run
            if i == 0:
                for line in result.stdout.split('\n'):
                    if 'collected' in line.lower() or 'error' in line.lower():
                        print(f" - {line.strip()}")
                        break
                else:
                    print()
            else:
                print()
        else:
            print(f"  Run {i+1}: FAILED (code {result.returncode})")

    if not times:
        return 0, 0, times

    mean = statistics.mean(times)
    stddev = statistics.stdev(times) if len(times) > 1 else 0

    print(f"  Mean: {mean:.3f}s ± {stddev:.3f}s")

    return mean, stddev, times

def clone_django(base_dir):
    """Clone Django repository."""
    django_dir = base_dir / "django"

    if django_dir.exists():
        print(f"Django already cloned at {django_dir}")
        return django_dir

    print(f"\nCloning Django (this may take a few minutes)...")
    result = subprocess.run(
        ["git", "clone", "--depth", "1",
         "https://github.com/django/django.git",
         str(django_dir)],
        capture_output=True,
        text=True,
        timeout=600
    )

    if result.returncode != 0:
        print(f"Failed to clone Django: {result.stderr}")
        return None

    print(f"Django cloned successfully to {django_dir}")

    # Install Django dependencies (basic setup)
    print("\nInstalling Django dependencies...")
    subprocess.run(
        ["pip", "install", "-e", ".", "-q"],
        cwd=django_dir,
        capture_output=True,
        timeout=300
    )

    return django_dir

def count_test_files(django_dir):
    """Count test files in Django."""
    test_files = list(django_dir.rglob("test_*.py"))
    test_files.extend(django_dir.rglob("*_test.py"))
    test_files.extend(django_dir.rglob("tests.py"))
    return len(set(test_files))

print("="*70)
print("Django Large-Scale Benchmark")
print("="*70)
print("\nThis benchmark validates the scalability hypothesis:")
print("  Small suite (183 tests): 0.96x (fixed overhead dominates)")
print("  Large suite (Django):    1.3-2.0x? (Rust parallelism wins)")
print()

# Setup Django
base_dir = Path("/tmp/pytest_fastcollect_django_bench")
base_dir.mkdir(exist_ok=True)

django_dir = clone_django(base_dir)
if not django_dir:
    print("\n❌ Failed to clone Django. Exiting.")
    sys.exit(1)

# Count test files
test_file_count = count_test_files(django_dir)
print(f"\nDjango test files: ~{test_file_count}")

# Test directories (Django's test suite structure)
test_paths = [
    "tests",  # Main test directory
]

# Check which paths exist
existing_paths = [p for p in test_paths if (django_dir / p).exists()]
if not existing_paths:
    print("\n⚠️  Django test directory not found. Trying alternate structure...")
    # Django might have different structure
    possible_paths = list(django_dir.glob("*/tests"))
    if possible_paths:
        test_path = str(possible_paths[0].relative_to(django_dir))
        print(f"Found tests at: {test_path}")
        existing_paths = [test_path]
    else:
        print("❌ Could not find Django tests. Exiting.")
        sys.exit(1)

print(f"Testing collection on: {existing_paths}")

# Scenarios to test
scenarios = [
    {
        "name": "Full Collection (all Django tests)",
        "args_plugin": existing_paths,
        "args_baseline": existing_paths + ["-p", "no:pytest_fastcollect"],
        "expected": "Rust parallelism should win on large suite"
    },
    {
        "name": "Selective Import (-k views)",
        "args_plugin": existing_paths + ["-k", "views"],
        "args_baseline": existing_paths + ["-k", "views", "-p", "no:pytest_fastcollect"],
        "expected": "Rust filtering + file skipping should show major speedup"
    },
    {
        "name": "Selective Import (-k admin)",
        "args_plugin": existing_paths + ["-k", "admin"],
        "args_baseline": existing_paths + ["-k", "admin", "-p", "no:pytest_fastcollect"],
        "expected": "Rust filtering should skip most files"
    },
]

results = []

for i, scenario in enumerate(scenarios, 1):
    print(f"\n{'='*70}")
    print(f"[{i}/{len(scenarios)}] {scenario['name']}")
    print(f"{'='*70}")
    print(f"Expected: {scenario['expected']}")

    # Run with plugin
    plugin_mean, plugin_std, plugin_times = run_benchmark(
        "WITH PLUGIN (pytest-fastcollect)",
        scenario['args_plugin'],
        django_dir,
        runs=3
    )

    # Run baseline
    baseline_mean, baseline_std, baseline_times = run_benchmark(
        "WITHOUT PLUGIN (baseline pytest)",
        scenario['args_baseline'],
        django_dir,
        runs=3
    )

    # Calculate speedup
    if baseline_mean > 0 and plugin_mean > 0:
        speedup = baseline_mean / plugin_mean
        improvement = ((baseline_mean - plugin_mean) / baseline_mean) * 100

        symbol = "🎯" if speedup >= 1.5 else ("✅" if speedup >= 1.1 else ("➖" if speedup >= 0.95 else "⚠️"))
        print(f"\n  Speedup: {speedup:.2f}x ({improvement:+.1f}%) {symbol}")

        results.append({
            "name": scenario['name'],
            "plugin": plugin_mean,
            "baseline": baseline_mean,
            "speedup": speedup,
            "improvement": improvement
        })

# Summary
print("\n" + "="*70)
print("SUMMARY - Django Large-Scale Benchmark Results")
print("="*70)
print(f"\n{'Scenario':<45} {'Plugin':>8} {'Baseline':>8} {'Speedup':>8}")
print("-"*70)

for result in results:
    speedup_str = f"{result['speedup']:.2f}x"
    symbol = "🎯" if result['speedup'] >= 1.5 else ("✅" if result['speedup'] >= 1.1 else ("➖" if result['speedup'] >= 0.95 else "⚠️"))
    print(f"{result['name']:<45} {result['plugin']:>7.2f}s {result['baseline']:>7.2f}s {speedup_str:>8} {symbol}")

avg_speedup = sum(r['speedup'] for r in results) / len(results)
print("-"*70)
print(f"{'AVERAGE':<45} {'':<8} {'':<8} {avg_speedup:>7.2f}x")

# Analysis
print("\n" + "="*70)
print("ANALYSIS: Scalability Hypothesis")
print("="*70)

if avg_speedup >= 1.5:
    print(f"\n🎯 HYPOTHESIS CONFIRMED: {avg_speedup:.2f}x average speedup on Django!")
    print("   Rust parallelism wins at scale as predicted.")
    print("   Fixed overhead amortized over large test suite.")
elif avg_speedup >= 1.1:
    print(f"\n✅ HYPOTHESIS VALIDATED: {avg_speedup:.2f}x average speedup")
    print("   Moderate improvement on large suite.")
    print("   Better than small suite (0.96x) as expected.")
elif avg_speedup >= 0.95:
    print(f"\n➖ HYPOTHESIS UNCLEAR: {avg_speedup:.2f}x (neutral)")
    print("   Large suite didn't show expected improvement.")
    print("   May need investigation of Django-specific factors.")
else:
    print(f"\n⚠️  HYPOTHESIS REJECTED: {avg_speedup:.2f}x (slower)")
    print("   Unexpected regression on large suite.")

print("\nComparison:")
print(f"  Small suite (183 tests):  0.96x")
print(f"  Large suite (Django):     {avg_speedup:.2f}x")
print(f"  Improvement:               {avg_speedup - 0.96:+.2f}x")

if avg_speedup > 0.96:
    print(f"\n✅ Scalability confirmed: Performance improves with suite size!")
else:
    print(f"\n⚠️  Scalability not demonstrated on Django")

print("\n" + "="*70)
print("NEXT STEPS")
print("="*70)

if avg_speedup >= 1.2:
    print("""
✅ Django benchmark validates scalability!
✅ Plugin provides value on large test suites
✅ Ready for Phase 4: Daemon Auto-Start

Proceed with Phase 4 to add 100-1000x speedup on re-runs.
    """)
elif avg_speedup >= 1.0:
    print("""
➖ Modest improvement on Django
✅ Still validates that overhead doesn't worsen at scale
✅ Selective import remains the best feature

Proceed with Phase 4 for maximum user value (daemon mode).
    """)
else:
    print("""
⚠️  Unexpected results on Django
🔍 May need investigation:
   - Django-specific collection patterns?
   - Plugin compatibility issues?
   - Different test discovery mechanisms?

Consider investigating before Phase 4.
    """)

print(f"\nBenchmark complete!")
print(f"Django directory preserved at: {django_dir}")
print(f"Run 'rm -rf {base_dir}' to clean up")
