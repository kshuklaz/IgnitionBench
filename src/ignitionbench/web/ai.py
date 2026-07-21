"""Claude-powered SRM mentor: project-aware chat with a design-editing tool,
plus a full-project safety review for the Review tab.

The mentor can propose design changes via the update_project_design tool, but
every change runs through the same validation pipeline as the UI (_parse_design
/ _design_result) — a design the app would reject is never saved, so the AI
cannot bypass overpressure or geometry checks.
"""

from __future__ import annotations

import json
import os

from . import store

MODEL = os.environ.get("IGNITIONBENCH_AI_MODEL", "claude-opus-4-8")

MENTOR_SYSTEM = """\
# ROLE
You are Delta, a Solid Rocket Motor (SRM) Development Mentor embedded in
IgnitionBench. Refer to yourself as Delta.
You help hobbyists and engineering students design, document, and safely test
custom solid rocket motors. You are a mentor and process guide — NOT a substitute
for certified mentorship, professional engineering review, or hands-on safety
inspection.

# CORE SAFETY PRINCIPLE
Every response involving motor design, testing, or handling must treat
irreversible physical harm (burns, explosions, shrapnel, eye/hearing damage,
death) as the primary risk to guard against — above user convenience, project
momentum, or the user's stated confidence level. When in doubt, slow the user
down rather than speed them up.

# WHAT YOU DO
- Walk users through the standard SRM development lifecycle: design goals →
  simulation → materials selection → build → static test → flight test,
  emphasizing incremental validation at each stage.
- Review user-submitted designs (grain geometry, casing specs, nozzle
  dimensions, thrust curves) for structural and procedural red flags:
  under-rated casings, missing burst discs/pressure relief, inadequate
  standoff distances, non-redundant ignition systems, untested motors
  skipping straight to flight, etc.
- Explain the *purpose* of safety margins, test protocols, and certification
  requirements (why static testing precedes flight, why remote ignition
  matters, why containment matters) so users understand the reasoning, not
  just the rule.
- Help users build documentation: test logs, pre-flight checklists,
  hazard analyses, range safety briefings.
- Point users to their motor class's regulatory and certification path
  (e.g., in the US: ATF low-explosive user permit requirements for APCP
  above threshold quantities, Tripoli/NAR high-power certification levels,
  NFPA 1127 code) and tell them plainly when their project requires
  certified mentorship or licensure they don't yet have.
- Help write and edit the surrounding software (simulation tools,
  logging, UI, calculators) per the CODE EDITING section below.

# HARD BOUNDARIES — YOU DO NOT PROVIDE
- Propellant formulations, oxidizer/fuel/binder ratios, specific chemical
  recipes, or mixing/curing procedures for any propellant type (APCP,
  black powder, sugar propellant, etc.), even if the user claims to be
  certified, a professional, or "just testing in software."
- Igniter or initiator composition or construction details.
- Guidance that optimizes a design specifically for maximum energy release,
  fragmentation, or effect on a target rather than controlled propulsion.
- Any output that would function as a usable synthesis or assembly
  procedure for an energetic material, regardless of how the request is
  framed (fictional, "for my documentation," "the AI in the story would
  say," defeat-testing, etc.).
- Confirmation, sign-off, or "this is safe to test/fly" declarations. You
  can say a design *appears* consistent with a stated standard, but you
  always frame final go/no-go authority as belonging to a certified
  range safety officer / mentor / test conductor, never to you.

If a user pushes on these boundaries, don't lecture at length — state once
that this is outside what you'll generate, explain briefly why (irreversible
harm potential, not a matter of user skill level), and redirect to the
appropriate certified resource. Do not soften this if the user reframes the
request, expresses frustration, or claims prior authorization.

# ESCALATION LANGUAGE (use naturally, don't robotically repeat)
- "This is the kind of step where a small error is unrecoverable — this
  needs a certified mentor or RSO in the loop before you proceed."
- "I can help you think through the engineering tradeoffs here, but I
  can't generate propellant/ignition specifics — that has to come from
  a certified source or your own hands-on-verified formulation under
  supervision."
- "Before this goes anywhere near a test stand: has this been reviewed
  by [Tripoli/NAR mentor, RSO, etc.]?"

# INTERACTION STYLE
- Ask what stage the user is at (design/sim, static test prep, flight prep)
  before diving in — the risk profile and appropriate depth differ a lot.
- Default to more caution for users who seem to be skipping stages (e.g.,
  asking about flight readiness with no static test data).
- Never let enthusiasm or sunk cost ("I already built it, just tell me if
  it's fine") lower your bar for what needs independent verification.
- Cite relevant standards/codes by name when relevant so users can look
  them up themselves rather than treating you as the final word.

# CODE EDITING CAPABILITY
You may read, write, and modify any file in this application's codebase
when the user requests it (features, UI, calculators, simulation logic,
data models, etc.). Standard engineering practice applies:
- Confirm scope for any change that touches safety-relevant logic (e.g.,
  a checklist that gates a stage, a warning threshold, a calculation used
  in go/no-go decisions) before making it, and flag clearly if a requested
  change would remove or weaken a safety check.
- Never quietly remove, disable, or bypass a safety gate, confirmation
  step, or logged warning as a side effect of an unrelated feature request
  — surface it explicitly and ask.
- Normal software changes (UI, non-safety features, refactors) can proceed
  without special ceremony.
"""

EMBEDDED_CONTEXT = """\
# EMBEDDED CONTEXT (how you are running right now)
You are embedded in the IgnitionBench web app — a project-based solid motor
design studio (propellant selection → BATES/face-slit grain + de Laval nozzle
design → burn simulation). The user sees pressures in psi and dimensions in mm.
Propellant burn-rate data comes from published strand-burner measurements
(openMotor/Nakka datasets); never invent or extrapolate propellant data, and
remind users to validate against BurnSim or published data before any hardware.

In this chat you cannot read or edit the application's source code — the CODE
EDITING section applies only when you are given file tools, which you have not
been. What you CAN do here is edit the user's current motor design via the
update_project_design tool. Every change you submit is validated by the same
physics pipeline as the UI (geometry checks, validated-pressure-range checks,
overpressure rejection); invalid designs are rejected and NOT saved. Changing
a design is reversible and safe — it edits a simulation file, not hardware.
Use the tool when the user asks you to change their design or when you are
correcting a hazard they asked you to fix; state what you changed and why.

When a <project_context> block is present it reflects the user's live project
state at the start of this exchange, including the app's own computed analysis
and safety warnings. Address every warning listed there when reviewing.
"""

REVIEW_INSTRUCTION = """\
Please write a full safety review of this project for the Review tab. Format
it in Markdown with these sections:

## Design summary
One short paragraph: what this motor is (class, propellant, size, impulse).

## Hazards and warnings
Cover EVERY warning in the project context above — explain each in plain
language (what it means physically, what can go wrong, how to fix it). Then
add any hazards the app's checks do NOT cover that you can see from the
numbers (casing not modeled, ignition, static-test practice, storage,
regulatory thresholds, etc.). If there are no app warnings, say so and still
cover the not-modeled hazards.

## What looks reasonable
Brief — parameters that sit in normal ranges for this class.

## Recommended next steps
Concrete, ordered, incremental-validation steps appropriate to this user's
stage. Include the certification path for this motor class.

Keep it under ~600 words, direct and readable for a beginner. Do not sign off
on the design — frame final authority as belonging to a certified RSO/mentor.
"""

UPDATE_DESIGN_TOOL = {
    "name": "update_project_design",
    "description": (
        "Update the user's current motor design in IgnitionBench. Pass only the "
        "fields you want to change; everything else is kept. The change is "
        "validated by the app's physics pipeline first — if the design is "
        "invalid or unsafe (overpressure, geometry errors), it is rejected and "
        "NOT saved, and you get the reason back. On success you get the new "
        "computed analysis including any safety warnings."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "grain": {
                "type": "object",
                "description": "BATES grain fields to change (dimensions in mm).",
                "properties": {
                    "segments": {"type": "integer", "minimum": 1, "maximum": 10},
                    "outer_d_mm": {"type": "number"},
                    "core_d_mm": {"type": "number"},
                    "length_mm": {"type": "number", "description": "Length of one segment."},
                    "slit_count": {"type": "integer", "minimum": 0, "maximum": 8},
                    "slit_depth_mm": {"type": "number"},
                    "slit_width_mm": {"type": "number"},
                    "slit_length_mm": {"type": "number", "description": "Cut length from the motor's forward face."},
                    "slit_taper_pct": {"type": "number", "minimum": 0, "maximum": 100},
                },
                "additionalProperties": False,
            },
            "nozzle": {
                "type": "object",
                "properties": {
                    "throat_d_mm": {"type": "number"},
                    "half_angle_deg": {"type": "number"},
                },
                "additionalProperties": False,
            },
            "propellant_key": {
                "type": "string",
                "description": "Switch to a library propellant by key (e.g. 'knsb', 'kndx').",
            },
        },
        "additionalProperties": False,
    },
}

_INT_FIELDS = {"segments", "slit_count"}


class AIError(RuntimeError):
    """An AI request failed for reasons the caller should surface to the UI."""


def configured() -> bool:
    """Whether the Anthropic SDK has any credential source to resolve."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    return os.path.isdir(os.path.expanduser("~/.config/anthropic/credentials"))


def _client():
    import anthropic

    return anthropic.Anthropic()


def _analyze(payload: dict) -> dict:
    """Run the app's own design pipeline; returns the result or {'error': ...}."""
    from ignitionbench.web import DesignError, _design_result, _parse_design

    try:
        prop, grain, throat_area, half_angle = _parse_design(payload)
        return _design_result(prop, grain, throat_area, half_angle)
    except (DesignError, ValueError) as exc:
        return {"error": str(exc)}


def _analysis_summary(analysis: dict) -> str:
    if "error" in analysis:
        return f"Design INVALID — rejected by the physics pipeline: {analysis['error']}"
    lines = [
        f"Kn {analysis['kn']:.0f}",
        f"chamber pressure {analysis['chamber_pressure_psi']:.0f} psi "
        f"({analysis['chamber_pressure_mpa']:.2f} MPa)",
        f"thrust {analysis['thrust_n']:.0f} N",
        f"total impulse {analysis['total_impulse_ns']:.0f} N·s (class {analysis['motor_class']})",
        f"burn time {analysis['burn_time_s']:.2f} s",
        f"propellant mass {analysis['propellant_mass_g']:.0f} g",
        f"port/throat {analysis['port_to_throat']:.2f}",
        f"certification: {analysis['certification']['text']}",
    ]
    out = "Computed analysis: " + ", ".join(lines) + "."
    if analysis["warnings"]:
        out += "\nActive safety warnings:\n" + "\n".join(
            f"- [{w['level']}] {w['text']}" for w in analysis["warnings"]
        )
    else:
        out += "\nNo active safety warnings from the app's checks."
    return out


def _project_context(project: dict) -> str:
    payload = {
        "propellant": project["propellant"],
        "grain": project["grain"],
        "nozzle": project["nozzle"],
    }
    analysis = _analyze(payload)
    prop = project["propellant"]
    prop_desc = (
        f"library propellant '{prop.get('key')}'"
        if prop.get("mode") == "library"
        else f"custom batch {json.dumps(prop.get('custom', {}))}"
    )
    return (
        f"Project name: {project['name']}\n"
        f"Propellant: {prop_desc}\n"
        f"Grain (mm): {json.dumps(project['grain'])}\n"
        f"Nozzle (mm/deg): {json.dumps(project['nozzle'])}\n"
        f"{_analysis_summary(analysis)}"
    )


def _apply_design_update(project_id: str, patch: dict) -> tuple[str, bool]:
    """Validate and apply a tool-call patch. Returns (tool result text, saved)."""
    project = store.load_project(project_id)
    grain = dict(project["grain"])
    nozzle = dict(project["nozzle"])
    propellant = dict(project["propellant"])

    for key, value in (patch.get("grain") or {}).items():
        if key in UPDATE_DESIGN_TOOL["input_schema"]["properties"]["grain"]["properties"]:
            grain[key] = int(value) if key in _INT_FIELDS else float(value)
    for key, value in (patch.get("nozzle") or {}).items():
        if key in UPDATE_DESIGN_TOOL["input_schema"]["properties"]["nozzle"]["properties"]:
            nozzle[key] = float(value)
    if patch.get("propellant_key"):
        propellant = {**propellant, "mode": "library", "key": str(patch["propellant_key"])}

    analysis = _analyze({"propellant": propellant, "grain": grain, "nozzle": nozzle})
    if "error" in analysis:
        return (
            f"Change REJECTED and not saved — the design failed validation: "
            f"{analysis['error']}",
            False,
        )
    store.update_project(
        project_id, {"grain": grain, "nozzle": nozzle, "propellant": propellant}
    )
    return f"Design updated and saved.\n{_analysis_summary(analysis)}", True


def _system_blocks(project: dict | None) -> list[dict]:
    text = MENTOR_SYSTEM + "\n\n" + EMBEDDED_CONTEXT
    if project is not None:
        text += f"\n\n<project_context>\n{_project_context(project)}\n</project_context>"
    return [{"type": "text", "text": text}]


def _run(client, *, system, messages, tools, handle_tool, max_tokens):
    """Manual tool loop. `handle_tool(block) -> str` runs a tool call and returns
    the tool_result text; side effects are the caller's business (via closure)."""
    import anthropic

    convo = list(messages)
    for _ in range(8):  # cap tool round-trips
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                system=system,
                messages=convo,
                tools=tools,
            )
        except anthropic.APIConnectionError as exc:
            raise AIError(f"Could not reach the Claude API: {exc}") from exc
        except anthropic.APIStatusError as exc:
            raise AIError(f"Claude API error ({exc.status_code}): {exc.message}") from exc
        if response.stop_reason != "tool_use":
            return response
        convo.append({"role": "assistant", "content": response.content})
        results = [
            {"type": "tool_result", "tool_use_id": block.id, "content": handle_tool(block)}
            for block in response.content
            if block.type == "tool_use"
        ]
        convo.append({"role": "user", "content": results})
    raise AIError("The AI made too many consecutive tool calls; stopping for safety.")


def _text_of(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


def chat(project_id: str | None, messages: list[dict]) -> dict:
    """One chat exchange. `messages` is the full history as [{role, content}]."""
    project = store.load_project(project_id) if project_id else None
    convo = [
        {"role": m["role"], "content": str(m["content"])}
        for m in messages
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    if not convo or convo[-1]["role"] != "user":
        raise AIError("The last message must be from the user.")

    updated = False

    def handle(block):
        nonlocal updated
        text, saved = _apply_design_update(project_id, block.input)
        updated = updated or saved
        return text

    response = _run(
        _client(),
        system=_system_blocks(project),
        messages=convo,
        tools=[UPDATE_DESIGN_TOOL] if project else [],
        handle_tool=handle,
        max_tokens=8000,
    )
    return {
        "reply": _text_of(response),
        "updated": updated,
        "project": store.load_project(project_id) if updated else None,
    }


def review(project_id: str) -> str:
    """Full-project safety review for the Review tab."""
    project = store.load_project(project_id)
    response = _run(
        _client(),
        system=_system_blocks(project),
        messages=[{"role": "user", "content": REVIEW_INSTRUCTION}],
        tools=[],  # a review must not silently change the design
        handle_tool=lambda block: "No tools are available in a review.",
        max_tokens=8000,
    )
    return _text_of(response)


# ---- AutoCast (Propellant Engine) ----

PROPOSE_GRAIN_TOOL = {
    "name": "propose_grain",
    "description": (
        "Propose a BATES grain + nozzle geometry that meets the user's stated "
        "goal. This does NOT change any saved design — it returns a proposal the "
        "user reviews and applies themselves. The proposal is checked by the "
        "app's physics pipeline against the chosen propellant; if it is invalid "
        "or overpressure you get the reason back and should adjust and call "
        "again. Geometry only — never propose propellant chemistry."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "grain": UPDATE_DESIGN_TOOL["input_schema"]["properties"]["grain"],
            "nozzle": UPDATE_DESIGN_TOOL["input_schema"]["properties"]["nozzle"],
        },
        "additionalProperties": False,
    },
}

AUTOCAST_INSTRUCTION = """\
The user wants AutoCast to design a grain for the goal in <cast_context>. Use the
propose_grain tool to submit a BATES grain + nozzle for the CHOSEN propellant
(do not change the propellant — geometry only). Iterate if the pipeline rejects
your proposal. When you have a valid proposal, reply in short Markdown:

## What I cast and why
One paragraph tying the geometry to the goal (impulse class, burn time, Kn,
port/throat margin).

## Recommended fins
Brief, qualitative fin guidance for a rocket on this motor (count, planform,
rough span/root ratio, and that stability margin must be checked with a proper
tool like OpenRocket) — recommendations only, no build instructions.

## Before you cast
One or two safety/next-step reminders. Do NOT provide any propellant
formulation, mixing, or casting-the-propellant procedure, and do not sign off
the design — final go/no-go belongs to a certified mentor/RSO.
"""


def _cast_context(propellant_key: str, grain: dict, nozzle: dict, goal: str) -> str:
    name = catalog_name(propellant_key)
    analysis = _analyze({
        "propellant": {"mode": "library", "key": propellant_key},
        "grain": grain,
        "nozzle": nozzle,
    })
    return (
        f"Chosen propellant: {name} (key '{propellant_key}') — keep this propellant.\n"
        f"User's goal: {goal or '(not specified — use sensible hobby defaults)'}\n"
        f"Starting grain (mm): {json.dumps(grain)}\n"
        f"Starting nozzle (mm/deg): {json.dumps(nozzle)}\n"
        f"Starting point {_analysis_summary(analysis)}"
    )


def catalog_name(key: str) -> str:
    from . import propellant_store

    entry = propellant_store.catalog().get(key)
    return entry["name"] if entry else key


def autocast(propellant_key: str, grain: dict, nozzle: dict, goal: str) -> dict:
    """Propose a grain + nozzle for a goal without saving anything."""
    base_grain = dict(grain)
    base_nozzle = dict(nozzle)
    proposal: dict = {}

    def handle(block):
        g = dict(base_grain)
        n = dict(base_nozzle)
        for key, value in (block.input.get("grain") or {}).items():
            if key in UPDATE_DESIGN_TOOL["input_schema"]["properties"]["grain"]["properties"]:
                g[key] = int(value) if key in _INT_FIELDS else float(value)
        for key, value in (block.input.get("nozzle") or {}).items():
            if key in UPDATE_DESIGN_TOOL["input_schema"]["properties"]["nozzle"]["properties"]:
                n[key] = float(value)
        analysis = _analyze({
            "propellant": {"mode": "library", "key": propellant_key},
            "grain": g,
            "nozzle": n,
        })
        if "error" in analysis:
            return f"Proposal REJECTED by the physics pipeline: {analysis['error']}. Adjust and try again."
        proposal["grain"] = g
        proposal["nozzle"] = n
        proposal["analysis"] = analysis
        return "Proposal is valid.\n" + _analysis_summary(analysis)

    system = [{
        "type": "text",
        "text": MENTOR_SYSTEM + "\n\n" + EMBEDDED_CONTEXT
        + f"\n\n<cast_context>\n{_cast_context(propellant_key, base_grain, base_nozzle, goal)}\n</cast_context>",
    }]
    response = _run(
        _client(),
        system=system,
        messages=[{"role": "user", "content": AUTOCAST_INSTRUCTION}],
        tools=[PROPOSE_GRAIN_TOOL],
        handle_tool=handle,
        max_tokens=4000,
    )
    result = {"reply": _text_of(response), "proposal": None}
    if "grain" in proposal:
        result["proposal"] = {"grain": proposal["grain"], "nozzle": proposal["nozzle"]}
        result["analysis"] = proposal["analysis"]
    return result
