import pytest

from ignitionbench.web import create_app

DESIGN = {
    "propellant": {"mode": "library", "key": "knsb"},
    "grain": {"segments": 3, "outer_d_mm": 54, "core_d_mm": 20, "length_mm": 95},
    "nozzle": {"throat_d_mm": 15, "half_angle_deg": 15},
}

CUSTOM = {
    **DESIGN,
    "propellant": {
        "mode": "custom",
        "custom": {
            "name": "Test batch",
            "density": 1800,
            "a_mm_mpa": 8.26,
            "n": 0.319,
            "gamma": 1.13,
            "temp_k": 1720,
            "molar_g": 42.0,
            "min_mpa": 0.1,
            "max_mpa": 10.0,
        },
    },
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("IGNITIONBENCH_DATA_DIR", str(tmp_path))
    return create_app().test_client()


def test_home_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"IgnitionBench" in res.data


def test_project_crud_roundtrip(client):
    created = client.post("/api/projects", json={"name": "My J motor"}).get_json()
    assert created["name"] == "My J motor"
    assert created["propellant"]["mode"] == "library"

    assert client.get(f"/project/{created['id']}").status_code == 200
    assert client.get("/project/nope").status_code == 302  # redirect home

    updated = client.put(
        f"/api/projects/{created['id']}", json={"name": "Renamed"}
    ).get_json()
    assert updated["name"] == "Renamed"

    names = [p["name"] for p in client.get("/api/projects").get_json()]
    assert "Renamed" in names

    assert client.delete(f"/api/projects/{created['id']}").status_code == 200
    assert client.get("/api/projects").get_json() == []


def test_create_requires_name(client):
    assert client.post("/api/projects", json={"name": "  "}).status_code == 422


def test_design_endpoint_library(client):
    res = client.post("/api/design", json=DESIGN)
    assert res.status_code == 200
    d = res.get_json()
    assert d["kn"] == pytest.approx(168, abs=1)
    assert d["motor_class"] == "J"
    assert d["certification"]["level"] == "L2"
    assert any(w["level"] == "warning" for w in d["warnings"])  # port/throat 1.78


def test_design_endpoint_custom_propellant(client):
    res = client.post("/api/design", json=CUSTOM)
    assert res.status_code == 200
    d = res.get_json()
    assert d["propellant_name"] == "Test batch"
    assert d["chamber_pressure_mpa"] > 0.1


def test_design_rejects_bad_custom_exponent(client):
    bad = {**CUSTOM, "propellant": {"mode": "custom", "custom": {**CUSTOM["propellant"]["custom"], "n": 1.4}}}
    assert client.post("/api/design", json=bad).status_code == 422


def test_design_endpoint_flags_overpressure(client):
    res = client.post("/api/design", json={**DESIGN, "nozzle": {"throat_d_mm": 4, "half_angle_deg": 15}})
    assert res.status_code == 422
    assert "overpressure" in res.get_json()["error"]


def test_simulate_endpoint(client):
    res = client.post("/api/simulate", json=DESIGN)
    assert res.status_code == 200
    d = res.get_json()
    assert len(d["time"]) == len(d["thrust"]) == len(d["pressure"]) == 241
    assert d["motor_class"] == "J"
    assert d["certification"]["level"] == "L2"
    assert d["thrust"][-1] == 0.0


def test_stl_endpoint(client):
    res = client.get("/api/stl?outer_d_mm=54&core_d_mm=20&length_mm=95")
    assert res.status_code == 200
    assert res.mimetype == "model/stl"
    assert len(res.data) > 84
    assert client.get("/api/stl?outer_d_mm=10&core_d_mm=20&length_mm=95").status_code == 422
