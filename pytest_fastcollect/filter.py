"""Test filtering logic for selective import optimization."""

import re
from typing import Dict, List, Set, Any


class TestFilter:
    """Filter tests based on pytest's -k and -m options."""

    def __init__(self, keyword_expr: str = None, marker_expr: str = None):
        """Initialize filter with keyword and marker expressions.

        Args:
            keyword_expr: The -k expression (e.g., "test_foo and not slow")
            marker_expr: The -m expression (e.g., "smoke and not slow")
        """
        self.keyword_expr = keyword_expr
        self.marker_expr = marker_expr

    def matches(self, test_item: Dict[str, Any]) -> bool:
        """Check if a test item matches the filter criteria.

        Args:
            test_item: Test item dict with keys: name, markers, class, etc.

        Returns:
            True if the test matches the filter
        """
        # If no filters, everything matches
        if not self.keyword_expr and not self.marker_expr:
            return True

        # Check keyword filter
        if self.keyword_expr:
            if not self._matches_keyword(test_item):
                return False

        # Check marker filter
        if self.marker_expr:
            if not self._matches_marker(test_item):
                return False

        return True

    def _matches_keyword(self, test_item: Dict[str, Any]) -> bool:
        """Check if test matches keyword expression (-k).

        The keyword expression can match against:
        - Test function name
        - Test class name
        - Test file path

        Supports: 'and', 'or', 'not', and parentheses.
        """
        # Build a searchable string from the test item
        parts = [test_item['name']]

        if 'class' in test_item:
            parts.append(test_item['class'])

        # Add file path components
        file_path = test_item.get('file_path', '')
        if file_path:
            # Extract file name without extension
            import os
            filename = os.path.splitext(os.path.basename(file_path))[0]
            parts.append(filename)

        search_text = ' '.join(parts).lower()

        # Evaluate the keyword expression
        return self._evaluate_expression(self.keyword_expr, search_text)

    def _matches_marker(self, test_item: Dict[str, Any]) -> bool:
        """Check if test matches marker expression (-m).

        Supports: 'and', 'or', 'not', and parentheses.
        """
        markers = test_item.get('markers', [])
        marker_set = set(m.lower() for m in markers)

        # Evaluate the marker expression
        return self._evaluate_marker_expression(self.marker_expr, marker_set)

    def _evaluate_expression(self, expr: str, search_text: str) -> bool:
        """Evaluate a keyword expression against search text.

        Simple implementation that handles common cases:
        - Single keywords: "test_foo"
        - AND: "test_foo and test_bar"
        - OR: "test_foo or test_bar"
        - NOT: "not slow"
        - Combinations: "test_foo and not slow"
        """
        expr = expr.lower().strip()

        # Handle simple case: single keyword
        if ' and ' not in expr and ' or ' not in expr and not expr.startswith('not '):
            return expr in search_text

        # Handle NOT
        if expr.startswith('not '):
            keyword = expr[4:].strip()
            return keyword not in search_text

        # Handle AND
        if ' and ' in expr:
            parts = expr.split(' and ')
            return all(self._evaluate_expression(p.strip(), search_text) for p in parts)

        # Handle OR
        if ' or ' in expr:
            parts = expr.split(' or ')
            return any(self._evaluate_expression(p.strip(), search_text) for p in parts)

        return expr in search_text

    def _evaluate_marker_expression(self, expr: str, markers: Set[str]) -> bool:
        """Evaluate a marker expression against a set of markers.

        Args:
            expr: Marker expression like "smoke and not slow"
            markers: Set of marker names on this test

        Returns:
            True if the expression matches
        """
        expr = expr.lower().strip()

        # Handle simple case: single marker
        if ' and ' not in expr and ' or ' not in expr and not expr.startswith('not '):
            return expr in markers

        # Handle NOT
        if expr.startswith('not '):
            marker = expr[4:].strip()
            return marker not in markers

        # Handle AND
        if ' and ' in expr:
            parts = expr.split(' and ')
            return all(self._evaluate_marker_expression(p.strip(), markers) for p in parts)

        # Handle OR
        if ' or ' in expr:
            parts = expr.split(' or ')
            return any(self._evaluate_marker_expression(p.strip(), markers) for p in parts)

        return expr in markers


def filter_collected_data(
    collected_data: Dict[str, List[Dict[str, Any]]],
    keyword_expr: str = None,
    marker_expr: str = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Filter collected test data based on keyword and marker expressions.

    Args:
        collected_data: Dict mapping file paths to lists of test items
        keyword_expr: Optional -k expression
        marker_expr: Optional -m expression

    Returns:
        Filtered dict with only matching tests and their files
    """
    # If no filters, return everything
    if not keyword_expr and not marker_expr:
        return collected_data

    test_filter = TestFilter(keyword_expr, marker_expr)
    filtered_data = {}

    for file_path, test_items in collected_data.items():
        # Filter test items in this file
        matching_items = [item for item in test_items if test_filter.matches(item)]

        # Only include file if it has matching tests
        if matching_items:
            filtered_data[file_path] = matching_items

    return filtered_data


def get_files_with_matching_tests(
    collected_data: Dict[str, List[Dict[str, Any]]],
    keyword_expr: str = None,
    marker_expr: str = None
) -> Set[str]:
    """Get the set of file paths that contain matching tests.

    This is used to populate _test_files_cache with only files
    that have tests matching the filter criteria.

    Args:
        collected_data: Dict mapping file paths to lists of test items
        keyword_expr: Optional -k expression
        marker_expr: Optional -m expression

    Returns:
        Set of file paths containing matching tests
    """
    filtered_data = filter_collected_data(collected_data, keyword_expr, marker_expr)
    return set(filtered_data.keys())
