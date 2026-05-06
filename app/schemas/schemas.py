"""Typed state and inter-agent contracts for the investment workflow."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


CompanyType = Literal["public", "private", "startup", "unknown"]
Confidence = Literal["low", "medium", "high"]
RiskLevel = Literal["low", "medium", "high"]


class EvidenceSource(BaseModel):
    title: str
    url: str
    publisher: str | None = None
    date: str | None = None
    snippet: str


class IdentityRequest(BaseModel):
    company_name: str


class CompanyIdentity(BaseModel):
    name: str
    url: str
    description: str
    ticker: str | None = None
    company_type: CompanyType = "unknown"
    confidence: Confidence = "medium"
    sources: list[EvidenceSource] = Field(default_factory=list)


class ResearchRequest(BaseModel):
    company: CompanyIdentity


class CompanyResearch(BaseModel):
    name: str
    url: str
    company_type: CompanyType
    ticker: str | None = None
    business_model: str
    products: list[str]
    team_size: str
    key_people: list[str]
    funding_or_financials: str
    market_size: str
    recent_news: list[str]
    competitors: list[str]
    sources: list[EvidenceSource] = Field(default_factory=list)


class DimensionScore(BaseModel):
    score: int = Field(ge=1, le=10)
    narrative: str
    confidence: Confidence = "medium"


class CompanyAnalysis(BaseModel):
    name: str
    market_opportunity: DimensionScore
    competitive_position: DimensionScore
    growth_potential: DimensionScore
    business_model_strength: DimensionScore
    overall_score: int = Field(default=1, ge=1, le=10)
    one_line_verdict: str

    @model_validator(mode="after")
    def compute_overall_score(self) -> "CompanyAnalysis":
        scores = [
            self.market_opportunity.score,
            self.competitive_position.score,
            self.growth_potential.score,
            self.business_model_strength.score,
        ]
        self.overall_score = round(sum(scores) / len(scores))
        return self


class CriticInput(BaseModel):
    research: CompanyResearch
    analysis: CompanyAnalysis


class CompanyRisk(BaseModel):
    name: str
    key_risks: list[str]
    analyst_weaknesses: list[str]
    open_questions: list[str]
    risk_level: RiskLevel
    sources_to_verify: list[str] = Field(default_factory=list)


class DecisionInput(BaseModel):
    research: list[CompanyResearch] = Field(default_factory=list)
    analysis: list[CompanyAnalysis] = Field(default_factory=list)
    risks: list[CompanyRisk] = Field(default_factory=list)


class AgentRunLog(BaseModel):
    agent: str
    company: str
    start_time: float
    end_time: float
    latency_seconds: float = 0.0
    tool_calls: list[str] = Field(default_factory=list)
    success: bool
    error: str | None = None

    @model_validator(mode="after")
    def compute_latency(self) -> "AgentRunLog":
        raw_latency = self.end_time - self.start_time
        self.latency_seconds = round(raw_latency, 3)
        if raw_latency > 0 and self.latency_seconds == 0:
            self.latency_seconds = 0.001
        return self


class RunLog(BaseModel):
    agent_runs: list[AgentRunLog] = Field(default_factory=list)
    total_latency_seconds: float = 0.0
    cumulative_agent_latency_seconds: float = 0.0
    identity_latency_seconds: float = 0.0
    parallel_pipeline_latency_seconds: float = 0.0
    decision_latency_seconds: float = 0.0
    company_pipeline_latency_seconds: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    def finalize(self, total_latency_seconds: float | None = None) -> "RunLog":
        self.cumulative_agent_latency_seconds = round(
            sum(run.latency_seconds for run in self.agent_runs),
            3,
        )
        self.identity_latency_seconds = round(
            sum(run.latency_seconds for run in self.agent_runs if run.agent == "Identity Agent"),
            3,
        )
        self.decision_latency_seconds = round(
            sum(run.latency_seconds for run in self.agent_runs if run.agent == "Decision Agent"),
            3,
        )

        pipeline_by_company: dict[str, float] = {}
        for run in self.agent_runs:
            if run.agent not in {"Research Agent", "Analyst Agent", "Critic Agent"}:
                continue
            pipeline_by_company[run.company] = round(
                pipeline_by_company.get(run.company, 0.0) + run.latency_seconds,
                3,
            )
        self.company_pipeline_latency_seconds = pipeline_by_company
        self.parallel_pipeline_latency_seconds = round(
            max(pipeline_by_company.values(), default=0.0),
            3,
        )
        critical_path_latency = round(
            self.identity_latency_seconds + self.parallel_pipeline_latency_seconds + self.decision_latency_seconds,
            3,
        )
        if total_latency_seconds is not None:
            self.total_latency_seconds = max(round(total_latency_seconds, 3), critical_path_latency)
        return self


class WorkflowState(BaseModel):
    raw_input: list[str]
    confirmed_companies: list[CompanyIdentity] = Field(default_factory=list)
    research: list[CompanyResearch] = Field(default_factory=list)
    analysis: list[CompanyAnalysis] = Field(default_factory=list)
    risks: list[CompanyRisk] = Field(default_factory=list)
    memo: str = ""
    start_time: float = 0.0
    run_log: RunLog = Field(default_factory=RunLog)
