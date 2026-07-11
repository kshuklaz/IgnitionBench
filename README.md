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
