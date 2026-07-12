import math
import struct

import pytest

from ignitionbench.export import grain_segment_stl


def _vertices(data):
    count = struct.unpack_from("<I", data, 80)[0]
    for i in range(count):
        values = struct.unpack_from("<12f", data, 84 + 50 * i)
        for v in range(3):
            yield values[3 + 3 * v : 6 + 3 * v]


def test_binary_stl_structure():
    data = grain_segment_stl(0.054, 0.020, 0.095, sections=96)
    count = struct.unpack_from("<I", data, 80)[0]
    # a plain tube is 8 triangles per angular step (two per wall/face)
    assert count == 96 * 8
    assert len(data) == 84 + 50 * count


def test_vertices_span_the_segment():
    data = grain_segment_stl(0.054, 0.020, 0.095, sections=16)
    zs, radii = [], []
    for x, y, z in _vertices(data):
        zs.append(z)
        radii.append(math.hypot(x, y))
    assert min(zs) == 0.0
    assert max(zs) == pytest.approx(95.0)  # mm
    assert max(radii) == pytest.approx(27.0)
    assert min(radii) == pytest.approx(10.0)


def test_slotted_stl_carves_tapered_face_slits():
    data = grain_segment_stl(
        0.054, 0.020, 0.095,
        slit_count=3, slit_depth=0.008, slit_width=0.003,
        slit_length=0.030, slit_taper=0.3,
        sections=360,
    )
    by_z: dict[float, list[float]] = {}
    for x, y, z in _vertices(data):
        r = math.hypot(x, y)
        if r < 26.9:  # inner boundary only
            by_z.setdefault(round(z, 3), []).append(r)
    # at the forward face the slit reaches core + depth = 18 mm; the
    # nozzle-end face is a plain annulus from the core
    assert max(by_z[0.0]) == pytest.approx(18.0, abs=0.3)
    assert max(by_z[95.0]) == pytest.approx(10.0, abs=0.1)
    # where the cut ends it has tapered to 30%: core + 0.3·depth = 12.4 mm
    at_end = max(r for z, rs in by_z.items() if abs(z - 30.0) < 0.01 for r in rs)
    assert at_end == pytest.approx(10 + 8 * 0.3, abs=0.3)
    # no slit-wall vertex (r beyond the core) lies past the cut length
    assert all(
        z <= 30.01
        for z, rs in by_z.items()
        for r in rs
        if r > 10.2
    )
    # and never through the web anywhere
    assert all(r < 27.0 for rs in by_z.values() for r in rs)


def test_rejects_bad_geometry():
    with pytest.raises(ValueError):
        grain_segment_stl(0.02, 0.054, 0.095)
    with pytest.raises(ValueError, match="radial web"):
        grain_segment_stl(
            0.054, 0.020, 0.095,
            slit_count=3, slit_depth=0.017, slit_width=0.003, slit_length=0.030,
        )
    with pytest.raises(ValueError, match="nozzle-end face"):
        grain_segment_stl(
            0.054, 0.020, 0.095,
            slit_count=3, slit_depth=0.008, slit_width=0.003, slit_length=0.095,
        )
