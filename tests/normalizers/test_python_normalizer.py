import pytest
from normalizers.python_normalizer import PythonNormalizer

@pytest.fixture
def python_normalizer():
    return PythonNormalizer()

def test_removes_single_and_multiline_comments(python_normalizer):
    code = '''
# single line comment
x = 5  # inline comment
"""
This is a multiline comment
that spans multiple lines
"""
y = 10
'''
    result = python_normalizer.normalize(code)
    assert "comment" not in result
    assert "x" not in result or "y" not in result

def test_string_literal_abstraction(python_normalizer):
    code1 = 'name = "Alice"'
    code2 = 'name = "Bob"'
    norm1 = python_normalizer.normalize(code1)
    norm2 = python_normalizer.normalize(code2)
    assert norm1 == norm2
    assert '"_STR"' in norm1

def test_escape_characters_in_strings(python_normalizer):
    code = 'print("Line 1\\nLine 2")'
    result = python_normalizer.normalize(code)
    assert '_STR' in result

def test_spacing_and_symbol_normalization(python_normalizer):
    code1 = "if(x==5):print(\"ok\")"
    code2 = "if ( x == 5 ) : print ( \"ok\" )"
    assert python_normalizer.normalize(code1) == python_normalizer.normalize(code2)

def test_identifier_normalization(python_normalizer):
    code1 = "def compute(x): return x + 1"
    code2 = "def calculate(y): return y + 1"
    norm1 = python_normalizer.normalize(code1)
    norm2 = python_normalizer.normalize(code2)
    assert norm1 == norm2
    assert '_v1' in norm1

def test_builtin_and_keyword_preservation(python_normalizer):
    code = "print(len([1, 2, 3])) and True or False"
    result = python_normalizer.normalize(code)
    for token in ["print", "len", "True", "False", "and", "or"]:
        assert token in result

def test_raw_and_fstrings(python_normalizer):
    code = 'name = f"Hello {user}"'
    normalized = python_normalizer.normalize(code)
    assert '_STR' in normalized

def test_empty_input(python_normalizer):
    assert python_normalizer.normalize("") == ""

def test_only_comments_input(python_normalizer):
    code = """
# just a comment
''' another multiline comment '''
"""
    assert python_normalizer.normalize(code).strip() == ""

def test_numeric_literals_preserved(python_normalizer):
    code = "x = 123\ny = x + 456"
    result = python_normalizer.normalize(code)
    assert "123" in result and "456" in result

def test_multiple_identifiers(python_normalizer):
    code = "alpha = 1\nbeta = alpha + 1\ngamma = beta + alpha"
    result = python_normalizer.normalize(code)
    assert result.count("_v") >= 3