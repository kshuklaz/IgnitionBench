# IgnitionBench

AI-powered rocket motor design software for hobbyist rocketeers.

IgnitionBench combines accurate solid-propellant rocket science with plain-language
guidance and an AI mentor, so a NAR/TRA Level 1 hobbyist without an engineering
degree can design their first solid motor safely.

## Product pillars

1. **Propellant** — APCP formulation database, Kn-ratio and chamber pressure calculator.
2. **Nozzle** — de Laval nozzle geometry, thrust coefficient, c*, and Isp calculator.
3. **Simulation** — 3D grain modeling, burn regression animation, 1D flight simulator.

An AI assistant (Claude API) sits across all three, with the current motor design
passed as context, to explain results, flag unsafe designs, and answer questions.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the phased plan and
[docs/LEARNING.md](docs/LEARNING.md) for the study path.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Quickstart

```python
import math
from ignitionbench.propellant import KNSB, BatesGrain, kn, steady_state_pressure
from ignitionbench.nozzle import optimal_expansion_ratio, thrust_coefficient, thrust

grain = BatesGrain(segment_count=3, outer_diameter=0.054,
                   core_diameter=0.020, segment_length=0.095)
throat_area = math.pi / 4 * 0.015**2  # 15 mm throat

kn_ratio = kn(grain.burning_area(), throat_area)      # ≈ 168
pc = steady_state_pressure(KNSB, kn_ratio)            # ≈ 2.0 MPa (292 psi)
eps = optimal_expansion_ratio(pc, KNSB.gamma)
cf = thrust_coefficient(pc, eps, KNSB.gamma, half_angle_deg=15)
print(f"{thrust(pc, throat_area, cf):.0f} N")         # ≈ 499 N
```

All units are SI (Pa, m, kg). Propellant data comes from Richard Nakka's
published measurements and characterized APCP formulations (via openMotor's
default set) — validate against BurnSim before building hardware.

## Tests

```bash
pytest
```

## Project layout

```
src/ignitionbench/
  propellant/   # Pillar 1 — APCP database, Kn/pressure calculator
  nozzle/       # Pillar 2 — de Laval nozzle formula engine
  simulation/   # Pillar 3 — 3D grain modeling, burn regression, flight sim
  ai/           # Claude API assistant, safety checks, context injection
tests/
```

Built by a hobbyist, for hobbyists.
