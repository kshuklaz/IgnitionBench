import pytest

from ignitionbench.simulation import certification, motor_class


@pytest.mark.parametrize(
    ("impulse", "expected"),
    [
        (0.5, "1/4A"),
        (1.0, "1/2A"),
        (2.5, "A"),
        (2.51, "B"),
        (150, "G"),
        (320, "H"),
        (1222, "J"),
        (40960, "O"),
        (50000, ">O"),
    ],
)
def test_motor_class(impulse, expected):
    assert motor_class(impulse) == expected


def test_motor_class_rejects_nonpositive():
    with pytest.raises(ValueError):
        motor_class(0)


@pytest.mark.parametrize(
    ("letter", "level"),
    [
        ("A", "none"),
        ("G", "none"),
        ("H", "L1"),
        ("I", "L1"),
        ("J", "L2"),
        ("L", "L2"),
        ("M", "L3"),
        ("O", "L3"),
        (">O", "beyond"),
    ],
)
def test_certification_levels(letter, level):
    cert = certification(letter)
    assert cert["level"] == level
    assert cert["text"]
