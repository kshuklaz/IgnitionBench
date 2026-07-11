# Roadmap

Multi-year, solo-founder project. Learning tasks precede build tasks in each
phase so the product stays grounded in real rocket science.

## Phase 1 (Months 1–3) — Foundations & learning

- Study APCP chemistry and Vieille's burn rate law
- Learn de Laval nozzle theory and Isp
- Set up Python + numpy + scipy + matplotlib
- Join The Rocketry Forum, study existing tools (OpenRocket, BurnSim, RASAero II)
- Scaffold IgnitionBench repo and folder structure

## Phase 2 (Months 4–6) — Propellant & nozzle modules

- Build propellant database with burn rate coefficients
- Build Kn calculator and chamber pressure model
- Implement nozzle geometry calculator
- Validate against BurnSim for identical inputs
- Wire up Claude API for basic AI chat

## Phase 3 (Months 7–9) — 3D motor design

- Build 2D grain cross-section renderer
- Implement burn regression animation
- Add 3D motor casing visualizer (Three.js or PyVista)
- Allow live parameter adjustment with 3D update
- Share with 5 hobbyists for structured feedback

## Phase 4 (Months 10–12) — Simulation & launch

- Build 1D flight simulator with trajectory animation
- Export .ENG file in RASP format
- Package as web app (Streamlit or Flask)
- Publish on GitHub and post to The Rocketry Forum
- Plan v2 scope based on community feedback

## Year 2+ — Advanced features

- Hybrid motor support (liquid oxidiser + solid fuel grain)
- 6-DOF trajectory simulation
- Fin stability analysis (Barrowman equations)
- Method of Characteristics nozzle contour design
- CFD integration (OpenFOAM / SU2) for nozzle flow analysis
