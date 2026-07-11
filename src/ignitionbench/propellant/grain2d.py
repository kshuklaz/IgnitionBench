"""Slotted grain geometry via 2D distance-field burn regression.

A slotted BATES grain is a hollow cylinder with N tapered radial slits cut
from the core partway into the web (never all the way through). No clean
closed form exists for the burning perimeter once slits start rounding and
merging into the core, so we regress the cross-section numerically:

For uniform normal regression, the burn front after distance x is exactly
the set of points at distance x from the initial void surface. On a grid,
the Euclidean distance transform gives every propellant cell's distance to
the void, so remaining cross-section area is A(x) = #{cells: dist > x} and
the burning perimeter is P(x) = -dA/dx. Burning area then assembles like
BATES: Ab(x) = N_seg · (P(x)·(L-2x) + 2·A(x)).

Grid resolution is ~D/512, giving A and P within a couple of percent of
analytic values (verified against BatesGrain in tests).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple

import numpy as np
from scipy import ndimage

from .database import Propellant

_GRID = 512


class _RegressionTable(NamedTuple):
    sorted_dists: np.ndarray  # distances of propellant cells to void, sorted (m)
    cell_area: float  # m²
    cell_size: float  # m
    max_dist: float  # m, radial web


@dataclass(frozen=True)
class SlottedGrain:
    """BATES-style segment stack with tapered radial slits cut from the core.

    Slits are evenly spaced wedges: `slit_width` across the mouth at the core
    surface, narrowing to `slit_width · slit_taper` at the tip, `slit_depth`
    into the web. They run the full segment length. All dimensions metres.
    """

    segment_count: int
    outer_diameter: float
    core_diameter: float
    segment_length: float
    slit_count: int = 0
    slit_depth: float = 0.0
    slit_width: float = 0.0
    slit_taper: float = 0.0  # tip width as a fraction of mouth width, 0..1

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
                    f"({radial_web * 1000:.1f} mm) — slits cannot go all the way through."
                )
            if self.slit_width <= 0:
                raise ValueError("slit_width must be positive when slits are present")
            if not 0 <= self.slit_taper <= 1:
                raise ValueError("slit_taper must be between 0 (pointed) and 1 (parallel)")
            mouth_angle = 2 * math.asin(
                min(self.slit_width / self.core_diameter, 1.0)
            )
            if self.slit_count * mouth_angle >= 2 * math.pi * 0.9:
                raise ValueError("slit mouths overlap — fewer or narrower slits needed")

    # ---- regression table ----

    @property
    def _table(self) -> _RegressionTable:
        return _build_table(self)

    @property
    def web_thickness(self) -> float:
        return min(self._table.max_dist, self.segment_length / 2)

    def cross_section_area(self, web_burned: float = 0.0) -> float:
        """Remaining propellant cross-section area (m²) after regression x."""
        table = self._table
        idx = np.searchsorted(table.sorted_dists, web_burned, side="right")
        return float((table.sorted_dists.size - idx) * table.cell_area)

    def burning_perimeter(self, web_burned: float = 0.0) -> float:
        """2D burning-front perimeter (m) after regression x, from -dA/dx.

        Central differences are unbiased away from x = 0, but a band anchored
        at zero over-counts jagged raster cells, so small x extrapolates
        linearly from two interior estimates (exact for circular fronts).
        """
        delta = 2 * self._table.cell_size

        def central(x: float) -> float:
            drop = self.cross_section_area(x - delta) - self.cross_section_area(x + delta)
            return max(drop / (2 * delta), 0.0)

        if web_burned >= 4 * delta:
            return central(web_burned)
        near, far = central(4 * delta), central(8 * delta)
        return max(near + (near - far) * (4 * delta - web_burned) / (4 * delta), 0.0)

    # ---- BatesGrain-compatible interface ----

    def burning_area(self, web_burned: float = 0.0) -> float:
        if web_burned < 0:
            raise ValueError("web_burned cannot be negative")
        if web_burned >= self.web_thickness:
            return 0.0
        length = self.segment_length - 2 * web_burned
        return self.segment_count * (
            self.burning_perimeter(web_burned) * length
            + 2 * self.cross_section_area(web_burned)
        )

    def volume(self, web_burned: float = 0.0) -> float:
        if web_burned < 0:
            raise ValueError("web_burned cannot be negative")
        if web_burned >= self.web_thickness:
            return 0.0
        length = self.segment_length - 2 * web_burned
        return self.segment_count * self.cross_section_area(web_burned) * length

    def port_area(self, web_burned: float = 0.0) -> float:
        disc = math.pi / 4 * self.outer_diameter**2
        return disc - self.cross_section_area(web_burned)

    def propellant_mass(self, propellant: Propellant, web_burned: float = 0.0) -> float:
        return self.volume(web_burned) * propellant.density


@lru_cache(maxsize=32)
def _build_table(grain: SlottedGrain) -> _RegressionTable:
    radius = grain.outer_diameter / 2
    core_r = grain.core_diameter / 2
    cell = grain.outer_diameter / _GRID

    axis = np.linspace(-radius + cell / 2, radius - cell / 2, _GRID)
    xs, ys = np.meshgrid(axis, axis)
    rr = np.hypot(xs, ys)

    void = rr <= core_r
    for k in range(grain.slit_count):
        theta = 2 * math.pi * k / grain.slit_count
        # coordinates along (u) and across (v) the slit axis
        u = xs * math.cos(theta) + ys * math.sin(theta)
        v = -xs * math.sin(theta) + ys * math.cos(theta)
        # mouth overlaps slightly into the core so the two voids fuse on-grid
        along = (u >= core_r * 0.95) & (u <= core_r + grain.slit_depth)
        frac = np.clip((u - core_r) / grain.slit_depth, 0.0, 1.0)
        half_width = (grain.slit_width / 2) * (1 - frac * (1 - grain.slit_taper))
        void |= along & (np.abs(v) <= half_width)

    propellant = (rr <= radius) & ~void
    # EDT measures to the nearest void cell centre; the true surface sits
    # about half a cell closer, so shift distances to remove the bias.
    dist = (ndimage.distance_transform_edt(~void) - 0.5) * cell
    dists = np.sort(np.maximum(dist[propellant].ravel(), 0.0))
    return _RegressionTable(
        sorted_dists=dists,
        cell_area=cell * cell,
        cell_size=cell,
        max_dist=float(dists[-1]) if dists.size else 0.0,
    )
