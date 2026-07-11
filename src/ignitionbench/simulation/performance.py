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
