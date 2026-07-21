"""AI mentor endpoints, with the Anthropic client mocked out."""

import pytest

from ignitionbench.web import ai, create_app


class Block:
    def __init__(self, type, **kw):
        self.type = type
        self.__dict__.update(kw)


class FakeResponse:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("IGNITIONBENCH_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    return create_app().test_client()


def _fake(monkeypatch, responses) -> FakeClient:
    fake = FakeClient(responses)
    monkeypatch.setattr(ai, "_client", lambda: fake)
    return fake


def _project(client) -> str:
    return client.post("/api/projects", json={"name": "AI test"}).get_json()["id"]


def test_status_reports_configuration(client, monkeypatch):
    assert client.get("/api/ai/status").get_json()["configured"] is True
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setattr("os.path.isdir", lambda p: False)
    assert client.get("/api/ai/status").get_json()["configured"] is False


def test_chat_unconfigured_is_503(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setattr("os.path.isdir", lambda p: False)
    res = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert res.status_code == 503


def test_chat_answers_with_project_context(client, monkeypatch):
    pid = _project(client)
    fake = _fake(monkeypatch, [FakeResponse([Block("text", text="Kn looks fine.")])])
    res = client.post(
        "/api/ai/chat",
        json={"project_id": pid, "messages": [{"role": "user", "content": "Is my Kn ok?"}]},
    )
    assert res.status_code == 200
    d = res.get_json()
    assert d["reply"] == "Kn looks fine."
    assert d["updated"] is False
    call = fake.messages.calls[0]
    system_text = call["system"][0]["text"]
    assert "IgnitionBench" in system_text
    assert "<project_context>" in system_text
    assert "Kn" in system_text  # the computed analysis rides along
    assert call["tools"][0]["name"] == "update_project_design"


def test_chat_tool_edits_the_design(client, monkeypatch):
    pid = _project(client)
    fake = _fake(
        monkeypatch,
        [
            FakeResponse(
                [
                    Block("text", text="Widening the core."),
                    Block(
                        "tool_use",
                        id="toolu_1",
                        name="update_project_design",
                        input={"grain": {"core_d_mm": 24}},
                    ),
                ],
                stop_reason="tool_use",
            ),
            FakeResponse([Block("text", text="Done — core is now 24 mm.")]),
        ],
    )
    res = client.post(
        "/api/ai/chat",
        json={"project_id": pid, "messages": [{"role": "user", "content": "Widen the core to 24"}]},
    )
    d = res.get_json()
    assert d["updated"] is True
    assert d["project"]["grain"]["core_d_mm"] == 24
    assert client.get(f"/api/projects/{pid}").get_json()["grain"]["core_d_mm"] == 24
    # the tool result fed back to the model carries the fresh analysis
    tool_result = fake.messages.calls[1]["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "toolu_1"
    assert "Design updated and saved" in tool_result["content"]


def test_chat_tool_rejects_invalid_designs(client, monkeypatch):
    pid = _project(client)
    fake = _fake(
        monkeypatch,
        [
            FakeResponse(
                [
                    Block(
                        "tool_use",
                        id="toolu_1",
                        name="update_project_design",
                        input={"grain": {"core_d_mm": 60}},  # bigger than the 54 mm OD
                    )
                ],
                stop_reason="tool_use",
            ),
            FakeResponse([Block("text", text="That would be invalid.")]),
        ],
    )
    res = client.post(
        "/api/ai/chat",
        json={"project_id": pid, "messages": [{"role": "user", "content": "Core to 60mm"}]},
    )
    d = res.get_json()
    assert d["updated"] is False
    assert client.get(f"/api/projects/{pid}").get_json()["grain"]["core_d_mm"] == 20
    tool_result = fake.messages.calls[1]["messages"][-1]["content"][0]
    assert "REJECTED" in tool_result["content"]


def test_review_returns_markdown_and_uses_no_tools(client, monkeypatch):
    pid = _project(client)
    fake = _fake(monkeypatch, [FakeResponse([Block("text", text="## Design summary\nA J motor.")])])
    res = client.post("/api/ai/review", json={"project_id": pid})
    assert res.status_code == 200
    assert res.get_json()["review"].startswith("## Design summary")
    call = fake.messages.calls[0]
    assert call["tools"] == []
    assert "safety review" in call["messages"][0]["content"]


def test_review_missing_project_is_404(client, monkeypatch):
    _fake(monkeypatch, [])
    assert client.post("/api/ai/review", json={"project_id": "nope"}).status_code == 404


GRAIN = {
    "segments": 3, "outer_d_mm": 54, "core_d_mm": 20, "length_mm": 95,
    "slit_count": 0, "slit_depth_mm": 8, "slit_width_mm": 3,
    "slit_length_mm": 30, "slit_taper_pct": 30,
}
NOZZLE = {"throat_d_mm": 15, "half_angle_deg": 15}


def test_autocast_unconfigured_is_503(client, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setattr("os.path.isdir", lambda p: False)
    res = client.post("/api/ai/autocast", json={"propellant_key": "knsb", "grain": GRAIN, "nozzle": NOZZLE})
    assert res.status_code == 503


def test_autocast_proposes_valid_geometry(client, monkeypatch):
    fake = _fake(
        monkeypatch,
        [
            FakeResponse(
                [Block("tool_use", id="t1", name="propose_grain",
                       input={"grain": {"core_d_mm": 22}})],
                stop_reason="tool_use",
            ),
            FakeResponse([Block("text", text="## What I cast and why\nA J motor.")]),
        ],
    )
    res = client.post(
        "/api/ai/autocast",
        json={"propellant_key": "knsb", "grain": GRAIN, "nozzle": NOZZLE, "goal": "J burn"},
    )
    assert res.status_code == 200
    d = res.get_json()
    assert d["proposal"]["grain"]["core_d_mm"] == 22
    assert d["proposal"]["nozzle"]["throat_d_mm"] == 15  # untouched fields carry through
    assert "What I cast" in d["reply"]
    # the propose call is geometry-only and the system prompt keeps the safety boundaries
    system_text = fake.messages.calls[0]["system"][0]["text"]
    assert "HARD BOUNDARIES" in system_text
    assert "<cast_context>" in system_text
    # the tool result fed back carries the validated analysis, and nothing was saved
    tool_result = fake.messages.calls[1]["messages"][-1]["content"][0]
    assert "Proposal is valid" in tool_result["content"]


def test_autocast_rejects_invalid_geometry(client, monkeypatch):
    fake = _fake(
        monkeypatch,
        [
            FakeResponse(
                [Block("tool_use", id="t1", name="propose_grain",
                       input={"grain": {"core_d_mm": 60}})],  # bigger than the 54 mm OD
                stop_reason="tool_use",
            ),
            FakeResponse([Block("text", text="That geometry won't work; try a smaller core.")]),
        ],
    )
    res = client.post(
        "/api/ai/autocast",
        json={"propellant_key": "knsb", "grain": GRAIN, "nozzle": NOZZLE, "goal": "J burn"},
    )
    d = res.get_json()
    assert d["proposal"] is None
    tool_result = fake.messages.calls[1]["messages"][-1]["content"][0]
    assert "REJECTED" in tool_result["content"]
