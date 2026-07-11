import pytest

from ignitionbench.web import create_app

DESIGN = {
    "propellant": "knsb",
    "segments": 3,
    "outer_d_mm": 54,
    "core_d_mm": 20,
    "length_mm": 95,
    "throat_d_mm": 15,
    "half_angle_deg": 15,
}


@pytest.fixture
def client():
    return create_app().test_client()


def test_propellants_endpoint(client):
    data = client.get("/api/propellants").get_json()
    assert "knsb" in data
    assert data["knsb"]["c_star"] == pytest.approx(885, rel=0.01)


def test_design_endpoint_matches_library(client):
    res = client.post("/api/design", json=DESIGN)
    assert res.status_code == 200
    d = res.get_json()
    assert d["kn"] == pytest.approx(168, abs=1)
    assert d["chamber_pressure_mpa"] == pytest.approx(2.01, abs=0.05)
    assert d["motor_class"] == "J"
    assert any(w["level"] == "warning" for w in d["warnings"])  # port/throat 1.78


def test_design_endpoint_flags_overpressure(client):
    res = client.post("/api/design", json={**DESIGN, "throat_d_mm": 4})
    assert res.status_code == 422
    assert "overpressure" in res.get_json()["error"]


def test_design_endpoint_rejects_garbage(client):
    res = client.post("/api/design", json={**DESIGN, "outer_d_mm": "not a number"})
    assert res.status_code == 422


def test_index_serves_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"IgnitionBench" in res.data
