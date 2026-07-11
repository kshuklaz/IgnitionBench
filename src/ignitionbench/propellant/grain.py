"""BATES grain geometry.

A BATES grain is a stack of identical hollow cylinders, inhibited on the
outer surface: combustion regresses the core outward and both segment ends
inward. All dimensions in metres, areas in m², volumes in m³.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .database import Propellant


@dataclass(frozen=True)
class BatesGrain:
    segment_count: int
    outer_diameter: float  # m
    core_diameter: float  # m
    segment_length: float  # m

    def __post_init__(self) -> None:
        if self.segment_count < 1:
            raise ValueError("segment_count must be at least 1")
        if not 0 < self.core_diameter < self.outer_diameter:
            raise ValueError("need 0 < core_diameter < outer_diameter")
        if self.segment_length <= 0:
            raise ValueError("segment_length must be positive")

    @property
    def web_thickness(self) -> float:
        """Distance the burn front travels before the grain is consumed.

        Radial web is (D−d)/2; the ends burn toward each other and meet at
        L/2. Whichever is smaller ends the burn.
        """
        radial = (self.outer_diameter - self.core_diameter) / 2
        axial = self.segment_length / 2
        return min(radial, axial)

    def burning_area(self, web_burned: float = 0.0) -> float:
        """Total burning surface (m²) after the front has regressed a distance x.

        Core surface plus both exposed ends of every segment; zero at burnout.
        """
        if web_burned < 0:
            raise ValueError("web_burned cannot be negative")
        if web_burned >= self.web_thickness:
            return 0.0
        core = self.core_diameter + 2 * web_burned
        length = self.segment_length - 2 * web_burned
        core_surface = math.pi * core * length
        end_faces = 2 * (math.pi / 4) * (self.outer_diameter**2 - core**2)
        return self.segment_count * (core_surface + end_faces)

    def volume(self, web_burned: float = 0.0) -> float:
        """Remaining propellant volume (m³) after regression x."""
        if web_burned < 0:
            raise ValueError("web_burned cannot be negative")
        if web_burned >= self.web_thickness:
            return 0.0
        core = self.core_diameter + 2 * web_burned
        length = self.segment_length - 2 * web_burned
        annulus = (math.pi / 4) * (self.outer_diameter**2 - core**2)
        return self.segment_count * annulus * length

    def port_area(self, web_burned: float = 0.0) -> float:
        """Flow area through the core (m²) after regression x."""
        core = min(self.core_diameter + 2 * web_burned, self.outer_diameter)
        return (math.pi / 4) * core**2

    def propellant_mass(self, propellant: Propellant, web_burned: float = 0.0) -> float:
        """Remaining propellant mass (kg)."""
        return self.volume(web_burned) * propellant.density
