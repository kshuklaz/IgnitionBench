<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/logo-white.png">
  <img src="assets/logo-black.png" alt="IgnitionBench" width="420">
</picture>

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
pip install -e ".[dev,web]"
```

## Run the web UI

```bash
python -m ignitionbench.web
```

Then open http://localhost:8000 — a dark design studio:

- **Home** — create and file multiple motor projects (stored as JSON under
  `~/.ignitionbench/projects/`), each carded with its impulse class.
- **Step 1 · Propellant** — pick a library formulation or enter a custom
  batch (a, n, density, γ, flame temp, molar mass) with a live burn-rate chart.
- **Step 2 · Motor design** — BATES grain + nozzle inputs, optional tapered
  radial slits (count, depth, width, tip taper — regressed with a 2D
  distance-field model), live Kn/pressure/thrust/class tiles, NAR/TRA
  certification requirement, safety warnings, an interactive Three.js 3D
  model with cutaway view, and STL export of the grain segment for CAD or
  3D printing.
- **Step 3 · Simulation** — burn-regression simulator with an animated grain
  (face + side views, play/scrub), thrust and chamber-pressure curves with a
  synced time cursor, and delivered performance numbers.
- **Step 4 · Review** — the AI mentor reads the full design and writes a
  safety review: every warning explained in plain language, hazards the
  calculators don't model, and recommended next steps.
- **✦ AI mentor** — a chat drawer on every page. In a project it sees your
  live geometry and computed results, answers questions about them, and can
  edit the design on request — every AI edit passes through the same
  validation pipeline as the forms, so an unsafe or invalid design is
  rejected and never saved. It never provides propellant formulations,
  ignition compositions, or go/no-go sign-offs — that authority stays with
  your certified RSO or mentor.

## AI setup (optional)

Everything except the AI mentor and the Review tab works offline with no
account. The AI features call the Claude API and need a key:

1. Create a key at [console.anthropic.com](https://console.anthropic.com)
   (Settings → API Keys) and add a few dollars of billing credit.
2. Export it in the environment where the server runs, then start the app:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python -m ignitionbench.web
```

Never commit the key. Without it the app runs normally and the AI surfaces
show a setup notice. Default model is Claude Opus 4.8; override with
`IGNITIONBENCH_AI_MODEL`.

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
  export/       # STL export
  web/          # Flask design studio + AI mentor (web/ai.py, Claude API)
tests/
```

Built by a hobbyist, for hobbyists.
