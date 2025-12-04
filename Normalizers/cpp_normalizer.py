import re
from .base import CodeNormalizer

class CppNormalizer(CodeNormalizer):
    def normalize(self, text: str) -> str:
        cpp_keywords = {
            "auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else",
            "enum", "extern", "float", "for", "goto", "if", "inline", "int", "long", "register",
            "restrict", "return", "short", "signed", "sizeof", "static", "struct", "switch",
            "typedef", "union", "unsigned", "void", "volatile", "while", "class", "delete", "new",
            "private", "protected", "public", "template", "this", "throw", "try", "catch", "using", "namespace"
        }

        # Step 1: Remove comments (single-line and multi-line)
        text = re.sub(r'//.*', '', text)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL) # DOTALL makes . match newlines, needed to remove multi-line /* ... */ comments

        # Step 2: Normalize string and char literals
        text = re.sub(r"'(\\.|.)'", "'_C'", text)
        text = re.sub(r'"(?:\\.|[^"\\])*"', '"_STR"', text) 

        # Step 3: Add spaces around common symbols (to standardize format)
        for symbol in "(){};=+-*/<>&|!":
            text = text.replace(symbol, f' {symbol} ')

        # Step 4: Normalize whitespace
        text = re.sub(r'\s+', ' ', text).strip() 

        # Step 5: Normalize #define macro names only
        text = re.sub(r'#define\s+([A-Z_][A-Z0-9_]*)', '#define _MACRO', text)

        # Step 6: Replace user-defined identifiers
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text)
        seen = {}  #remember which identifiers we've already replaced
        var_id = 1
        for ident in identifiers:
            if ident in cpp_keywords or ident.isdigit():
                continue
            if ident in {"_STR", "_C", "_MACRO"}:
                continue  # Skip placeholders
            if ident not in seen:
                seen[ident] = f"_v{var_id}"
                var_id += 1
            text = re.sub(rf'\b{re.escape(ident)}\b', seen[ident], text)

        return text