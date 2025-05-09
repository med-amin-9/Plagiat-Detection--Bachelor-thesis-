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
    Compute rolling hashes for a list of k-grams using a simple polynomial hash function.
    
    Args:
        kgrams (list[str]): A list of strings of equal length (k-grams).
        base (int): The base used in the polynomial hash (default: 256 for ASCII).
        prime (int): A prime number used as modulus to reduce collisions.
        
    Returns:
        list[int]: A list of integer hash values, one for each k-gram.
    """
    if not kgrams:
        return []

    k = len(kgrams[0])
    if any(len(gram) != k for gram in kgrams):
        raise ValueError("All k-grams must have the same length")

    hashes = []

    # Precompute base^(k-1) % prime
    high_order = pow(base, k - 1, prime)

    # Compute hash for first k-gram
    h = 0
    for char in kgrams[0]:
        h = (h * base + ord(char)) % prime
    hashes.append(h)

    # Compute rolling hashes for subsequent k-grams
    for i in range(1, len(kgrams)):
        out_char = ord(kgrams[i - 1][0])
        in_char = ord(kgrams[i][-1])
        h = ((h - out_char * high_order) * base + in_char) % prime
        hashes.append(h)

    return hashes

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