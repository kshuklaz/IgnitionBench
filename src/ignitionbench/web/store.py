"""JSON-file project store under ~/.ignitionbench/projects/.

One file per project; transparent, greppable, easy to back up. Override the
location with IGNITIONBENCH_DATA_DIR (tests use this).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

_SAVABLE = ("name", "propellant", "grain", "nozzle", "summary")


def _projects_dir() -> Path:
    root = os.environ.get("IGNITIONBENCH_DATA_DIR") or Path.home() / ".ignitionbench"
    path = Path(root) / "projects"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _default_project(name: str) -> dict:
    return {
        "name": name,
        "propellant": {
            "mode": "library",
            "key": "knsb",
            "custom": {
                "name": "My batch",
                "density": 1750,
                "a_mm_mpa": 8.26,
                "n": 0.319,
                "gamma": 1.13,
                "temp_k": 1600,
                "molar_g": 40.0,
                "min_mpa": 0.2,
                "max_mpa": 8.0,
            },
        },
        "grain": {"segments": 3, "outer_d_mm": 54, "core_d_mm": 20, "length_mm": 95},
        "nozzle": {"throat_d_mm": 15, "half_angle_deg": 15},
        "summary": {},
    }


def list_projects() -> list[dict]:
    projects = []
    for path in _projects_dir().glob("*.json"):
        try:
            projects.append(json.loads(path.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    projects.sort(key=lambda p: p.get("updated", 0), reverse=True)
    return projects


def load_project(project_id: str) -> dict:
    path = _projects_dir() / f"{project_id}.json"
    if not path.is_file():
        raise KeyError(project_id)
    return json.loads(path.read_text())


def create_project(name: str) -> dict:
    project = _default_project(name)
    project["id"] = uuid.uuid4().hex[:12]
    project["created"] = project["updated"] = time.time()
    _write(project)
    return project


def update_project(project_id: str, changes: dict) -> dict:
    project = load_project(project_id)
    for key in _SAVABLE:
        if key in changes:
            project[key] = changes[key]
    project["updated"] = time.time()
    _write(project)
    return project


def delete_project(project_id: str) -> None:
    path = _projects_dir() / f"{project_id}.json"
    if not path.is_file():
        raise KeyError(project_id)
    path.unlink()


def _write(project: dict) -> None:
    path = _projects_dir() / f"{project['id']}.json"
    path.write_text(json.dumps(project, indent=2))
