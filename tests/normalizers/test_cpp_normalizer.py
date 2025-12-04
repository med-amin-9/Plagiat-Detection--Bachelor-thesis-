import pytest
from normalizers.cpp_normalizer import CppNormalizer

@pytest.fixture
def cpp_normalizer():
    """Fixture to provide a fresh instance of CppNormalizer for each test."""
    return CppNormalizer()

def test_comment_removal(cpp_normalizer):
    """
    Test that both single-line and block comments are removed from the code.
    """
    code = "int x = 1; // comment\n/* block */ int y = 2;"
    result = cpp_normalizer.normalize(code)

    assert "comment" not in result
    assert "block" not in result
    assert "int" in result  # Keywords should remain

def test_string_and_char_normalization(cpp_normalizer):
    """
    Test that string and character literals are abstracted consistently.
    'Hi' vs. 'Hello' and 'x' vs. 'y' should normalize the same.
    """
    code1 = 'cout << "Hi"; char ch = \'x\';'
    code2 = 'cout << "Hello"; char ch = \'y\';'
    norm1 = cpp_normalizer.normalize(code1)
    norm2 = cpp_normalizer.normalize(code2)

    assert norm1 == norm2
    assert "_STR" in norm1  # Placeholder for string literals
    assert "_C" in norm1    # Placeholder for character literals

def test_whitespace_normalization(cpp_normalizer):
    """
    Ensure different formatting styles normalize to the same output.
    """
    variants = [
        "int   main(){ return    0; }",
        "int main( ){return 0;}",
        "int    main(){ return 0; }"
    ]
    results = [cpp_normalizer.normalize(code) for code in variants]

    # All formatted variants should result in the same normalized output
    assert all(result == results[0] for result in results)

def test_identifier_normalization_equivalence(cpp_normalizer):
    """
    Different user-defined identifiers should be normalized consistently.
    For example: 'apples' and 'bananas' should normalize to the same placeholder.
    """
    code1 = "int apples = 5; return apples;"
    code2 = "int bananas = 5; return bananas;"
    norm1 = cpp_normalizer.normalize(code1)
    norm2 = cpp_normalizer.normalize(code2)

    assert norm1 == norm2
    assert "_v1" in norm1
    assert "_v1" in norm2

def test_keywords_preserved(cpp_normalizer):
    """
    Ensure that essential C++ keywords are preserved and not replaced by placeholders.
    """
    code = "int main() { if (x > 0) return x; else return 0; }"
    result = cpp_normalizer.normalize(code)

    for keyword in ["int", "if", "return", "else"]:
        assert keyword in result

def test_macro_normalization(cpp_normalizer):
    """
    Ensure that macros like #define SIZE are normalized to _MACRO.
    """
    code = "#define SIZE 100\nint arr[SIZE];"
    result = cpp_normalizer.normalize(code)
    assert "_MACRO" in result

def test_structure_spacing(cpp_normalizer):
    """
    Test that spacing around control structures is normalized.
    """
    code1 = "if(x>0){return 1;}"
    code2 = "if ( x > 0 ) { return 1 ; }"
    assert cpp_normalizer.normalize(code1) == cpp_normalizer.normalize(code2)

def test_empty_input(cpp_normalizer):
    """
    Ensure empty string returns an empty string.
    """
    assert cpp_normalizer.normalize("") == ""

def test_only_comments(cpp_normalizer):
    """
    Code with only comments should normalize to an empty string.
    """
    code = "// comment only\n/* block */"
    assert cpp_normalizer.normalize(code).strip() == ""