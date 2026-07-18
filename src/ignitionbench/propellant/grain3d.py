"""Face-slit grain geometry via 3D distance-field burn regression.

Real grain slits are saw cuts made from the forward (non-nozzle) end of the
motor: each is one continuous kerf that reaches ``slit_depth`` outward from
the core, runs ``slit_length`` aft through the grain stack — carrying over
from one segment into the next — and tapers to ``slit_taper`` of its mouth
size where the cut ends. It never passes through the web and never reaches
the nozzle-end face. Segments therefore differ: the forward segment carries
the deepest part of the cut, later segments its shallower continuation or a
plain bore.

For uniform normal regression the burn front after web x is exactly the set
of points at distance x from the initial void surface. A Euclidean distance
transform over each distinct segment's voxel grid gives every propellant
voxel's distance to the void; remaining volume is
V(x) = #{voxels: dist > x}·cellvol and burning area is Ab(x) = -dV/dx.
The ignition surface (x = 0) instead comes from the exact parametric mesh
shared with the STL exporter, which is also what the 3D viewer renders.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple

import numpy as np
from scipy import ndimage

from .database import Propellant

_MAX_VOXELS = 3_000_000  # keeps each distance transform around a second
_PAD = 4  # voxel layers of chamber void beyond the faces
_TAPER_RINGS = 14  # mesh slices through the tapered cut zone
_STACK_GAP = 0.003  # m, spacing between segments in stack views


class _Table3D(NamedTuple):
    sorted_dists: np.ndarray  # per propellant voxel of one segment, m
    cell: float  # m
    cell_volume: float  # m³
    max_dist: float  # m
    # distance field on the (u, z) plane through slit axis 0,
    # u radial 0→outer radius, z axial 0 (forward face) → L (aft face)
    section_dist: np.ndarray


@dataclass(frozen=True)
class FaceSlitGrain:
    """BATES-style segment stack with tapered slits cut from the motor front.

    Each slit is a straight-sided kerf ``slit_width`` across, reaching
    ``slit_depth`` outward from the core. It starts at the forward face of
    the forward segment and runs ``slit_length`` aft along the propellant
    (continuing across segment joints), scaling linearly down to
    ``slit_taper`` of its mouth size where the cut ends. All dimensions
    metres.
    """

    segment_count: int
    outer_diameter: float
    core_diameter: float
    segment_length: float
    slit_count: int = 0
    slit_depth: float = 0.0  # radial reach beyond the core
    slit_width: float = 0.0  # kerf width at the mouth
    slit_length: float = 0.0  # axial reach aft from the motor front
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
            total = self.segment_count * self.segment_length
            if not 0 < self.slit_length < total:
                raise ValueError(
                    f"slit_length must be positive and less than the grain stack "
                    f"({total * 1000:.1f} mm) — cuts cannot pass through to the "
                    "nozzle-end face."
                )
            if self.slit_width <= 0:
                raise ValueError("slit_width must be positive when slits are present")
            if not 0 <= self.slit_taper <= 1:
                raise ValueError("slit_taper must be between 0 (pointed) and 1 (straight)")
            mouth_angle = 2 * math.asin(min(self.slit_width / self.core_diameter, 1.0))
            if self.slit_count * mouth_angle >= 2 * math.pi * 0.9:
                raise ValueError("slit mouths overlap — fewer or narrower slits needed")

    # ---- per-segment cut bookkeeping ----

    def _offsets(self) -> list[float]:
        """Propellant distance from the motor front to each segment's
        forward face (gaps between segments carry no cut length)."""
        return [i * self.segment_length for i in range(self.segment_count)]

    def _scale_at(self, along: float) -> float:
        """Kerf cross-section scale a given distance along the cut."""
        if self.slit_count == 0 or along >= self.slit_length:
            return 0.0
        return 1 - (along / self.slit_length) * (1 - self.slit_taper)

    def _cut_key(self, offset: float) -> float:
        """Cache key: every segment past the cut shares the plain table."""
        return min(offset, self.slit_length) if self.slit_count else 0.0

    # ---- regression tables ----

    @property
    def web_thickness(self) -> float:
        if self.slit_count == 0:
            return min(
                (self.outer_diameter - self.core_diameter) / 2, self.segment_length / 2
            )
        return max(
            _build_table(self, self._cut_key(off)).max_dist for off in self._offsets()
        )

    def _area_numeric(self, table: _Table3D, web_burned: float) -> float:
        """-dV/dx for one segment (m²), central differences on its table.

        A band anchored at zero over-counts jagged raster voxels, so small x
        extrapolates linearly from two interior estimates (exact for fronts
        of constant curvature).
        """
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
            return sum(
                _ignition_area(self, self._cut_key(off)) for off in self._offsets()
            )
        if web_burned >= self.web_thickness:
            return 0.0
        return sum(
            self._area_numeric(_build_table(self, self._cut_key(off)), web_burned)
            for off in self._offsets()
        )

    def volume(self, web_burned: float = 0.0) -> float:
        if web_burned < 0:
            raise ValueError("web_burned cannot be negative")
        if web_burned == 0.0:
            annulus = (
                math.pi / 4 * (self.outer_diameter**2 - self.core_diameter**2)
                * self.segment_length
            )
            pockets = self.slit_count * _pocket_volume(self)
            return self.segment_count * annulus - pockets
        if web_burned >= self.web_thickness:
            return 0.0
        total = 0.0
        for off in self._offsets():
            table = _build_table(self, self._cut_key(off))
            idx = np.searchsorted(table.sorted_dists, web_burned, side="right")
            total += float(table.sorted_dists.size - idx) * table.cell_volume
        return total

    def port_area(self, web_burned: float = 0.0) -> float:
        """Flow channel at the aft (nozzle-end) face — a plain core there,
        since the cut never reaches it."""
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
    """Volume of one whole slit cut (m³): its mouth cross-section integrated
    along the cut as it scales down to the taper (Simpson's rule)."""
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


def _rings(
    length: float,
    slit_count: int,
    slit_length: float,
    slit_taper: float,
    cut_offset: float,
):
    """(z, scale) mesh rings for one segment whose forward face sits
    ``cut_offset`` along the cut. A duplicate-z pair marks the flat annular
    wall where the cut ends inside this segment; a cut that carries through
    leaves an open mouth on the aft face for the next segment."""
    if slit_count == 0 or cut_offset >= slit_length:
        return [(0.0, 0.0), (length, 0.0)]

    def scale(along: float) -> float:
        return 1 - (along / slit_length) * (1 - slit_taper)

    local = min(length, slit_length - cut_offset)
    rings = []
    for j in range(_TAPER_RINGS + 1):
        z = local * j / _TAPER_RINGS
        rings.append((z, scale(cut_offset + z)))
    if local < length:
        rings.append((local, 0.0))
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
    cut_offset: float = 0.0,
) -> SegmentMesh:
    """Watertight triangle mesh of one grain segment (metres). ``slit_length``
    is the whole cut's length; ``cut_offset`` is how far along the cut this
    segment's forward face sits."""
    if not 0 < core_diameter < outer_diameter or length <= 0:
        raise ValueError("need 0 < core_diameter < outer_diameter and length > 0")
    if slit_count > 0:
        radial_web = (outer_diameter - core_diameter) / 2
        if not 0 < slit_depth < radial_web:
            raise ValueError(
                "slit_depth must be positive and less than the radial web — "
                "slits cannot go all the way through the web."
            )
        if slit_length <= 0 or slit_width <= 0 or not 0 <= slit_taper <= 1:
            raise ValueError(
                "need slit_length > 0, slit_width > 0 and 0 <= slit_taper <= 1"
            )
    if sections is None:
        sections = 720 if slit_count else 96
    R = outer_diameter / 2
    rc = core_diameter / 2
    axes = [2 * math.pi * k / slit_count - math.pi / 2 for k in range(slit_count)]
    rings = _rings(length, slit_count, slit_length, slit_taper, cut_offset)

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
        # inner walls and the end-of-cut annulus, normals toward the void
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
def _ignition_area(grain: FaceSlitGrain, cut_offset: float) -> float:
    """Exact burning surface of one segment at x = 0 from the parametric mesh."""
    mesh = segment_mesh(
        grain.outer_diameter, grain.core_diameter, grain.segment_length,
        slit_count=grain.slit_count, slit_depth=grain.slit_depth,
        slit_width=grain.slit_width, slit_length=grain.slit_length,
        slit_taper=grain.slit_taper,
        sections=720 if grain.slit_count else 128,
        cut_offset=cut_offset,
    )
    tris = mesh.burning
    ab = tris[:, 1] - tris[:, 0]
    ac = tris[:, 2] - tris[:, 0]
    return float(np.sum(0.5 * np.linalg.norm(np.cross(ab, ac), axis=1)))


# ---- voxel tables ----


def _radial_slice(
    dist: np.ndarray, axis: np.ndarray, cell: float, nz: int, ang: float
) -> np.ndarray:
    """Interpolated (u, z) slice of the distance field along one radial ray,
    u ascending from the motor axis outward."""
    nu = len(axis) // 2
    us = (np.arange(nu) + 0.5) * cell
    ix = (us * math.cos(ang) - axis[0]) / cell
    iy = (us * math.sin(ang) - axis[0]) / cell
    coords = np.empty((3, nu, nz))
    coords[0] = ix[:, None]
    coords[1] = iy[:, None]
    coords[2] = np.arange(nz)[None, :]
    return ndimage.map_coordinates(dist, coords, order=1).astype(np.float32)


@lru_cache(maxsize=16)
def _build_table(grain: FaceSlitGrain, cut_offset: float) -> _Table3D:
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
    if grain.slit_count and cut_offset < grain.slit_length:
        along = cut_offset + zc
        scale = np.where(
            along < grain.slit_length,
            1 - (along / grain.slit_length) * (1 - grain.slit_taper),
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

    # full-bore (u, z) section for the regression view: the top half is the
    # ray midway between slits, the bottom half the ray through slit axis 0,
    # so the display shows both the slitted and the plain side of the bore
    through = _radial_slice(dist, axis, cell, nz, -math.pi / 2)
    ang = (
        -math.pi / 2 + math.pi / grain.slit_count
        if grain.slit_count
        else math.pi / 2
    )
    between = _radial_slice(dist, axis, cell, nz, ang)
    section = np.vstack([between[::-1], through])  # rows run +R → -R

    return _Table3D(
        sorted_dists=dists,
        cell=cell,
        cell_volume=cell**3,
        max_dist=float(dists[-1]) if dists.size else 0.0,
        section_dist=section,
    )


def regression_section(grain: FaceSlitGrain, max_u: int = 128, max_z: int = 220) -> dict:
    """Downsampled full-bore (u, z) distance field for the UI: u spans the
    bore diameter (top half between slits, bottom half through a slit), z
    runs along the whole grain stack from the forward face to the nozzle
    end, with the inter-segment gaps as void."""
    sections = [
        _build_table(grain, grain._cut_key(off)).section_dist
        for off in grain._offsets()
    ]
    table = _build_table(grain, grain._cut_key(0.0))
    gap_cols = max(int(round(_STACK_GAP / table.cell)), 1)
    gap = np.zeros((sections[0].shape[0], gap_cols), dtype=np.float32)
    columns: list[np.ndarray] = []
    for j, sec in enumerate(sections):
        if j:
            columns.append(gap)
        columns.append(sec)
    full = np.concatenate(columns, axis=1)
    su = max(1, math.ceil(full.shape[0] / max_u))
    sz = max(1, math.ceil(full.shape[1] / max_z))
    # block-mean pooling: striding would turn the slit taper into a staircase
    pu = (-full.shape[0]) % su
    pz = (-full.shape[1]) % sz
    full = np.pad(full, ((0, pu), (0, pz)), mode="edge")
    ds = full.reshape(full.shape[0] // su, su, full.shape[1] // sz, sz).mean(
        axis=(1, 3)
    )
    return {
        "du_mm": table.cell * su * 1000,
        "dz_mm": table.cell * sz * 1000,
        "nu": ds.shape[0],
        "nz": ds.shape[1],
        "web_mm": grain.web_thickness * 1000,
        "cell_mm": table.cell * 1000,
        "dist_mm": [round(float(v) * 1000, 2) for v in ds.ravel(order="C")],
    }
