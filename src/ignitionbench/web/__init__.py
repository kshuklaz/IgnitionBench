"""Flask web UI: dark single-page motor design calculator."""

from __future__ import annotations

import math

from flask import Flask, jsonify, render_template, request

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
    kn,
    port_to_throat,
    steady_state_pressure,
)
from ignitionbench.simulation import motor_class


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/propellants")
    def propellants():
        return jsonify(
            {
                key: {
                    "name": prop.name,
                    "density": prop.density,
                    "c_star": prop.c_star,
                    "min_pressure": prop.min_pressure,
                    "max_pressure": prop.max_pressure,
                }
                for key, prop in PROPELLANTS.items()
            }
        )

    @app.post("/api/design")
    def design():
        data = request.get_json(force=True)
        try:
            prop = PROPELLANTS[data["propellant"]]
            segments = int(data["segments"])
            outer_d = float(data["outer_d_mm"]) / 1000
            core_d = float(data["core_d_mm"]) / 1000
            length = float(data["length_mm"]) / 1000
            throat_d = float(data["throat_d_mm"]) / 1000
            half_angle = float(data["half_angle_deg"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "All inputs must be valid numbers."}), 422
        if throat_d <= 0 or not 0 < half_angle < 90:
            return jsonify({"error": "Throat diameter and half-angle must be positive (half-angle < 90°)."}), 422

        try:
            grain = BatesGrain(segments, outer_d, core_d, length)
            throat_area = math.pi / 4 * throat_d**2
            kn_ratio = kn(grain.burning_area(), throat_area)
            pc = steady_state_pressure(prop, kn_ratio)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 422

        eps = optimal_expansion_ratio(pc, prop.gamma)
        cf = thrust_coefficient(pc, eps, prop.gamma, half_angle_deg=half_angle)
        force = thrust(pc, throat_area, cf)
        isp = specific_impulse(cf, prop.c_star)
        mdot = mass_flow(pc, throat_area, prop.c_star)
        mass = grain.propellant_mass(prop)
        burn_time = mass / mdot  # constant-pressure estimate until burn regression lands
        total_impulse = force * burn_time
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
                    f"data limit ({prop.max_pressure / 1e6:.1f} MPa). Reduce Kn for margin.",
                }
            )

        return jsonify(
            {
                "kn": kn_ratio,
                "chamber_pressure_mpa": pc / 1e6,
                "chamber_pressure_psi": pc / 6895,
                "thrust_n": force,
                "isp_s": isp,
                "expansion_ratio": eps,
                "cf": cf,
                "exit_d_mm": nozzle.exit_diameter * 1000,
                "divergent_length_mm": nozzle.divergent_length * 1000,
                "mass_flow_kg_s": mdot,
                "propellant_mass_g": mass * 1000,
                "burn_time_s": burn_time,
                "total_impulse_ns": total_impulse,
                "motor_class": motor_class(total_impulse),
                "port_to_throat": p2t,
                "warnings": warnings,
                "geometry": {
                    "segments": segments,
                    "outer_d_mm": outer_d * 1000,
                    "core_d_mm": core_d * 1000,
                    "length_mm": length * 1000,
                    "throat_d_mm": throat_d * 1000,
                    "exit_d_mm": nozzle.exit_diameter * 1000,
                    "divergent_length_mm": nozzle.divergent_length * 1000,
                    "half_angle_deg": half_angle,
                },
            }
        )

    return app
