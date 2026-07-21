"""JSON-file store for user-created propellants under ~/.ignitionbench/propellants/.

A saved propellant is user-authored documentation — a name, an ingredient list,
a source note, preparation notes — attached to a set of burn-rate parameters
that drive the physics. Those parameters come from one of two places, never from
the app inventing a formulation:

* ``base_key`` — the propellant burns like a published, characterized entry from
  the built-in library (e.g. KNSB's real multi-segment Nakka fit). The app keeps
  that vetted data and simply labels it with the user's batch name and notes.
* ``ballistics`` — a single-segment Vieille's-law fit (a, n, density, gamma,
  flame temp, molar mass, valid pressure range) for someone who has their own
  strand-burner measurements or published data for a specific formulation.

Custom propellants surface in the propellant selection menu keyed as
``custom:<id>`` so they can be picked in any project like a built-in.

Override the location with IGNITIONBENCH_DATA_DIR (tests use this).
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
import uuid
from pathlib import Path

from ignitionbench.propellant import (
    PROPELLANTS,
    BurnRateSegment,
    Propellant,
)

CUSTOM_PREFIX = "custom:"

# The ballistic fields a single-segment custom needs, mirroring the project
# "custom batch" form so the two share one conversion path.
BALLISTIC_FIELDS = (
    "a_mm_mpa", "n", "density", "gamma", "temp_k", "molar_g", "min_mpa", "max_mpa",
)
INGREDIENT_ROLES = ("oxidizer", "fuel", "binder", "additive", "catalyst")


class PropellantError(ValueError):
    pass


def _dir() -> Path:
    root = os.environ.get("IGNITIONBENCH_DATA_DIR") or Path.home() / ".ignitionbench"
    path = Path(root) / "propellants"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ballistics_to_propellant(fields: dict, name: str = "Custom batch") -> Propellant:
    """Build a Propellant from the MPa/mm form fields, or raise PropellantError.

    Shared by the persisted library and the project inline "custom batch" mode
    so validation stays identical.
    """
    try:
        a_mm = float(fields["a_mm_mpa"])
        n = float(fields["n"])
        density = float(fields["density"])
        gamma = float(fields["gamma"])
        temp = float(fields["temp_k"])
        molar_g = float(fields["molar_g"])
        p_min = float(fields["min_mpa"]) * 1e6
        p_max = float(fields["max_mpa"]) * 1e6
    except (KeyError, TypeError, ValueError):
        raise PropellantError("Custom propellant fields must all be valid numbers.") from None
    if a_mm <= 0 or not 0 < n < 1 or density <= 0 or gamma <= 1 or temp <= 0 or molar_g <= 0:
        raise PropellantError(
            "Custom propellant out of range: need a > 0, 0 < n < 1, density > 0, "
            "gamma > 1, temperature > 0, molar mass > 0."
        )
    if not 0 < p_min < p_max:
        raise PropellantError("Valid pressure range needs 0 < min < max (MPa).")
    a_si = a_mm * 1e-3 / (1e6**n)  # mm/s at MPa → m/s at Pa
    return Propellant(
        name=str(name or "Custom batch"),
        density=density,
        combustion_temp=temp,
        molar_mass=molar_g / 1000,
        gamma=gamma,
        segments=(BurnRateSegment(p_min, p_max, a_si, n),),
    )


def record_to_propellant(record: dict) -> Propellant:
    """Resolve a saved record to a Propellant, or raise PropellantError."""
    base_key = record.get("base_key")
    if base_key:
        base = PROPELLANTS.get(base_key)
        if base is None:
            raise PropellantError(f"Unknown base propellant {base_key!r}.")
        return dataclasses.replace(base, name=record.get("name") or base.name)
    return ballistics_to_propellant(record.get("ballistics", {}), record.get("name", ""))


def _serialize(p: Propellant, *, custom: bool, extra: dict | None = None) -> dict:
    data = {
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
        "custom": custom,
    }
    if extra:
        data.update(extra)
    return data


def catalog() -> dict:
    """Every selectable propellant: built-ins plus saved customs (custom:<id>)."""
    out = {key: _serialize(p, custom=False) for key, p in PROPELLANTS.items()}
    for record in list_propellants():
        try:
            prop = record_to_propellant(record)
        except (PropellantError, KeyError, TypeError):
            continue
        out[CUSTOM_PREFIX + record["id"]] = _serialize(
            prop,
            custom=True,
            extra={
                "id": record["id"],
                "base_key": record.get("base_key", ""),
                "ingredients": record.get("ingredients", []),
                "source": record.get("source", ""),
                "prepare_notes": record.get("prepare_notes", ""),
                "created": record.get("created", 0),
                "updated": record.get("updated", 0),
            },
        )
    return out


def resolve(key: str) -> Propellant | None:
    """Return a Propellant for a selection key, or None if it isn't a saved custom."""
    if not key or not key.startswith(CUSTOM_PREFIX):
        return None
    try:
        record = load_propellant(key[len(CUSTOM_PREFIX):])
    except KeyError:
        raise PropellantError(f"Saved propellant {key!r} no longer exists.") from None
    return record_to_propellant(record)


# ---- CRUD ----


def list_propellants() -> list[dict]:
    records = []
    for path in _dir().glob("*.json"):
        try:
            records.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    records.sort(key=lambda r: r.get("updated", 0), reverse=True)
    return records


def load_propellant(propellant_id: str) -> dict:
    path = _dir() / f"{propellant_id}.json"
    if not path.is_file():
        raise KeyError(propellant_id)
    return json.loads(path.read_text())


def _clean_ingredients(raw) -> list[dict]:
    out = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        role = str(item.get("role", "")).strip().lower()
        if role not in INGREDIENT_ROLES:
            role = "additive"
        try:
            percent = round(float(item.get("percent", 0)), 3)
        except (TypeError, ValueError):
            percent = 0.0
        out.append({"name": name[:60], "role": role, "percent": percent})
    return out


def _burn_source(data: dict) -> dict:
    """Pick the burn-rate source from create/update input: base_key or ballistics."""
    base_key = (data.get("base_key") or "").strip()
    if base_key:
        if base_key not in PROPELLANTS:
            raise PropellantError(f"Unknown base propellant {base_key!r}.")
        return {"base_key": base_key}
    if "ballistics" in data:
        ballistics = {f: data["ballistics"].get(f) for f in BALLISTIC_FIELDS}
        ballistics_to_propellant(ballistics, data.get("name", ""))  # validate
        return {"ballistics": {f: float(ballistics[f]) for f in BALLISTIC_FIELDS}}
    raise PropellantError("Provide a base propellant to start from, or your own a/n data.")


def create_propellant(data: dict) -> dict:
    name = (data.get("name") or "").strip()
    if not name:
        raise PropellantError("Propellant name is required.")
    record = {
        "id": uuid.uuid4().hex[:12],
        "name": name[:60],
        "ingredients": _clean_ingredients(data.get("ingredients")),
        "source": str(data.get("source", "")).strip()[:200],
        "prepare_notes": str(data.get("prepare_notes", "")).strip()[:4000],
        "created": time.time(),
        "updated": time.time(),
        **_burn_source(data),
    }
    _write(record)
    return record


def update_propellant(propellant_id: str, data: dict) -> dict:
    record = load_propellant(propellant_id)
    if "name" in data:
        name = (data.get("name") or "").strip()
        if not name:
            raise PropellantError("Propellant name is required.")
        record["name"] = name[:60]
    if "ingredients" in data:
        record["ingredients"] = _clean_ingredients(data.get("ingredients"))
    if "source" in data:
        record["source"] = str(data.get("source", "")).strip()[:200]
    if "prepare_notes" in data:
        record["prepare_notes"] = str(data.get("prepare_notes", "")).strip()[:4000]
    if data.get("base_key") or "ballistics" in data:
        record.pop("base_key", None)
        record.pop("ballistics", None)
        record.update(_burn_source(data))
    record["updated"] = time.time()
    _write(record)
    return record


def delete_propellant(propellant_id: str) -> None:
    path = _dir() / f"{propellant_id}.json"
    if not path.is_file():
        raise KeyError(propellant_id)
    path.unlink()


def _write(record: dict) -> None:
    path = _dir() / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2))
