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
    sections = 96
    data = grain_segment_stl(0.054, 0.020, 0.095, sections=sections)
    count = struct.unpack_from("<I", data, 80)[0]
    assert count == sections * 8
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


def test_slotted_stl_carves_the_slits():
    data = grain_segment_stl(
        0.054, 0.020, 0.095,
        slit_count=3, slit_depth=0.008, slit_width=0.003, slit_taper=0.3,
        sections=360,
    )
    count = struct.unpack_from("<I", data, 80)[0]
    assert count == 360 * 8
    inner_radii = [math.hypot(x, y) for x, y, _ in _vertices(data) if math.hypot(x, y) < 26.9]
    # between slits the void is the core (10 mm); at slit tips it reaches 18 mm
    assert min(inner_radii) == pytest.approx(10.0, abs=0.05)
    assert max(inner_radii) == pytest.approx(18.0, abs=0.3)
    # but never through the web
    assert max(inner_radii) < 27.0


def test_rejects_bad_geometry():
    with pytest.raises(ValueError):
        grain_segment_stl(0.02, 0.054, 0.095)
    with pytest.raises(ValueError, match="radial web"):
        grain_segment_stl(0.054, 0.020, 0.095, slit_count=3, slit_depth=0.017, slit_width=0.003)
