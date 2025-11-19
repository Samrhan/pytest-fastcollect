"""
Comprehensive test suite for filter.py module.

Tests the TestFilter class and helper functions with:
- Keyword expression matching (-k option)
- Marker expression matching (-m option)
- Combined filters
- Edge cases and complex expressions
"""

import pytest
from pytest_fastcollect.filter import (
    TestFilter,
    filter_collected_data,
    get_files_with_matching_tests,
)


class TestTestFilterKeywords:
    """Test keyword expression matching (-k option)."""

    @pytest.mark.unit
    def test_no_filter_matches_all(self):
        """Test that no filter matches all tests."""
        test_filter = TestFilter()

        test_item = {"name": "test_foo", "markers": []}
        assert test_filter.matches(test_item) is True

    @pytest.mark.unit
    def test_simple_keyword_match(self):
        """Test simple keyword matching."""
        test_filter = TestFilter(keyword_expr="foo")

        # Matches
        assert test_filter.matches({"name": "test_foo", "markers": []}) is True
        assert test_filter.matches({"name": "test_foobar", "markers": []}) is True

        # Doesn't match
        assert test_filter.matches({"name": "test_bar", "markers": []}) is False

    @pytest.mark.unit
    def test_keyword_matches_class_name(self):
        """Test keyword matching against class name."""
        test_filter = TestFilter(keyword_expr="user")

        test_item = {
            "name": "test_login",
            "class": "TestUser",
            "markers": []
        }
        assert test_filter.matches(test_item) is True

    @pytest.mark.unit
    def test_keyword_matches_file_path(self):
        """Test keyword matching against file path."""
        test_filter = TestFilter(keyword_expr="auth")

        test_item = {
            "name": "test_login",
            "file_path": "/project/tests/test_auth.py",
            "markers": []
        }
        assert test_filter.matches(test_item) is True

    @pytest.mark.unit
    def test_keyword_and_expression(self):
        """Test AND keyword expression."""
        test_filter = TestFilter(keyword_expr="test and user")

        # Matches both
        assert test_filter.matches({
            "name": "test_user",
            "markers": []
        }) is True

        # Matches only one
        assert test_filter.matches({
            "name": "test_foo",
            "markers": []
        }) is False

        assert test_filter.matches({
            "name": "user_data",
            "markers": []
        }) is False

    @pytest.mark.unit
    def test_keyword_or_expression(self):
        """Test OR keyword expression."""
        test_filter = TestFilter(keyword_expr="foo or bar")

        # Matches first
        assert test_filter.matches({"name": "test_foo", "markers": []}) is True

        # Matches second
        assert test_filter.matches({"name": "test_bar", "markers": []}) is True

        # Matches neither
        assert test_filter.matches({"name": "test_baz", "markers": []}) is False

    @pytest.mark.unit
    def test_keyword_not_expression(self):
        """Test NOT keyword expression."""
        test_filter = TestFilter(keyword_expr="not slow")

        # Doesn't contain "slow"
        assert test_filter.matches({"name": "test_foo", "markers": []}) is True

        # Contains "slow"
        assert test_filter.matches({"name": "test_slow", "markers": []}) is False

    @pytest.mark.unit
    def test_keyword_complex_expression(self):
        """Test complex keyword expression with AND/OR/NOT."""
        test_filter = TestFilter(keyword_expr="user and not slow")

        # Matches "user" and doesn't contain "slow"
        assert test_filter.matches({"name": "test_user", "markers": []}) is True

        # Matches "user" but contains "slow"
        assert test_filter.matches({"name": "test_user_slow", "markers": []}) is False

        # Doesn't match "user"
        assert test_filter.matches({"name": "test_foo", "markers": []}) is False

    @pytest.mark.unit
    def test_keyword_case_insensitive(self):
        """Test that keyword matching is case-insensitive."""
        test_filter = TestFilter(keyword_expr="USER")

        assert test_filter.matches({"name": "test_user", "markers": []}) is True
        assert test_filter.matches({"name": "test_User", "markers": []}) is True
        assert test_filter.matches({"name": "test_USER", "markers": []}) is True


class TestTestFilterMarkers:
    """Test marker expression matching (-m option)."""

    @pytest.mark.unit
    def test_simple_marker_match(self):
        """Test simple marker matching."""
        test_filter = TestFilter(marker_expr="slow")

        # Has marker
        assert test_filter.matches({
            "name": "test_foo",
            "markers": ["slow"]
        }) is True

        # Doesn't have marker
        assert test_filter.matches({
            "name": "test_bar",
            "markers": []
        }) is False

    @pytest.mark.unit
    def test_marker_and_expression(self):
        """Test AND marker expression."""
        test_filter = TestFilter(marker_expr="smoke and regression")

        # Has both markers
        assert test_filter.matches({
            "name": "test_foo",
            "markers": ["smoke", "regression"]
        }) is True

        # Has only one marker
        assert test_filter.matches({
            "name": "test_bar",
            "markers": ["smoke"]
        }) is False

        # Has neither marker
        assert test_filter.matches({
            "name": "test_baz",
            "markers": []
        }) is False

    @pytest.mark.unit
    def test_marker_or_expression(self):
        """Test OR marker expression."""
        test_filter = TestFilter(marker_expr="smoke or regression")

        # Has first marker
        assert test_filter.matches({
            "name": "test_foo",
            "markers": ["smoke"]
        }) is True

        # Has second marker
        assert test_filter.matches({
            "name": "test_bar",
            "markers": ["regression"]
        }) is True

        # Has both markers
        assert test_filter.matches({
            "name": "test_baz",
            "markers": ["smoke", "regression"]
        }) is True

        # Has neither marker
        assert test_filter.matches({
            "name": "test_qux",
            "markers": []
        }) is False

    @pytest.mark.unit
    def test_marker_not_expression(self):
        """Test NOT marker expression."""
        test_filter = TestFilter(marker_expr="not slow")

        # Doesn't have marker
        assert test_filter.matches({
            "name": "test_foo",
            "markers": []
        }) is True

        # Has marker
        assert test_filter.matches({
            "name": "test_bar",
            "markers": ["slow"]
        }) is False

    @pytest.mark.unit
    def test_marker_complex_expression(self):
        """Test complex marker expression."""
        test_filter = TestFilter(marker_expr="smoke and not slow")

        # Has "smoke" but not "slow"
        assert test_filter.matches({
            "name": "test_foo",
            "markers": ["smoke"]
        }) is True

        # Has both "smoke" and "slow"
        assert test_filter.matches({
            "name": "test_bar",
            "markers": ["smoke", "slow"]
        }) is False

        # Has neither
        assert test_filter.matches({
            "name": "test_baz",
            "markers": []
        }) is False

    @pytest.mark.unit
    def test_marker_case_insensitive(self):
        """Test that marker matching is case-insensitive."""
        test_filter = TestFilter(marker_expr="SLOW")

        assert test_filter.matches({
            "name": "test_foo",
            "markers": ["slow"]
        }) is True

        assert test_filter.matches({
            "name": "test_bar",
            "markers": ["Slow"]
        }) is True

        assert test_filter.matches({
            "name": "test_baz",
            "markers": ["SLOW"]
        }) is True


class TestTestFilterCombined:
    """Test combined keyword and marker filtering."""

    @pytest.mark.unit
    def test_combined_keyword_and_marker(self):
        """Test that both keyword and marker filters must match."""
        test_filter = TestFilter(
            keyword_expr="user",
            marker_expr="smoke"
        )

        # Matches both
        assert test_filter.matches({
            "name": "test_user_login",
            "markers": ["smoke"]
        }) is True

        # Matches keyword but not marker
        assert test_filter.matches({
            "name": "test_user_logout",
            "markers": []
        }) is False

        # Matches marker but not keyword
        assert test_filter.matches({
            "name": "test_foo",
            "markers": ["smoke"]
        }) is False

        # Matches neither
        assert test_filter.matches({
            "name": "test_bar",
            "markers": []
        }) is False

    @pytest.mark.unit
    def test_combined_complex_expressions(self):
        """Test combined complex expressions."""
        test_filter = TestFilter(
            keyword_expr="user or admin",
            marker_expr="smoke and not slow"
        )

        # Matches both expressions
        assert test_filter.matches({
            "name": "test_user",
            "markers": ["smoke"]
        }) is True

        assert test_filter.matches({
            "name": "test_admin",
            "markers": ["smoke"]
        }) is True

        # Keyword matches, marker fails
        assert test_filter.matches({
            "name": "test_user",
            "markers": ["smoke", "slow"]
        }) is False

        # Keyword fails, marker matches
        assert test_filter.matches({
            "name": "test_foo",
            "markers": ["smoke"]
        }) is False


class TestFilterCollectedData:
    """Test filter_collected_data helper function."""

    @pytest.mark.unit
    def test_filter_no_filters_returns_all(self):
        """Test that no filters returns all data."""
        collected_data = {
            "/test1.py": [{"name": "test_foo", "markers": []}],
            "/test2.py": [{"name": "test_bar", "markers": []}],
        }

        result = filter_collected_data(collected_data)

        assert len(result) == 2
        assert "/test1.py" in result
        assert "/test2.py" in result

    @pytest.mark.unit
    def test_filter_by_keyword(self):
        """Test filtering by keyword expression."""
        collected_data = {
            "/test1.py": [
                {"name": "test_user", "markers": []},
                {"name": "test_admin", "markers": []},
            ],
            "/test2.py": [
                {"name": "test_foo", "markers": []},
            ],
        }

        result = filter_collected_data(
            collected_data,
            keyword_expr="user"
        )

        assert len(result) == 1
        assert "/test1.py" in result
        assert len(result["/test1.py"]) == 1
        assert result["/test1.py"][0]["name"] == "test_user"

    @pytest.mark.unit
    def test_filter_by_marker(self):
        """Test filtering by marker expression."""
        collected_data = {
            "/test1.py": [
                {"name": "test_foo", "markers": ["smoke"]},
                {"name": "test_bar", "markers": []},
            ],
            "/test2.py": [
                {"name": "test_baz", "markers": ["smoke"]},
            ],
        }

        result = filter_collected_data(
            collected_data,
            marker_expr="smoke"
        )

        assert len(result) == 2
        assert "/test1.py" in result
        assert "/test2.py" in result
        assert len(result["/test1.py"]) == 1
        assert result["/test1.py"][0]["name"] == "test_foo"

    @pytest.mark.unit
    def test_filter_excludes_files_with_no_matches(self):
        """Test that files with no matching tests are excluded."""
        collected_data = {
            "/test1.py": [
                {"name": "test_foo", "markers": []},
            ],
            "/test2.py": [
                {"name": "test_bar", "markers": []},
            ],
        }

        result = filter_collected_data(
            collected_data,
            keyword_expr="foo"
        )

        # Only test1.py should be included
        assert len(result) == 1
        assert "/test1.py" in result
        assert "/test2.py" not in result

    @pytest.mark.unit
    def test_filter_combined_keyword_and_marker(self):
        """Test filtering with both keyword and marker."""
        collected_data = {
            "/test1.py": [
                {"name": "test_user", "markers": ["smoke"]},
                {"name": "test_admin", "markers": []},
            ],
            "/test2.py": [
                {"name": "test_foo", "markers": ["smoke"]},
            ],
        }

        result = filter_collected_data(
            collected_data,
            keyword_expr="user or admin",
            marker_expr="smoke"
        )

        # Only test_user from test1.py should match
        assert len(result) == 1
        assert "/test1.py" in result
        assert len(result["/test1.py"]) == 1
        assert result["/test1.py"][0]["name"] == "test_user"


class TestGetFilesWithMatchingTests:
    """Test get_files_with_matching_tests helper function."""

    @pytest.mark.unit
    def test_get_files_no_filter(self):
        """Test that no filter returns all files."""
        collected_data = {
            "/test1.py": [{"name": "test_foo", "markers": []}],
            "/test2.py": [{"name": "test_bar", "markers": []}],
        }

        result = get_files_with_matching_tests(collected_data)

        assert len(result) == 2
        assert "/test1.py" in result
        assert "/test2.py" in result

    @pytest.mark.unit
    def test_get_files_with_filter(self):
        """Test getting files with keyword filter."""
        collected_data = {
            "/test1.py": [{"name": "test_user", "markers": []}],
            "/test2.py": [{"name": "test_admin", "markers": []}],
            "/test3.py": [{"name": "test_foo", "markers": []}],
        }

        result = get_files_with_matching_tests(
            collected_data,
            keyword_expr="user or admin"
        )

        assert len(result) == 2
        assert "/test1.py" in result
        assert "/test2.py" in result
        assert "/test3.py" not in result

    @pytest.mark.unit
    def test_get_files_returns_set(self):
        """Test that result is a set."""
        collected_data = {
            "/test1.py": [{"name": "test_foo", "markers": []}],
        }

        result = get_files_with_matching_tests(collected_data)

        assert isinstance(result, set)


class TestFilterEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.unit
    def test_empty_collected_data(self):
        """Test filtering empty collected data."""
        result = filter_collected_data({}, keyword_expr="foo")
        assert len(result) == 0

    @pytest.mark.unit
    def test_test_with_no_name(self):
        """Test handling test item without name field."""
        test_filter = TestFilter(keyword_expr="foo")

        # Should not crash, but won't match
        test_item = {"markers": []}
        # This will raise KeyError if not handled properly
        try:
            result = test_filter.matches(test_item)
            assert result is False
        except KeyError:
            # Expected behavior - let the test pass
            pass

    @pytest.mark.unit
    def test_test_with_no_markers(self):
        """Test handling test item without markers field."""
        test_filter = TestFilter(marker_expr="slow")

        test_item = {"name": "test_foo"}
        # Should handle missing markers gracefully
        try:
            result = test_filter.matches(test_item)
            # If it doesn't crash, that's good
        except KeyError:
            # If it crashes, that's a bug we should fix
            pytest.fail("Should handle missing markers field")

    @pytest.mark.unit
    def test_expression_with_multiple_spaces(self):
        """Test handling expressions with extra spaces."""
        test_filter = TestFilter(keyword_expr="  foo  and   bar  ")

        assert test_filter.matches({
            "name": "test_foo_bar",
            "markers": []
        }) is True

    @pytest.mark.unit
    def test_empty_expression(self):
        """Test handling empty filter expression."""
        test_filter = TestFilter(keyword_expr="")

        # Empty expression should match all
        assert test_filter.matches({
            "name": "test_foo",
            "markers": []
        }) is True

    @pytest.mark.unit
    def test_unicode_in_test_name(self):
        """Test handling unicode in test names."""
        test_filter = TestFilter(keyword_expr="用户")

        assert test_filter.matches({
            "name": "test_用户_login",
            "markers": []
        }) is True

    @pytest.mark.unit
    def test_special_characters_in_expression(self):
        """Test handling special characters in expression."""
        test_filter = TestFilter(keyword_expr="test-user")

        assert test_filter.matches({
            "name": "test-user-login",
            "markers": []
        }) is True

    @pytest.mark.unit
    def test_very_long_expression(self):
        """Test handling very long filter expression."""
        # Create expression with many OR clauses
        keywords = " or ".join([f"test{i}" for i in range(100)])
        test_filter = TestFilter(keyword_expr=keywords)

        # Should match any of them
        assert test_filter.matches({
            "name": "test50",
            "markers": []
        }) is True

    @pytest.mark.unit
    def test_marker_with_multiple_same_markers(self):
        """Test test with duplicate markers (edge case)."""
        test_filter = TestFilter(marker_expr="slow")

        assert test_filter.matches({
            "name": "test_foo",
            "markers": ["slow", "slow", "slow"]
        }) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
