"""Persistent custom-propellant library: store + API + design integration."""

import pytest

from ignitionbench.web import create_app, propellant_store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("IGNITIONBENCH_DATA_DIR", str(tmp_path))
    return create_app().test_client()


# a valid KNSB-like batch expressed in the MPa/mm form fields
BATCH = {
    "name": "My sugar batch",
    "ingredients": [
        {"name": "Potassium nitrate", "role": "oxidizer", "percent": 65},
        {"name": "Sorbitol", "role": "fuel", "percent": 35},
    ],
    "source": "Started from published KNSB data",
    "prepare_notes": "Mentor-supervised, PPE on.",
    "ballistics": {
        "a_mm_mpa": 8.26, "n": 0.319, "density": 1750, "gamma": 1.1361,
        "temp_k": 1520, "molar_g": 39.9, "min_mpa": 0.2, "max_mpa": 8.0,
    },
}


def test_create_shows_up_in_catalog_with_metadata(client):
    rec = client.post("/api/propellants", json=BATCH).get_json()
    assert client.post("/api/propellants", json=BATCH).status_code  # sanity: endpoint exists
    catalog = client.get("/api/propellants").get_json()

    key = f"custom:{rec['id']}"
    assert key in catalog
    entry = catalog[key]
    assert entry["custom"] is True
    assert entry["name"] == "My sugar batch"
    assert entry["c_star"] > 0
    assert len(entry["segments"]) == 1
    assert entry["ingredients"][0]["name"] == "Potassium nitrate"
    # built-ins are still present and flagged non-custom
    assert catalog["knsb"]["custom"] is False


def test_create_rejects_invalid_ballistics(client):
    bad = {**BATCH, "ballistics": {**BATCH["ballistics"], "n": 1.5}}  # n must be < 1
    res = client.post("/api/propellants", json=bad)
    assert res.status_code == 422
    assert "n" in res.get_json()["error"]


def test_create_requires_a_name(client):
    res = client.post("/api/propellants", json={**BATCH, "name": "  "})
    assert res.status_code == 422


def test_saved_propellant_drives_a_real_design(client):
    rec = client.post("/api/propellants", json=BATCH).get_json()
    design = client.post(
        "/api/design",
        json={
            "propellant": {"mode": "library", "key": f"custom:{rec['id']}"},
            "grain": {"segments": 3, "outer_d_mm": 54, "core_d_mm": 20, "length_mm": 95,
                      "slit_count": 0},
            "nozzle": {"throat_d_mm": 15, "half_angle_deg": 15},
        },
    )
    assert design.status_code == 200
    d = design.get_json()
    assert d["propellant_name"] == "My sugar batch"
    assert d["chamber_pressure_psi"] > 0


def test_delete_removes_from_catalog(client):
    rec = client.post("/api/propellants", json=BATCH).get_json()
    key = f"custom:{rec['id']}"
    assert key in client.get("/api/propellants").get_json()
    assert client.delete(f"/api/propellants/{rec['id']}").status_code == 200
    assert key not in client.get("/api/propellants").get_json()
    assert client.delete("/api/propellants/nope").status_code == 404


def test_update_changes_fields(client):
    rec = client.post("/api/propellants", json=BATCH).get_json()
    client.put(f"/api/propellants/{rec['id']}", json={"name": "Renamed batch"})
    catalog = client.get("/api/propellants").get_json()
    assert catalog[f"custom:{rec['id']}"]["name"] == "Renamed batch"


def test_resolve_unknown_custom_raises(client):
    with pytest.raises(propellant_store.PropellantError):
        propellant_store.resolve("custom:doesnotexist")
    assert propellant_store.resolve("knsb") is None  # built-ins aren't custom keys


def test_base_key_derives_published_physics(client):
    """A propellant started from a published baseline keeps the real multi-segment data."""
    rec = client.post(
        "/api/propellants",
        json={
            "name": "My KNSB batch",
            "base_key": "knsb",
            "ingredients": [{"name": "Potassium nitrate", "role": "oxidizer", "percent": 65}],
        },
    ).get_json()
    entry = client.get("/api/propellants").get_json()[f"custom:{rec['id']}"]
    # KNSB's published fit has 5 burn-rate segments — the label changes, not the physics
    assert len(entry["segments"]) == 5
    assert entry["name"] == "My KNSB batch"
    assert entry["base_key"] == "knsb"
    assert entry["c_star"] == pytest.approx(client.get("/api/propellants").get_json()["knsb"]["c_star"])


def test_create_needs_a_burn_source(client):
    res = client.post("/api/propellants", json={"name": "Nameless physics"})
    assert res.status_code == 422


def test_bad_base_key_is_rejected(client):
    res = client.post("/api/propellants", json={"name": "X", "base_key": "unobtanium"})
    assert res.status_code == 422
