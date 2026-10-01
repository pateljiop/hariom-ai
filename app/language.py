"""Natural-language normalization for short Hinglish computer commands.

This layer is deliberately deterministic: it normalizes common shorthand and
Hinglish spellings without trying to infer sensitive actions on its own.
"""

import re


REPLACEMENTS = {
    "krdo": "kar do",
    "krde": "kar de",
    "kr": "kar",
    "kro": "karo",
    "bnado": "bana do",
    "bnao": "banao",
    "bna": "bana",
    "shi": "sahi",
    "sahi": "sahi",
    "pr": "par",
    "pe": "par",
    "me": "mein",
    "m": "mein",
    "hn": "haan",
    "ha": "haan",
    "nhi": "nahi",
    "nh": "nahi",
    "bt": "bata",
    "bta": "bata",
    "dekh": "dekho",
    "dikh": "dikhao",
    "kholo": "khol do",
    "khol": "khol do",
    "padho": "read karo",
    "padh": "read karo",
}


def normalize_text(text):
    """Normalize common Hinglish shorthand while preserving technical terms."""
    value = re.sub(r"\s+", " ", str(text or "").strip())
    if not value:
        return ""

    tokens = value.split(" ")
    normalized = []
    for token in tokens:
        match = re.match(r"^([^A-Za-z0-9_]*)([A-Za-z0-9_]+)([^A-Za-z0-9_]*)$", token)
        if not match:
            normalized.append(token)
            continue
        prefix, word, suffix = match.groups()
        replacement = REPLACEMENTS.get(word.lower(), word)
        normalized.append(prefix + replacement + suffix)

    return " ".join(normalized)


def command_context(text):
    """Return normalized text plus lightweight linguistic hints for the planner."""
    original = str(text or "").strip()
    normalized = normalize_text(original)
    lower = normalized.lower()
    return {
        "original": original,
        "normalized": normalized,
        "language": "hinglish" if any(
            word in lower.split() for word in
            ("karo", "kar", "do", "bana", "banao", "par", "mein", "nahi", "haan", "dekho")
        ) else "english",
        "is_short_command": len(normalized.split()) <= 7,
    }
