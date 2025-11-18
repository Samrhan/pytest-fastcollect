#!/usr/bin/env python3
"""Benchmark incremental collection with caching."""

import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path


def generate_test_files(test_dir: Path, num_files: int, tests_per_file: int):
    """Generate test files for benchmarking."""
    test_dir.mkdir(parents=True, exist_ok=True)

    for i in range(num_files):
        file_path = test_dir / f"test_file_{i:04d}.py"
        with open(file_path, "w") as f:
            f.write('"""Auto-generated test file."""\n\n')
            for j in range(tests_per_file):
                f.write(f"def test_function_{j:04d}():\n")
                f.write(f'    """Test function {j}."""\n')
                f.write(f"    assert {j} + 1 == {j + 1}\n\n")


def modify_file(file_path: Path):
    """Modify a test file to trigger re-parsing."""
    content = file_path.read_text()
    # Add a comment to change mtime
    file_path.write_text(content + "\n# Modified\n")


def run_collection(test_dir: Path, use_cache: bool = True):
    """Run pytest collection and measure time."""
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q", str(test_dir)]

    if not use_cache:
        cmd.append("--no-fastcollect-cache")

    start_time = time.perf_counter()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=test_dir.parent,
    )
    end_time = time.perf_counter()

    return end_time - start_time, result


def clear_cache(test_dir: Path):
    """Clear the pytest cache."""
    subprocess.run(
        [sys.executable, "-m", "pytest", "--fastcollect-clear-cache", "--collect-only", "-q", str(test_dir)],
        capture_output=True,
        cwd=test_dir.parent,
    )


def main():
    """Run incremental caching benchmark."""
    num_files = 500
    tests_per_file = 20
    files_to_modify = 5  # Only modify 1% of files

    print(f"\n{'='*80}")
    print(f"Incremental Caching Benchmark")
    print(f"{'='*80}")
    print(f"Total files: {num_files}")
    print(f"Tests per file: {tests_per_file}")
    print(f"Files to modify: {files_to_modify} ({files_to_modify/num_files*100:.1f}%)")
    print(f"{'='*80}\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "tests"
        generate_test_files(test_dir, num_files, tests_per_file)

        # Scenario 1: Cold start (no cache)
        print("Scenario 1: Cold start (no cache)")
        print("-" * 80)
        clear_cache(test_dir)
        cold_times = []
        for i in range(3):
            clear_cache(test_dir)
            elapsed, _ = run_collection(test_dir, use_cache=False)
            cold_times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.4f}s")

        avg_cold = sum(cold_times) / len(cold_times)
        print(f"  Average: {avg_cold:.4f}s\n")

        # Scenario 2: Warm cache (no changes)
        print("Scenario 2: Warm cache (no file changes)")
        print("-" * 80)
        clear_cache(test_dir)
        # Prime the cache
        run_collection(test_dir, use_cache=True)
        warm_times = []
        for i in range(5):
            elapsed, _ = run_collection(test_dir, use_cache=True)
            warm_times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.4f}s")

        avg_warm = sum(warm_times) / len(warm_times)
        print(f"  Average: {avg_warm:.4f}s\n")

        # Scenario 3: Incremental (modify a few files)
        print(f"Scenario 3: Incremental ({files_to_modify} files modified)")
        print("-" * 80)

        incremental_times = []
        for i in range(5):
            # Modify a few files
            for j in range(files_to_modify):
                file_idx = (i * files_to_modify + j) % num_files
                file_path = test_dir / f"test_file_{file_idx:04d}.py"
                modify_file(file_path)

            elapsed, _ = run_collection(test_dir, use_cache=True)
            incremental_times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.4f}s ({files_to_modify} files modified)")

        avg_incremental = sum(incremental_times) / len(incremental_times)
        print(f"  Average: {avg_incremental:.4f}s\n")

        # Results summary
        print(f"{'='*80}")
        print("RESULTS SUMMARY")
        print(f"{'='*80}")
        print(f"Cold start (no cache):              {avg_cold:.4f}s  (baseline)")
        print(f"Warm cache (no changes):            {avg_warm:.4f}s  ({avg_cold/avg_warm:.2f}x faster)")
        print(f"Incremental ({files_to_modify} files changed):      {avg_incremental:.4f}s  ({avg_cold/avg_incremental:.2f}x faster)")
        print(f"\nCache effectiveness:")
        print(f"  Warm cache vs cold:               {avg_cold/avg_warm:.2f}x speedup")
        print(f"  Incremental vs cold:              {avg_cold/avg_incremental:.2f}x speedup")
        print(f"  Incremental overhead:             {((avg_incremental/avg_warm - 1) * 100):.1f}% slower than warm")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
