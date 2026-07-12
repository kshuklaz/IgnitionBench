"""Burn regression simulator.

Marches the burn front through the grain web in equal geometry steps. At
each position the burning area gives Kn, Kn gives steady-state chamber
pressure, and pressure gives burn rate — which converts the geometry step
into a time step. Thrust follows from a fixed nozzle sized for optimal
expansion at ignition pressure.

Quasi-steady assumptions: no ignition transient, no erosive burning, no
nozzle erosion. Good for BATES-class hobby motors; validate against BurnSim
before cutting metal.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ignitionbench.nozzle import (
    STANDARD_ATMOSPHERE,
    optimal_expansion_ratio,
    thrust_coefficient,
)
from ignitionbench.propellant import G0, BatesGrain, Propellant, steady_state_pressure

from .performance import motor_class


@dataclass(frozen=True)
class BurnSimResult:
    time: list[float]  # s
    web: list[float]  # m, regression distance
    kn: list[float]
    pressure: list[float]  # Pa, chamber
    thrust: list[float]  # N
    mass: list[float]  # kg, propellant remaining
    expansion_ratio: float
    burn_time: float  # s
    total_impulse: float  # N·s
    max_thrust: float
    avg_thrust: float
    max_pressure: float
    peak_kn: float
    isp_delivered: float  # s
    motor_class: str
    low_pressure_clamped: bool = field(default=False)


def simulate_burn(
    propellant: Propellant,
    grain: BatesGrain,
    throat_area: float,
    *,
    half_angle_deg: float = 15.0,
    ambient_pressure: float = STANDARD_ATMOSPHERE,
    steps: int = 240,
) -> BurnSimResult:
    web_total = grain.web_thickness
    dx = web_total / steps

    pc0 = steady_state_pressure(propellant, grain.burning_area(0.0) / throat_area)
    eps = optimal_expansion_ratio(pc0, propellant.gamma, ambient_pressure)

    times: list[float] = []
    webs: list[float] = []
    kns: list[float] = []
    pressures: list[float] = []
    thrusts: list[float] = []
    masses: list[float] = []

    t = 0.0
    clamped = False
    for i in range(steps):
        x = i * dx
        kn_i = grain.burning_area(x) / throat_area
        try:
            pc = steady_state_pressure(propellant, kn_i)
        except ValueError:
            r_max = propellant.burn_rate(propellant.max_pressure)
            if kn_i * propellant.density * r_max * propellant.c_star > propellant.max_pressure:
                raise ValueError(
                    f"Overpressure at t = {t:.2f} s (web {x * 1000:.1f} mm, Kn = {kn_i:.0f}): "
                    f"the design exceeds {propellant.name}'s validated maximum of "
                    f"{propellant.max_pressure / 6895:.0f} psi mid-burn."
                ) from None
            # Kn too low to sustain the validated minimum — treat the tail as
            # burning at the lowest characterized pressure.
            pc = propellant.min_pressure
            clamped = True

        cf = max(
            thrust_coefficient(pc, eps, propellant.gamma, ambient_pressure, half_angle_deg),
            0.0,
        )
        times.append(t)
        webs.append(x)
        kns.append(kn_i)
        pressures.append(pc)
        thrusts.append(cf * pc * throat_area)
        masses.append(grain.propellant_mass(propellant, x))
        t += dx / propellant.burn_rate(pc)

    # burnout: web consumed, no surface left
    times.append(t)
    webs.append(web_total)
    kns.append(0.0)
    pressures.append(0.0)
    thrusts.append(0.0)
    masses.append(0.0)

    total_impulse = sum(
        0.5 * (thrusts[i] + thrusts[i + 1]) * (times[i + 1] - times[i])
        for i in range(len(times) - 1)
    )
    initial_mass = grain.propellant_mass(propellant, 0.0)

    return BurnSimResult(
        time=times,
        web=webs,
        kn=kns,
        pressure=pressures,
        thrust=thrusts,
        mass=masses,
        expansion_ratio=eps,
        burn_time=t,
        total_impulse=total_impulse,
        max_thrust=max(thrusts),
        avg_thrust=total_impulse / t,
        max_pressure=max(pressures),
        peak_kn=max(kns),
        isp_delivered=total_impulse / (initial_mass * G0),
        motor_class=motor_class(total_impulse),
        low_pressure_clamped=clamped,
    )
