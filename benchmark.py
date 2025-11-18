#!/usr/bin/env python3
"""Benchmark script to compare collection performance."""

import os
import sys
import time
import subprocess
import tempfile
from pathlib import Path
import argparse


def generate_test_files(base_dir: Path, num_files: int, tests_per_file: int):
    """Generate test files for benchmarking."""
    test_dir = base_dir / "generated_tests"
    test_dir.mkdir(exist_ok=True)

    for i in range(num_files):
        file_path = test_dir / f"test_generated_{i:04d}.py"
        with open(file_path, "w") as f:
            f.write('"""Auto-generated test file."""\n\n')

            # Add some test functions
            for j in range(tests_per_file):
                f.write(f"def test_function_{j:04d}():\n")
                f.write(f'    """Test function {j}."""\n')
                f.write(f"    assert {j} + 1 == {j + 1}\n\n")

            # Add a test class
            f.write(f"class TestClass{i:04d}:\n")
            f.write(f'    """Test class {i}."""\n\n')
            for j in range(tests_per_file // 2):
                f.write(f"    def test_method_{j:04d}(self):\n")
                f.write(f'        """Test method {j}."""\n')
                f.write(f"        assert {j} * 2 == {j * 2}\n\n")

    return test_dir


def run_collection(test_dir: Path, use_fast: bool, use_cache: bool = True, collect_only: bool = True):
    """Run pytest collection and measure time."""
    env = os.environ.copy()

    cmd = [sys.executable, "-m", "pytest"]

    if collect_only:
        cmd.append("--collect-only")

    if use_fast:
        cmd.append("--use-fast-collect")
    else:
        cmd.append("--no-fast-collect")

    if not use_cache:
        cmd.append("--no-fastcollect-cache")

    cmd.extend(["-q", str(test_dir)])

    start_time = time.perf_counter()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=test_dir.parent,
    )
    end_time = time.perf_counter()

    elapsed = end_time - start_time
    return elapsed, result


def clear_cache(test_dir: Path):
    """Clear the pytest cache."""
    subprocess.run(
        [sys.executable, "-m", "pytest", "--fastcollect-clear-cache", "--collect-only", "-q", str(test_dir)],
        capture_output=True,
        cwd=test_dir.parent,
    )


def benchmark_synthetic(num_files: int = 100, tests_per_file: int = 50):
    """Benchmark on synthetic test suite."""
    print(f"\n{'='*70}")
    print(f"Synthetic Benchmark: {num_files} files, {tests_per_file} tests/file")
    print(f"{'='*70}\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = generate_test_files(Path(tmpdir), num_files, tests_per_file)

        # Warmup
        print("Warming up...")
        clear_cache(test_dir)
        run_collection(test_dir, use_fast=True, use_cache=False)
        run_collection(test_dir, use_fast=False)

        # Benchmark with fast collection (NO CACHE - first run)
        print("\nRunning with Rust fast collection (no cache, cold start)...")
        clear_cache(test_dir)
        fast_nocache_times = []
        for i in range(3):
            clear_cache(test_dir)
            elapsed, result = run_collection(test_dir, use_fast=True, use_cache=False)
            fast_nocache_times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.4f}s")

        # Benchmark with fast collection (WITH CACHE - warm cache)
        print("\nRunning with Rust fast collection (with cache, warm)...")
        clear_cache(test_dir)
        # Prime the cache
        run_collection(test_dir, use_fast=True, use_cache=True)
        fast_cache_times = []
        for i in range(5):
            elapsed, result = run_collection(test_dir, use_fast=True, use_cache=True)
            fast_cache_times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.4f}s")

        # Benchmark without fast collection
        print("\nRunning with standard pytest collection...")
        standard_times = []
        for i in range(3):
            elapsed, result = run_collection(test_dir, use_fast=False)
            standard_times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.4f}s")

        # Calculate statistics
        avg_fast_nocache = sum(fast_nocache_times) / len(fast_nocache_times)
        avg_fast_cache = sum(fast_cache_times) / len(fast_cache_times)
        avg_standard = sum(standard_times) / len(standard_times)
        speedup_nocache = avg_standard / avg_fast_nocache
        speedup_cache = avg_standard / avg_fast_cache

        print(f"\n{'='*70}")
        print(f"Results:")
        print(f"  Standard collection average:           {avg_standard:.4f}s")
        print(f"  Fast collection (no cache) average:    {avg_fast_nocache:.4f}s ({speedup_nocache:.2f}x)")
        print(f"  Fast collection (cached) average:      {avg_fast_cache:.4f}s ({speedup_cache:.2f}x)")
        print(f"  Cache improvement:                     {avg_fast_nocache / avg_fast_cache:.2f}x")
        print(f"{'='*70}\n")

        return {
            "fast_nocache_avg": avg_fast_nocache,
            "fast_cache_avg": avg_fast_cache,
            "standard_avg": avg_standard,
            "speedup_nocache": speedup_nocache,
            "speedup_cache": speedup_cache,
        }


def benchmark_real_project(project_path: Path):
    """Benchmark on a real project."""
    if not project_path.exists():
        print(f"Error: Project path {project_path} does not exist")
        return None

    print(f"\n{'='*70}")
    print(f"Real Project Benchmark: {project_path}")
    print(f"{'='*70}\n")

    # Warmup
    print("Warming up...")
    run_collection(project_path, use_fast=True)
    run_collection(project_path, use_fast=False)

    # Benchmark with fast collection
    print("\nRunning with Rust fast collection...")
    fast_times = []
    for i in range(3):
        elapsed, result = run_collection(project_path, use_fast=True)
        fast_times.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.4f}s")

    # Benchmark without fast collection
    print("\nRunning with standard pytest collection...")
    standard_times = []
    for i in range(3):
        elapsed, result = run_collection(project_path, use_fast=False)
        standard_times.append(elapsed)
        print(f"  Run {i+1}: {elapsed:.4f}s")

    # Calculate statistics
    avg_fast = sum(fast_times) / len(fast_times)
    avg_standard = sum(standard_times) / len(standard_times)
    speedup = avg_standard / avg_fast

    print(f"\n{'='*70}")
    print(f"Results:")
    print(f"  Fast collection average:     {avg_fast:.4f}s")
    print(f"  Standard collection average: {avg_standard:.4f}s")
    print(f"  Speedup:                     {speedup:.2f}x")
    print(f"{'='*70}\n")

    return {
        "fast_avg": avg_fast,
        "standard_avg": avg_standard,
        "speedup": speedup,
    }


def main():
    """Main benchmark function."""
    parser = argparse.ArgumentParser(description="Benchmark pytest-fastcollect")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Run synthetic benchmark",
    )
    parser.add_argument(
        "--num-files",
        type=int,
        default=100,
        help="Number of test files for synthetic benchmark",
    )
    parser.add_argument(
        "--tests-per-file",
        type=int,
        default=50,
        help="Number of tests per file for synthetic benchmark",
    )
    parser.add_argument(
        "--project",
        type=Path,
        help="Path to real project for benchmarking",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all benchmarks",
    )

    args = parser.parse_args()

    if args.all or args.synthetic:
        benchmark_synthetic(args.num_files, args.tests_per_file)

    if args.project:
        benchmark_real_project(args.project)

    if not (args.all or args.synthetic or args.project):
        # Default: run synthetic benchmark
        benchmark_synthetic()


if __name__ == "__main__":
    main()
