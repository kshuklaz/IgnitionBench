import pytest

from ignitionbench.nozzle import (
    STANDARD_ATMOSPHERE,
    ConicalNozzle,
    area_ratio_from_mach,
    divergence_factor,
    exit_pressure,
    mach_from_area_ratio,
    mass_flow,
    optimal_expansion_ratio,
    pressure_ratio,
    specific_impulse,
    throat_area_for_thrust,
    thrust,
    thrust_coefficient,
)
from ignitionbench.propellant import KNSB


def test_throat_is_unity_area_ratio():
    assert area_ratio_from_mach(1.0, 1.2) == pytest.approx(1.0)
    assert mach_from_area_ratio(1.0, 1.2) == pytest.approx(1.0)


def test_area_ratio_at_mach_2():
    # k=1.2: A/At = (1/2)·((2/2.2)(1+0.1·4))^5.5 = 1.88360
    assert area_ratio_from_mach(2.0, 1.2) == pytest.approx(1.88360, rel=1e-4)


def test_mach_area_round_trip():
    ratio = area_ratio_from_mach(2.0, 1.2)
    assert mach_from_area_ratio(ratio, 1.2) == pytest.approx(2.0, rel=1e-6)


def test_sonic_pressure_ratio_air():
    # Classic value: P/P0 at M=1, k=1.4 is 0.528282
    assert pressure_ratio(1.0, 1.4) == pytest.approx(0.528282, rel=1e-5)


def test_optimal_expansion_recovers_ambient_pressure():
    pc, k = 6.895e6, 1.2
    ratio = optimal_expansion_ratio(pc, k)
    assert exit_pressure(pc, ratio, k) == pytest.approx(STANDARD_ATMOSPHERE, rel=1e-6)


def test_thrust_coefficient_at_optimal_expansion():
    # k=1.2, Pc/Pa = 68.05, matched exit: Cf ≈ 1.60 (Sutton ch. 3 territory)
    pc, k = 6.895e6, 1.2
    ratio = optimal_expansion_ratio(pc, k)
    assert thrust_coefficient(pc, ratio, k) == pytest.approx(1.5966, rel=1e-3)


def test_divergence_loss_reduces_cf():
    pc, k = 6.895e6, 1.2
    ratio = optimal_expansion_ratio(pc, k)
    ideal = thrust_coefficient(pc, ratio, k)
    conical = thrust_coefficient(pc, ratio, k, half_angle_deg=15)
    assert conical < ideal
    assert divergence_factor(15) == pytest.approx(0.98296, rel=1e-4)


def test_knsb_ideal_isp_is_plausible():
    # Full chain: KNSB c* + Cf at 1000 psi optimally expanded → ~148 s
    pc = 6.895e6
    ratio = optimal_expansion_ratio(pc, KNSB.gamma)
    cf = thrust_coefficient(pc, ratio, KNSB.gamma)
    isp = specific_impulse(cf, KNSB.c_star)
    assert 140 < isp < 155


def test_thrust_and_throat_sizing_are_inverses():
    at = throat_area_for_thrust(thrust=100.0, chamber_pressure=2.4e6, cf=1.5)
    assert thrust(2.4e6, at, 1.5) == pytest.approx(100.0)


def test_mass_flow_identity():
    # ṁ·c* = Pc·At by definition
    assert mass_flow(2.4e6, 1e-4, 885.0) * 885.0 == pytest.approx(2.4e6 * 1e-4)


def test_conical_nozzle_geometry():
    nozzle = ConicalNozzle(throat_diameter=0.015, expansion_ratio=4.0)
    assert nozzle.exit_diameter == pytest.approx(0.030)
    assert nozzle.exit_area == pytest.approx(4 * nozzle.throat_area)
    # (De−Dt) / (2·tan 15°)
    assert nozzle.divergent_length == pytest.approx(0.027990, rel=1e-4)


def test_conical_nozzle_validation():
    with pytest.raises(ValueError):
        ConicalNozzle(throat_diameter=0.0, expansion_ratio=4.0)
    with pytest.raises(ValueError):
        ConicalNozzle(throat_diameter=0.015, expansion_ratio=0.5)
