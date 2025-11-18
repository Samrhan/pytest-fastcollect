"""Advanced sample tests."""
import pytest


def test_list_operations():
    """Test list operations."""
    data = [1, 2, 3, 4, 5]
    assert len(data) == 5
    assert sum(data) == 15
    assert max(data) == 5
    assert min(data) == 1


def test_dict_operations():
    """Test dictionary operations."""
    data = {"a": 1, "b": 2, "c": 3}
    assert len(data) == 3
    assert data["a"] == 1
    assert "b" in data


@pytest.mark.parametrize("input,expected", [
    (1, 2),
    (2, 4),
    (3, 6),
    (4, 8),
])
def test_double(input, expected):
    """Test doubling numbers."""
    assert input * 2 == expected


class TestDataStructures:
    """Test various data structures."""

    def test_list_append(self):
        """Test list append."""
        data = []
        data.append(1)
        data.append(2)
        assert data == [1, 2]

    def test_dict_update(self):
        """Test dict update."""
        data = {"a": 1}
        data["b"] = 2
        assert data == {"a": 1, "b": 2}

    def test_set_operations(self):
        """Test set operations."""
        set1 = {1, 2, 3}
        set2 = {3, 4, 5}
        assert set1 & set2 == {3}
        assert set1 | set2 == {1, 2, 3, 4, 5}
