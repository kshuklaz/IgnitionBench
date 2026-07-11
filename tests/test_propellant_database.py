import pytest

from ignitionbench.propellant import KNDX, KNSB, PROPELLANTS


def test_registry_contents():
    assert set(PROPELLANTS) == {
        "kndx",
        "knsb",
        "cherry_limeade",
        "ocean_water",
        "white_lightning",
        "blue_thunder",
    }


def test_kndx_burn_rate_matches_nakka_measurement():
    # Nakka's published KNDX fit gives 7.553 mm/s at 1 MPa.
    assert KNDX.burn_rate(1e6) == pytest.approx(7.553e-3, rel=1e-3)


def test_knsb_burn_rate_at_5mpa():
    # Segment 4: a=2.7097e-6, n=0.5245 → r = a·(5e6)^n
    assert KNSB.burn_rate(5e6) == pytest.approx(8.8415e-3, rel=1e-3)


def test_knsb_segments_are_continuous_at_boundaries():
    for left, right in zip(KNSB.segments, KNSB.segments[1:]):
        boundary = left.max_pressure
        assert right.min_pressure == boundary
        assert left.burn_rate(boundary) == pytest.approx(
            right.burn_rate(boundary), rel=0.02
        )


def test_c_star_matches_published_values():
    # Nakka publishes c* ≈ 885 m/s for KNSB; KNDX comes out ≈ 890 m/s with
    # openMotor's practical chamber temperature.
    assert KNSB.c_star == pytest.approx(885, rel=0.01)
    assert KNDX.c_star == pytest.approx(890, rel=0.01)


def test_burn_rate_outside_validated_range_raises():
    with pytest.raises(ValueError, match="outside the validated pressure range"):
        KNSB.burn_rate(50e6)
    with pytest.raises(ValueError, match="outside the validated pressure range"):
        KNSB.burn_rate(1_000.0)
