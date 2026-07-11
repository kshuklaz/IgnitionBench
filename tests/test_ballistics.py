import pytest

from ignitionbench.propellant import (
    KNSB,
    kn,
    kn_for_pressure,
    port_to_throat,
    steady_state_pressure,
)


def test_kn_is_area_ratio():
    assert kn(burning_area=0.019, throat_area=1e-4) == pytest.approx(190)


def test_steady_state_pressure_for_typical_knsb_kn():
    # Kn 200 is inside KNSB's conventional operating band; expect a chamber
    # pressure in the low-MPa range (~350 psi).
    p = steady_state_pressure(KNSB, 200)
    assert 2.0e6 < p < 2.8e6


def test_pressure_and_kn_are_inverses():
    p = steady_state_pressure(KNSB, 200)
    assert kn_for_pressure(KNSB, p) == pytest.approx(200, rel=1e-6)

    kn_at_5mpa = kn_for_pressure(KNSB, 5e6)
    assert steady_state_pressure(KNSB, kn_at_5mpa) == pytest.approx(5e6, rel=1e-6)


def test_higher_kn_means_higher_pressure():
    assert steady_state_pressure(KNSB, 250) > steady_state_pressure(KNSB, 150)


def test_excessive_kn_raises_overpressure_error():
    with pytest.raises(ValueError, match="overpressure"):
        steady_state_pressure(KNSB, 2000)


def test_insufficient_kn_raises():
    with pytest.raises(ValueError, match="stable combustion"):
        steady_state_pressure(KNSB, 1)


def test_port_to_throat_ratio():
    assert port_to_throat(port_area=3e-4, throat_area=1e-4) == pytest.approx(3.0)
    with pytest.raises(ValueError):
        port_to_throat(3e-4, 0)
