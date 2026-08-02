"""Flask web app: project library + 3-step motor designer."""

from __future__ import annotations

import dataclasses
import math

from flask import Flask, Response, jsonify, redirect, render_template, request

from ignitionbench.export import grain_segment_stl
from ignitionbench.nozzle import (
    STANDARD_ATMOSPHERE,
    ConicalNozzle,
    exit_pressure,
    mass_flow,
    optimal_expansion_ratio,
    specific_impulse,
    thrust,
    thrust_coefficient,
)
from ignitionbench.propellant import (
    MIN_PORT_TO_THROAT,
    PROPELLANTS,
    BatesGrain,
    FaceSlitGrain,
    Propellant,
    kn,
    port_to_throat,
    regression_section,
    steady_state_pressure,
)
from ignitionbench.simulation import certification, motor_class, simulate_burn

from . import propellant_store, store


class DesignError(ValueError):
    pass


def _build_propellant(spec: dict) -> Propellant:
    if spec.get("mode") == "library":
        key = spec.get("key")
        try:
            resolved = propellant_store.resolve(key)  # saved custom:<id>?
        except propellant_store.PropellantError as exc:
            raise DesignError(str(exc)) from None
        if resolved is not None:
            return resolved
        try:
            return PROPELLANTS[key]
        except KeyError:
            raise DesignError(f"Unknown propellant {key!r}.") from None
    custom = spec.get("custom") or {}
    try:
        return propellant_store.ballistics_to_propellant(
            custom, custom.get("name") or "Custom batch"
        )
    except propellant_store.PropellantError as exc:
        raise DesignError(str(exc)) from None


def _parse_ambient(data: dict) -> float:
    """Ambient (back-)pressure in Pa. Defaults to sea level; clamped to a sane range.

    Accepts ``ambient_pa`` (Pa). Blank/missing/invalid falls back to sea level so
    existing callers and the project designer are unaffected.
    """
    raw = data.get("ambient_pa", None)
    if raw is None or raw == "":
        return STANDARD_ATMOSPHERE
    try:
        pa = float(raw)
    except (TypeError, ValueError):
        return STANDARD_ATMOSPHERE
    # 0 = vacuum (space); cap the top a little above a dense sea-level day.
    return max(0.0, min(pa, 150_000.0))


def _parse_design(data: dict) -> tuple[Propellant, BatesGrain, float, float, float]:
    prop = _build_propellant(data.get("propellant", {}))
    g = data.get("grain", {})
    nz = data.get("nozzle", {})
    ambient = _parse_ambient(data)
    try:
        slit_count = int(g.get("slit_count") or 0)
        if slit_count > 0:
            length_mm = float(g["length_mm"])
            grain = FaceSlitGrain(
                int(g["segments"]),
                float(g["outer_d_mm"]) / 1000,
                float(g["core_d_mm"]) / 1000,
                length_mm / 1000,
                slit_count=slit_count,
                slit_depth=float(g["slit_depth_mm"]) / 1000,
                slit_width=float(g["slit_width_mm"]) / 1000,
                slit_length=float(g.get("slit_length_mm") or length_mm / 3) / 1000,
                slit_taper=float(g.get("slit_taper_pct") or 0) / 100,
            )
        else:
            grain = BatesGrain(
                int(g["segments"]),
                float(g["outer_d_mm"]) / 1000,
                float(g["core_d_mm"]) / 1000,
                float(g["length_mm"]) / 1000,
            )
        throat_d = float(nz["throat_d_mm"]) / 1000
        half_angle = float(nz["half_angle_deg"])
    except (KeyError, TypeError) as exc:
        raise DesignError("All design inputs must be valid numbers.") from exc
    except ValueError as exc:
        raise DesignError(str(exc) or "All design inputs must be valid numbers.") from exc
    if throat_d <= 0 or not 0 < half_angle < 90:
        raise DesignError("Throat diameter must be positive and half-angle between 0 and 90°.")
    return prop, grain, math.pi / 4 * throat_d**2, half_angle, ambient


def _design_result(
    prop: Propellant,
    grain: BatesGrain,
    throat_area: float,
    half_angle: float,
    ambient: float = STANDARD_ATMOSPHERE,
) -> dict:
    kn_ratio = kn(grain.burning_area(), throat_area)
    pc = steady_state_pressure(prop, kn_ratio)

    # The nozzle is sized to expand optimally at sea level (a buildable, finite
    # geometry). Ambient pressure then only drives the pressure-thrust term, so
    # the same motor's thrust/Isp rise with altitude and peak in vacuum without
    # the exit diameter running off to infinity.
    eps = optimal_expansion_ratio(pc, prop.gamma)
    cf = thrust_coefficient(pc, eps, prop.gamma, ambient_pressure=ambient, half_angle_deg=half_angle)
    pe = exit_pressure(pc, eps, prop.gamma)
    force = thrust(pc, throat_area, cf)
    mdot = mass_flow(pc, throat_area, prop.c_star)
    mass = grain.propellant_mass(prop)
    burn_time = mass / mdot
    total_impulse = force * burn_time
    letter = motor_class(total_impulse)
    throat_d = math.sqrt(4 * throat_area / math.pi)
    nozzle = ConicalNozzle(throat_d, eps, half_angle)
    p2t = port_to_throat(grain.port_area(), throat_area)

    warnings = []
    if p2t < MIN_PORT_TO_THROAT:
        warnings.append(
            {
                "level": "warning",
                "text": f"Port-to-throat ratio {p2t:.2f} is below {MIN_PORT_TO_THROAT:.1f} — "
                "expect erosive burning and a pressure spike at ignition. Widen the core.",
            }
        )
    if pc > 0.85 * prop.max_pressure:
        warnings.append(
            {
                "level": "serious",
                "text": f"Chamber pressure is within 15% of the propellant's validated "
                f"data limit ({prop.max_pressure / 6895:.0f} psi). Reduce Kn for margin.",
            }
        )

    return {
        "kn": kn_ratio,
        "chamber_pressure_mpa": pc / 1e6,
        "chamber_pressure_psi": pc / 6895,
        "thrust_n": force,
        "isp_s": specific_impulse(cf, prop.c_star),
        "expansion_ratio": eps,
        "cf": cf,
        "ambient_pa": ambient,
        "ambient_kpa": ambient / 1000,
        "exit_pressure_kpa": pe / 1000,
        "exit_d_mm": nozzle.exit_diameter * 1000,
        "divergent_length_mm": nozzle.divergent_length * 1000,
        "mass_flow_kg_s": mdot,
        "propellant_mass_g": mass * 1000,
        "burn_time_s": burn_time,
        "total_impulse_ns": total_impulse,
        "motor_class": letter,
        "certification": certification(letter),
        "port_to_throat": p2t,
        "warnings": warnings,
        "propellant_name": prop.name,
        "geometry": {
            "segments": grain.segment_count,
            "outer_d_mm": grain.outer_diameter * 1000,
            "core_d_mm": grain.core_diameter * 1000,
            "length_mm": grain.segment_length * 1000,
            "slit_count": getattr(grain, "slit_count", 0),
            "slit_depth_mm": getattr(grain, "slit_depth", 0.0) * 1000,
            "slit_width_mm": getattr(grain, "slit_width", 0.0) * 1000,
            "slit_length_mm": getattr(grain, "slit_length", 0.0) * 1000,
            "slit_taper": getattr(grain, "slit_taper", 0.0),
            "throat_d_mm": throat_d * 1000,
            "exit_d_mm": nozzle.exit_diameter * 1000,
            "divergent_length_mm": nozzle.divergent_length * 1000,
            "half_angle_deg": half_angle,
        },
    }


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["TEMPLATES_AUTO_RELOAD"] = True  # local tool; pick up edits without restart

    # ---- pages ----

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.get("/project/<project_id>")
    def project_page(project_id: str):
        try:
            store.load_project(project_id)
        except KeyError:
            return redirect("/")
        return render_template("project.html", project_id=project_id)

    @app.get("/engine")
    def engine_page():
        return render_template("engine.html")

    # ---- propellant data ----

    @app.get("/api/propellants")
    def propellants():
        return jsonify(propellant_store.catalog())

    @app.post("/api/propellants")
    def propellants_create():
        try:
            return jsonify(propellant_store.create_propellant(request.get_json(force=True))), 201
        except propellant_store.PropellantError as exc:
            return jsonify({"error": str(exc)}), 422

    @app.put("/api/propellants/<propellant_id>")
    def propellants_update(propellant_id: str):
        try:
            return jsonify(
                propellant_store.update_propellant(propellant_id, request.get_json(force=True))
            )
        except KeyError:
            return jsonify({"error": "Propellant not found."}), 404
        except propellant_store.PropellantError as exc:
            return jsonify({"error": str(exc)}), 422

    @app.delete("/api/propellants/<propellant_id>")
    def propellants_delete(propellant_id: str):
        try:
            propellant_store.delete_propellant(propellant_id)
        except KeyError:
            return jsonify({"error": "Propellant not found."}), 404
        return jsonify({"ok": True})

    # ---- projects ----

    @app.get("/api/projects")
    def projects_list():
        return jsonify(store.list_projects())

    @app.post("/api/projects")
    def projects_create():
        name = (request.get_json(force=True).get("name") or "").strip()
        if not name:
            return jsonify({"error": "Project name is required."}), 422
        return jsonify(store.create_project(name)), 201

    @app.get("/api/projects/<project_id>")
    def projects_get(project_id: str):
        try:
            return jsonify(store.load_project(project_id))
        except KeyError:
            return jsonify({"error": "Project not found."}), 404

    @app.put("/api/projects/<project_id>")
    def projects_update(project_id: str):
        try:
            return jsonify(store.update_project(project_id, request.get_json(force=True)))
        except KeyError:
            return jsonify({"error": "Project not found."}), 404

    @app.delete("/api/projects/<project_id>")
    def projects_delete(project_id: str):
        try:
            store.delete_project(project_id)
        except KeyError:
            return jsonify({"error": "Project not found."}), 404
        return jsonify({"ok": True})

    # ---- physics ----

    @app.post("/api/design")
    def design():
        try:
            prop, grain, throat_area, half_angle, ambient = _parse_design(request.get_json(force=True))
            return jsonify(_design_result(prop, grain, throat_area, half_angle, ambient))
        except (DesignError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 422

    @app.post("/api/simulate")
    def simulate():
        try:
            prop, grain, throat_area, half_angle, _ambient = _parse_design(request.get_json(force=True))
            # The burn sim optimizes its own nozzle to sea level; ambient is a
            # design-page what-if only, so it is intentionally not threaded here.
            result = simulate_burn(prop, grain, throat_area, half_angle_deg=half_angle)
        except (DesignError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 422
        payload = dataclasses.asdict(result)
        payload["certification"] = certification(result.motor_class)
        payload["initial_mass_g"] = grain.propellant_mass(prop) * 1000
        # distance field through a slit axis for the regression view
        payload["slit_section"] = (
            regression_section(grain) if isinstance(grain, FaceSlitGrain) else None
        )
        return jsonify(payload)

    # ---- AI mentor ----

    from . import ai
    from . import settings as app_settings

    def _ai_status_payload() -> dict:
        source = ai.credential_source()
        return {
            "configured": ai.configured(),
            "model": ai.MODEL,
            "source": source,
            "key_hint": app_settings.masked_key(),
            # An env-var key can't be changed from the UI (it would be overridden).
            "editable": source in ("stored", "none"),
        }

    @app.get("/api/ai/status")
    def ai_status():
        return jsonify(_ai_status_payload())

    @app.post("/api/ai/key")
    def ai_set_key():
        key = (request.get_json(force=True).get("key") or "").strip()
        try:
            ai.validate_key(key)
        except ai.AIError as exc:
            return jsonify({"error": str(exc)}), 422
        app_settings.set_api_key(key)
        return jsonify(_ai_status_payload())

    @app.delete("/api/ai/key")
    def ai_clear_key():
        app_settings.clear_api_key()
        return jsonify(_ai_status_payload())

    @app.post("/api/ai/chat")
    def ai_chat():
        if not ai.configured():
            return jsonify({"error": "AI is not configured — set ANTHROPIC_API_KEY."}), 503
        data = request.get_json(force=True)
        try:
            return jsonify(ai.chat(data.get("project_id"), data.get("messages") or []))
        except KeyError:
            return jsonify({"error": "Project not found."}), 404
        except ai.AIError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.post("/api/ai/review")
    def ai_review():
        if not ai.configured():
            return jsonify({"error": "AI is not configured — set ANTHROPIC_API_KEY."}), 503
        data = request.get_json(force=True)
        try:
            return jsonify({"review": ai.review(data["project_id"])})
        except KeyError:
            return jsonify({"error": "Project not found."}), 404
        except ai.AIError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.post("/api/ai/autocast")
    def ai_autocast():
        if not ai.configured():
            return jsonify({"error": "AI is not configured — set ANTHROPIC_API_KEY."}), 503
        data = request.get_json(force=True)
        try:
            return jsonify(
                ai.autocast(
                    data.get("propellant_key") or "knsb",
                    data.get("grain") or {},
                    data.get("nozzle") or {},
                    data.get("goal") or "",
                )
            )
        except ai.AIError as exc:
            return jsonify({"error": str(exc)}), 502

    @app.get("/api/stl")
    def stl():
        try:
            data = grain_segment_stl(
                float(request.args["outer_d_mm"]) / 1000,
                float(request.args["core_d_mm"]) / 1000,
                float(request.args["length_mm"]) / 1000,
                slit_count=int(request.args.get("slit_count") or 0),
                slit_depth=float(request.args.get("slit_depth_mm") or 0) / 1000,
                slit_width=float(request.args.get("slit_width_mm") or 0) / 1000,
                slit_length=float(request.args.get("slit_length_mm") or 0) / 1000,
                slit_taper=float(request.args.get("slit_taper_pct") or 0) / 100,
                segment_count=int(request.args.get("segments") or 1),
            )
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify({"error": f"Invalid grain dimensions: {exc}"}), 422
        return Response(
            data,
            mimetype="model/stl",
            headers={"Content-Disposition": "attachment; filename=grain.stl"},
        )

    return app
