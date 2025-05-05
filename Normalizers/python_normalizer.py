import re
import keyword
import builtins
from .base import CodeNormalizer

class PythonNormalizer(CodeNormalizer):
    def normalize(self, text: str) -> str:
        # Step 1: Remove comments (single-line and multi-line)
        text = re.sub(r'#.*', '', text)
        text = re.sub(r'"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\'', '', text)

        # Step 2: Normalize string literals (single and double quoted)
        text = re.sub(r'r?f?"(?:\\.|[^"\\])*"', '"_STR"', text)
        text = re.sub(r"r?f?'(?:\\.|[^'\\])*'", "'_STR'", text)
        
        # Step 3: Add space around common symbols
        for sym in "(){}[]:,=+-*/<>!":
            text = text.replace(sym, f" {sym} ")
        
        # Step 4: Normalize whitespace
        text = re.sub(r'\s+', ' ', text)

        # Step 5: Normalize user-defined identifiers
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text)
        protected = set(keyword.kwlist + dir(builtins)) | {"_STR"}

        seen = {}
        var_id = 1
        for ident in identifiers:
            if ident not in protected and not ident.isdigit():
                if ident not in seen:
                    seen[ident] = f"_v{var_id}"
                    var_id += 1
                text = re.sub(rf'\b{re.escape(ident)}\b', seen[ident], text)

        return text