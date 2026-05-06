from app.schemas import WorkflowState
from app.workflows import InvestmentResearchWorkflow, run_mock_workflow


def test_mock_workflow_populates_all_state_layers() -> None:
    state = run_mock_workflow(["Nvidia", "AMD", "Intel"])

    assert isinstance(state, WorkflowState)
    assert len(state.confirmed_companies) == 3
    assert len(state.research) == 3
    assert len(state.analysis) == 3
    assert len(state.risks) == 3
    assert all(item.sources for item in state.research)


def test_mock_workflow_memo_contains_required_sections() -> None:
    state = run_mock_workflow(["Nvidia", "AMD", "Intel"])

    for section in [
        "# Investment Recommendation Memo",
        "## Executive Summary",
        "## Company Profiles",
        "## Side-by-Side Comparison",
        "## Recommendation",
        "Invest in:",
        "## Sources",
    ]:
        assert section in state.memo


def test_mock_workflow_records_agent_runs() -> None:
    state = run_mock_workflow(["Nvidia", "AMD", "Intel"])

    # 3 identity + 3 research + 3 analyst + 3 critic + 1 decision
    assert len(state.run_log.agent_runs) == 13
    assert state.run_log.total_latency_seconds >= 0
    assert state.run_log.cumulative_agent_latency_seconds > state.run_log.total_latency_seconds
    assert state.run_log.identity_latency_seconds > 0
    assert state.run_log.parallel_pipeline_latency_seconds > 0
    assert state.run_log.decision_latency_seconds > 0
    assert set(state.run_log.company_pipeline_latency_seconds) == {"Nvidia", "AMD", "Intel"}
    assert all(run.company for run in state.run_log.agent_runs)
    assert all(run.success for run in state.run_log.agent_runs)
    assert all(run.latency_seconds > 0 for run in state.run_log.agent_runs)


def test_mock_workflow_varies_analysis_for_unknown_companies() -> None:
    state = run_mock_workflow(["YSL", "CMU", "NYU"])
    score_tuples = {
        (
            item.market_opportunity.score,
            item.competitive_position.score,
            item.growth_potential.score,
            item.business_model_strength.score,
        )
        for item in state.analysis
    }

    assert len(score_tuples) > 1
    assert "modeled as a" in state.memo


def test_workflow_supports_arbitrary_company_count() -> None:
    state = run_mock_workflow(["OpenAI", "Anthropic", "Mistral", "Cohere"])

    assert len(state.raw_input) == 4
    assert len(state.research) == 4
    assert len(state.analysis) == 4
    assert len(state.risks) == 4


def test_workflow_can_be_called_asynchronously() -> None:
    workflow = InvestmentResearchWorkflow()

    assert hasattr(workflow, "arun")
