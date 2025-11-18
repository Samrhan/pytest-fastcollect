#!/usr/bin/env python3
"""
Benchmark parallel import performance on real-world projects.

Tests the --parallel-import optimization that pre-imports modules
in parallel before pytest's collection phase.
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Project configurations
PROJECTS = {
    "django": {
        "path": Path("/tmp/django/tests"),
        "name": "Django",
        "expected_files": 1977,
    },
    "sqlalchemy": {
        "path": Path("/tmp/sqlalchemy/test"),
        "name": "SQLAlchemy",
        "expected_files": 219,
    },
    "pytest": {
        "path": Path("/tmp/pytest/testing"),
        "name": "Pytest",
        "expected_files": 108,
    },
}


def run_collection(
    test_path: Path,
    use_parallel: bool = False,
    workers: int = None,
    timeout: int = 300
) -> Optional[float]:
    """Run pytest collection and measure time."""
    venv_python = Path("/home/user/pytest-fastcollect/.venv/bin/python")
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable

    cmd = [python_cmd, "-m", "pytest", "--collect-only", "-q", str(test_path)]

    if use_parallel:
        cmd.append("--parallel-import")
        if workers:
            cmd.append(f"--parallel-workers={workers}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start
        return elapsed
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


def benchmark_parallel_import(project_key: str) -> Dict[str, Optional[float]]:
    """Benchmark parallel import on a single project."""
    project = PROJECTS[project_key]
    test_path = project["path"]

    if not test_path.exists():
        print(f"❌ {project['name']}: Test path not found at {test_path}")
        return {}

    print(f"\n{'='*70}")
    print(f"📦 {project['name']} - {project['expected_files']} test files")
    print(f"{'='*70}")

    results = {}

    # 1. Baseline (no parallel import)
    print(f"  Running baseline (no parallel)...", end=" ", flush=True)
    baseline = run_collection(test_path, use_parallel=False)
    if baseline:
        results["baseline"] = baseline
        print(f"✓ {baseline:.2f}s")
    else:
        print("✗ Failed")

    # 2. Parallel import with default workers
    print(f"  Running with parallel import (default workers)...", end=" ", flush=True)
    parallel_default = run_collection(test_path, use_parallel=True)
    if parallel_default:
        results["parallel_default"] = parallel_default
        print(f"✓ {parallel_default:.2f}s")
    else:
        print("✗ Failed")

    # 3. Parallel import with 4 workers
    print(f"  Running with parallel import (4 workers)...", end=" ", flush=True)
    parallel_4 = run_collection(test_path, use_parallel=True, workers=4)
    if parallel_4:
        results["parallel_4"] = parallel_4
        print(f"✓ {parallel_4:.2f}s")
    else:
        print("✗ Failed")

    # 4. Parallel import with 8 workers
    print(f"  Running with parallel import (8 workers)...", end=" ", flush=True)
    parallel_8 = run_collection(test_path, use_parallel=True, workers=8)
    if parallel_8:
        results["parallel_8"] = parallel_8
        print(f"✓ {parallel_8:.2f}s")
    else:
        print("✗ Failed")

    return results


def calculate_speedup(baseline: Optional[float], optimized: Optional[float]) -> str:
    """Calculate and format speedup."""
    if baseline and optimized and baseline > 0 and optimized > 0:
        speedup = baseline / optimized
        return f"{speedup:.2f}x"
    return "N/A"


def print_results(all_results: Dict[str, Dict[str, Optional[float]]]):
    """Print results table."""
    print("\n" + "="*70)
    print("PARALLEL IMPORT BENCHMARK RESULTS")
    print("="*70)

    for project_key, results in all_results.items():
        if not results:
            continue

        project = PROJECTS[project_key]
        print(f"\n{project['name']} ({project['expected_files']} files)")
        print("-" * 70)

        baseline = results.get("baseline")
        parallel_default = results.get("parallel_default")
        parallel_4 = results.get("parallel_4")
        parallel_8 = results.get("parallel_8")

        if baseline:
            print(f"  Baseline (no parallel):      {baseline:6.2f}s")

        if parallel_default:
            speedup = calculate_speedup(baseline, parallel_default)
            improvement = ""
            if baseline and parallel_default < baseline:
                improvement = f" ({speedup} faster)"
            elif baseline and parallel_default > baseline:
                slowdown = baseline / parallel_default
                improvement = f" ({slowdown:.2f}x slower)"
            print(f"  Parallel (default workers):  {parallel_default:6.2f}s{improvement}")

        if parallel_4:
            speedup = calculate_speedup(baseline, parallel_4)
            improvement = ""
            if baseline and parallel_4 < baseline:
                improvement = f" ({speedup} faster)"
            elif baseline and parallel_4 > baseline:
                slowdown = baseline / parallel_4
                improvement = f" ({slowdown:.2f}x slower)"
            print(f"  Parallel (4 workers):        {parallel_4:6.2f}s{improvement}")

        if parallel_8:
            speedup = calculate_speedup(baseline, parallel_8)
            improvement = ""
            if baseline and parallel_8 < baseline:
                improvement = f" ({speedup} faster)"
            elif baseline and parallel_8 > baseline:
                slowdown = baseline / parallel_8
                improvement = f" ({slowdown:.2f}x slower)"
            print(f"  Parallel (8 workers):        {parallel_8:6.2f}s{improvement}")


def print_summary(all_results: Dict[str, Dict[str, Optional[float]]]):
    """Print summary."""
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)

    print("\nParallel import pre-warms module imports using ThreadPoolExecutor.")
    print("Even with Python's GIL, I/O operations can benefit from parallelism.")
    print()

    # Calculate if parallel import helps
    helped = []
    neutral = []
    hurt = []

    for project_key, results in all_results.items():
        baseline = results.get("baseline")
        parallel = results.get("parallel_default")

        if baseline and parallel:
            if parallel < baseline * 0.95:  # At least 5% improvement
                helped.append(PROJECTS[project_key]["name"])
            elif parallel > baseline * 1.05:  # More than 5% slower
                hurt.append(PROJECTS[project_key]["name"])
            else:
                neutral.append(PROJECTS[project_key]["name"])

    if helped:
        print(f"✅ Helped: {', '.join(helped)}")
    if neutral:
        print(f"→ Neutral: {', '.join(neutral)}")
    if hurt:
        print(f"⚠️ Slowed down: {', '.join(hurt)}")

    print("\n" + "="*70)


def main():
    """Run parallel import benchmarks."""
    print("="*70)
    print("PARALLEL IMPORT BENCHMARK")
    print("="*70)
    print()
    print("Testing --parallel-import optimization on real-world projects")
    print("This pre-imports modules in parallel before pytest's collection phase")
    print()

    all_results = {}

    # Run benchmarks (small to large)
    for project_key in ["pytest", "sqlalchemy", "django"]:
        try:
            results = benchmark_parallel_import(project_key)
            if results:
                all_results[project_key] = results
        except KeyboardInterrupt:
            print("\n\n⚠️  Benchmark interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error benchmarking {project_key}: {e}")

    # Print results
    if all_results:
        print_results(all_results)
        print_summary(all_results)
    else:
        print("\n❌ No benchmark results collected")

    print("\nBenchmark complete! 🎉")


if __name__ == "__main__":
    main()
