"""Request/response models — the service's API contract with the Django backend."""
from typing import Literal

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    """One discrepancy's facts, as produced by the reconciliation engine."""

    discrepancy_type: str
    severity: str
    risk_bucket: str = ""
    order_reference: str
    transaction_refs: list[str] = []
    amount_at_risk: str
    engine_facts: dict = {}


class SummarizeRequest(BaseModel):
    """Aggregated run findings for the executive summary."""

    headline: dict
    breakdown_by_type: dict


class Explanation(BaseModel):
    """Structured explanation of one discrepancy (agent output model)."""

    summary: str = Field(description="One-sentence plain-language summary of what happened")
    likely_cause: str = Field(description="Most plausible cause given the facts (2-3 sentences)")
    recommended_action: str = Field(description="Concrete next step for the revenue owner")
    urgency: Literal["low", "medium", "high"] = Field(description="How urgently to act")


class Summary(BaseModel):
    """Structured executive summary (agent output model)."""

    executive_summary: str = Field(description="2-4 sentence overview of the state of reconciliation")
    top_priorities: list[str] = Field(description="Ordered list of what to investigate first and why")
    recommended_actions: list[str] = Field(description="Concrete actions to take")
