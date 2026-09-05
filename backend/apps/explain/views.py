"""Explain endpoints: LLM explanation for one discrepancy / summary for a filtered set.

The LLM lives in a separate FastAPI microservice (ai-service/). This app calls
it over HTTP with a shared API key; every failure mode (service down, auth
rejected, timeout, provider failure) degrades to a deterministic fallback so
the dashboard never breaks. Failures are logged, never silent.
"""
import logging

from django.contrib.auth import get_user_model
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reconciliation.models import Discrepancy, ReconciliationRun

from . import client
from .sanitize import sanitize_payload

User = get_user_model()
logger = logging.getLogger(__name__)


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
    label = disc.type.replace("_", " ")
    facts = ", ".join(f"{k}={v}" for k, v in disc.detail.items())
    return {
        "summary": f"{label.title()} on {disc.order_ref} — {disc.amount_at_risk} at risk.",
        "likely_cause": (
            "AI explanation is unavailable. These are the deterministic facts from the "
            f"reconciliation engine: {facts}."
        ),
        "recommended_action": "Review the raw order and payment records in the detail view.",
        "urgency": "high" if disc.severity == "high" else "medium" if disc.severity == "medium" else "low",
        "degraded": True,
    }


def _discrepancy_payload(disc: Discrepancy) -> dict:
    """Facts the AI service is allowed to see. Classification is ground truth.

    sanitize_payload strips control characters/newlines and bounds length so
    crafted CSV values cannot smuggle instructions into the prompt.
    """
    payload = {
        "discrepancy_type": disc.type,
        "severity": disc.severity,
        "risk_bucket": disc.risk_bucket,
        "order_reference": disc.order_ref,
        "transaction_refs": disc.transaction_refs,
        "amount_at_risk": str(disc.amount_at_risk),
        "engine_facts": disc.detail,
    }
    return sanitize_payload(payload)


class ExplainDiscrepancyView(APIView):
    """POST /api/discrepancies/:id/explain/ — LLM explanation (or cached/fallback)."""

    def post(self, request, discrepancy_id: int):
        disc = _owned_discrepancy(request.user, discrepancy_id)
        if disc is None:
            return Response({"detail": "Not found."}, status=404)

        if disc.explanation and not disc.explanation.get("degraded"):
            return Response(disc.explanation)

        if not client.is_configured():
            fallback = _fallback_explanation(disc)
            disc.explanation = fallback
            disc.save(update_fields=["explanation"])
            return Response(fallback)

        payload = _discrepancy_payload(disc)
        try:
            data = client.explain_discrepancy(payload)
            data["degraded"] = False
        except client.AIServiceError as exc:
            logger.warning(
                "AI explanation failed for discrepancy %s: %s", disc.id, exc.reason
            )
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
        payload = sanitize_payload(payload)

        def fallback_summary() -> dict:
            return {
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

        if not client.is_configured():
            return Response(fallback_summary())

        try:
            data = client.summarize_findings(payload)
            data["degraded"] = False
        except client.AIServiceError as exc:
            logger.warning("AI summary failed for run %s: %s", run.id, exc.reason)
            data = fallback_summary()
        return Response(data)
