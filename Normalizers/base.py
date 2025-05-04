from abc import ABC, abstractmethod

class CodeNormalizer(ABC):
    """
    Abstract base class for all code normalizers.
    Each subclass must implement the `normalize` method
    that takes raw code and returns a normalized version.
    """
    def __init__(self):
        super().__init__()

    @abstractmethod
    def normalize(self, text: str) -> str:
        """
        Normalize source code by removing irrelevant differences
        such as comments, whitespace, or variable names.
        """
        raise NotImplementedError("Subclasses must implement this method")