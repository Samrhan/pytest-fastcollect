#!/usr/bin/env python3
"""Explore how to create pytest items programmatically."""

from pathlib import Path
from _pytest.python import Module, Function, Class
from _pytest.config import Config
from _pytest.main import Session
import pytest


def explore_item_creation():
    """Understand how pytest creates items."""

    # Create a minimal pytest config and session
    config = pytest.Config.fromdictargs({}, [])
    config._do_configure()
    session = Session(config)

    # Create a Module
    test_file = Path("tests/sample_tests/test_basic.py")
    module = Module.from_parent(session, path=test_file)

    print(f"Module: {module}")
    print(f"Module path: {module.path}")
    print(f"Module nodeid: {module.nodeid}")
    print()

    # Collect items from module
    items = list(module.collect())
    print(f"Collected {len(items)} items from module")

    for item in items[:3]:
        print(f"\nItem: {item}")
        print(f"  Type: {type(item).__name__}")
        print(f"  NodeID: {item.nodeid}")
        print(f"  Name: {item.name}")

        if isinstance(item, Function):
            print(f"  Function: {item.function}")
            print(f"  OriginalName: {item.originalname}")

    # Try to create a Function directly
    print("\n" + "="*60)
    print("Attempting direct Function creation...")

    # We need to get the actual function object from the module
    import importlib.util
    spec = importlib.util.spec_from_file_location("test_basic", test_file)
    test_module_obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(test_module_obj)

    # Get a test function
    test_func = getattr(test_module_obj, "test_simple_addition")
    print(f"\nTest function: {test_func}")

    # Create Function item
    func_item = Function.from_parent(
        module,
        name="test_simple_addition",
        callobj=test_func,
    )

    print(f"Created Function item: {func_item}")
    print(f"  NodeID: {func_item.nodeid}")
    print(f"  Can run: {hasattr(func_item, 'runtest')}")


if __name__ == "__main__":
    explore_item_creation()
