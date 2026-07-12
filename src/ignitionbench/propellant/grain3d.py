"""Face-slit grain geometry via 3D distance-field burn regression.

Real grain slits are saw cuts made into the forward (non-nozzle) face of a
segment: they reach ``slit_depth`` outward from the core, run
``slit_length`` aft from that face, and taper to ``slit_taper`` of their
mouth size where the cut ends — they never pass through the web and never
reach the nozzle-end face. The burning surface is therefore genuinely
three-dimensional (the cut narrows as the front advances), so the
regression is computed on a voxel grid:

For uniform normal regression the burn front after web x is exactly the
set of points at distance x from the initial void surface. A Euclidean
distance transform over the segment voxel grid gives every propellant
voxel's distance to the void; remaining volume is
V(x) = #{voxels: dist > x}·cellvol and burning area is Ab(x) = -dV/dx.
The ignition surface (x = 0) instead comes from the exact parametric mesh
shared with the STL exporter and the 3D viewer, so the design tab needs no
voxel table.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple

import numpy as np
from scipy import ndimage

from .database import Propellant

_MAX_VOXELS = 3_000_000  # keeps the distance transform around a second
_PAD = 4  # voxel layers of chamber void beyond the face
_TAPER_RINGS = 14  # mesh slices through the tapered cut zone


class _Table3D(NamedTuple):
    sorted_dists: np.ndarray  # per half-segment propellant voxel, m
    cell: float  # m
    cell_volume: float  # m³
    max_dist: float  # m
    # distance field on the (u, z) plane through slit axis 0,
    # u radial 0→outer radius, z axial 0 (slit face) → L (nozzle face)
    section_dist: np.ndarray


@dataclass(frozen=True)
class FaceSlitGrain:
    """BATES-style segment stack with tapered slits cut into the forward face.

    Each slit is a straight-sided kerf ``slit_width`` across, reaching
    ``slit_depth`` outward from the core and ``slit_length`` aft from the
    forward (non-nozzle) face, scaling linearly down to ``slit_taper`` of
    its mouth size where the cut ends. Every segment carries the same evenly
    spaced pattern. All dimensions metres.
    """

    segment_count: int
    outer_diameter: float
    core_diameter: float
    segment_length: float
    slit_count: int = 0
    slit_depth: float = 0.0  # radial reach beyond the core
    slit_width: float = 0.0  # kerf width at the face
    slit_length: float = 0.0  # axial reach aft from the forward face
    slit_taper: float = 0.0  # cross-section scale where the cut ends, 0..1

    def __post_init__(self) -> None:
        if self.segment_count < 1:
            raise ValueError("segment_count must be at least 1")
        if not 0 < self.core_diameter < self.outer_diameter:
            raise ValueError("need 0 < core_diameter < outer_diameter")
        if self.segment_length <= 0:
            raise ValueError("segment_length must be positive")
        if self.slit_count < 0:
            raise ValueError("slit_count cannot be negative")
        if self.slit_count > 0:
            radial_web = (self.outer_diameter - self.core_diameter) / 2
            if not 0 < self.slit_depth < radial_web:
                raise ValueError(
                    f"slit_depth must be positive and less than the radial web "
                    f"({radial_web * 1000:.1f} mm) — slits cannot go all the way "
                    "through the web."
                )
            if not 0 < self.slit_length < self.segment_length:
                raise ValueError(
                    f"slit_length must be positive and less than the segment "
                    f"({self.segment_length * 1000:.1f} mm) — cuts cannot pass "
                    "through to the nozzle-end face."
                )
            if self.slit_width <= 0:
                raise ValueError("slit_width must be positive when slits are present")
            if not 0 <= self.slit_taper <= 1:
                raise ValueError("slit_taper must be between 0 (pointed) and 1 (straight)")
            mouth_angle = 2 * math.asin(min(self.slit_width / self.core_diameter, 1.0))
            if self.slit_count * mouth_angle >= 2 * math.pi * 0.9:
                raise ValueError("slit mouths overlap — fewer or narrower slits needed")

    # ---- regression table ----

    @property
    def _table(self) -> _Table3D:
        return _build_table(self)

    @property
    def web_thickness(self) -> float:
        if self.slit_count == 0:
            return min(
                (self.outer_diameter - self.core_diameter) / 2, self.segment_length / 2
            )
        return self._table.max_dist

    def _area_numeric(self, web_burned: float) -> float:
        """-dV/dx per half segment (m²), central differences on the table.

        A band anchored at zero over-counts jagged raster voxels, so small x
        extrapolates linearly from two interior estimates (exact for fronts
        of constant curvature).
        """
        table = self._table
        delta = 2 * table.cell

        def central(x: float) -> float:
            hi = np.searchsorted(table.sorted_dists, x + delta, side="right")
            lo = np.searchsorted(table.sorted_dists, x - delta, side="right")
            return max(float(hi - lo) * table.cell_volume / (2 * delta), 0.0)

        if web_burned >= 4 * delta:
            return central(web_burned)
        near, far = central(4 * delta), central(8 * delta)
        return max(near + (near - far) * (4 * delta - web_burned) / (4 * delta), 0.0)

    # ---- BatesGrain-compatible interface ----

    def burning_area(self, web_burned: float = 0.0) -> float:
        if web_burned < 0:
            raise ValueError("web_burned cannot be negative")
        if web_burned == 0.0:
            # exact, from the parametric mesh — no voxel table needed, so the
            # design tab stays instant
            return self.segment_count * _ignition_area(self)
        if web_burned >= self.web_thickness:
            return 0.0
        return self.segment_count * self._area_numeric(web_burned)

    def volume(self, web_burned: float = 0.0) -> float:
        if web_burned < 0:
            raise ValueError("web_burned cannot be negative")
        if web_burned == 0.0:
            annulus = (
                math.pi / 4 * (self.outer_diameter**2 - self.core_diameter**2)
                * self.segment_length
            )
            pockets = self.slit_count * _pocket_volume(self)
            return self.segment_count * (annulus - pockets)
        if web_burned >= self.web_thickness:
            return 0.0
        table = self._table
        idx = np.searchsorted(table.sorted_dists, web_burned, side="right")
        remaining = float(table.sorted_dists.size - idx) * table.cell_volume
        return self.segment_count * remaining

    def port_area(self, web_burned: float = 0.0) -> float:
        """Flow channel at the aft (nozzle-end) face — a plain core there,
        since the slits are cut into the forward face only."""
        rc = self.core_diameter / 2 + web_burned
        return math.pi * min(rc, self.outer_diameter / 2) ** 2

    def propellant_mass(self, propellant: Propellant, web_burned: float = 0.0) -> float:
        return self.volume(web_burned) * propellant.density


def _mouth_area(rc: float, w2: float, depth: float) -> float:
    """Area of one slit mouth outside the core circle: the rectangle
    |v| ≤ w2, u ≤ rc+depth minus the circular segment it overlaps."""
    if w2 <= 0 or depth <= 0:
        return 0.0
    w2 = min(w2, rc)
    circ = w2 * math.sqrt(rc * rc - w2 * w2) + rc * rc * math.asin(w2 / rc)
    return max(2 * w2 * (rc + depth) - circ, 0.0)


@lru_cache(maxsize=64)
def _pocket_volume(grain: FaceSlitGrain) -> float:
    """Volume of one slit pocket (m³): its mouth cross-section integrated
    over the cut length as it scales down to the taper (Simpson's rule)."""
    if grain.slit_count == 0:
        return 0.0
    rc = grain.core_diameter / 2
    n = 64
    dz = grain.slit_length / n
    total = 0.0
    for j in range(n + 1):
        s = 1 - (j / n) * (1 - grain.slit_taper)
        area = _mouth_area(rc, (grain.slit_width / 2) * s, grain.slit_depth * s)
        weight = 1 if j in (0, n) else (4 if j % 2 else 2)
        total += weight * area
    return total * dz / 3


# ---- parametric surface, shared by STL export, 3D viewer, and Ab(0) ----


def _inner_radius(theta: float, rc: float, w2: float, tip_r: float, axes: list[float]) -> float:
    """Distance from the axis to the void boundary along the ray at theta,
    for a cross-section where the kerfs have half-width w2 and reach tip_r."""
    best = rc
    if w2 <= 0:
        return best
    for axis in axes:
        delta = math.atan2(math.sin(theta - axis), math.cos(theta - axis))
        c = math.cos(delta)
        if c <= 0:
            continue
        s = abs(math.sin(delta))
        if tip_r * s <= w2:
            best = max(best, tip_r / c)  # ray exits through the flat end wall
        elif w2 / s > rc:
            best = max(best, w2 / s)  # ray exits through a side wall
    return best


def _rings(length: float, slit_count: int, slit_length: float, slit_taper: float):
    """(z, scale) mesh rings from the forward face (z = 0, where the slits
    are cut) to the nozzle-end face. The duplicate-z pair marks the flat
    annular wall where the cut ends."""
    if slit_count == 0:
        return [(0.0, 0.0), (length, 0.0)]
    rings = []
    for j in range(_TAPER_RINGS + 1):
        f = j / _TAPER_RINGS
        rings.append((slit_length * f, 1 - f * (1 - slit_taper)))
    rings.append((slit_length, 0.0))
    rings.append((length, 0.0))
    return rings


class SegmentMesh(NamedTuple):
    burning: np.ndarray  # (n, 3, 3) core, slit, and face triangles, m
    outer: np.ndarray  # (n, 3, 3) inhibited outer wall triangles, m


def segment_mesh(
    outer_diameter: float,
    core_diameter: float,
    length: float,
    slit_count: int = 0,
    slit_depth: float = 0.0,
    slit_width: float = 0.0,
    slit_length: float = 0.0,
    slit_taper: float = 0.0,
    sections: int | None = None,
) -> SegmentMesh:
    """Watertight triangle mesh of one grain segment (metres)."""
    # reuse the dataclass validation
    FaceSlitGrain(
        1, outer_diameter, core_diameter, length,
        slit_count=slit_count, slit_depth=slit_depth, slit_width=slit_width,
        slit_length=slit_length, slit_taper=slit_taper,
    )
    if sections is None:
        sections = 720 if slit_count else 96
    R = outer_diameter / 2
    rc = core_diameter / 2
    axes = [2 * math.pi * k / slit_count - math.pi / 2 for k in range(slit_count)]
    rings = _rings(length, slit_count, slit_length, slit_taper)

    thetas = np.linspace(0.0, 2 * math.pi, sections + 1)
    # inner radius per (ring, theta)
    r_in = np.empty((len(rings), sections + 1))
    for j, (_, scale) in enumerate(rings):
        w2 = (slit_width / 2) * scale
        tip = rc + slit_depth * scale
        for i, th in enumerate(thetas):
            r_in[j, i] = _inner_radius(th, rc, w2, tip, axes)
    r_in[:, -1] = r_in[:, 0]  # closed seam

    cos, sin = np.cos(thetas), np.sin(thetas)

    def pt(j: int, i: int) -> tuple[float, float, float]:
        return (r_in[j, i] * cos[i], r_in[j, i] * sin[i], rings[j][0])

    burning: list[tuple] = []
    outer: list[tuple] = []

    def quad(dest, a, b, c, d):
        dest.append((a, b, c))
        dest.append((a, c, d))

    for i in range(sections):
        # inner walls and end-of-cut annuli, normals toward the void
        for j in range(len(rings) - 1):
            z0, z1 = rings[j][0], rings[j + 1][0]
            if z1 > z0:  # wall band, normal toward the axis
                quad(burning, pt(j, i), pt(j + 1, i), pt(j + 1, i + 1), pt(j, i + 1))
            else:  # flat annulus where the cut ends: void below, normal -z
                lo, hi = (j + 1, j) if r_in[j, i] >= r_in[j + 1, i] else (j, j + 1)
                if r_in[hi, i] - r_in[lo, i] < 1e-12 and r_in[hi, i + 1] - r_in[lo, i + 1] < 1e-12:
                    continue
                quad(burning, pt(lo, i), pt(lo, i + 1), pt(hi, i + 1), pt(hi, i))
        # end faces, annulus from the void boundary to the outer wall
        j0, j1 = 0, len(rings) - 1
        quad(
            burning,
            pt(j0, i), pt(j0, i + 1),
            (R * cos[i + 1], R * sin[i + 1], 0.0), (R * cos[i], R * sin[i], 0.0),
        )
        quad(
            burning,
            pt(j1, i),
            (R * cos[i], R * sin[i], length), (R * cos[i + 1], R * sin[i + 1], length),
            pt(j1, i + 1),
        )
        # inhibited outer wall
        quad(
            outer,
            (R * cos[i], R * sin[i], 0.0), (R * cos[i + 1], R * sin[i + 1], 0.0),
            (R * cos[i + 1], R * sin[i + 1], length), (R * cos[i], R * sin[i], length),
        )

    def clean(tris: list[tuple]) -> np.ndarray:
        arr = np.array(tris, dtype=float)
        ab = arr[:, 1] - arr[:, 0]
        ac = arr[:, 2] - arr[:, 0]
        areas = 0.5 * np.linalg.norm(np.cross(ab, ac), axis=1)
        return arr[areas > 1e-14]

    return SegmentMesh(burning=clean(burning), outer=clean(outer))


@lru_cache(maxsize=64)
def _ignition_area(grain: FaceSlitGrain) -> float:
    """Exact burning surface of one segment at x = 0 from the parametric mesh."""
    mesh = segment_mesh(
        grain.outer_diameter, grain.core_diameter, grain.segment_length,
        slit_count=grain.slit_count, slit_depth=grain.slit_depth,
        slit_width=grain.slit_width, slit_length=grain.slit_length,
        slit_taper=grain.slit_taper,
        sections=720 if grain.slit_count else 128,
    )
    tris = mesh.burning
    ab = tris[:, 1] - tris[:, 0]
    ac = tris[:, 2] - tris[:, 0]
    return float(np.sum(0.5 * np.linalg.norm(np.cross(ab, ac), axis=1)))


# ---- voxel table ----


@lru_cache(maxsize=8)
def _build_table(grain: FaceSlitGrain) -> _Table3D:
    R = grain.outer_diameter / 2
    rc = grain.core_diameter / 2
    length = grain.segment_length

    cell = (grain.outer_diameter**2 * length / _MAX_VOXELS) ** (1 / 3)
    cell = max(cell, grain.outer_diameter / 420)
    nxy = max(int(round(grain.outer_diameter / cell)), 32)
    cell = grain.outer_diameter / nxy
    nz = max(int(math.ceil(length / cell)), 8)

    axis = np.linspace(-R + cell / 2, R - cell / 2, nxy)
    xs, ys = np.meshgrid(axis, axis, indexing="ij")
    rr = np.hypot(xs, ys)
    zc = (np.arange(nz) + 0.5) * cell  # voxel centres, forward face at z = 0

    void = np.broadcast_to((rr <= rc)[:, :, None], (nxy, nxy, nz)).copy()
    if grain.slit_count:
        scale = np.where(
            zc < grain.slit_length,
            1 - (zc / grain.slit_length) * (1 - grain.slit_taper),
            0.0,
        )
        w2 = (grain.slit_width / 2) * scale  # per z slice
        tip = rc + grain.slit_depth * scale
        for k in range(grain.slit_count):
            a = 2 * math.pi * k / grain.slit_count - math.pi / 2
            u = xs * math.cos(a) + ys * math.sin(a)
            v = -xs * math.sin(a) + ys * math.cos(a)
            void |= (
                (u[:, :, None] >= 0)
                & (u[:, :, None] <= tip[None, None, :])
                & (np.abs(v)[:, :, None] <= w2[None, None, :])
            )

    # chamber void beyond both faces
    pad = np.ones((nxy, nxy, _PAD), dtype=bool)
    full = np.concatenate([pad, void, pad], axis=2)
    # surface sits about half a voxel closer than the nearest void centre
    dist = (ndimage.distance_transform_edt(~full) - 0.5) * cell
    dist = np.maximum(dist[:, :, _PAD:-_PAD], 0.0)

    inside = (~void) & (rr <= R)[:, :, None]
    dists = np.sort(dist[inside].ravel())

    # (u, z) section through slit axis 0 = -y for the regression view
    ixc = int(np.argmin(np.abs(axis)))
    idx = np.where(axis <= cell / 2)[0][::-1]  # u ascending 0 → R
    section = dist[ixc, idx, :].astype(np.float32)

    return _Table3D(
        sorted_dists=dists,
        cell=cell,
        cell_volume=cell**3,
        max_dist=float(dists[-1]) if dists.size else 0.0,
        section_dist=section,
    )


def regression_section(grain: FaceSlitGrain, max_u: int = 96, max_z: int = 150) -> dict:
    """Downsampled (u, z) distance field through a slit axis for the UI:
    u radial from the motor axis, z from the forward (slit) face to the
    nozzle-end face."""
    table = grain._table
    full = table.section_dist  # (nu, nz)
    su = max(1, math.ceil(full.shape[0] / max_u))
    sz = max(1, math.ceil(full.shape[1] / max_z))
    ds = full[::su, ::sz]
    return {
        "du_mm": table.cell * su * 1000,
        "dz_mm": table.cell * sz * 1000,
        "nu": ds.shape[0],
        "nz": ds.shape[1],
        "web_mm": table.max_dist * 1000,
        "cell_mm": table.cell * 1000,
        "dist_mm": [round(float(v) * 1000, 2) for v in ds.ravel(order="C")],
    }
