import pytest
from normalizers.base import CodeNormalizer


def test_abstract_base_class():
    """Test that CodeNormalizer is an abstract base class that can't be instantiated directly."""
    with pytest.raises(TypeError):
        CodeNormalizer()


def test_subclass_must_implement_normalize():
    """Test that subclasses must implement the normalize method."""
    class InvalidNormalizer(CodeNormalizer):
        pass
    
    with pytest.raises(TypeError):
        InvalidNormalizer()


def test_valid_subclass_can_be_instantiated():
    """Test that a valid subclass with normalize method can be instantiated."""
    class ValidNormalizer(CodeNormalizer):
        def normalize(self, text):
            return text
    
    # This should not raise an exception
    normalizer = ValidNormalizer()
    assert isinstance(normalizer, CodeNormalizer)
    
    # The normalize method should be callable
    assert normalizer.normalize("test") == "test"