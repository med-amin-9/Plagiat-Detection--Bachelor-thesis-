from utils import RingBuffer

def get_kgrams(text: str, k: int) -> list[str]:
    """
    Generate a list of k-grams from the input text.
    """
    

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