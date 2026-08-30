# Safety Guide: IgnitionBench and the Delta Mentor

## Overview

IgnitionBench is an **educational design and simulation tool** for amateur rocketry. Delta is an AI mentor that helps you explore rocket motor designs and understand the physics. This document clarifies what IgnitionBench and Delta can and cannot do, and why some decisions remain exclusively human responsibilities.

---

## What IgnitionBench Does

### ✅ Design & Visualization
- Draw grain geometry (BATES cylinders with tapered radial slits)
- Specify nozzle dimensions and material
- Select or document propellant burn-rate characteristics
- Visualize grain web in 3D, export STL for inspection
- Calculate geometric properties (core/surface area, volume)

### ✅ Physics Simulation
- Solve unsteady chamber pressure using burn-rate regression and grain geometry
- Apply Vieille's law (_r = a·Pⁿ_) with published propellant data
- Calculate thrust, impulse, Isp, burn time, and motor class (G/H/I/etc.)
- Model nozzle expansion and throat erosion
- Simulate ambient pressure effects (sea-level to vacuum) as a design what-if
- Warn on hazards: over-pressure (>6.9 MPa nominal), rapid pressure rise (>1 MPa/s), high Kn (>1400)

### ✅ Document & Review
- Archive designs with metadata (dates, propellant used, results)
- Export designs for sharing and review
- Annotate designs with notes and test data
- Generate a design review checklist (Prepare tab)

### ✅ Education
- Interactive guided tour for new users
- Physics explanations in UI tooltips and the Prepare tab
- Warning messages that link to why a design is risky
- Confidence-building through experimentation

---

## What IgnitionBench Does NOT Do

### ❌ Propellant Formulation
IgnitionBench will **never**:
- Tell you how to mix propellant (ratios, order, temperature, equipment, duration)
- Suggest new propellant compositions
- Help you source or synthesize oxidizers, binders, or fuels
- Predict how a custom propellant will burn without test data

**Why?** Propellant mixing and synthesis involves explosion risk, legal control (oxidizers especially), and chemistry knowledge beyond this tool's scope. Every propellant in IgnitionBench's catalog has been publicly tested by experienced rocketeers and published by open-source projects like openMotor.

If you want to formulate your own propellant, you must:
1. Learn the chemistry and safety practices (books, forums, mentors)
2. Perform small-scale burn tests under controlled conditions
3. Measure burn rate across a range of pressures (at least 3 points)
4. Enter your measured burn-rate law (_a_ and _n_ coefficients) into the Characterization tab
5. Validate results with additional test data before using in a motor

### ❌ Ignition System Design
IgnitionBench will **never**:
- Recommend igniters (brand, type, quantity)
- Explain igniter construction or materials
- Predict igniter reliability or performance
- Help with electrical firing circuits (unless you're using commercial hardware)

**Why?** Ignition reliability directly affects safety — a misfire can trap a pressurized motor with a chambered grain. Igniter design requires hands-on knowledge, testing in your specific motor, and real-world experience.

Consult NAR/Tripoli club resources and experienced mentors for igniter guidance specific to your motor.

### ❌ Certification or Go/No-Go Decisions
IgnitionBench will **never**:
- Approve a design as "safe to fly"
- Sign off on a motor for competition or public launch
- Replace the role of a Range Safety Officer (RSO), club inspector, or certified mentor
- Make a final pass/fail judgment

**Why?** IgnitionBench can warn you of obvious hazards (over-pressure, rapid rise), but a complete safety assessment includes:
- Structural integrity (casing, nozzle material and stress analysis)
- Assembly and handling procedures (grain packing, grain orientation, seal integrity)
- Launch site and weather conditions
- Recovery system readiness
- Regulatory compliance (local, state, federal)
- Club insurance and liability rules
- Operator experience and preparation

**Only a human RSO or qualified mentor can make the go/no-go call.** Use IgnitionBench as a tool to explore and document your design, then bring that documentation to your club's launch control or a trusted experienced mentor for final review.

---

## What Delta (The AI Mentor) Does

### ✅ Delta Can:
- **Explain physics** — Help you understand why the simulator gives a certain result
- **Spot obvious hazards** — Point out over-pressure, rapid rise, extreme Kn
- **Suggest published propellants** — Recommend established propellants from the catalog by name
- **Ask clarifying questions** — Help you think through your design choices
- **Provide references** — Point you to NAR, Tripoli, NFPA, or scientific sources
- **Encourage iteration** — Suggest adjusting grain diameter, nozzle throat, or slit design to explore tradeoffs
- **Document decisions** — Help you articulate why you made a design choice (for a launch log or review)

### ❌ Delta Will Not:
- **Formulate propellants** — Never emit mixing ratios, ingredient sources, or synthesis procedures
- **Recommend igniters** — Never specify igniter types or electrical systems
- **Sign off on safety** — Never give a thumbs-up for launch; never replace an RSO
- **Guarantee results** — Never claim your motor will behave as simulated; simulation has limits
- **Bypass the Prepare tab** — Never skip the safety checklist questions; these are your responsibility

**Delta's safety system is strict:** The mentor prompt explicitly forbids propellant formulations, ignition details, and go/no-go sign-offs. If you ask Delta to break these rules, it will refuse.

---

## Simulation Accuracy & Limits

IgnitionBench's simulator is based on published rocket science (Nakka's burn-regression model, ideal-gas chamber pressure), but has known limits. It's excellent for **comparing designs** (slit depth, core diameter, nozzle throat) but not perfect for **predicting absolute performance**.

### Known Limitations:
- **Grain geometry:** Only BATES cylinders with tapered radial slits. No star, finocyl, or moonburner grains yet.
- **Burn-rate model:** Quasi-steady Vieille's law. Good for classic amateur motors (Kn 800–1400), not ideal for erosive burning or very high Kn.
- **Nozzle:** Modeled for sea-level expansion. Actual high-altitude nozzles may diverge differently.
- **Casing & structure:** Simulator does not check casing stress, material limits, or assembly integrity. You must verify these separately.
- **Ignition dynamics:** No prediction of initial rise rate or ignition transient.
- **Propellant variability:** Real propellant batches vary. Test data is an average; your batch may differ.

**Before flying a motor**, test it in a test stand or on a small-scale flight under controlled conditions. A good simulator makes bad designs obvious, but only a real burn proves a design works.

---

## Using IgnitionBench Responsibly

1. **Understand the model's limits.** Use simulation to compare designs, not to declare a design "proven."
2. **Test custom propellants.** If you've formulated or measured your own propellant, burn-test it at multiple pressures before flying a motor with it.
3. **Use published propellants when starting.** The catalog includes well-characterized propellants (KNSB, KNDX, etc.) with flight heritage.
4. **Seek expert review.** Before your first flight with a new design, show your IgnitionBench project and test data to an experienced club member or mentor.
5. **Get RSO clearance.** No matter how confident IgnitionBench makes you, your launch site requires an RSO sign-off. Bring your design documentation to the range.
6. **Follow club and legal rules.** NAR, Tripoli, and local regulations govern what you can fly. IgnitionBench doesn't know your rules; you do.

---

## External Resources

- **NAR (National Association for Rocketry):** [nar.org](https://www.nar.org) — rules, safety, RSO certification
- **Tripoli Rocketry Association:** [tripoli.org](https://www.tripoli.org) — launches, mentoring, insurance
- **NFPA 1127 (Standard for High Power Rocketry):** Safety codes and definitions
- **Nakka's Rocket Motor Page:** [nakka-rocketry.net](https://www.nakka-rocketry.net) — detailed motor physics and data
- **openMotor:** [github.com/tpooch/openMotor](https://github.com/tpooch/openMotor) — open-source motor design tool; propellant data source for IgnitionBench

---

## Questions About This Tool?

If you have questions about IgnitionBench's capabilities, limitations, or Delta's responses, open an issue on GitHub (kshuklaz/IgnitionBench) or contact the maintainer.

**This tool is for learning and design exploration. The people at your launch site are your safety partners.** Bring them your designs, your questions, and your curiosity—that's what makes our community strong.
