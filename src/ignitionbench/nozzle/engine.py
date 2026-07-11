"""De Laval nozzle formula engine.

Standard one-dimensional isentropic ideal-rocket relations (Sutton &
Biblarz, ch. 3). All quantities SI: pressures Pa, areas m², velocities m/s.
gamma (k) is the exhaust ratio of specific heats from the propellant data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.optimize import brentq

from ignitionbench.propellant.database import G0

STANDARD_ATMOSPHERE = 101_325.0  # Pa


def area_ratio_from_mach(mach: float, gamma: float) -> float:
    """A/At for isentropic flow at a given Mach number."""
    if mach <= 0:
        raise ValueError("mach must be positive")
    k = gamma
    term = (2 / (k + 1)) * (1 + (k - 1) / 2 * mach**2)
    return (1 / mach) * term ** ((k + 1) / (2 * (k - 1)))


def mach_from_area_ratio(area_ratio: float, gamma: float) -> float:
    """Supersonic exit Mach number for an expansion ratio Ae/At ≥ 1."""
    if area_ratio < 1:
        raise ValueError("area_ratio must be ≥ 1 (throat is the minimum area)")
    if area_ratio == 1:
        return 1.0
    return brentq(lambda m: area_ratio_from_mach(m, gamma) - area_ratio, 1.0, 100.0)


def pressure_ratio(mach: float, gamma: float) -> float:
    """Static-to-stagnation pressure ratio P/P0 at a Mach number."""
    k = gamma
    return (1 + (k - 1) / 2 * mach**2) ** (-k / (k - 1))


def exit_pressure(chamber_pressure: float, area_ratio: float, gamma: float) -> float:
    """Nozzle exit static pressure (Pa) for a given expansion ratio."""
    mach = mach_from_area_ratio(area_ratio, gamma)
    return chamber_pressure * pressure_ratio(mach, gamma)


def optimal_expansion_ratio(
    chamber_pressure: float,
    gamma: float,
    ambient_pressure: float = STANDARD_ATMOSPHERE,
) -> float:
    """Ae/At that expands the exhaust exactly to ambient pressure."""
    if chamber_pressure <= ambient_pressure:
        raise ValueError("chamber pressure must exceed ambient pressure")
    k = gamma
    ratio = ambient_pressure / chamber_pressure
    mach = math.sqrt(2 / (k - 1) * (ratio ** (-(k - 1) / k) - 1))
    return area_ratio_from_mach(mach, gamma)


def thrust_coefficient(
    chamber_pressure: float,
    area_ratio: float,
    gamma: float,
    ambient_pressure: float = STANDARD_ATMOSPHERE,
    half_angle_deg: float | None = None,
) -> float:
    """Thrust coefficient Cf: thrust = Cf · Pc · At.

    Momentum term plus pressure-thrust term; if half_angle_deg is given, the
    momentum term is scaled by the conical divergence loss λ = (1+cos α)/2.
    """
    k = gamma
    pe = exit_pressure(chamber_pressure, area_ratio, gamma)
    momentum = math.sqrt(
        (2 * k**2 / (k - 1))
        * (2 / (k + 1)) ** ((k + 1) / (k - 1))
        * (1 - (pe / chamber_pressure) ** ((k - 1) / k))
    )
    if half_angle_deg is not None:
        momentum *= divergence_factor(half_angle_deg)
    pressure_term = (pe - ambient_pressure) / chamber_pressure * area_ratio
    return momentum + pressure_term


def divergence_factor(half_angle_deg: float) -> float:
    """Conical nozzle divergence loss λ = (1 + cos α) / 2."""
    return (1 + math.cos(math.radians(half_angle_deg))) / 2


def throat_area_for_thrust(thrust: float, chamber_pressure: float, cf: float) -> float:
    """Throat area (m²) needed for a target thrust (N)."""
    if min(thrust, chamber_pressure, cf) <= 0:
        raise ValueError("thrust, chamber_pressure, and cf must all be positive")
    return thrust / (cf * chamber_pressure)


def thrust(chamber_pressure: float, throat_area: float, cf: float) -> float:
    """Thrust (N) from Cf · Pc · At."""
    return cf * chamber_pressure * throat_area


def mass_flow(chamber_pressure: float, throat_area: float, c_star: float) -> float:
    """Nozzle mass flow (kg/s): ṁ = Pc · At / c*."""
    return chamber_pressure * throat_area / c_star


def specific_impulse(cf: float, c_star: float) -> float:
    """Isp (s) = Cf · c* / g0."""
    return cf * c_star / G0


@dataclass(frozen=True)
class ConicalNozzle:
    """Conical nozzle geometry, ready for machining or 3D-printing specs."""

    throat_diameter: float  # m
    expansion_ratio: float  # Ae/At
    half_angle_deg: float = 15.0  # divergent cone half-angle
    convergence_angle_deg: float = 45.0  # convergent cone half-angle

    def __post_init__(self) -> None:
        if self.throat_diameter <= 0:
            raise ValueError("throat_diameter must be positive")
        if self.expansion_ratio < 1:
            raise ValueError("expansion_ratio must be ≥ 1")
        if not 0 < self.half_angle_deg < 90:
            raise ValueError("half_angle_deg must be between 0 and 90")

    @property
    def throat_area(self) -> float:
        return math.pi / 4 * self.throat_diameter**2

    @property
    def exit_diameter(self) -> float:
        return self.throat_diameter * math.sqrt(self.expansion_ratio)

    @property
    def exit_area(self) -> float:
        return self.throat_area * self.expansion_ratio

    @property
    def divergent_length(self) -> float:
        """Axial length of the divergent cone (m)."""
        return (self.exit_diameter - self.throat_diameter) / (
            2 * math.tan(math.radians(self.half_angle_deg))
        )

    @property
    def divergence_factor(self) -> float:
        return divergence_factor(self.half_angle_deg)
