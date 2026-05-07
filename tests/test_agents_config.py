from agno.agent import Agent

from app.agents import (
    analyst_agent,
    critic_agent,
    decision_agent,
    financial_extractor_agent,
    identity_agent,
    research_agent,
)
from app.config import get_agent_debug_config, get_reasoning_model, get_settings, get_worker_model
from app.schemas import (
    CompanyAnalysis,
    CompanyIdentity,
    CompanyResearch,
    CompanyRisk,
    CriticInput,
    DecisionInput,
    FinancialExtractionRequest,
    FinancialExtractionResult,
    IdentityRequest,
    ResearchRequest,
)


def test_default_settings_use_openai(monkeypatch) -> None:
    monkeypatch.setenv("AGNO_DEBUG", "false")
    monkeypatch.setenv("AGNO_DEBUG_LEVEL", "1")

    settings = get_settings()

    assert settings.llm_provider == "openai"
    assert settings.openai_worker_model
    assert settings.openai_reasoning_model
    assert settings.agno_debug is False
    assert settings.agno_debug_level == 1


def test_agent_debug_config_is_env_controlled(monkeypatch) -> None:
    monkeypatch.setenv("AGNO_DEBUG", "false")
    monkeypatch.setenv("AGNO_DEBUG_LEVEL", "1")

    debug_config = get_agent_debug_config()

    assert debug_config == {"debug_mode": False, "debug_level": 1}


def test_model_factories_create_models_without_api_calls() -> None:
    worker = get_worker_model(max_tokens=123)
    reasoning = get_reasoning_model(max_tokens=456)

    assert worker.id == get_settings().openai_worker_model
    assert worker.max_tokens == 123
    assert reasoning.id == get_settings().openai_reasoning_model
    assert reasoning.max_tokens == 456


def test_stage3_agents_are_agno_agents() -> None:
    for agent in [
        identity_agent,
        research_agent,
        analyst_agent,
        critic_agent,
        financial_extractor_agent,
        decision_agent,
    ]:
        assert isinstance(agent, Agent)
        assert agent.name
        assert agent.model is not None


def test_agent_input_and_output_schemas_are_typed() -> None:
    assert identity_agent.input_schema is IdentityRequest
    assert identity_agent.output_schema is CompanyIdentity

    assert research_agent.input_schema is ResearchRequest
    assert research_agent.output_schema is CompanyResearch

    assert analyst_agent.input_schema is CompanyResearch
    assert analyst_agent.output_schema is CompanyAnalysis

    assert critic_agent.input_schema is CriticInput
    assert critic_agent.output_schema is CompanyRisk

    assert financial_extractor_agent.input_schema is FinancialExtractionRequest
    assert financial_extractor_agent.output_schema is FinancialExtractionResult

    assert decision_agent.input_schema is DecisionInput
    assert decision_agent.output_schema is None


def test_structured_agents_enable_structured_outputs() -> None:
    for agent in [identity_agent, research_agent, analyst_agent, critic_agent, financial_extractor_agent]:
        assert agent.structured_outputs is True
        assert agent.retries in {1, 2}


def test_research_agent_has_tool_budget_for_stage4() -> None:
    assert research_agent.tool_call_limit == 20
