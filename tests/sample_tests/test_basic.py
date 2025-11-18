"""Sample test file for testing pytest-fastcollect."""


def test_simple_addition():
    """Test simple addition."""
    assert 1 + 1 == 2


def test_simple_subtraction():
    """Test simple subtraction."""
    assert 5 - 3 == 2


def test_simple_multiplication():
    """Test simple multiplication."""
    assert 3 * 4 == 12


def test_simple_division():
    """Test simple division."""
    assert 10 / 2 == 5


class TestMathOperations:
    """Test class for math operations."""

    def test_addition(self):
        """Test addition in class."""
        assert 10 + 5 == 15

    def test_subtraction(self):
        """Test subtraction in class."""
        assert 10 - 5 == 5

    def test_multiplication(self):
        """Test multiplication in class."""
        assert 10 * 5 == 50

    def test_division(self):
        """Test division in class."""
        assert 10 / 5 == 2


class TestStringOperations:
    """Test class for string operations."""

    def test_concatenation(self):
        """Test string concatenation."""
        assert "hello" + " " + "world" == "hello world"

    def test_upper(self):
        """Test string upper."""
        assert "hello".upper() == "HELLO"

    def test_lower(self):
        """Test string lower."""
        assert "HELLO".lower() == "hello"

    def test_split(self):
        """Test string split."""
        assert "a,b,c".split(",") == ["a", "b", "c"]
