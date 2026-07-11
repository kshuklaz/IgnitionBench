import pytest

from ignitionbench.propellant import KNSB, BatesGrain

# 2 segments, 50 mm OD, 20 mm core, 100 mm long
GRAIN = BatesGrain(
    segment_count=2,
    outer_diameter=0.05,
    core_diameter=0.02,
    segment_length=0.10,
)


def test_web_thickness_is_radial_web_here():
    assert GRAIN.web_thickness == pytest.approx(0.015)


def test_web_thickness_limited_by_length_for_short_segments():
    pancake = BatesGrain(1, 0.05, 0.02, 0.02)
    assert pancake.web_thickness == pytest.approx(0.01)


def test_initial_burning_area():
    # per segment: core π·0.02·0.10 = 6.2832e-3, ends 2·(π/4)·(0.05²−0.02²) = 3.2987e-3
    assert GRAIN.burning_area() == pytest.approx(1.91637e-2, rel=1e-4)


def test_initial_volume_and_mass():
    assert GRAIN.volume() == pytest.approx(3.29867e-4, rel=1e-4)
    assert GRAIN.propellant_mass(KNSB) == pytest.approx(0.57727, rel=1e-4)


def test_burnout_leaves_nothing():
    assert GRAIN.burning_area(GRAIN.web_thickness) == 0.0
    assert GRAIN.volume(GRAIN.web_thickness) == 0.0


def test_port_area_grows_with_regression():
    assert GRAIN.port_area() < GRAIN.port_area(0.005)


def test_geometry_validation():
    with pytest.raises(ValueError):
        BatesGrain(0, 0.05, 0.02, 0.1)
    with pytest.raises(ValueError):
        BatesGrain(1, 0.05, 0.06, 0.1)  # core wider than grain
    with pytest.raises(ValueError):
        BatesGrain(1, 0.05, 0.02, 0.0)
