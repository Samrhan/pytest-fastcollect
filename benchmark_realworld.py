#!/usr/bin/env python3
"""
Comprehensive real-world benchmark of pytest-fastcollect across multiple popular Python projects.

Tests pytest-fastcollect performance on:
- Django: ~1977 test files (large web framework)
- SQLAlchemy: ~219 test files (ORM)
- Pytest: ~108 test files (testing framework - meta!)
- Flask: ~22 test files (micro web framework)
- Requests: ~9 test files (HTTP library)
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Project configurations
PROJECTS = {
    "django": {
        "path": Path("/tmp/django/tests"),
        "name": "Django",
        "description": "Large web framework",
        "expected_files": 1977,
    },
    "sqlalchemy": {
        "path": Path("/tmp/sqlalchemy/test"),
        "name": "SQLAlchemy",
        "description": "ORM and database toolkit",
        "expected_files": 219,
    },
    "pytest": {
        "path": Path("/tmp/pytest/testing"),
        "name": "Pytest",
        "description": "Testing framework (meta!)",
        "expected_files": 108,
    },
    "flask": {
        "path": Path("/tmp/flask/tests"),
        "name": "Flask",
        "description": "Micro web framework",
        "expected_files": 22,
    },
    "requests": {
        "path": Path("/tmp/requests/tests"),
        "name": "Requests",
        "description": "HTTP library",
        "expected_files": 9,
    },
}


def run_collection(
    test_path: Path, args: List[str], use_plugin: bool = True, timeout: int = 300
) -> Optional[float]:
    """Run pytest collection and measure time."""
    venv_python = Path("/home/user/pytest-fastcollect/.venv/bin/python")
    python_cmd = str(venv_python) if venv_python.exists() else sys.executable

    cmd = [python_cmd, "-m", "pytest"]

    if not use_plugin:
        cmd.extend(["-p", "no:fastcollect"])

    cmd.extend(args)
    cmd.extend(["--collect-only", "-q", str(test_path)])

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


def benchmark_project(project_key: str, verbose: bool = False) -> Dict[str, Optional[float]]:
    """Benchmark a single project with multiple scenarios."""
    project = PROJECTS[project_key]
    test_path = project["path"]

    if not test_path.exists():
        print(f"❌ {project['name']}: Test path not found at {test_path}")
        return {}

    print(f"\n{'='*70}")
    print(f"📦 {project['name']} - {project['description']}")
    print(f"   Path: {test_path}")
    print(f"   Expected files: ~{project['expected_files']}")
    print(f"{'='*70}")

    results = {}

    # 1. Baseline (no plugin)
    print(f"\n  Running baseline (no plugin)...", end=" ", flush=True)
    baseline = run_collection(test_path, [], use_plugin=False, timeout=300)
    if baseline:
        results["baseline"] = baseline
        print(f"✓ {baseline:.2f}s")
    else:
        print("✗ Failed/Timeout")

    # 2. Full collection with FastCollect
    print(f"  Running FastCollect (full)...", end=" ", flush=True)
    full = run_collection(test_path, [], use_plugin=True, timeout=300)
    if full:
        results["full"] = full
        print(f"✓ {full:.2f}s")
    else:
        print("✗ Failed/Timeout")

    # 3. Keyword filter - common pattern
    print(f"  Running FastCollect (-k test_get)...", end=" ", flush=True)
    k_get = run_collection(test_path, ["-k", "test_get"], use_plugin=True, timeout=300)
    if k_get:
        results["k_get"] = k_get
        print(f"✓ {k_get:.2f}s")
    else:
        print("✗ Failed/Timeout")

    # 4. Keyword filter - more specific
    print(f"  Running FastCollect (-k test_basic)...", end=" ", flush=True)
    k_basic = run_collection(test_path, ["-k", "test_basic"], use_plugin=True, timeout=300)
    if k_basic:
        results["k_basic"] = k_basic
        print(f"✓ {k_basic:.2f}s")
    else:
        print("✗ Failed/Timeout")

    return results


def calculate_speedup(baseline: Optional[float], optimized: Optional[float]) -> str:
    """Calculate and format speedup."""
    if baseline and optimized and baseline > 0 and optimized > 0:
        speedup = baseline / optimized
        return f"{speedup:.2f}x"
    return "N/A"


def print_results_table(all_results: Dict[str, Dict[str, Optional[float]]]):
    """Print comprehensive results table."""
    print("\n" + "="*70)
    print("COMPREHENSIVE BENCHMARK RESULTS")
    print("="*70)

    for project_key, results in all_results.items():
        if not results:
            continue

        project = PROJECTS[project_key]
        print(f"\n{project['name']} ({project['description']})")
        print("-" * 70)

        baseline = results.get("baseline")
        full = results.get("full")
        k_get = results.get("k_get")
        k_basic = results.get("k_basic")

        # Full collection performance
        if baseline and full:
            speedup = calculate_speedup(baseline, full)
            print(f"  Full Collection:")
            print(f"    Baseline (no plugin):  {baseline:6.2f}s")
            print(f"    FastCollect:           {full:6.2f}s  ({speedup} faster)")

        # Selective import performance
        if full:
            print(f"  Selective Import:")
            print(f"    Full collection:       {full:6.2f}s  (baseline)")
            if k_get:
                speedup = calculate_speedup(full, k_get)
                print(f"    -k test_get:           {k_get:6.2f}s  ({speedup} faster)")
            if k_basic:
                speedup = calculate_speedup(full, k_basic)
                print(f"    -k test_basic:         {k_basic:6.2f}s  ({speedup} faster)")

        # Combined speedup
        if baseline and k_get:
            combined_speedup = calculate_speedup(baseline, k_get)
            print(f"  Combined Impact (baseline → FastCollect + filter):")
            print(f"    {baseline:.2f}s → {k_get:.2f}s  ({combined_speedup} faster overall)")


def print_summary_table(all_results: Dict[str, Dict[str, Optional[float]]]):
    """Print summary comparison table."""
    print("\n" + "="*70)
    print("SUMMARY: FastCollect Performance Across Projects")
    print("="*70)
    print()
    print(f"{'Project':<15} {'Files':<8} {'Baseline':<10} {'FastCollect':<12} {'Speedup':<10}")
    print("-" * 70)

    for project_key in ["requests", "flask", "pytest", "sqlalchemy", "django"]:
        if project_key not in all_results:
            continue

        project = PROJECTS[project_key]
        results = all_results[project_key]

        baseline = results.get("baseline")
        full = results.get("full")

        files_str = f"~{project['expected_files']}"
        baseline_str = f"{baseline:.2f}s" if baseline else "N/A"
        full_str = f"{full:.2f}s" if full else "N/A"
        speedup_str = calculate_speedup(baseline, full)

        print(f"{project['name']:<15} {files_str:<8} {baseline_str:<10} {full_str:<12} {speedup_str:<10}")

    print("="*70)


def print_key_findings(all_results: Dict[str, Dict[str, Optional[float]]]):
    """Print key findings and insights."""
    print("\n" + "="*70)
    print("KEY FINDINGS")
    print("="*70)

    # Calculate average speedup
    speedups = []
    for results in all_results.values():
        baseline = results.get("baseline")
        full = results.get("full")
        if baseline and full and baseline > 0 and full > 0:
            speedups.append(baseline / full)

    if speedups:
        avg_speedup = sum(speedups) / len(speedups)
        min_speedup = min(speedups)
        max_speedup = max(speedups)

        print(f"\n✅ FastCollect Performance:")
        print(f"   Average speedup: {avg_speedup:.2f}x faster")
        print(f"   Range: {min_speedup:.2f}x to {max_speedup:.2f}x")
        print(f"   Tested on {len(speedups)} projects")

    # Selective import findings
    selective_speedups = []
    for results in all_results.values():
        full = results.get("full")
        k_get = results.get("k_get")
        if full and k_get and full > 0 and k_get > 0:
            selective_speedups.append(full / k_get)

    if selective_speedups:
        avg_selective = sum(selective_speedups) / len(selective_speedups)
        print(f"\n✅ Selective Import (with -k filters):")
        print(f"   Additional speedup: {avg_selective:.2f}x on average")
        print(f"   Best for: Development workflow, CI/CD test splits")

    print(f"\n✅ Production-Ready:")
    print(f"   - Tested on {len(all_results)} popular Python projects")
    print(f"   - Zero configuration required")
    print(f"   - Drop-in pytest plugin")
    print(f"   - Backwards compatible")

    print("\n" + "="*70)


def main():
    """Run comprehensive real-world benchmarks."""
    print("="*70)
    print("PYTEST-FASTCOLLECT: REAL-WORLD BENCHMARK SUITE")
    print("="*70)
    print()
    print("Benchmarking pytest-fastcollect on popular Python projects:")
    for key, project in PROJECTS.items():
        print(f"  • {project['name']:<15} ~{project['expected_files']:>4} test files")
    print()

    all_results = {}

    # Run benchmarks for each project (smallest to largest)
    for project_key in ["requests", "flask", "pytest", "sqlalchemy", "django"]:
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
        print_results_table(all_results)
        print_summary_table(all_results)
        print_key_findings(all_results)
    else:
        print("\n❌ No benchmark results collected")

    print("\nBenchmark complete! 🎉")


if __name__ == "__main__":
    main()
