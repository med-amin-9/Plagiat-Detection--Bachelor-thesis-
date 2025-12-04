import pytest
from normalizers.base import CodeNormalizer
from normalizers.python_normalizer import PythonNormalizer
from normalizers.cpp_normalizer import CppNormalizer
from normalizers.normalizer_factory import get_normalizer


def test_get_normalizer_python():
    """Test that the factory returns a Python normalizer for 'python'."""
    normalizer = get_normalizer("python")
    assert isinstance(normalizer, PythonNormalizer)


def test_get_normalizer_cpp():
    """Test that the factory returns a C++ normalizer for 'cpp'."""
    normalizer = get_normalizer("cpp")
    assert isinstance(normalizer, CppNormalizer)

def test_get_normalizer_c():
    """Test that the factory returns a C++ normalizer for 'c'."""
    normalizer = get_normalizer("c")
    assert isinstance(normalizer, CppNormalizer)

def test_get_normalizer_unsupported():
    """Test that the factory raises an error for unsupported languages."""
    with pytest.raises(ValueError) as exc_info:
        get_normalizer("javascript")
    assert "Unsupported language" in str(exc_info.value)


def test_normalizer_usage_through_factory():
    """Test that normalizers created by the factory work correctly."""
    # Get a Python normalizer
    py_normalizer = get_normalizer("python")
    
    # Test basic normalization
    python_code = "def hello_world():\n    print('Hello, world!')"
    normalized = py_normalizer.normalize(python_code)
    
    # Verify normalization happened
    assert "hello_world" not in normalized
    assert "_v" in normalized
    assert "def" in normalized
    assert "print" in normalized
    
    # Get a C++ normalizer
    cpp_normalizer = get_normalizer("cpp")
    
    # Test basic normalization
    cpp_code = "void hello_world() {\n    cout << \"Hello, world!\" << endl;\n}"
    normalized = cpp_normalizer.normalize(cpp_code)
    
    # Verify normalization happened
    assert "hello_world" not in normalized
    assert "_v" in normalized
    assert "void" in normalized