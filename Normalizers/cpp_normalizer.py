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

        text = re.sub(r'//.*', '', text)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        text = re.sub(r'\s+', ' ', text)

        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', text)
        seen = {}
        var_id = 1
        for ident in identifiers:
            if ident not in cpp_keywords and not ident.isdigit():
                if ident not in seen:
                    seen[ident] = f"_v{var_id}"
                    var_id += 1
                text = re.sub(rf'\b{re.escape(ident)}\b', seen[ident], text)

        return text