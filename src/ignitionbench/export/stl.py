"""Binary STL export of grain geometry, for 3D printing molds or CAD import.

The triangle mesh comes from ``propellant.grain3d.segment_mesh`` — the same
exact parametric surface the burn model and the 3D viewer use — so the STL
always matches what was simulated: tapered face slits included.
"""

from __future__ import annotations

import math
import struct

import numpy as np

from ignitionbench.propellant.grain3d import segment_mesh


def grain_segment_stl(
    outer_diameter: float,
    core_diameter: float,
    length: float,
    slit_count: int = 0,
    slit_depth: float = 0.0,
    slit_width: float = 0.0,
    slit_length: float = 0.0,
    slit_taper: float = 0.0,
    sections: int | None = None,
) -> bytes:
    """One grain segment (with optional face slits) as binary STL, in mm."""
    mesh = segment_mesh(
        outer_diameter,
        core_diameter,
        length,
        slit_count=slit_count,
        slit_depth=slit_depth,
        slit_width=slit_width,
        slit_length=slit_length,
        slit_taper=slit_taper,
        sections=sections,
    )
    triangles = np.concatenate([mesh.burning, mesh.outer]) * 1000  # m → mm

    parts = [b"IgnitionBench grain segment".ljust(80, b"\0")]
    parts.append(struct.pack("<I", len(triangles)))
    for v1, v2, v3 in triangles:
        u = v2 - v1
        w = v3 - v1
        n = (
            u[1] * w[2] - u[2] * w[1],
            u[2] * w[0] - u[0] * w[2],
            u[0] * w[1] - u[1] * w[0],
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
