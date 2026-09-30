"""Trust-boundary helpers for model-visible external content."""

INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "system message",
    "developer message",
    "reveal your prompt",
    "disregard the user",
    "bypass approval",
    "disable safety",
    "send secrets",
)


def mark_untrusted(source, content):
    """Return model-visible data explicitly separated from trusted instructions."""
    text = str(content)
    lowered = text.lower()
    signals = tuple(pattern for pattern in INJECTION_PATTERNS if pattern in lowered)
    return {
        "source": str(source),
        "trust": "untrusted",
        "content": text,
        "injection_signals": signals,
        "instruction_authority": "none",
    }


def contains_injection_signals(content):
    text = str(content).lower()
    return tuple(pattern for pattern in INJECTION_PATTERNS if pattern in text)
