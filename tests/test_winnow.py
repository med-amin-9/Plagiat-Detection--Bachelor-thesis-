import pytest
from winnow import get_kgrams

class TestGetKgrams:
    """Test class for the get_kgrams function from the winnow module."""
    
    def test_normal_case(self):
        """Test the normal case with typical input."""
        text = "abcdefghijklmnopqrstuvwxyz"
        k = 3
        expected = ["abc", "bcd", "cde", "def", "efg", "fgh", "ghi", "hij", "ijk", 
                    "jkl", "klm", "lmn", "mno", "nop", "opq", "pqr", "qrs", "rst", 
                    "stu", "tuv", "uvw", "vwx", "wxy", "xyz"]
        assert get_kgrams(text, k) == expected
    
    def test_default_k_value(self):
        """Test with a text shorter than the default k value."""
        text = "abcdefghijklmnopqrstuvwxyz"  # 26 chars
        # Default k is 25, so we expect only 2 kgrams
        expected = ["abcdefghijklmnopqrstuvwxy", "bcdefghijklmnopqrstuvwxyz"]
        assert get_kgrams(text) == expected
    
    def test_empty_string(self):
        """Test with an empty string."""
        assert get_kgrams("", 5) == []
    
    def test_k_zero(self):
        """Test with k=0 (invalid k value)."""
        assert get_kgrams("sample text", 0) == []
    
    def test_k_negative(self):
        """Test with negative k (invalid k value)."""
        assert get_kgrams("sample text", -3) == []
    
    def test_k_larger_than_text(self):
        """Test with k larger than text length."""
        assert get_kgrams("abc", 5) == []
    
    def test_k_equal_to_text_length(self):
        """Test with k equal to text length."""
        text = "abcde"
        k = 5
        expected = ["abcde"]
        assert get_kgrams(text, k) == expected
    
    def test_single_character_text(self):
        """Test with a single character text and k=1."""
        assert get_kgrams("a", 1) == ["a"]
    
    def test_special_characters(self):
        """Test with special characters."""
        text = "a!b@c#d$"
        k = 2
        expected = ["a!", "!b", "b@", "@c", "c#", "#d", "d$"]
        assert get_kgrams(text, k) == expected