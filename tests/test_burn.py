import math

import pytest

from ignitionbench.propellant import KNSB, BatesGrain
from ignitionbench.simulation import simulate_burn

GRAIN = BatesGrain(3, 0.054, 0.020, 0.095)
THROAT_AREA = math.pi / 4 * 0.015**2


@pytest.fixture(scope="module")
def result():
    return simulate_burn(KNSB, GRAIN, THROAT_AREA)


def test_arrays_consistent(result):
    n = len(result.time)
    assert n == 241  # steps + terminal burnout point
    for series in (result.web, result.kn, result.pressure, result.thrust, result.mass):
        assert len(series) == n


def test_time_marches_forward(result):
    assert all(t1 > t0 for t0, t1 in zip(result.time, result.time[1:]))


def test_ends_at_burnout(result):
    assert result.web[-1] == pytest.approx(GRAIN.web_thickness)
    assert result.thrust[-1] == 0.0
    assert result.mass[-1] == 0.0
    assert result.mass[0] == pytest.approx(GRAIN.propellant_mass(KNSB), rel=1e-6)


def test_summary_matches_steady_state_ballpark(result):
    # The steady-state estimate gave ~2.45 s, ~1220 N·s, class J.
    assert 2.0 < result.burn_time < 3.0
    assert 1000 < result.total_impulse < 1450
    assert result.motor_class == "J"
    assert 100 < result.isp_delivered < 140


def test_bates_with_small_core_is_progressive(result):
    # Core surface grows faster than the ends shrink for this geometry.
    assert result.peak_kn > result.kn[0]
    assert result.max_pressure > result.pressure[0]


def test_impulse_equals_isp_identity(result):
    initial_mass = GRAIN.propellant_mass(KNSB)
    assert result.total_impulse == pytest.approx(
        result.isp_delivered * initial_mass * 9.80665, rel=1e-9
    )


def test_overpressure_design_raises():
    with pytest.raises(ValueError, match="[Oo]verpressure"):
        simulate_burn(KNSB, GRAIN, math.pi / 4 * 0.004**2)
