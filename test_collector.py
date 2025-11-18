#!/usr/bin/env python3
"""Test the Rust collector directly."""

from pytest_fastcollect import FastCollector
from pprint import pprint

# Test the collector
collector = FastCollector("tests/sample_tests")
results = collector.collect()

print("Collected tests:")
pprint(results)

print(f"\nTotal files: {len(results)}")
total_tests = sum(len(tests) for tests in results.values())
print(f"Total test items: {total_tests}")
