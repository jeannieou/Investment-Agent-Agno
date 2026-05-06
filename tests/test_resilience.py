import asyncio

import pytest

from app.schemas import CompanyIdentity, WorkflowState
from app.tools._utils import retry_call
from app.workflows import (
    InvestmentResearchWorkflow,
    make_fallback_pipeline_result,
    run_mock_workflow,
)


class FailingResearchWorkflow(InvestmentResearchWorkflow):
    def _mock_research(self, company):
        if company.name == "AMD":
            raise RuntimeError("mock research outage")
        return super()._mock_research(company)


def test_workflow_keeps_company_when_pipeline_fails() -> None:
    workflow = FailingResearchWorkflow()
    state = WorkflowState(raw_input=["Nvidia", "AMD", "Intel"])

    result = asyncio.run(workflow.arun(state))

    assert len(result.research) == 3
    assert len(result.analysis) == 3
    assert len(result.risks) == 3
    failed_research = next(item for item in result.research if item.name == "AMD")
    failed_analysis = next(item for item in result.analysis if item.name == "AMD")
    failed_risk = next(item for item in result.risks if item.name == "AMD")
    assert failed_research.business_model == "Not found"
    assert failed_analysis.overall_score == 1
    assert failed_risk.risk_level == "high"
    assert result.run_log.warnings
    assert "AMD" in result.run_log.warnings[0]
    assert "mock research outage" in result.memo


def test_fallback_pipeline_result_is_valid_typed_state() -> None:
    company = CompanyIdentity(
        name="UnknownCo",
        url="https://example.com",
        description="Unknown company",
        company_type="unknown",
    )

    research, analysis, risk = make_fallback_pipeline_result(company, error="tool timeout")

    assert research.name == "UnknownCo"
    assert analysis.name == "UnknownCo"
    assert risk.name == "UnknownCo"
    assert analysis.overall_score == 1
    assert risk.risk_level == "high"


def test_retry_call_retries_until_success() -> None:
    calls = {"count": 0}

    def flaky_call():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RuntimeError("temporary failure")
        return "ok"

    assert retry_call(flaky_call, attempts=3) == "ok"
    assert calls["count"] == 3


def test_retry_call_raises_last_error_after_attempts() -> None:
    with pytest.raises(RuntimeError, match="permanent failure"):
        retry_call(lambda: (_ for _ in ()).throw(RuntimeError("permanent failure")), attempts=2)


def test_normal_mock_workflow_still_has_no_warnings() -> None:
    state = run_mock_workflow(["Nvidia", "AMD", "Intel"])

    assert state.run_log.warnings == []

