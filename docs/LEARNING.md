# Learning & study path

Learning and building happen in parallel. This maps the knowledge needed for
each module.

## Propellant section

- Richard Nakka's website (nakka-rocketry.net) — primary free resource for amateur solid motor design
- Vieille's burn rate law: r = a · Pⁿ
- Kn ratio = burning surface area / throat area — the key parameter controlling chamber pressure
- APCP chemistry: oxidiser (KNO₃ / ammonium nitrate), fuel (HTPB / sorbitol), additives

## Nozzle engine

- De Laval nozzle theory — throat, supersonic expansion, exit conditions
- Thrust coefficient (Cf) and characteristic velocity (c*)
- Specific impulse (Isp) — the primary measure of propellant efficiency
- Sutton & Biblarz, *Rocket Propulsion Elements* — Chapters 3, 5, and 12

## 3D design + simulation

- Grain geometry types: BATES (cylindrical), star, finocyl and their burn profiles
- Burn regression — stepping through time, shrinking grain surface, updating pressure
- Three.js (web 3D) or PyVista (Python 3D)
- 1D flight dynamics — drag equation, numerical integration of equations of motion

## AI integration

- Anthropic Claude API — messages endpoint, system prompts, context injection
- Prompt engineering for encoding rocketry safety rules
- `anthropic` Python SDK for backend API calls

## Recommended order

1. Richard Nakka's website — read everything, work through his spreadsheet tools
2. Sutton & Biblarz Chapters 3 and 5 — nozzle theory and solid propellants
3. Run the rocket equation in Python by hand before building any UI
4. OpenRocket source code — read how it implements grain geometry and flight simulation
5. Claude API "hello world" — confirm the AI integration works before building around it
