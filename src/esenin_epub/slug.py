"""ASCII-safe slugs for EPUB internal paths and cache files."""

import re
import unicodedata

_TABLE = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def translit(text: str) -> str:
    out = []
    for ch in text.lower():
        if ch in _TABLE:
            out.append(_TABLE[ch])
        else:
            out.append(unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode())
    return "".join(out)


def slugify(text: str, max_len: int = 60) -> str:
    text = re.sub(r"\s*\((Есенин|есенин)\)\s*$", "", text)
    s = translit(text)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s or "work"
