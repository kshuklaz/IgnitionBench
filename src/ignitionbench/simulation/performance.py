"""Motor performance summaries.

Impulse classification per NAR/TRA letter classes: each class's upper bound
is double the previous, with A topping out at 2.5 N·s.
"""

from __future__ import annotations

_CLASS_NAMES = (
    "1/4A", "1/2A", "A", "B", "C", "D", "E", "F", "G",
    "H", "I", "J", "K", "L", "M", "N", "O",
)


def motor_class(total_impulse: float) -> str:
    """NAR/TRA letter class for a total impulse (N·s), e.g. 1222 → 'J'."""
    if total_impulse <= 0:
        raise ValueError("total_impulse must be positive")
    upper = 0.625  # 1/4A ceiling
    for name in _CLASS_NAMES:
        if total_impulse <= upper:
            return name
        upper *= 2
    return ">O"


_CERT_LEVELS = (
    ({"1/4A", "1/2A", "A", "B", "C", "D"}, "none", "No certification required (model rocket)"),
    ({"E", "F", "G"}, "none", "No certification required (mid-power — check field rules)"),
    ({"H", "I"}, "L1", "NAR/TRA Level 1 certification required"),
    ({"J", "K", "L"}, "L2", "NAR/TRA Level 2 certification required"),
    ({"M", "N", "O"}, "L3", "NAR/TRA Level 3 certification required"),
)


def certification(letter: str) -> dict[str, str]:
    """Certification requirement for a motor class letter.

    Returns {"level": "none"|"L1"|"L2"|"L3"|"beyond", "text": ...}.
    """
    for letters, level, text in _CERT_LEVELS:
        if letter in letters:
            return {"level": level, "text": text}
    return {
        "level": "beyond",
        "text": "Beyond O class — outside NAR/TRA hobby certification entirely",
    }
