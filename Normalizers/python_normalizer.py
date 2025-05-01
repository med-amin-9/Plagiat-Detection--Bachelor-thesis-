import re
import keyword
import builtins
from .base import CodeNormalizer

class PythonNormalizer(CodeNormalizer):
    def normalize(self, text: str) -> str:
        text = re.sub(r'#.*', '', text)  # Remove single-line comments
        text = re.sub(r'""".*?"""|\'\'\'.*?\'\'\'', '', text, flags=re.DOTALL)  # Multiline comments
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace

        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text)
        protected = set(keyword.kwlist + dir(builtins))
        seen = {}
        var_id = 1
        for ident in identifiers:
            if ident not in protected and not ident.isdigit():
                if ident not in seen:
                    seen[ident] = f"_v{var_id}"
                    var_id += 1
                text = re.sub(rf'\b{re.escape(ident)}\b', seen[ident], text)

        return text