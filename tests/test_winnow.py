import pytest
from winnow import get_kgrams, rolling_hash, select_fingerprints, robust_winnowing

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

class TestRollingHash:
    """Test class for the rolling_hash function from the winnow module."""

    def test_hashes_generated_for_kgrams(self):
        """Ensure hash list length matches k-gram list."""
        kgrams = get_kgrams("abcdef", 3)
        hashes = rolling_hash(kgrams)
        assert len(hashes) == len(kgrams)

    def test_stable_hash_for_same_input(self):
        """Same k-grams should yield same hashes every time."""
        kgrams1 = get_kgrams("abcdef", 4)
        kgrams2 = get_kgrams("abcdef", 4)
        assert rolling_hash(kgrams1) == rolling_hash(kgrams2)

    def test_detects_differences_in_input(self):
        """Slight change in input should change hashes."""
        kgrams1 = get_kgrams("abcdef", 3)
        kgrams2 = get_kgrams("abcxef", 3)
        assert rolling_hash(kgrams1) != rolling_hash(kgrams2)

    def test_handles_empty_input(self):
        """Should return empty list when no k-grams are given."""
        assert rolling_hash([]) == []

    def test_rejects_inconsistent_kgram_lengths(self):
        """Raise error when k-grams are not same length."""
        with pytest.raises(ValueError):
            rolling_hash(["abc", "de"])

class TestSelectFingerprints:
    """Test class for the select_fingerprints function from the winnow module."""

    def test_finds_minimum_in_each_window(self):
        """Should select the minimum value in each window of size w."""
        hashes = [9, 3, 5, 2, 6, 4, 1, 7]
        w = 4
        result = select_fingerprints(hashes, w)
        # Known minima: windows [9,3,5,2] -> 2, [3,5,2,6] -> 2, [5,2,6,4] -> 2, [2,6,4,1] -> 1, [6,4,1,7] -> 1
        assert 2 in result
        assert 1 in result
        assert len(result) >= 2  # Could include more depending on position logic

    def test_no_input(self):
        """Should return empty set when input is empty."""
        assert select_fingerprints([], 4) == set()

    def test_window_larger_than_input(self):
        """Should return empty set when window size is larger than the hash list."""
        assert select_fingerprints([1, 2, 3], 5) == set()

    def test_single_window(self):
        """Single window should return minimum only."""
        hashes = [8, 4, 7]
        result = select_fingerprints(hashes, 3)
        assert result == {4}

    def test_duplicate_minima(self):
        """Duplicate minimums in overlapping windows should not be added more than once."""
        hashes = [5, 1, 1, 1, 6]
        result = select_fingerprints(hashes, 3)
        assert 1 in result
        assert isinstance(result, set)

    def test_minimum_at_end(self):
        """Should detect minimum at last possible position."""
        hashes = [10, 8, 7, 6, 5]
        result = select_fingerprints(hashes, 2)
        assert 5 in result

class TestRobustWinnowing:
    """Test class for the robust_winnowing pipeline."""

    def test_basic_pipeline_python(self):
        """Basic test with Python code using k=5 and w=4."""
        code = "def add(a, b): return a + b"
        result = robust_winnowing(code, language="python", k=5, window_size=4)
        assert isinstance(result, set)
        assert len(result) > 0

    def test_basic_pipeline_cpp(self):
        """Basic test with C++ code using k=5 and w=4."""
        code = "int add(int a, int b) { return a + b; }"
        result = robust_winnowing(code, language="cpp", k=5, window_size=4)
        assert isinstance(result, set)
        assert len(result) > 0

    def test_empty_code(self):
        """Empty source code should return empty set."""
        result = robust_winnowing("", language="python", k=5, window_size=4)
        assert result == set()

    def test_window_larger_than_hashes(self):
        """If window is too large, no fingerprint should be returned."""
        code = "print('ok')"
        result = robust_winnowing(code, "python", k=10, window_size=50)
        assert result == set()

    def test_invalid_language(self):
        """Should raise ValueError if language not supported."""
        with pytest.raises(ValueError):
            robust_winnowing("x = 1", language="javascript", k=5, window_size=4)