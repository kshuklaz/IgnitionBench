"""Binary STL export of grain geometry, for 3D printing molds or CAD import."""

from __future__ import annotations

import math
import struct


def bates_segment_stl(
    outer_diameter: float,
    core_diameter: float,
    length: float,
    sections: int = 96,
) -> bytes:
    """One BATES segment (annular cylinder) as binary STL, in millimetres.

    Inputs are metres (consistent with the rest of the library); STL files
    are unitless so we emit mm, the convention slicers and CAD expect.
    """
    if not 0 < core_diameter < outer_diameter or length <= 0:
        raise ValueError("need 0 < core_diameter < outer_diameter and length > 0")

    big_r = outer_diameter / 2 * 1000
    small_r = core_diameter / 2 * 1000
    height = length * 1000

    triangles: list[tuple[tuple[float, float, float], ...]] = []
    for i in range(sections):
        a0 = 2 * math.pi * i / sections
        a1 = 2 * math.pi * (i + 1) / sections
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        ob0 = (big_r * c0, big_r * s0, 0.0)
        ob1 = (big_r * c1, big_r * s1, 0.0)
        ot0 = (big_r * c0, big_r * s0, height)
        ot1 = (big_r * c1, big_r * s1, height)
        ib0 = (small_r * c0, small_r * s0, 0.0)
        ib1 = (small_r * c1, small_r * s1, 0.0)
        it0 = (small_r * c0, small_r * s0, height)
        it1 = (small_r * c1, small_r * s1, height)
        # outer wall (normal outward)
        triangles.append((ob0, ob1, ot1))
        triangles.append((ob0, ot1, ot0))
        # core wall (normal inward)
        triangles.append((ib0, it1, ib1))
        triangles.append((ib0, it0, it1))
        # bottom annulus (normal -z)
        triangles.append((ob0, ib0, ib1))
        triangles.append((ob0, ib1, ob1))
        # top annulus (normal +z)
        triangles.append((ot0, it1, it0))
        triangles.append((ot0, ot1, it1))

    parts = [b"IgnitionBench BATES grain segment".ljust(80, b"\0")]
    parts.append(struct.pack("<I", len(triangles)))
    for v1, v2, v3 in triangles:
        ux = (v2[0] - v1[0], v2[1] - v1[1], v2[2] - v1[2])
        vx = (v3[0] - v1[0], v3[1] - v1[1], v3[2] - v1[2])
        n = (
            ux[1] * vx[2] - ux[2] * vx[1],
            ux[2] * vx[0] - ux[0] * vx[2],
            ux[0] * vx[1] - ux[1] * vx[0],
        )
        mag = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        parts.append(
            struct.pack(
                "<12fH",
                n[0] / mag, n[1] / mag, n[2] / mag,
                *v1, *v2, *v3,
                0,
            )
        )
    return b"".join(parts)
