import struct

import pytest

from ignitionbench.export import bates_segment_stl


def test_binary_stl_structure():
    sections = 96
    data = bates_segment_stl(0.054, 0.020, 0.095, sections=sections)
    count = struct.unpack_from("<I", data, 80)[0]
    assert count == sections * 8
    assert len(data) == 84 + 50 * count


def test_vertices_span_the_segment():
    data = bates_segment_stl(0.054, 0.020, 0.095, sections=16)
    count = struct.unpack_from("<I", data, 80)[0]
    zs, radii = [], []
    for i in range(count):
        values = struct.unpack_from("<12f", data, 84 + 50 * i)
        for v in range(3):
            x, y, z = values[3 + 3 * v : 6 + 3 * v]
            zs.append(z)
            radii.append((x**2 + y**2) ** 0.5)
    assert min(zs) == 0.0
    assert max(zs) == pytest.approx(95.0)  # mm
    assert max(radii) == pytest.approx(27.0)
    assert min(radii) == pytest.approx(10.0)


def test_rejects_bad_geometry():
    with pytest.raises(ValueError):
        bates_segment_stl(0.02, 0.054, 0.095)
