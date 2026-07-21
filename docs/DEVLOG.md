# IgnitionBench - Devlog

A running log of what shipped, in reverse-chronological order. Each entry lists
the change, why it exists, and the commits behind it.

---

## 2026-07 - The Propellant Engine

A dedicated workspace for developing your own propellant, separate from the motor
project designer. It grew over several passes into a home-like gallery of saved
propellants, each opening into a four-tab workflow.

### Home-like gallery + workspace (f2ac210)

The engine now mirrors the projects home screen.

- `/engine` opens on a gallery of propellant cards - one per saved batch,
  showing what it's based on, its ingredients, and when it was last updated.
  Empty state, a "+ New propellant" button, per-card rename, and a two-step
  delete - the same interaction model as project cards.
- "New propellant" opens a name modal, creates the batch from a published KNSB
  baseline, and drops you into its workspace.
- Clicking a card opens a workspace scoped to that one propellant at
  `/engine?p=<id>`. It's history-aware: browser back and refresh both work.
  Because the workspace is scoped, Prepare and Cast dropped their propellant
  selectors and act on the open propellant; Plan loads the record and saves
  changes with PUT instead of always creating a new one.
- Own-a/n propellants round-trip cleanly through the Plan form - the stored SI
  burn coefficient is reconstructed back to mm/s-at-MPa on load
  (a_mm = a_si * 1e3 * 1e6^n), verified exact across a save-then-reload cycle.

Tab order settled at: Plan, Prepare, Cast, Characterization.

### Characterization tab (c521739)

Making your own propellant means measuring how it actually burns - you can't
trust Cast predictions for a custom batch until you've characterized it.

- Log test-burn data points (pressure in MPa, measured burn rate in mm/s),
  persisted in the browser.
- Least-squares fit of r = a * P^n in log space, reporting a, n, R^2, and the
  validated pressure range, with a live scatter-plus-fit chart.
- Guardrails: warns when n falls outside 0-1, when R^2 < 0.9 (scattered data),
  or when the burns cover too narrow a pressure span to trust.
- "Use in Plan" copies the fit into Plan's "my own a/n data" form.
- A skip notice appears when the propellant starts from a published baseline
  whose a and n are already established - you only characterize your own batches.

### Foundation: Plan / Prepare / Cast + saved propellants (b5bfe13)

- Plan - an ingredient notebook (documentation only) plus a characterize/save
  panel: start from a published baseline or enter your own a/n data.
- Prepare - a safety checklist plus a place to record your own preparation
  notes per propellant.
- Cast - BATES grain and nozzle inputs with live Kn / pressure / thrust / class
  tiles, AutoCast (Delta proposes grain geometry and fin recommendations,
  validated by the physics pipeline, applied only on your approval), and a
  hand-off into a full motor project.
- Saved custom propellants persist under `~/.ignitionbench/propellants/` and
  surface in every project's propellant menu as `custom:<id>` keys, resolved
  through the same physics pipeline as the built-ins.

### Safety stance (applies across the whole engine)

IgnitionBench never invents propellant formulations, ratios, or mixing/casting
procedures. Burn-rate data comes from one of two places only: a published,
characterized baseline (e.g. Richard Nakka's KNSB fit, relabeled with your batch
name) or your own measured a/n data. The AI recommends published propellants and
explains hazards; it does not generate energetics recipes, and it never signs
off a design as safe to fly. Live-fire steps (preparation, characterization) are
framed as work done under a certified mentor or RSO at a legal test site - the
app fits numbers, the human owns the discipline.

---

## 2026-07 - The AI mentor becomes "Delta" (a4c2f1b)

The Claude-powered mentor got a name. Delta now appears across the side tab,
drawer header, status messages, AutoCast, the Review tab, and the README, and
introduces itself by name via its system prompt. All hard safety boundaries in
the prompt are unchanged; references to a real-world "certified mentor/RSO" mean
a human and were deliberately left as-is.

---

## 2026-07 - Learning resources + docs

- Resources button (c801bde) - a button in the home sidebar opens a curated
  modal of trusted websites (Nakka, ThrustCurve, NAR, Tripoli), open-source
  tools (openMotor, OpenRocket, BurnSim), and books, each with a one-line note
  and a reminder to cross-check numbers before trusting hardware.
- README + AI setup (ee70ec8) - documented the Review tab, the AI mentor, and
  the optional `ANTHROPIC_API_KEY` setup (the app works fully offline except the
  AI features).

---

Tests pass at each milestone (109 as of f2ac210). Burn-rate data is validated
against published sources; validate any design against BurnSim before building
hardware.
