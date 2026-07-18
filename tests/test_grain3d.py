"""FaceSlitGrain: 3D voxel regression validated against analytic BATES."""

import pytest

from ignitionbench.propellant import KNSB, BatesGrain, FaceSlitGrain, regression_section
from ignitionbench.simulation import simulate_burn

BATES = BatesGrain(3, 0.054, 0.020, 0.095)
PLAIN = FaceSlitGrain(3, 0.054, 0.020, 0.095)
# one continuous cut, 100 mm from the motor front — crosses into segment 2
SLIT = FaceSlitGrain(
    3, 0.054, 0.020, 0.095,
    slit_count=3, slit_depth=0.008, slit_width=0.003,
    slit_length=0.100, slit_taper=0.3,
)


def test_plain_grain_matches_analytic_bates():
    assert PLAIN.web_thickness == pytest.approx(BATES.web_thickness, rel=0.01)
    assert PLAIN.burning_area(0) == pytest.approx(BATES.burning_area(0), rel=0.005)
    assert PLAIN.volume(0) == pytest.approx(BATES.volume(0), rel=0.005)
    for x in (0.002, 0.008, 0.015):
        assert PLAIN.burning_area(x) == pytest.approx(BATES.burning_area(x), rel=0.03)
        # near burnout the remaining sliver is a few voxels thick, so compare
        # the volume error against the initial volume, not the remainder
        assert abs(PLAIN.volume(x) - BATES.volume(x)) < 0.01 * BATES.volume(0)


def test_slits_add_ignition_surface_then_burn_out():
    assert SLIT.burning_area(0) > PLAIN.burning_area(0) * 1.05
    # by the time the front has passed the slit depth the cuts are consumed
    # and the areas converge
    late = SLIT.burning_area(0.012) / PLAIN.burning_area(0.012)
    assert late < 1.03
    # pockets remove only a sliver of propellant
    assert SLIT.volume(0) / PLAIN.volume(0) > 0.99


def test_longer_and_wider_cuts_add_more_surface():
    def area(**kw):
        base = dict(
            slit_count=3, slit_depth=0.008, slit_width=0.003,
            slit_length=0.030, slit_taper=0.3,
        )
        base.update(kw)
        return FaceSlitGrain(3, 0.054, 0.020, 0.095, **base).burning_area(0)

    assert area(slit_length=0.045) > area(slit_length=0.030) > area(slit_length=0.015)
    assert area(slit_depth=0.012) > area(slit_depth=0.008)


def test_validation():
    with pytest.raises(ValueError, match="all the way through the web"):
        FaceSlitGrain(
            3, 0.054, 0.020, 0.095,
            slit_count=3, slit_depth=0.017, slit_width=0.003, slit_length=0.030,
        )
    with pytest.raises(ValueError, match="nozzle-end face"):
        FaceSlitGrain(
            3, 0.054, 0.020, 0.095,
            slit_count=3, slit_depth=0.008, slit_width=0.003, slit_length=0.300,
        )
    with pytest.raises(ValueError, match="overlap"):
        FaceSlitGrain(
            3, 0.054, 0.020, 0.095,
            slit_count=8, slit_depth=0.008, slit_width=0.015, slit_length=0.030,
        )


def test_simulation_runs_to_burnout():
    throat_area = 3.14159 / 4 * 0.015**2
    plain = simulate_burn(KNSB, PLAIN, throat_area)
    slit = simulate_burn(KNSB, SLIT, throat_area)
    # slits raise ignition Kn and pressure, cost a little total impulse
    assert slit.kn[0] > plain.kn[0] * 1.05
    assert slit.pressure[0] > plain.pressure[0]
    assert slit.total_impulse == pytest.approx(plain.total_impulse, rel=0.05)
    assert slit.thrust[-1] == 0.0


def test_regression_section_payload():
    sec = regression_section(SLIT)
    assert sec["nu"] * sec["nz"] == len(sec["dist_mm"])
    assert sec["web_mm"] == pytest.approx(SLIT.web_thickness * 1000, rel=0.01)
    # the section spans the bore diameter and the whole stack (3 segments
    # of 95 mm plus two 3 mm gaps)
    assert sec["nu"] * sec["du_mm"] == pytest.approx(54.0, abs=1.5)
    assert sec["nz"] * sec["dz_mm"] == pytest.approx(291.0, abs=4.0)
    # bottom half cuts through a slit, top half runs between slits, so the
    # forward columns of the bottom half carry more initial void
    import numpy as np

    arr = np.array(sec["dist_mm"]).reshape(sec["nu"], sec["nz"])
    half = sec["nu"] // 2
    fwd = slice(0, 5)
    assert (arr[half:, fwd] == 0).sum() > (arr[:half, fwd] == 0).sum()


def test_cut_carries_across_the_joint():
    # the forward segment's aft face keeps an open mouth where the cut
    # carries through, and segment 2 starts at exactly that scale
    from ignitionbench.propellant.grain3d import _rings

    fwd = _rings(0.095, 3, 0.100, 0.3, 0.0)
    nxt = _rings(0.095, 3, 0.100, 0.3, 0.095)
    assert fwd[-1][0] == pytest.approx(0.095)
    assert fwd[-1][1] == pytest.approx(nxt[0][1])  # scales match at the joint
    assert fwd[-1][1] > 0  # open mouth, not a closed wall
    # the cut ends 5 mm into segment 2, then it is a plain bore
    assert nxt[-2] == (pytest.approx(0.005), 0.0)
    assert nxt[-1] == (pytest.approx(0.095), 0.0)
    # segment 3 is entirely past the cut
    assert _rings(0.095, 3, 0.100, 0.3, 0.190) == [(0.0, 0.0), (0.095, 0.0)]
