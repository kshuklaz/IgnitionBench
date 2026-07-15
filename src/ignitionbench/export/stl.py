"""Binary STL export of grain geometry, for 3D printing molds or CAD import.

The triangle mesh comes from ``propellant.grain3d.segment_mesh`` — the same
exact parametric surface the burn model and the 3D viewer use — so the STL
always matches what was simulated. With slits the cut runs from the motor
front through the stack, so segments differ: a multi-segment export emits
every segment as its own solid, spaced along the axis in stack order
(forward segment first, at z = 0).
"""

from __future__ import annotations

import math
import struct

import numpy as np

from ignitionbench.propellant.grain3d import _STACK_GAP, FaceSlitGrain, segment_mesh


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
    segment_count: int = 1,
) -> bytes:
    """Grain geometry as binary STL, in mm. ``segment_count`` > 1 emits the
    whole stack (one solid per segment) so the per-segment slit continuation
    is preserved."""
    if slit_count > 0:
        # validate the cut against the whole stack, not one segment
        FaceSlitGrain(
            segment_count, outer_diameter, core_diameter, length,
            slit_count=slit_count, slit_depth=slit_depth, slit_width=slit_width,
            slit_length=slit_length, slit_taper=slit_taper,
        )
    solids = []
    for i in range(segment_count):
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
            cut_offset=i * length,
        )
        tris = np.concatenate([mesh.burning, mesh.outer])
        tris = tris + np.array([0.0, 0.0, i * (length + _STACK_GAP)])
        solids.append(tris)
    triangles = np.concatenate(solids) * 1000  # m → mm

    parts = [b"IgnitionBench grain".ljust(80, b"\0")]
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
