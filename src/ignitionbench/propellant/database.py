"""Propellant database with burn-rate coefficients.

All quantities are SI: pressure in Pa, density in kg/m³, burn rate in m/s,
temperature in K, molar mass in kg/mol.

Burn rate follows Vieille's law, r = a · Pⁿ, with coefficients valid only
inside each segment's pressure range. The KN* data is Richard Nakka's
published strand-burner measurements; the APCP entries are characterized
commercial/university formulations. All values were taken from openMotor's
default propellant set (github.com/reilleya/openMotor, retrieved 2026-07-11),
which stores them in SI form.

These are *practical* values (as-cast density, effective combustion
temperature), not theoretical ideals — so computed c* and Isp land near
delivered performance rather than thermochemical maximums.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

R_UNIVERSAL = 8.31446  # J/(mol·K)
G0 = 9.80665  # m/s², standard gravity


@dataclass(frozen=True)
class BurnRateSegment:
    """One pressure range of a Vieille's-law fit: r = a · Pⁿ (SI units)."""

    min_pressure: float  # Pa
    max_pressure: float  # Pa
    a: float  # burn rate coefficient, m/s at 1 Pa (SI-consistent)
    n: float  # pressure exponent, dimensionless

    def burn_rate(self, pressure: float) -> float:
        return self.a * pressure**self.n


@dataclass(frozen=True)
class Propellant:
    name: str
    density: float  # kg/m³, as-cast
    combustion_temp: float  # K, effective chamber temperature
    molar_mass: float  # kg/mol of exhaust products
    gamma: float  # ratio of specific heats of exhaust
    segments: tuple[BurnRateSegment, ...]

    @property
    def min_pressure(self) -> float:
        """Lowest chamber pressure the burn-rate data is valid for (Pa)."""
        return self.segments[0].min_pressure

    @property
    def max_pressure(self) -> float:
        """Highest chamber pressure the burn-rate data is valid for (Pa)."""
        return self.segments[-1].max_pressure

    @property
    def specific_gas_constant(self) -> float:
        """R of the exhaust products, J/(kg·K)."""
        return R_UNIVERSAL / self.molar_mass

    @property
    def c_star(self) -> float:
        """Characteristic exhaust velocity c* (m/s).

        c* = √(k·R·T) / (k · (2/(k+1))^((k+1)/(2(k-1))))
        """
        k = self.gamma
        return math.sqrt(k * self.specific_gas_constant * self.combustion_temp) / (
            k * (2 / (k + 1)) ** ((k + 1) / (2 * (k - 1)))
        )

    def burn_rate(self, pressure: float) -> float:
        """Burn rate (m/s) at a chamber pressure (Pa).

        Raises ValueError outside the validated pressure range — operating
        there means the model has no experimental basis, which is itself a
        design red flag.
        """
        for segment in self.segments:
            if segment.min_pressure <= pressure <= segment.max_pressure:
                return segment.burn_rate(pressure)
        raise ValueError(
            f"{pressure:.0f} Pa is outside the validated pressure range for "
            f"{self.name} ({self.min_pressure:.0f}–{self.max_pressure:.0f} Pa). "
            "Burn-rate data does not exist for this condition."
        )


KNDX = Propellant(
    name="KNDX (potassium nitrate / dextrose 65:35)",
    density=1785.0,
    combustion_temp=1625.0,
    molar_mass=0.04239,
    gamma=1.1308,
    segments=(
        BurnRateSegment(103_425, 779_135, 1.7096289148678155e-06, 0.619),
        BurnRateSegment(779_135, 2_571_835, 8.553459092346196e-03, -0.009),
        BurnRateSegment(2_571_835, 5_929_700, 2.90330733578913e-07, 0.688),
        BurnRateSegment(5_929_700, 8_501_535, 1.330457207587796e-01, -0.148),
        BurnRateSegment(8_501_535, 11_204_375, 1.0537671694797537e-05, 0.444),
    ),
)

KNSB = Propellant(
    name="KNSB (potassium nitrate / sorbitol 65:35)",
    density=1750.0,
    combustion_temp=1520.0,
    molar_mass=0.0399,
    gamma=1.1361,
    segments=(
        BurnRateSegment(103_425, 806_715, 1.9253259619746373e-06, 0.625),
        BurnRateSegment(806_715, 1_503_110, 6.656608561590813e-01, -0.313),
        BurnRateSegment(1_503_110, 3_792_250, 9.528121181782798e-03, -0.0145),
        BurnRateSegment(3_792_250, 7_032_900, 2.709667768835332e-06, 0.5245),
        BurnRateSegment(7_032_900, 10_673_460, 4.17677261069904e-03, 0.059),
    ),
)

CHERRY_LIMEADE = Propellant(
    name="MIT Cherry Limeade (APCP, HTPB-based)",
    density=1680.0,
    combustion_temp=3500.0,
    molar_mass=0.02367,
    gamma=1.21,
    segments=(BurnRateSegment(0.0, 6_895_000, 3.517054143255937e-05, 0.3273),),
)

OCEAN_WATER = Propellant(
    name="MIT Ocean Water (APCP, HTPB-based)",
    density=1650.0,
    combustion_temp=3500.0,
    molar_mass=0.02367,
    gamma=1.25,
    segments=(BurnRateSegment(0.0, 6_895_000, 1.467e-05, 0.382),),
)

WHITE_LIGHTNING = Propellant(
    name="RCS White Lightning (APCP, HTPB-based)",
    density=1820.2,
    combustion_temp=2339.0,
    molar_mass=0.027125,
    gamma=1.243,
    segments=(BurnRateSegment(0.0, 10_342_500, 5.710516747228669e-06, 0.45),),
)

BLUE_THUNDER = Propellant(
    name="RCS Blue Thunder (APCP, HTPB-based)",
    density=1625.1,
    combustion_temp=2616.5,
    molar_mass=0.022959,
    gamma=1.235,
    segments=(BurnRateSegment(0.0, 10_342_500, 6.994600946367753e-05, 0.321),),
)

PROPELLANTS: dict[str, Propellant] = {
    "kndx": KNDX,
    "knsb": KNSB,
    "cherry_limeade": CHERRY_LIMEADE,
    "ocean_water": OCEAN_WATER,
    "white_lightning": WHITE_LIGHTNING,
    "blue_thunder": BLUE_THUNDER,
}
