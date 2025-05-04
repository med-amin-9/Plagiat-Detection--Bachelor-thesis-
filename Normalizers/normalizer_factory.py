from .python_normalizer import PythonNormalizer
from .cpp_normalizer import CppNormalizer


def get_normalizer(language: str):
    if language == "python":
        return PythonNormalizer()
    elif language in ("cpp", "c"):
        return CppNormalizer()
    else:
        raise ValueError(f"Unsupported language: {language}")