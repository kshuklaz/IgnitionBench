"""Binary STL export of grain geometry, for 3D printing molds or CAD import.

The segment cross-section is an outer circle with a star-shaped inner
boundary (core circle fused with tapered radial slit wedges), so the whole
solid meshes cleanly as radial strips: at each sample angle the inner
radius r_in(θ) is computed exactly from the wedge geometry, and every
angular step contributes two triangles each on the top face, bottom face,
inner wall, and outer wall — a watertight mesh by construction.
"""

from __future__ import annotations

import math
import struct


def _inner_radius(
    theta: float,
    core_r: float,
    slit_count: int,
    slit_depth: float,
    slit_width: float,
    slit_taper: float,
) -> float:
    """Distance from the axis to the void boundary along the ray at theta."""
    if slit_count == 0:
        return core_r
    mouth_half = slit_width / 2
    tip_half = mouth_half * slit_taper
    narrowing = (mouth_half - tip_half) / slit_depth  # width lost per unit depth
    best = core_r
    for k in range(slit_count):
        axis = 2 * math.pi * k / slit_count
        delta = math.atan2(math.sin(theta - axis), math.cos(theta - axis))
        cos_d, sin_d = math.cos(delta), abs(math.sin(delta))
        if cos_d <= 0:
            continue
        # ray exits through the tapered side wall: r·|sin δ| = half(r·cos δ − rc)
        denom = sin_d + narrowing * cos_d
        if denom > 0:
            r_wall = (mouth_half + narrowing * core_r) / denom
            depth_at = r_wall * cos_d - core_r
            if 0 <= depth_at <= slit_depth:
                best = max(best, r_wall)
                continue
        # ray exits through the flat tip face
        r_tip = (core_r + slit_depth) / cos_d
        if r_tip * sin_d <= tip_half:
            best = max(best, r_tip)
    return best


def grain_segment_stl(
    outer_diameter: float,
    core_diameter: float,
    length: float,
    slit_count: int = 0,
    slit_depth: float = 0.0,
    slit_width: float = 0.0,
    slit_taper: float = 0.0,
    sections: int | None = None,
) -> bytes:
    """One grain segment (with optional slits) as binary STL, emitted in mm."""
    if not 0 < core_diameter < outer_diameter or length <= 0:
        raise ValueError("need 0 < core_diameter < outer_diameter and length > 0")
    if slit_count > 0:
        radial_web = (outer_diameter - core_diameter) / 2
        if not 0 < slit_depth < radial_web:
            raise ValueError("slit_depth must be positive and less than the radial web")
        if slit_width <= 0 or not 0 <= slit_taper <= 1:
            raise ValueError("need slit_width > 0 and 0 <= slit_taper <= 1")
    if sections is None:
        sections = 96 if slit_count == 0 else 720

    big_r = outer_diameter / 2 * 1000
    core_r = core_diameter / 2 * 1000
    height = length * 1000
    inner = [
        _inner_radius(
            2 * math.pi * i / sections,
            core_r,
            slit_count,
            slit_depth * 1000,
            slit_width * 1000,
            slit_taper,
        )
        for i in range(sections)
    ]

    triangles: list[tuple[tuple[float, float, float], ...]] = []
    for i in range(sections):
        j = (i + 1) % sections
        a0 = 2 * math.pi * i / sections
        a1 = 2 * math.pi * j / sections
        c0, s0, c1, s1 = math.cos(a0), math.sin(a0), math.cos(a1), math.sin(a1)
        ob = ((big_r * c0, big_r * s0, 0.0), (big_r * c1, big_r * s1, 0.0))
        ot = ((big_r * c0, big_r * s0, height), (big_r * c1, big_r * s1, height))
        ib = ((inner[i] * c0, inner[i] * s0, 0.0), (inner[j] * c1, inner[j] * s1, 0.0))
        it = ((inner[i] * c0, inner[i] * s0, height), (inner[j] * c1, inner[j] * s1, height))
        # outer wall (normal outward)
        triangles.append((ob[0], ob[1], ot[1]))
        triangles.append((ob[0], ot[1], ot[0]))
        # inner wall (normal into the void)
        triangles.append((ib[0], it[1], ib[1]))
        triangles.append((ib[0], it[0], it[1]))
        # bottom face (normal -z)
        triangles.append((ob[0], ib[0], ib[1]))
        triangles.append((ob[0], ib[1], ob[1]))
        # top face (normal +z)
        triangles.append((ot[0], it[1], it[0]))
        triangles.append((ot[0], ot[1], it[1]))

    parts = [b"IgnitionBench grain segment".ljust(80, b"\0")]
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
