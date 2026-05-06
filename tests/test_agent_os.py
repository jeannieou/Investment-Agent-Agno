import asyncio

from fastapi.testclient import TestClient

from app.schemas import WorkflowState
from app.agent_os import app, mock_research_workflow


def test_agent_os_demo_health_route() -> None:
    client = TestClient(app)

    response = client.get("/demo/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_agent_os_demo_config_route() -> None:
    client = TestClient(app)

    response = client.get("/demo/config")

    assert response.status_code == 200
    body = response.json()
    assert "openai_api_key_set" in body
    assert "exa_api_key_set" in body


def test_agent_os_resolve_route_returns_identities() -> None:
    client = TestClient(app)

    response = client.post("/demo/resolve", json={"companies": ["Nvidia", "AMD", "Intel"]})

    assert response.status_code == 200
    body = response.json()
    assert len(body["confirmed_companies"]) == 3
    assert body["confirmed_companies"][0]["name"] == "Nvidia"


def test_agent_os_mock_research_route_returns_memo_and_state() -> None:
    client = TestClient(app)

    response = client.post("/demo/mock-research", json={"companies": ["Nvidia", "AMD", "Intel"]})

    assert response.status_code == 200
    body = response.json()
    assert "# Investment Recommendation Memo" in body["memo"]
    assert "Invest in:" in body["memo"]
    assert "## Sources" in body["memo"]
    assert len(body["state"]["research"]) == 3


def test_agent_os_mock_research_route_rejects_more_than_eight_companies() -> None:
    client = TestClient(app)

    response = client.post(
        "/demo/mock-research",
        json={"companies": [f"Company {index}" for index in range(9)]},
    )

    assert response.status_code == 400
    assert "at most 8" in response.json()["detail"]


def test_agno_workflow_wrapper_runs_without_llm() -> None:
    output = asyncio.run(mock_research_workflow.arun("Nvidia,AMD,Intel"))

    assert output.content.startswith("> Usage: enter up to 6 company names")
    assert "# Investment Recommendation Memo" in output.content
    assert "Invest in:" in output.content
    assert "Nvidia" in output.content


def test_agno_workflow_endpoint_accepts_plain_company_names() -> None:
    client = TestClient(app)

    response = client.post(
        "/workflows/mock-investment-research/runs",
        data={"message": "Nvidia,AMD,Intel", "stream": "false"},
    )

    assert response.status_code == 200
    body = response.json()
    assert "Usage: enter up to 6 company names" in body["content"]
    assert "# Investment Recommendation Memo" in body["content"]
    assert "Invest in:" in body["content"]


def test_agno_workflow_endpoint_returns_limit_message() -> None:
    client = TestClient(app)

    response = client.post(
        "/workflows/mock-investment-research/runs",
        data={
            "message": ",".join(f"Company {index}" for index in range(9)),
            "stream": "false",
        },
    )

    assert response.status_code == 200
    assert "Cannot start workflow" in response.json()["content"]
    assert "at most 8" in response.json()["content"]


def test_agent_os_session_route_is_available_for_ui() -> None:
    client = TestClient(app)

    response = client.post("/sessions", json={"workflow_id": "mock-investment-research"})

    assert response.status_code == 201
    assert response.json()["session_id"]


def test_agent_os_live_route_can_be_mocked(monkeypatch) -> None:
    def fake_run_live_workflow(companies, auto_confirm=True, progress_callback=None):
        return WorkflowState(
            raw_input=companies,
            memo="# Investment Recommendation Memo\n\n## Recommendation\n**Invest in: Nvidia**\n",
        )

    monkeypatch.setattr("app.agent_os.run_live_workflow", fake_run_live_workflow)
    client = TestClient(app)

    response = client.post("/demo/live-research", json={"companies": ["Nvidia"]})

    assert response.status_code == 200
    body = response.json()
    assert body["state"]["raw_input"] == ["Nvidia"]
    assert "Invest in:" in body["memo"]
