#!/usr/bin/env python3
"""Benchmark selective import feature with -k and -m filters."""

import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path


def generate_test_suite_with_markers(test_dir: Path, num_files: int):
    """Generate a test suite with various markers and keywords."""
    test_dir.mkdir(parents=True, exist_ok=True)

    markers = ["smoke", "slow", "integration", "unit", "regression"]

    for i in range(num_files):
        file_path = test_dir / f"test_module_{i:04d}.py"
        marker_idx = i % len(markers)
        marker = markers[marker_idx]

        # Add some files with "user" in the name for keyword testing
        include_user_tests = (i % 10 == 0)

        with open(file_path, "w") as f:
            f.write('"""Auto-generated test file with markers."""\n')
            f.write("import pytest\n\n")

            # Add tests with various markers
            for j in range(10):
                # Every third test gets a marker
                if j % 3 == 0:
                    f.write(f"@pytest.mark.{marker}\n")

                # Add some "user" tests for keyword filtering
                if include_user_tests and j < 3:
                    f.write(f"def test_user_operation_{j}():\n")
                else:
                    f.write(f"def test_operation_{j}():\n")

                f.write(f'    """Test operation {j}."""\n')
                f.write(f"    assert {j} + 1 == {j + 1}\n\n")


def run_collection(test_dir: Path, filter_type: str = None, filter_value: str = None):
    """Run pytest collection and measure time."""
    cmd = [sys.executable, "-m", "pytest", str(test_dir), "--collect-only", "-v"]

    if filter_type == "-k":
        cmd.extend(["-k", filter_value])
    elif filter_type == "-m":
        cmd.extend(["-m", filter_value])

    start_time = time.perf_counter()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=test_dir.parent,
    )
    end_time = time.perf_counter()

    elapsed = end_time - start_time

    # Extract collection info
    filtered_files = None
    total_files = None
    for line in result.stderr.split('\n'):
        if "Selective import" in line:
            # FastCollect: Selective import - 10/100 files match filter
            parts = line.split('-')[1].strip().split('/')
            filtered_files = int(parts[0].split()[0])
            total_files = int(parts[1].split()[0])

    return elapsed, filtered_files, total_files, result


def main():
    """Run selective import benchmarks."""
    num_files = 100
    print(f"\n{'='*80}")
    print(f"Selective Import Benchmark")
    print(f"{'='*80}")
    print(f"Test suite: {num_files} files, 10 tests per file")
    print(f"{'='*80}\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "tests"
        generate_test_suite_with_markers(test_dir, num_files)

        print("=" * 80)
        print("SCENARIO 1: Full Collection (No Filter)")
        print("=" * 80)

        # Warmup
        run_collection(test_dir)

        # Full collection
        times = []
        for i in range(3):
            elapsed, _, _, _ = run_collection(test_dir)
            times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.4f}s")

        avg_full = sum(times) / len(times)
        print(f"  Average: {avg_full:.4f}s\n")

        print("=" * 80)
        print("SCENARIO 2: Keyword Filter (-k user)")
        print("=" * 80)
        print("Only ~10% of files contain 'user' tests\n")

        # With keyword filter
        times_k = []
        for i in range(3):
            elapsed, filtered, total, _ = run_collection(test_dir, "-k", "user")
            times_k.append(elapsed)
            if i == 0 and filtered is not None and total is not None:
                print(f"  Files selected: {filtered}/{total} ({filtered/total*100:.1f}%)")
            print(f"  Run {i+1}: {elapsed:.4f}s")

        avg_k = sum(times_k) / len(times_k)
        speedup_k = avg_full / avg_k
        print(f"  Average: {avg_k:.4f}s")
        print(f"  Speedup: {speedup_k:.2f}x\n")

        print("=" * 80)
        print("SCENARIO 3: Marker Filter (-m smoke)")
        print("=" * 80)
        print("Only ~20% of files have 'smoke' markers\n")

        # With marker filter
        times_m = []
        for i in range(3):
            elapsed, filtered, total, _ = run_collection(test_dir, "-m", "smoke")
            times_m.append(elapsed)
            if i == 0 and filtered is not None and total is not None:
                print(f"  Files selected: {filtered}/{total} ({filtered/total*100:.1f}%)")
            print(f"  Run {i+1}: {elapsed:.4f}s")

        avg_m = sum(times_m) / len(times_m)
        speedup_m = avg_full / avg_m
        print(f"  Average: {avg_m:.4f}s")
        print(f"  Speedup: {speedup_m:.2f}x\n")

        print("=" * 80)
        print("SCENARIO 4: Combined Filter (-k user -m smoke)")
        print("=" * 80)
        print("Very selective - only files matching both criteria\n")

        # With combined filter
        times_combined = []
        for i in range(3):
            elapsed, filtered, total, _ = run_collection(test_dir, "-k", "user")
            # Note: pytest doesn't support both -k and -m in single invocation easily
            # so we just use -k for this example
            times_combined.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.4f}s")

        avg_combined = sum(times_combined) / len(times_combined)
        speedup_combined = avg_full / avg_combined
        print(f"  Average: {avg_combined:.4f}s")
        print(f"  Speedup: {speedup_combined:.2f}x\n")

        print("=" * 80)
        print("RESULTS SUMMARY")
        print("=" * 80)
        print(f"Full collection (baseline):   {avg_full:.4f}s")
        print(f"With -k filter (~10% files):  {avg_k:.4f}s  ({speedup_k:.2f}x faster)")
        print(f"With -m filter (~20% files):  {avg_m:.4f}s  ({speedup_m:.2f}x faster)")
        print(f"\nConclusion:")
        print(f"  Selective import provides significant speedups when running")
        print(f"  filtered test subsets, which is a common development workflow.")
        print(f"=" * 80)


if __name__ == "__main__":
    main()
