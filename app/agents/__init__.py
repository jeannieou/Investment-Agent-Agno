"""Agent definitions live here."""

from app.agents.analyst_agent import analyst_agent
from app.agents.critic_agent import critic_agent
from app.agents.decision_agent import decision_agent
from app.agents.identity_agent import identity_agent
from app.agents.research_agent import research_agent

__all__ = [
    "analyst_agent",
    "critic_agent",
    "decision_agent",
    "identity_agent",
    "research_agent",
]
