# Known Limitations & Roadmap

This document lists what IgnitionBench currently does not support, why, and what's planned.

---

## Current Limitations

### Grain Geometry
**Current:** BATES cylinders (solid core, hollow radial slits)  
**Not yet:** Star grains, finocyl, moonburner, regressive geometries

The current slit model is parametric (depth, count, taper) and fully differentiable for optimization. Extending to star and finocyl requires:
- Radial cross-section definition (complex non-convex geometry)
- Per-segment voxel EDT (expensive; current 3D slits use this)
- UI for point-and-click star/finocyl design

This is on the roadmap (Phase 4–5) but not critical for BATES-focused hobbyists.

### Burn-Rate Model
**Current:** Vieille's law with two constants (_a_, _n_)  
**r = a · P^n_

This is quasi-steady: we assume the burn-rate law applies instantly at each pressure. It's excellent for:
- Classic amateur motors (Kn 800–1400, subsonic regimes)
- Comparing designs (slit depth, nozzle throat)
- Educational exploration

It's not ideal for:
- **Erosive burning** (high mass flux; real burn rate rises above prediction)
- **Very high Kn** (>1400; transition to erosive and pressure coupling effects)
- **Vortex shedding** (cavity-induced oscillations; beyond scope)
- **Multi-phase effects** (aluminized propellants; two-phase modeling not implemented)

### Casing & Structural Analysis
**Current:** None. The simulator only calculates internal pressure.  
**Not yet:** Wall stress, material yield limits, safety factors

You must independently verify:
- Casing wall thickness (tensile hoop stress ≤ yield at peak pressure)
- Nozzle material and throat erosion (aluminum ablates rapidly; steel required for high pressure/duration)
- O-ring squeeze and sealing (test with your motor assembly)
- Grain fracture risk (mechanical shock, thermal cycling)

This is a user responsibility, not a tool feature, because:
- Material specs vary (vendor, batch, temperature)
- Casing design is often legacy or custom-built
- Structural FEA is expensive and outside this tool's scope

**Roadmap:** None. This remains a user responsibility.

### Nozzle Model
**Current:** Ideal isentropic expansion to optimum expansion ratio for sea level (pe = 1 atm)

Limitations:
- **High altitude:** Nozzle is sized for sea-level expansion. At altitude, it will over-expand and lose thrust efficiency. The simulator shows this as an interactive what-if (ambient pressure control), but the nozzle geometry doesn't re-optimize for altitude.
- **Two-phase flow:** Aluminized propellants produce particles; we assume one-phase ideal gas. Real Isp is ~3–5% lower.
- **Turbulence & viscous losses:** ~1–2% real loss; not modeled.
- **Throat erosion prediction:** We warn on long burn time, but don't predict throat-radius growth over the burn.

### Ignition Dynamics
**Current:** Assumed instantaneous at t=0 with chamber pressure following burn regression.  
**Not yet:** Transient rise rate, ignition delay, pressure spikes

Real motors have:
- Ignition delay (msec) before pressure rises
- Rapid rise to peak pressure (often 0.5–2 sec for small motors)
- Potential overshoot or oscillation in first 0.1–0.2 sec

IgnitionBench assumes steady rise and no overshoot. For small BATES motors this is usually fine; for high Kn or erosive-burning designs, real transients may differ.

**Roadmap:** Phase 4 (1D flight sim will include transient modeling).

### Propellant Variability
**Current:** Single Vieille law per propellant (mean _a_, _n_ from published data).  
**Not yet:** Uncertainty bands or Monte Carlo sampling

Real propellant batches vary:
- **Density:** ±0.5% (affects burn rate via Kn)
- **Burn-rate coefficients:** ±2–5% (published dispersions are wide)
- **Cure and aging:** Propellant properties drift over months

IgnitionBench shows a nominal curve. You should:
1. Always test your propellant batch (or use trusted published stock)
2. Collect 3+ test burns to verify _a_ and _n_
3. Use the Characterization tab to validate your measured data
4. Accept that simulation is a prediction, not a guarantee

### Flight Simulation
**Current:** None. Simulator outputs thrust and Isp but does not predict flight trajectory.  
**Not yet:** 1D or 6-DOF flight dynamics

What IgnitionBench cannot predict:
- **Altitude reached**
- **Apogee and landing location**
- **Stability and drift** (depends on weight, CG, CP, wind)
- **Recovery readiness** (chute deployment, descent rate)

These require a separate flight simulator (RockSim, OpenRocket, etc.). IgnitionBench gives you the motor data (thrust curve, weight, impulse); a flight sim uses that data to predict trajectory.

**Roadmap:** Phase 4. A 1D vertical-ascent flight model (no wind, no stability) may be added to show rough apogee and descent time. Full 6-DOF is out of scope.

### Export Formats
**Current:** STL (3D printable grain geometry).  
**Not yet:** .ENG (RASP format), CSV thrust curves, PDF reports

You can manually export:
- **Thrust curve:** Copy the simulator chart values by hand or screenshot
- **Motor specs:** Note the class, impulse, burn time from the result tiles
- **STL:** Download and print/inspect

Full automation would require:
- **.ENG format spec** (RASP; open but complex)
- **PDF generation** (adds heavy dependencies)
- **CSV streaming** (straightforward but not urgent)

**Roadmap:** Phase 4. .ENG export is the priority (interop with RockSim, OpenRocket).

### AI Mentor Scope
**Current:** Claude Opus 4.8 with safety guardrails (no propellant formulation, ignition details, or go/no-go sign-off).  
**Not yet:** Offline mode, offline LLM, local model support

Delta requires an Anthropic API key. If your key is not set:
- You still use IgnitionBench for design and simulation
- Delta is disabled; the Review tab shows a "key needed" notice
- You can add your key in-app (Settings → Delta)

**Roadmap:** Phase 5. Consideration for lightweight offline mentors (if licensing permits).

---

## Why These Limits Exist

### Scope & Complexity
A complete rocket motor simulator would include:
- Structural FEA (casing, nozzle)
- Two-phase flow (aluminized, composite propellants)
- Real-time ablation (nozzle throat growth)
- Transient ignition (pressure overshoot)
- Flight dynamics (6-DOF, wind, stability)

This is a PhD-level project (see: RockSim, GLOW, commercial aerospace tools). IgnitionBench targets **amateur BATES motor design**—a smaller scope that remains educational and usable by hobbyists without deep physics background.

### Safety
Some features are intentionally omitted because they enable harm:
- **Propellant formulation guidance** — beginners can over-charge or under-stabilize; real propellants must be tested by experienced chemists
- **Ignition system design** — bad ignition causes injuries; requires hands-on mentoring and real test-stand work
- **Certification** — go/no-go authority must stay with qualified humans (RSO, mentors); no AI can responsibly replace this

### User Responsibility
IgnitionBench is a design tool, not a substitute for:
- **Engineering judgment** — you choose what to simulate and why
- **Hands-on testing** — custom propellants, igniters, and casing integrity must be verified experimentally
- **Mentorship** — a experienced club member or RSO must review your design before flight
- **Regulatory compliance** — NAR/Tripoli rules, local ordinances, and club insurance apply regardless of what IgnitionBench says

---

## Roadmap

### Phase 1–3 (Complete)
- Core simulator (burn regression, chamber pressure, nozzle)
- 3D visualization and STL export
- Propellant library (published data)
- Interactive design UI
- Propellant Characterization (user test data)
- Guided tutorial
- Delta AI mentor with safety guardrails

### Phase 4 (In Progress)
- **1D flight simulation** (apogee, descent time estimate)
- **.ENG (RASP) export** (interop with RockSim/OpenRocket)
- **Star and finocyl grains** (expanded geometry library)
- **Thrust-curve download** (CSV export for flight sims)

### Phase 5 (Future)
- Advanced grain geometries (moon burner, regressive)
- Offline LLM mentor (local model support, if feasible)
- Multi-propellant designs (hybrid motors)
- Casing stress calculator (basic, for reference only)

### Out of Scope (Intentional)
- Propellant synthesis or formulation tools
- Igniter design or electrical firing circuits
- Structural FEA or yield analysis
- Flight stability and wind modeling
- Regulatory compliance checking
- Go/no-go certification or sign-off authority

---

## Testing Against Reality

Before flying any motor designed with IgnitionBench:

1. **Simulate a well-known design** — pick a published motor (e.g., Nakka KNSB K motor) and compare IgnitionBench results to published thrust curves. You should see agreement within 5–10%.

2. **Test a custom propellant** — burn test your propellant at 3+ pressures; measure burn rate. Enter your measured _a_ and _n_ into Characterization and compare IgnitionBench's prediction to your data. It should match.

3. **Test the motor on a stand** (if possible) — fire a full-scale motor on an instrumented thrust stand and compare actual thrust/pressure to IgnitionBench's prediction. Expect 5–15% error due to ignition transients, propellant variability, and casing/nozzle geometry details not captured by the model.

4. **Fly conservatively** — your first flight with a new design should be at a controlled club launch with RSO oversight. If it flies well, you've validated the design.

If IgnitionBench consistently predicts high (simulator says 500 N but you measure 450 N), the model may be under-estimating erosion or two-phase losses for your propellant. Adjust your design margins accordingly.

---

## Questions or Issues?

If you find a limitation not listed here, or if IgnitionBench's predictions diverge from your test data, open an issue on GitHub: [kshuklaz/IgnitionBench/issues](https://github.com/kshuklaz/IgnitionBench/issues).

Provide:
- The motor design (grain, nozzle, propellant)
- IgnitionBench's prediction (thrust, impulse, peak pressure)
- Your test data (if available)
- Expected vs. actual result

This helps improve the simulator and keeps the community safe.
