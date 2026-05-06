import pytest
from pydantic import ValidationError

from app.schemas import AgentRunLog, CompanyAnalysis, DimensionScore, EvidenceSource, RunLog, WorkflowState


def test_workflow_state_defaults_are_initialized() -> None:
    state = WorkflowState(raw_input=["Nvidia"])

    assert state.confirmed_companies == []
    assert state.research == []
    assert state.analysis == []
    assert state.risks == []
    assert state.memo == ""
    assert state.run_log.agent_runs == []


def test_dimension_score_validates_score_range() -> None:
    with pytest.raises(ValidationError):
        DimensionScore(score=11, narrative="Too high")


def test_evidence_source_requires_traceable_url() -> None:
    source = EvidenceSource(
        title="Mock source",
        url="https://example.com/source",
        publisher="Mock",
        snippet="Evidence snippet",
    )

    assert source.url.startswith("https://")


def test_company_analysis_computes_overall_score() -> None:
    analysis = CompanyAnalysis(
        name="Nvidia",
        market_opportunity=DimensionScore(score=9, narrative="Large market"),
        competitive_position=DimensionScore(score=8, narrative="Strong position"),
        growth_potential=DimensionScore(score=7, narrative="Good growth"),
        business_model_strength=DimensionScore(score=6, narrative="Durable model"),
        overall_score=1,
        one_line_verdict="Strong but not risk-free.",
    )

    assert analysis.overall_score == 8


def test_agent_run_log_computes_latency() -> None:
    run_log = AgentRunLog(
        agent="Research Agent",
        company="Nvidia",
        start_time=10.0,
        end_time=12.3456,
        success=True,
    )

    assert run_log.latency_seconds == 2.346


def test_run_log_finalize_computes_parallel_metrics() -> None:
    run_log = RunLog(
        agent_runs=[
            AgentRunLog(agent="Identity Agent", company="A", start_time=0, end_time=1, success=True),
            AgentRunLog(agent="Identity Agent", company="B", start_time=1, end_time=3, success=True),
            AgentRunLog(agent="Research Agent", company="A", start_time=3, end_time=8, success=True),
            AgentRunLog(agent="Analyst Agent", company="A", start_time=8, end_time=10, success=True),
            AgentRunLog(agent="Critic Agent", company="A", start_time=10, end_time=11, success=True),
            AgentRunLog(agent="Research Agent", company="B", start_time=3, end_time=13, success=True),
            AgentRunLog(agent="Analyst Agent", company="B", start_time=13, end_time=15, success=True),
            AgentRunLog(agent="Critic Agent", company="B", start_time=15, end_time=16, success=True),
            AgentRunLog(agent="Decision Agent", company="all", start_time=16, end_time=20, success=True),
        ]
    )

    run_log.finalize(total_latency_seconds=20.1234)

    assert run_log.total_latency_seconds == 20.123
    assert run_log.cumulative_agent_latency_seconds == 28
    assert run_log.identity_latency_seconds == 3
    assert run_log.decision_latency_seconds == 4
    assert run_log.company_pipeline_latency_seconds == {"A": 8, "B": 13}
    assert run_log.parallel_pipeline_latency_seconds == 13
