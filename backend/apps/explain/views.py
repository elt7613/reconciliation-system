"""Explain endpoints: LLM explanation for one discrepancy / summary for a filtered set.

The LLM call is async; the view is sync and drives the coroutine via asyncio.run().
This keeps ORM access simple and works under both WSGI and ASGI.
"""
import asyncio

from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reconciliation.models import Discrepancy, ReconciliationRun

from .agents import explain_discrepancy_async, llm_available, summarize_findings_async

User = get_user_model()


def _owned_discrepancy(user, disc_id: int) -> Discrepancy | None:
    try:
        disc = Discrepancy.objects.select_related("run", "run__batch").get(id=disc_id)
    except Discrepancy.DoesNotExist:
        return None
    if disc.run.batch.user_id != user.id:
        return None
    return disc


def _fallback_explanation(disc: Discrepancy) -> dict:
    """Deterministic offline explanation — always available, never misleading."""
    label = disc.get_type_display().replace("_", " ") if hasattr(disc, "get_type_display") else disc.type
    facts = ", ".join(f"{k}={v}" for k, v in disc.detail.items())
    return {
        "summary": f"{label.replace('_', ' ').title()} on {disc.order_ref} — {disc.amount_at_risk} at risk.",
        "likely_cause": (
            "AI explanation is unavailable. These are the deterministic facts from the "
            f"reconciliation engine: {facts}."
        ),
        "recommended_action": "Review the raw order and payment records in the detail view.",
        "urgency": "high" if disc.severity == "high" else "medium" if disc.severity == "medium" else "low",
        "degraded": True,
    }


def _discrepancy_payload(disc: Discrepancy) -> dict:
    """Facts the LLM is allowed to see. Classification is ground truth."""
    return {
        "discrepancy_type": disc.type,
        "severity": disc.severity,
        "risk_bucket": disc.risk_bucket,
        "order_reference": disc.order_ref,
        "transaction_refs": disc.transaction_refs,
        "amount_at_risk": str(disc.amount_at_risk),
        "engine_facts": disc.detail,
    }


class ExplainDiscrepancyView(APIView):
    """POST /api/discrepancies/:id/explain/ — LLM explanation (or cached/fallback)."""

    def post(self, request, discrepancy_id: int):
        disc = _owned_discrepancy(request.user, discrepancy_id)
        if disc is None:
            return Response({"detail": "Not found."}, status=404)

        if disc.explanation and not disc.explanation.get("degraded"):
            return Response(disc.explanation)

        if not llm_available():
            fallback = _fallback_explanation(disc)
            disc.explanation = fallback
            disc.save(update_fields=["explanation"])
            return Response(fallback)

        payload = _discrepancy_payload(disc)
        try:
            explanation = asyncio.run(explain_discrepancy_async(payload))
            data = explanation.model_dump()
            data["degraded"] = False
        except Exception:
            data = _fallback_explanation(disc)

        disc.explanation = data
        disc.save(update_fields=["explanation"])
        return Response(data)


class SummarizeRunView(APIView):
    """POST /api/runs/:id/summarize/ — LLM executive summary of the run's findings."""

    def post(self, request, run_id: int):
        try:
            run = ReconciliationRun.objects.select_related("batch").get(id=run_id)
        except ReconciliationRun.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if run.batch.user_id != request.user.id:
            return Response({"detail": "Not found."}, status=404)

        payload = {
            "headline": {
                "total_orders": run.total_orders,
                "total_payments": run.total_payments,
                "matched_pairs": run.matched_pairs,
                "value_reconciled": str(run.value_reconciled),
                "value_in_dispute": str(run.value_in_dispute),
                "money_at_risk": str(run.money_at_risk),
            },
            "breakdown_by_type": run.breakdown,
        }

        if not llm_available():
            return Response(
                {
                    "executive_summary": (
                        "AI summary unavailable. Deterministic headline: "
                        f"{run.matched_pairs} matched pairs, {run.value_in_dispute} in dispute, "
                        f"{run.money_at_risk} at risk."
                    ),
                    "top_priorities": [
                        f"{t}: {v['count']} case(s), {v['amount']} at risk"
                        for t, v in sorted(
                            run.breakdown.items(),
                            key=lambda kv: float(kv[1]["amount"]),
                            reverse=True,
                        )[:3]
                    ],
                    "recommended_actions": ["Review the discrepancy table, highest amount first."],
                    "degraded": True,
                }
            )

        try:
            summary = asyncio.run(summarize_findings_async(payload))
            data = summary.model_dump()
            data["degraded"] = False
        except Exception:
            data = {
                "executive_summary": (
                    "AI summary failed. Deterministic headline: "
                    f"{run.matched_pairs} matched pairs, {run.value_in_dispute} in dispute, "
                    f"{run.money_at_risk} at risk."
                ),
                "top_priorities": [
                    f"{t}: {v['count']} case(s), {v['amount']} at risk"
                    for t, v in sorted(
                        run.breakdown.items(),
                        key=lambda kv: float(kv[1]["amount"]),
                        reverse=True,
                    )[:3]
                ],
                "recommended_actions": ["Review the discrepancy table, highest amount first."],
                "degraded": True,
            }
        return Response(data)
