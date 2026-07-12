"""Flask web app: project library + 3-step motor designer."""

from __future__ import annotations

import dataclasses
import math

from flask import Flask, Response, jsonify, redirect, render_template, request

from ignitionbench.export import grain_segment_stl
from ignitionbench.nozzle import (
    ConicalNozzle,
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
    BurnRateSegment,
    FaceSlitGrain,
    Propellant,
    kn,
    port_to_throat,
    regression_section,
    steady_state_pressure,
)
from ignitionbench.simulation import certification, motor_class, simulate_burn

from . import store


class DesignError(ValueError):
    pass


def _build_propellant(spec: dict) -> Propellant:
    if spec.get("mode") == "library":
        try:
            return PROPELLANTS[spec["key"]]
        except KeyError:
            raise DesignError(f"Unknown propellant {spec.get('key')!r}.") from None
    c = spec.get("custom", {})
    try:
        a_mm = float(c["a_mm_mpa"])
        n = float(c["n"])
        density = float(c["density"])
        gamma = float(c["gamma"])
        temp = float(c["temp_k"])
        molar_g = float(c["molar_g"])
        p_min = float(c["min_mpa"]) * 1e6
        p_max = float(c["max_mpa"]) * 1e6
    except (KeyError, TypeError, ValueError):
        raise DesignError("Custom propellant fields must all be valid numbers.") from None
    if a_mm <= 0 or not 0 < n < 1 or density <= 0 or gamma <= 1 or temp <= 0 or molar_g <= 0:
        raise DesignError(
            "Custom propellant out of range: need a > 0, 0 < n < 1, density > 0, "
            "gamma > 1, temperature > 0, molar mass > 0."
        )
    if not 0 < p_min < p_max:
        raise DesignError("Valid pressure range needs 0 < min < max (MPa).")
    a_si = a_mm * 1e-3 / (1e6**n)  # mm/s at MPa → m/s at Pa
    return Propellant(
        name=str(c.get("name") or "Custom batch"),
        density=density,
        combustion_temp=temp,
        molar_mass=molar_g / 1000,
        gamma=gamma,
        segments=(BurnRateSegment(p_min, p_max, a_si, n),),
    )


def _parse_design(data: dict) -> tuple[Propellant, BatesGrain, float, float]:
    prop = _build_propellant(data.get("propellant", {}))
    g = data.get("grain", {})
    nz = data.get("nozzle", {})
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
    return prop, grain, math.pi / 4 * throat_d**2, half_angle


def _design_result(prop: Propellant, grain: BatesGrain, throat_area: float, half_angle: float) -> dict:
    kn_ratio = kn(grain.burning_area(), throat_area)
    pc = steady_state_pressure(prop, kn_ratio)

    eps = optimal_expansion_ratio(pc, prop.gamma)
    cf = thrust_coefficient(pc, eps, prop.gamma, half_angle_deg=half_angle)
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

    # ---- propellant data ----

    @app.get("/api/propellants")
    def propellants():
        return jsonify(
            {
                key: {
                    "name": p.name,
                    "density": p.density,
                    "c_star": p.c_star,
                    "gamma": p.gamma,
                    "temp_k": p.combustion_temp,
                    "molar_g": p.molar_mass * 1000,
                    "min_pressure": p.min_pressure,
                    "max_pressure": p.max_pressure,
                    "segments": [
                        {"min": s.min_pressure, "max": s.max_pressure, "a": s.a, "n": s.n}
                        for s in p.segments
                    ],
                }
                for key, p in PROPELLANTS.items()
            }
        )

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
            prop, grain, throat_area, half_angle = _parse_design(request.get_json(force=True))
            return jsonify(_design_result(prop, grain, throat_area, half_angle))
        except (DesignError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 422

    @app.post("/api/simulate")
    def simulate():
        try:
            prop, grain, throat_area, half_angle = _parse_design(request.get_json(force=True))
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
            )
        except (KeyError, TypeError, ValueError) as exc:
            return jsonify({"error": f"Invalid grain dimensions: {exc}"}), 422
        return Response(
            data,
            mimetype="model/stl",
            headers={"Content-Disposition": "attachment; filename=grain-segment.stl"},
        )

    return app
