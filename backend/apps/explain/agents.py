"""Pydantic AI agents for explaining discrepancies (backend only; keys never leave the server).

Two linear agents — no orchestration framework needed:
- explainer: one discrepancy's facts → structured explanation
- summarizer: a filtered set of discrepancies → prioritized executive summary

Guardrails:
- The engine's classification is ground truth; prompts tell the model to explain,
  never re-classify or dispute the deterministic findings.
- Temperature 0.1 (env-driven): explanations must be faithful and consistent,
  not creative. Documented in README.
- Structured outputs via output_type; retries on validation failure (env-driven).
- Any failure → deterministic fallback text with the raw facts, so the dashboard
  never breaks because the LLM is down.
"""
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.settings import ModelSettings

from django.conf import settings


class Explanation(BaseModel):
    """Structured explanation of one discrepancy."""

    summary: str = Field(description="One-sentence plain-language summary of what happened")
    likely_cause: str = Field(description="Most plausible cause given the facts (2-3 sentences)")
    recommended_action: str = Field(description="Concrete next step for the revenue owner")
    urgency: Literal["low", "medium", "high"] = Field(description="How urgently to act")


class Summary(BaseModel):
    """Structured executive summary of a set of discrepancies."""

    executive_summary: str = Field(description="2-4 sentence overview of the state of reconciliation")
    top_priorities: list[str] = Field(description="Ordered list of what to investigate first and why")
    recommended_actions: list[str] = Field(description="Concrete actions to take")


EXPLAIN_INSTRUCTIONS = """\
You are a payments-reconciliation analyst for an online store.

You will receive the deterministic findings of a reconciliation engine that
compared the store's order system against its payment processor. The
classification (discrepancy type, amounts, dates, statuses) is GROUND TRUTH
produced by exact rules — never dispute or re-classify it.

Your job: explain in plain language what likely happened operationally, and
what someone responsible for the store's revenue should do about it.

Constraints:
- Base every statement on the provided facts. If the cause is uncertain, say
  what the most plausible causes are and what evidence would distinguish them.
- Be concrete and actionable; no generic advice.
- Keep the summary to one sentence, likely_cause to 2-3 sentences.
- urgency must reflect money at risk and recoverability, not dramatics.\
"""

SUMMARIZE_INSTRUCTIONS = """\
You are a payments-reconciliation analyst for an online store.

You will receive aggregated, deterministic findings from a reconciliation
engine (counts and amounts by discrepancy type). The numbers are GROUND TRUTH —
never dispute them.

Your job: give the revenue owner an executive summary — how bad is it, what
kinds of problems exist, and which to look at first.

Constraints:
- Base every statement on the provided numbers.
- top_priorities: order by money at risk and recoverability.
- recommended_actions: concrete, specific to the discrepancy types present.\
"""


def _build_model() -> OpenRouterModel:
    cfg = settings.LLM_SETTINGS
    return OpenRouterModel(
        cfg["model"],
        provider=OpenRouterProvider(api_key=cfg["api_key"] or None),
    )


def _model_settings() -> ModelSettings:
    cfg = settings.LLM_SETTINGS
    return ModelSettings(temperature=cfg["temperature"], timeout=cfg["timeout_seconds"])


@lru_cache(maxsize=1)
def _explainer_agent() -> Agent[None, Explanation]:
    if not llm_available():
        raise RuntimeError("LLM is not configured: set OPENROUTER_API_KEY and LLM_ENABLED=true")
    return Agent(
        _build_model(),
        output_type=Explanation,
        instructions=EXPLAIN_INSTRUCTIONS,
        model_settings=_model_settings(),
        retries=settings.LLM_SETTINGS["max_retries"],
    )


@lru_cache(maxsize=1)
def _summarizer_agent() -> Agent[None, Summary]:
    if not llm_available():
        raise RuntimeError("LLM is not configured: set OPENROUTER_API_KEY and LLM_ENABLED=true")
    return Agent(
        _build_model(),
        output_type=Summary,
        instructions=SUMMARIZE_INSTRUCTIONS,
        model_settings=_model_settings(),
        retries=settings.LLM_SETTINGS["max_retries"],
    )


def llm_available() -> bool:
    return bool(settings.LLM_SETTINGS["enabled"] and settings.LLM_SETTINGS["api_key"])


async def explain_discrepancy_async(payload: dict) -> Explanation:
    """Call the explainer agent with a discrepancy's facts. Raises on failure."""
    agent = _explainer_agent()
    result = await agent.run(payload)  # type: ignore[arg-type]
    return result.output


async def summarize_findings_async(payload: dict) -> Summary:
    """Call the summarizer agent with aggregated findings. Raises on failure."""
    agent = _summarizer_agent()
    result = await agent.run(payload)  # type: ignore[arg-type]
    return result.output
