#!/usr/bin/env python3
"""
Benchmark ProcessPoolExecutor vs ThreadPoolExecutor performance.

Compares:
- Baseline (no parallel import)
- ThreadPoolExecutor (limited by GIL)
- ProcessPoolExecutor (bypasses GIL, true parallelism)
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Project configurations
PROJECTS = {
    "pytest": {
        "path": Path("/tmp/pytest/testing"),
        "name": "Pytest",
        "expected_files": 108,
    },
    "sqlalchemy": {
        "path": Path("/tmp/sqlalchemy/test"),
        "name": "SQLAlchemy",
        "expected_files": 219,
    },
    "django": {
        "path": Path("/tmp/django/tests"),
        "name": "Django",
        "expected_files": 1977,
    },
}


def run_collection(
    test_path: Path,
    parallel_mode: str = "none",  # "none", "threads", "processes"
    workers: int = 4,
    timeout: int = 300
) -> Optional[float]:
    """Run pytest collection and measure time.

    Args:
        parallel_mode: "none", "threads", or "processes"
    """
    venv_python = Path("/home/user/pytest-fastcollect/.venv/bin/python")
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable

    cmd = [python_cmd, "-m", "pytest", "--collect-only", "-q", str(test_path)]

    if parallel_mode == "threads":
        cmd.extend(["--parallel-import", f"--parallel-workers={workers}"])
    elif parallel_mode == "processes":
        cmd.extend(["--parallel-import", "--use-processes", f"--parallel-workers={workers}"])

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


def benchmark_project(project_key: str) -> Dict[str, Optional[float]]:
    """Benchmark all modes on a single project."""
    project = PROJECTS[project_key]
    test_path = project["path"]

    if not test_path.exists():
        print(f"❌ {project['name']}: Test path not found at {test_path}")
        return {}

    print(f"\n{'='*70}")
    print(f"📦 {project['name']} - {project['expected_files']} test files")
    print(f"{'='*70}")

    results = {}

    # 1. Baseline (no parallel)
    print(f"  Baseline (no parallel)...", end=" ", flush=True)
    baseline = run_collection(test_path, parallel_mode="none")
    if baseline:
        results["baseline"] = baseline
        print(f"✓ {baseline:.2f}s")
    else:
        print("✗ Failed")

    # 2. ThreadPoolExecutor (4 workers)
    print(f"  ThreadPoolExecutor (4 workers)...", end=" ", flush=True)
    threads_4 = run_collection(test_path, parallel_mode="threads", workers=4)
    if threads_4:
        results["threads_4"] = threads_4
        print(f"✓ {threads_4:.2f}s")
    else:
        print("✗ Failed")

    # 3. ThreadPoolExecutor (8 workers)
    print(f"  ThreadPoolExecutor (8 workers)...", end=" ", flush=True)
    threads_8 = run_collection(test_path, parallel_mode="threads", workers=8)
    if threads_8:
        results["threads_8"] = threads_8
        print(f"✓ {threads_8:.2f}s")
    else:
        print("✗ Failed")

    # 4. ProcessPoolExecutor (4 workers) - NEW!
    print(f"  ProcessPoolExecutor (4 workers)...", end=" ", flush=True)
    processes_4 = run_collection(test_path, parallel_mode="processes", workers=4)
    if processes_4:
        results["processes_4"] = processes_4
        print(f"✓ {processes_4:.2f}s")
    else:
        print("✗ Failed")

    # 5. ProcessPoolExecutor (8 workers) - NEW!
    print(f"  ProcessPoolExecutor (8 workers)...", end=" ", flush=True)
    processes_8 = run_collection(test_path, parallel_mode="processes", workers=8)
    if processes_8:
        results["processes_8"] = processes_8
        print(f"✓ {processes_8:.2f}s")
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
    """Print comprehensive results table."""
    print("\n" + "="*70)
    print("THREAD vs PROCESS: BENCHMARK RESULTS")
    print("="*70)

    for project_key, results in all_results.items():
        if not results:
            continue

        project = PROJECTS[project_key]
        print(f"\n{project['name']} ({project['expected_files']} files)")
        print("-" * 70)

        baseline = results.get("baseline")
        threads_4 = results.get("threads_4")
        threads_8 = results.get("threads_8")
        processes_4 = results.get("processes_4")
        processes_8 = results.get("processes_8")

        if baseline:
            print(f"  Baseline (no parallel):        {baseline:6.2f}s")

        if threads_4:
            speedup = calculate_speedup(baseline, threads_4)
            print(f"  ThreadPool (4 workers):        {threads_4:6.2f}s  ({speedup})")

        if threads_8:
            speedup = calculate_speedup(baseline, threads_8)
            print(f"  ThreadPool (8 workers):        {threads_8:6.2f}s  ({speedup})")

        if processes_4:
            speedup = calculate_speedup(baseline, processes_4)
            improvement = ""
            if threads_4:
                vs_threads = threads_4 / processes_4
                improvement = f" [{vs_threads:.2f}x vs threads]"
            print(f"  ProcessPool (4 workers):       {processes_4:6.2f}s  ({speedup}){improvement}")

        if processes_8:
            speedup = calculate_speedup(baseline, processes_8)
            improvement = ""
            if threads_8:
                vs_threads = threads_8 / processes_8
                improvement = f" [{vs_threads:.2f}x vs threads]"
            print(f"  ProcessPool (8 workers):       {processes_8:6.2f}s  ({speedup}){improvement}")


def print_summary(all_results: Dict[str, Dict[str, Optional[float]]]):
    """Print summary and analysis."""
    print("\n" + "="*70)
    print("SUMMARY: ProcessPoolExecutor vs ThreadPoolExecutor")
    print("="*70)

    print("\n🔬 GIL Bypass Analysis:")
    print("ThreadPoolExecutor: Limited by Python's GIL (Global Interpreter Lock)")
    print("ProcessPoolExecutor: Bypasses GIL - each process has own interpreter")
    print()

    for project_key, results in all_results.items():
        project = PROJECTS[project_key]
        threads_4 = results.get("threads_4")
        processes_4 = results.get("processes_4")

        if threads_4 and processes_4:
            improvement = processes_4 / threads_4
            if improvement < 0.95:  # Processes slower
                status = f"⚠️ Slower ({improvement:.2f}x)"
                reason = "Process overhead > GIL benefit"
            elif improvement > 1.1:  # Processes significantly faster
                status = f"⚡ Much faster ({improvement:.2f}x)"
                reason = "GIL bypass enables true parallelism!"
            else:  # Marginal difference
                status = f"→ Similar ({improvement:.2f}x)"
                reason = "I/O-bound, GIL not limiting factor"

            print(f"{project['name']:15} Processes vs Threads: {status}")
            print(f"                Reason: {reason}")
            print()

    print("="*70)


def main():
    """Run Thread vs Process benchmarks."""
    print("="*70)
    print("THREAD vs PROCESS EXECUTOR BENCHMARK")
    print("="*70)
    print()
    print("Comparing ThreadPoolExecutor vs ProcessPoolExecutor")
    print("Testing GIL bypass benefit on real-world projects")
    print()

    all_results = {}

    # Run benchmarks (small to large)
    for project_key in ["pytest", "sqlalchemy", "django"]:
        try:
            results = benchmark_project(project_key)
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
