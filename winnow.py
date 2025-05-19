from normalizers.normalizer_factory import get_normalizer

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

def select_fingerprints(hashes: list[int], window_size: int = 21) -> set[int]:
    """
    Select fingerprints using the Winnowing algorithm.

    This function implements the core of the Winnowing technique:
    from all rolling hashes, it selects the minimum value in every 
    sliding window of size `w`. To ensure no duplicates and preserve
    detection properties, it uses both the hash value and its position.

    Args:
        hashes (list[int]): List of hash values computed from k-grams.
        window_size (int): Size of the sliding window (w > 0).

    Returns:
        set[int]: A set of selected fingerprint hashes.
    """
    if not hashes or window_size <= 0:
        return set()

    fingerprints = set()
    min_pos = -1
    min_val = None

    for i in range(len(hashes) - window_size + 1):
        window = hashes[i:i + window_size]

        # If previous min is outside the window, recompute
        if min_pos < i:
            min_val = min(window)
            min_pos = i + window.index(min_val)
            fingerprints.add((min_val, min_pos))
        else:
            new_val = window[-1]
            if min_val is None or new_val <= min_val:
                min_val = new_val
                min_pos = i + window_size - 1
                fingerprints.add((min_val, min_pos))

    # Return only hash values
    return set(f[0] for f in fingerprints)

def robust_winnowing(text: str, language: str, k: int, window_size: int) -> set[int]:
    """
    Perform the full Winnowing pipeline to detect document fingerprints.

    This function normalizes the input text based on the programming language,
    extracts k-grams, computes rolling hashes, and selects fingerprints.

    Args:
        text (str): Raw source code as string.
        language (str): Programming language (e.g., 'python', 'cpp', 'c').
        k (int): Length of each k-gram.
        window_size (int): Size of sliding window used for fingerprinting.

    Returns:
        set[int]: Selected fingerprint hash values.
    """
    # Step 1: Normalize
    normalizer = get_normalizer(language)
    normalized_text = normalizer.normalize(text)

    # Step 2: Generate k-grams
    kgrams = get_kgrams(normalized_text, k)

    # Step 3: Compute hashes
    hashes = rolling_hash(kgrams)

    # Step 4: Winnow the hashes to fingerprints
    fingerprints = select_fingerprints(hashes, window_size)

    return fingerprints

def compare_all_submissions(self):
    """
    Compares all student submissions using Jaccard similarity.
    Groups similarities across all repositories and flags results above a threshold.
    """
    threshold = self.config["plagiarism_detection"].get("threshold", 0.5)
    all_files = []

    for repo in self.repositories:
        for fname, fp in repo.fingerprints.items():
            all_files.append((repo.identifier, fname, fp))

    for i in range(len(all_files)):
        for j in range(i + 1, len(all_files)):
            id1, file1, fp1 = all_files[i]
            id2, file2, fp2 = all_files[j]

            if not fp1 or not fp2:
                continue

            intersection = len(fp1 & fp2)
            union = len(fp1 | fp2)
            if union == 0:
                continue

            jaccard = intersection / union
            if jaccard >= threshold:
                self.results.append({
                    "file_1": f"{id1}/{file1}",
                    "file_2": f"{id2}/{file2}",
                    "similarity": round(jaccard, 4)
                })
