import pytest

from ignitionbench.simulation import motor_class


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
