#!/usr/bin/env python3
"""
Benchmark pytest-fastcollect on Django's test suite.
Django is a large, real-world codebase with ~1977 test files.
"""

import subprocess
import sys
import time
from pathlib import Path

DJANGO_PATH = Path("/tmp/django/tests")


def run_collection(args, label, use_plugin=True):
    """Run pytest collection and measure time."""
    # Use the venv python that has pytest installed
    venv_python = Path("/home/user/pytest-fastcollect/.venv/bin/python")
    if venv_python.exists():
        python_cmd = str(venv_python)
    else:
        python_cmd = sys.executable

    cmd = [python_cmd, "-m", "pytest"]

    if not use_plugin:
        cmd.append("-p")
        cmd.append("no:fastcollect")

    cmd.extend(args)
    cmd.append("--collect-only")
    cmd.append("-q")
    cmd.append(str(DJANGO_PATH))

    print(f"\n{'='*60}")
    print(f"Running: {label}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(DJANGO_PATH.parent),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        elapsed = time.time() - start

        # Extract test count from output
        output_lines = result.stdout.split('\n')
        for line in output_lines:
            if 'test' in line.lower():
                print(f"Output: {line}")

        if result.stderr:
            # Print relevant stderr (but not all of it)
            stderr_lines = result.stderr.split('\n')
            for line in stderr_lines[:5]:
                if line.strip():
                    print(f"  {line}")

        print(f"⏱️  Time: {elapsed:.2f}s")
        return elapsed
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout after 300s")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def main():
    """Run Django benchmarks."""
    print("="*60)
    print("DJANGO TEST SUITE BENCHMARK")
    print("="*60)
    print(f"Django tests path: {DJANGO_PATH}")
    print(f"Test files: ~1977 Python files")
    print()

    # Check if Django tests exist
    if not DJANGO_PATH.exists():
        print(f"❌ Django tests not found at {DJANGO_PATH}")
        print("Run: cd /tmp && git clone https://github.com/django/django.git --depth 1")
        sys.exit(1)

    results = {}

    # 1. Baseline - Standard pytest (no plugin)
    baseline = run_collection([], "Baseline - Standard pytest (no plugin)", use_plugin=False)
    if baseline:
        results['baseline'] = baseline

    # 2. Full collection with FastCollect
    full = run_collection([], "FastCollect - Full collection", use_plugin=True)
    if full:
        results['full'] = full

    # 3. Keyword filter - common test names
    k_filter = run_collection(["-k", "test_get"], "FastCollect - Keyword filter (-k test_get)", use_plugin=True)
    if k_filter:
        results['k_filter'] = k_filter

    # 4. Keyword filter - more specific
    k_specific = run_collection(["-k", "test_forms"], "FastCollect - Keyword filter (-k test_forms)", use_plugin=True)
    if k_specific:
        results['k_specific'] = k_specific

    # 5. Combined filter
    k_combined = run_collection(["-k", "test_view or test_model"], "FastCollect - Combined filter (-k 'test_view or test_model')", use_plugin=True)
    if k_combined:
        results['k_combined'] = k_combined

    # Print summary
    print("\n" + "="*60)
    print("BENCHMARK RESULTS SUMMARY")
    print("="*60)

    if 'baseline' in results and 'full' in results:
        speedup = results['baseline'] / results['full']
        print(f"\n📊 Full Collection Performance:")
        print(f"  Baseline (no plugin):  {results['baseline']:6.2f}s")
        print(f"  FastCollect:           {results['full']:6.2f}s  ({speedup:.2f}x)")

    if 'full' in results:
        print(f"\n📊 Selective Import Performance:")
        if 'k_filter' in results:
            speedup = results['full'] / results['k_filter']
            print(f"  Full collection:       {results['full']:6.2f}s  (baseline)")
            print(f"  -k test_get:           {results['k_filter']:6.2f}s  ({speedup:.2f}x faster)")

        if 'k_specific' in results:
            speedup = results['full'] / results['k_specific']
            print(f"  -k test_forms:         {results['k_specific']:6.2f}s  ({speedup:.2f}x faster)")

        if 'k_combined' in results:
            speedup = results['full'] / results['k_combined']
            print(f"  -k combined:           {results['k_combined']:6.2f}s  ({speedup:.2f}x faster)")

    print("\n" + "="*60)
    print("Django is a real-world codebase with ~1977 test files.")
    print("Results show pytest-fastcollect performance on production code.")
    print("="*60)


if __name__ == "__main__":
    main()
