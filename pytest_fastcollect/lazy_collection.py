"""
Lazy Collection - Custom Pytest Nodes that defer Python imports until test execution.

This is the GAME CHANGER: Instead of importing modules during collection,
we create "virtual" nodes from Rust AST data and only import when tests actually run.

This bypasses pytest's slowest bottlenecks:
- Python module importing (slow)
- Python reflection/introspection (slow)
- Decorator evaluation (slow)
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import sys
import importlib.util

import pytest
from _pytest.python import Module, Function, Class
from _pytest.config import Config


class FastModule(Module):
    """
    Custom Module node that skips Python imports during collection.

    Instead of importing the module and using Python reflection to find tests,
    it trusts the Rust AST parser to tell it what tests exist.

    The actual module import only happens when a test is about to run!
    """

    def __init__(self, *args, rust_metadata: Optional[Dict] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rust_metadata = rust_metadata or {}
        self._module_imported = False
        self._real_obj = None

    @property
    def obj(self):
        """
        Lazy property that imports the module only when accessed.

        This is called by pytest during test SETUP (not collection),
        so we defer all the expensive import work until then.
        """
        if not self._module_imported:
            self._import_module()
            self._module_imported = True
        return self._real_obj

    def _import_module(self):
        """Actually import the Python module (deferred until needed)."""
        try:
            # Convert file path to module name
            path_obj = Path(self.path)

            # Try to get module name from pytest's import system
            # This respects pytest's import mode settings
            module_name = self.module.__name__ if hasattr(self, 'module') and self.module else None

            if not module_name:
                # Fallback: construct module name from path
                try:
                    root_obj = Path(self.config.rootpath)
                    rel_path = path_obj.relative_to(root_obj)
                    module_name = str(rel_path.with_suffix('')).replace('/', '.')
                except ValueError:
                    module_name = path_obj.stem

            # Check if already imported
            if module_name in sys.modules:
                self._real_obj = sys.modules[module_name]
                return

            # Import the module using importlib
            spec = importlib.util.spec_from_file_location(module_name, self.path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                self._real_obj = module
            else:
                # Fallback to standard import
                self._real_obj = super().obj
        except Exception:
            # If custom import fails, fall back to pytest's standard import
            self._real_obj = super().obj

    def collect(self):
        """
        The Magic: Generate test nodes from Rust AST data WITHOUT importing the module!

        Standard pytest Module.collect() imports the file here. We DO NOT.
        Instead, we trust the Rust parser's metadata.
        """
        items_data = self.rust_metadata.get('items', [])

        # Group items by type
        classes = {}
        functions = []

        for item in items_data:
            name = item['name']
            item_type = item['type']

            if item_type == 'Function':
                # Standalone test function
                functions.append(item)
            elif item_type == 'Class':
                # Test class (will contain methods)
                classes[name] = {
                    'item': item,
                    'methods': []
                }
            elif item_type == 'Method':
                # Test method (belongs to a class)
                class_name = item.get('class')
                if class_name and class_name in classes:
                    classes[class_name]['methods'].append(item)

        # Generate class nodes
        for class_name, class_data in classes.items():
            yield FastClass.from_parent(
                self,
                name=class_name,
                rust_item=class_data['item'],
                rust_methods=class_data['methods']
            )

        # Generate function nodes
        for func_item in functions:
            # Don't try to expand parametrized tests ourselves - let pytest handle it
            # Just create the base node and pytest will expand it during setup
            yield FastFunction.from_parent(
                self,
                name=func_item['name'],
                rust_item=func_item
            )


class FastClass(Class):
    """
    Custom Class node that defers import and generates method nodes from Rust metadata.
    """

    def __init__(self, *args, rust_item: Optional[Dict] = None,
                 rust_methods: Optional[List[Dict]] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rust_item = rust_item or {}
        self.rust_methods = rust_methods or []

        # Apply markers from Rust metadata immediately
        # This allows -m filtering to work without importing!
        for marker_name in self.rust_item.get('markers', []):
            self.add_marker(marker_name)

    @property
    def obj(self):
        """
        Lazy property that only accesses the class when needed.
        Triggers parent module import.
        """
        parent_module = self.getparent(FastModule)
        if parent_module:
            module_obj = parent_module.obj  # This triggers import
            return getattr(module_obj, self.name, None)
        return super().obj

    def collect(self):
        """
        Generate method nodes from Rust metadata WITHOUT importing.
        """
        for method_item in self.rust_methods:
            # Don't try to expand parametrized tests - let pytest handle it
            yield FastFunction.from_parent(
                self,
                name=method_item['name'],
                rust_item=method_item
            )


class FastFunction(Function):
    """
    Custom Function node that defers import until test execution.

    This is the leaf node that represents an actual test.
    All metadata (markers, line numbers, etc.) comes from Rust AST parsing.
    """

    def __init__(self, *args, rust_item: Optional[Dict] = None,
                 callspec_index: Optional[int] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rust_item = rust_item or {}
        self.callspec_index = callspec_index

        # Apply markers from Rust metadata immediately
        # This allows -m filtering to work without importing!
        for marker_name in self.rust_item.get('markers', []):
            self.add_marker(marker_name)

    @property
    def obj(self):
        """
        Lazy property that only accesses the function when needed.
        Triggers parent module/class import.
        """
        # Find parent (either Module or Class)
        parent = self.getparent(FastClass)
        if parent:
            # Method in a class
            class_obj = parent.obj
            if class_obj:
                return getattr(class_obj, self.name, None)
        else:
            # Standalone function
            parent = self.getparent(FastModule)
            if parent:
                module_obj = parent.obj  # This triggers import
                return getattr(module_obj, self.name, None)

        return super().obj

    def setup(self):
        """
        ONLY import the module when the test is actually about to run.

        This is where the magic happens: collection is complete and we're about
        to execute the test, so NOW we import the module.
        """
        # Access obj property triggers import
        _ = self.obj

        # Call parent setup (this will resolve fixtures, etc.)
        super().setup()
