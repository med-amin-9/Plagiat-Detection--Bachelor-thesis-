from utils import RingBuffer

def get_kgrams(text: str, k: int = 25) -> list[str]:  #25 from the sigmoid paper for larger projects (40-60)
    """
    Generate a list of k-grams from the input text.
    A k-gram is a substring of length k from the original text.
    
    Args:
        text: The input text to generate k-grams from
        k: The length of each k-gram
        
    Returns:
        A list of all possible k-grams from the input text
    """
    if not text or k <= 0 or k > len(text):
        return []
    
    # Generate all possible k-grams by sliding a window of size k over the text
    return [text[i:i+k] for i in range(len(text) - k + 1)]

def rolling_hash(kgrams: list[str], base: int = 256, prime: int = 101) -> list[int]:
    """
    Compute rolling hashes for each k-gram using a simple polynomial hash.
    """
    pass


def select_fingerprints(hashes: list[int], window_size: int) -> set[int]:
    """
    Perform Winnowing by selecting the minimum hash in each sliding window.
    """
    pass


def robust_winnowing(text: str, k: int, window_size: int) -> set[int]:
    """
    Perform the full robust winnowing pipeline:
    normalize -> k-grams -> rolling hash -> fingerprint selection.
    """
    pass