#!/usr/bin/env python3
"""Benchmark pytest-fastcollect on real-world projects."""

import os
import sys
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
import argparse
import json


class RealWorldBenchmark:
    """Benchmark pytest-fastcollect on real-world projects."""

    def __init__(self, project_path: Path, project_name: str = None):
        self.project_path = project_path.absolute()
        self.project_name = project_name or project_path.name

    def count_test_files(self):
        """Count the number of test files in the project."""
        test_files = list(self.project_path.rglob("test_*.py"))
        test_files.extend(self.project_path.rglob("*_test.py"))
        return len(set(test_files))

    def run_collection(self, use_fast: bool, use_cache: bool = True, clear_cache: bool = False):
        """Run pytest collection and measure time."""
        cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"]

        if use_fast:
            cmd.append("--use-fast-collect")
        else:
            cmd.append("--no-fast-collect")

        if not use_cache:
            cmd.append("--no-fastcollect-cache")

        if clear_cache:
            cmd.append("--fastcollect-clear-cache")

        start_time = time.perf_counter()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_path,
        )
        end_time = time.perf_counter()

        elapsed = end_time - start_time

        # Extract test count from output
        test_count = 0
        for line in result.stdout.split('\n'):
            if 'collected' in line.lower():
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit():
                        test_count = int(part)
                        break

        return elapsed, test_count, result

    def clear_cache(self):
        """Clear the pytest cache."""
        cache_dir = self.project_path / ".pytest_cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)

    def benchmark(self, runs: int = 3, warmup: int = 1):
        """Run a comprehensive benchmark."""
        print(f"\n{'='*80}")
        print(f"Real-World Benchmark: {self.project_name}")
        print(f"{'='*80}")
        print(f"Project path: {self.project_path}")

        test_file_count = self.count_test_files()
        print(f"Test files: {test_file_count}")
        print(f"{'='*80}\n")

        # Warmup
        if warmup > 0:
            print(f"Warming up ({warmup} runs)...")
            for _ in range(warmup):
                self.clear_cache()
                self.run_collection(use_fast=True, use_cache=False)
                self.run_collection(use_fast=False)
            print()

        # Scenario 1: Standard pytest collection (baseline)
        print("Scenario 1: Standard pytest collection (baseline)")
        print("-" * 80)
        self.clear_cache()
        standard_times = []
        test_count = 0
        for i in range(runs):
            self.clear_cache()
            elapsed, count, _ = self.run_collection(use_fast=False)
            standard_times.append(elapsed)
            test_count = count
            print(f"  Run {i+1}: {elapsed:.4f}s")

        avg_standard = sum(standard_times) / len(standard_times)
        print(f"  Average: {avg_standard:.4f}s")
        print(f"  Tests collected: {test_count}\n")

        # Scenario 2: Fast collection (no cache)
        print("Scenario 2: Fast collection (no cache, cold start)")
        print("-" * 80)
        fast_nocache_times = []
        for i in range(runs):
            self.clear_cache()
            elapsed, count, _ = self.run_collection(use_fast=True, use_cache=False)
            fast_nocache_times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.4f}s")

        avg_fast_nocache = sum(fast_nocache_times) / len(fast_nocache_times)
        print(f"  Average: {avg_fast_nocache:.4f}s\n")

        # Scenario 3: Fast collection (with cache, warm)
        print("Scenario 3: Fast collection (with cache, warm)")
        print("-" * 80)
        self.clear_cache()
        # Prime the cache
        self.run_collection(use_fast=True, use_cache=True)
        fast_cache_times = []
        for i in range(runs):
            elapsed, count, result = self.run_collection(use_fast=True, use_cache=True)
            fast_cache_times.append(elapsed)
            print(f"  Run {i+1}: {elapsed:.4f}s")
            # Show cache stats from stderr
            if i == 0 and "FastCollect Cache:" in result.stderr:
                for line in result.stderr.split('\n'):
                    if "FastCollect Cache:" in line:
                        print(f"    {line.strip()}")

        avg_fast_cache = sum(fast_cache_times) / len(fast_cache_times)
        print(f"  Average: {avg_fast_cache:.4f}s\n")

        # Results summary
        speedup_nocache = avg_standard / avg_fast_nocache
        speedup_cache = avg_standard / avg_fast_cache
        cache_improvement = avg_fast_nocache / avg_fast_cache

        print(f"{'='*80}")
        print("RESULTS SUMMARY")
        print(f"{'='*80}")
        print(f"Project:                          {self.project_name}")
        print(f"Test files:                       {test_file_count}")
        print(f"Tests collected:                  {test_count}")
        print(f"")
        print(f"Standard collection:              {avg_standard:.4f}s  (baseline)")
        print(f"Fast collection (no cache):       {avg_fast_nocache:.4f}s  ({speedup_nocache:.2f}x)")
        print(f"Fast collection (cached):         {avg_fast_cache:.4f}s  ({speedup_cache:.2f}x)")
        print(f"")
        print(f"Performance Analysis:")
        if speedup_cache > 1.0:
            print(f"  ✅ Speedup achieved:             {speedup_cache:.2f}x faster than baseline")
        elif speedup_cache > 0.95:
            print(f"  ≈  Comparable performance:       {speedup_cache:.2f}x (within 5%)")
        else:
            print(f"  ⚠️  Slower than baseline:        {speedup_cache:.2f}x")

        print(f"  Cache effectiveness:             {cache_improvement:.2f}x improvement")
        print(f"{'='*80}\n")

        return {
            "project_name": self.project_name,
            "test_files": test_file_count,
            "tests_collected": test_count,
            "standard_avg": avg_standard,
            "fast_nocache_avg": avg_fast_nocache,
            "fast_cache_avg": avg_fast_cache,
            "speedup_nocache": speedup_nocache,
            "speedup_cache": speedup_cache,
            "cache_improvement": cache_improvement,
        }


def clone_project(project_url: str, target_dir: Path):
    """Clone a git repository."""
    print(f"Cloning {project_url}...")
    subprocess.run(
        ["git", "clone", "--depth", "1", project_url, str(target_dir)],
        check=True,
        capture_output=True,
    )
    print(f"Cloned to {target_dir}")


def setup_project_env(project_dir: Path):
    """Install project dependencies."""
    # Try to install the project
    setup_py = project_dir / "setup.py"
    pyproject_toml = project_dir / "pyproject.toml"

    if pyproject_toml.exists():
        print("Installing project with pyproject.toml...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(project_dir)],
            capture_output=True,
        )
    elif setup_py.exists():
        print("Installing project with setup.py...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(project_dir)],
            capture_output=True,
        )


def main():
    """Main benchmarking function."""
    parser = argparse.ArgumentParser(description="Benchmark pytest-fastcollect on real projects")
    parser.add_argument(
        "--project",
        type=Path,
        help="Path to local project directory",
    )
    parser.add_argument(
        "--clone",
        type=str,
        help="Git URL to clone and benchmark",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="Project name for display",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of benchmark runs per scenario",
    )
    parser.add_argument(
        "--pandas",
        action="store_true",
        help="Benchmark on pandas (clone if needed)",
    )
    parser.add_argument(
        "--requests",
        action="store_true",
        help="Benchmark on requests library",
    )
    parser.add_argument(
        "--flask",
        action="store_true",
        help="Benchmark on flask",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Benchmark on all popular projects",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save results to JSON file",
    )

    args = parser.parse_args()

    results = []

    # Predefined projects
    popular_projects = {
        "pandas": "https://github.com/pandas-dev/pandas.git",
        "requests": "https://github.com/psf/requests.git",
        "flask": "https://github.com/pallets/flask.git",
    }

    projects_to_benchmark = []

    if args.project:
        projects_to_benchmark.append((args.project, args.name or args.project.name))

    if args.clone:
        with tempfile.TemporaryDirectory() as tmpdir:
            clone_dir = Path(tmpdir) / "project"
            clone_project(args.clone, clone_dir)
            projects_to_benchmark.append((clone_dir, args.name or "cloned-project"))

    if args.pandas or args.all:
        projects_to_benchmark.append(("pandas", "pandas"))

    if args.requests or args.all:
        projects_to_benchmark.append(("requests", "requests"))

    if args.flask or args.all:
        projects_to_benchmark.append(("flask", "flask"))

    if not projects_to_benchmark:
        parser.print_help()
        print("\nNo project specified. Use --project, --clone, or --pandas/--requests/--flask")
        return

    # Benchmark each project
    for project_spec, name in projects_to_benchmark:
        if isinstance(project_spec, str) and project_spec in popular_projects:
            # Need to clone
            with tempfile.TemporaryDirectory() as tmpdir:
                project_dir = Path(tmpdir) / project_spec
                clone_project(popular_projects[project_spec], project_dir)

                benchmark = RealWorldBenchmark(project_dir, name)
                result = benchmark.benchmark(runs=args.runs)
                results.append(result)
        else:
            # Local project
            benchmark = RealWorldBenchmark(Path(project_spec), name)
            result = benchmark.benchmark(runs=args.runs)
            results.append(result)

    # Save results if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")

    # Print summary if multiple projects
    if len(results) > 1:
        print(f"\n{'='*80}")
        print("OVERALL SUMMARY")
        print(f"{'='*80}")
        for result in results:
            speedup = result['speedup_cache']
            status = "✅" if speedup > 1.0 else "≈" if speedup > 0.95 else "⚠️"
            print(f"{status} {result['project_name']:20s} - {speedup:.2f}x speedup ({result['tests_collected']} tests)")
        print(f"{'='*80}")


if __name__ == "__main__":
    main()
