import math

import pytest

from ignitionbench.propellant import KNSB, BatesGrain, SlottedGrain
from ignitionbench.simulation import simulate_burn

BATES = BatesGrain(3, 0.054, 0.020, 0.095)
PLAIN = SlottedGrain(3, 0.054, 0.020, 0.095)  # no slits — must match BATES
SLOTTED = SlottedGrain(
    3, 0.054, 0.020, 0.095,
    slit_count=3, slit_depth=0.008, slit_width=0.003, slit_taper=0.3,
)
THROAT_AREA = math.pi / 4 * 0.015**2


def test_plain_slotted_matches_analytic_bates():
    assert PLAIN.web_thickness == pytest.approx(BATES.web_thickness, rel=0.02)
    assert PLAIN.volume() == pytest.approx(BATES.volume(), rel=0.01)
    for x in (0.0, 0.005, 0.012):
        assert PLAIN.burning_area(x) == pytest.approx(BATES.burning_area(x), rel=0.03)


def test_slits_add_initial_burning_surface():
    assert SLOTTED.burning_area(0.0) > 1.2 * BATES.burning_area(0.0)
    # slit volume is removed from the propellant
    assert SLOTTED.volume() < BATES.volume()
    assert SLOTTED.port_area() > BATES.port_area()


def test_slit_surface_fades_as_slits_burn_out():
    # extra perimeter over plain BATES shrinks once the front passes the slits
    extra_at_start = SLOTTED.burning_perimeter(0.0) - PLAIN.burning_perimeter(0.0)
    extra_late = SLOTTED.burning_perimeter(0.013) - PLAIN.burning_perimeter(0.013)
    assert extra_late < extra_at_start * 0.6


def test_slotted_web_never_exceeds_plain():
    assert SLOTTED.web_thickness <= PLAIN.web_thickness + 1e-4
    assert SLOTTED.web_thickness > SLOTTED.slit_depth


def test_burnout_is_clean():
    web = SLOTTED.web_thickness
    assert SLOTTED.burning_area(web) == 0.0
    assert SLOTTED.volume(web) == 0.0


def test_simulation_runs_with_slotted_grain():
    plain = simulate_burn(KNSB, PLAIN, THROAT_AREA)
    slotted = simulate_burn(KNSB, SLOTTED, THROAT_AREA)
    # more initial surface → higher ignition pressure; less propellant → less impulse
    assert slotted.pressure[0] > plain.pressure[0]
    assert 0.7 * plain.total_impulse < slotted.total_impulse < plain.total_impulse
    assert slotted.thrust[-1] == 0.0


def test_validation():
    with pytest.raises(ValueError, match="all the way through"):
        SlottedGrain(1, 0.054, 0.020, 0.095, slit_count=3, slit_depth=0.017, slit_width=0.003)
    with pytest.raises(ValueError, match="slit_width"):
        SlottedGrain(1, 0.054, 0.020, 0.095, slit_count=3, slit_depth=0.008, slit_width=0)
    with pytest.raises(ValueError, match="overlap"):
        SlottedGrain(1, 0.054, 0.020, 0.095, slit_count=6, slit_depth=0.008, slit_width=0.011)
    with pytest.raises(ValueError, match="slit_taper"):
        SlottedGrain(1, 0.054, 0.020, 0.095, slit_count=2, slit_depth=0.008, slit_width=0.003, slit_taper=1.4)
