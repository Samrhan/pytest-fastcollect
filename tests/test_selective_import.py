"""Test file for selective import feature."""

import pytest


def test_basic_function():
    """A basic test with no markers."""
    assert True


@pytest.mark.slow
def test_slow_function():
    """A slow test."""
    assert True


@pytest.mark.smoke
def test_smoke_function():
    """A smoke test."""
    assert True


@pytest.mark.smoke
@pytest.mark.regression
def test_smoke_and_regression():
    """A test with multiple markers."""
    assert True


def test_user_login():
    """Test user login functionality."""
    assert True


def test_user_logout():
    """Test user logout functionality."""
    assert True


def test_admin_panel():
    """Test admin panel access."""
    assert True


@pytest.mark.slow
class TestSlowOperations:
    """Class with slow marker."""

    def test_slow_operation_1(self):
        assert True

    def test_slow_operation_2(self):
        assert True


class TestQuickOperations:
    """Class without markers."""

    def test_quick_1(self):
        assert True

    def test_quick_2(self):
        assert True
