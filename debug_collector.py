#!/usr/bin/env python3
"""Debug the collector."""

import os
from pathlib import Path
from pytest_fastcollect import FastCollector

# Check current directory
print(f"Current directory: {os.getcwd()}")

# Check if test directory exists
test_dir = Path("tests/sample_tests")
print(f"Test directory exists: {test_dir.exists()}")

if test_dir.exists():
    print(f"Test directory absolute: {test_dir.absolute()}")
    files = list(test_dir.glob("*.py"))
    print(f"Python files in test directory: {files}")

# Try with absolute path
abs_path = test_dir.absolute()
print(f"\nTrying with absolute path: {abs_path}")
collector = FastCollector(str(abs_path))
results = collector.collect()
print(f"Results: {results}")

# Try with current directory
print(f"\nTrying with current directory: .")
collector2 = FastCollector(".")
results2 = collector2.collect()
print(f"Results: {results2}")
