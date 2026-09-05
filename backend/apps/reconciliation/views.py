"""Reconciliation API: run list/detail, discrepancy drill-down with filters/search."""
from django.contrib.auth import get_user_model
from django.db.models import Case, Value, When
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ingestion.models import ImportBatch, Order, Payment
from apps.ingestion.serializers import ImportBatchSerializer

from .models import Discrepancy, ReconciliationRun
from .services import run_reconciliation

User = get_user_model()


class DiscrepancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Discrepancy
        fields = (
            "id",
            "type",
            "severity",
            "risk_bucket",
            "order_ref",
            "transaction_refs",
            "amount_at_risk",
            "detail",
        )


class RunSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReconciliationRun
        fields = (
            "id",
            "created_at",
            "batch",
            "total_orders",
            "total_payments",
            "matched_pairs",
            "value_reconciled",
            "value_in_dispute",
            "money_at_risk",
            "uncollected_revenue",
            "refund_obligations",
            "needs_investigation",
            "breakdown",
        )


def _user_run_or_404(user, run_id: int) -> tuple[ReconciliationRun | None, int]:
    """Fetch a run only if it belongs to the requesting user."""
    try:
        run = ReconciliationRun.objects.select_related("batch", "batch__user").get(id=run_id)
    except ReconciliationRun.DoesNotExist:
        return None, 404
    if run.batch.user_id != user.id:
        return None, 404
    return run, 200


class RunListView(APIView):
    """GET: all runs for the user. POST: re-run reconciliation on the user's latest batch."""

    def get(self, request):
        runs = (
            ReconciliationRun.objects.select_related("batch")
            .filter(batch__user=request.user)
            .order_by("-created_at")
        )
        return Response({"results": RunSummarySerializer(runs, many=True).data})

    def post(self, request):
        batch = (
            ImportBatch.objects.filter(user=request.user).order_by("-created_at").first()
        )
        if not batch:
            return Response({"detail": "No imported data yet."}, status=400)
        run = run_reconciliation(batch)
        return Response(RunSummarySerializer(run).data, status=201)


class RunDetailView(APIView):
    """Headline figures + breakdown for one run."""

    def get(self, request, run_id: int):
        run, code = _user_run_or_404(request.user, run_id)
        if code == 404:
            return Response({"detail": "Not found."}, status=404)
        return Response(RunSummarySerializer(run).data)


class RunDiscrepanciesView(APIView):
    """Drill-down: filter by type/severity/risk bucket, free-text search, paginated."""

    def get(self, request, run_id: int):
        run, code = _user_run_or_404(request.user, run_id)
        if code == 404:
            return Response({"detail": "Not found."}, status=404)

        qs = Discrepancy.objects.filter(run=run)
        type_filter = request.GET.get("type")
        if type_filter:
            qs = qs.filter(type=type_filter)
        severity_filter = request.GET.get("severity")
        if severity_filter:
            qs = qs.filter(severity=severity_filter)
        bucket_filter = request.GET.get("risk_bucket")
        if bucket_filter:
            qs = qs.filter(risk_bucket=bucket_filter)
        search = (request.GET.get("search") or "").strip()
        if search:
            from django.db.models import Q

            qs = qs.filter(
                Q(order_ref__icontains=search) | Q(transaction_refs__icontains=search)
            )

        # Default ordering: severity first (high → medium → low → info), then
        # amount at risk descending, then a stable tiebreaker. Users can still
        # sort explicitly via ?ordering=.
        severity_rank = Case(
            When(severity="high", then=Value(0)),
            When(severity="medium", then=Value(1)),
            When(severity="low", then=Value(2)),
            When(severity="info", then=Value(3)),
            default=Value(4),
        )
        ordering = request.GET.get("ordering", "")
        if ordering.lstrip("-") in ("type", "severity", "order_ref", "amount_at_risk"):
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by(severity_rank, "-amount_at_risk", "order_ref")

        from rest_framework.pagination import PageNumberPagination

        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(DiscrepancySerializer(page, many=True).data)


class DiscrepancyDetailView(APIView):
    """Full detail for one discrepancy, including the raw order + payment records."""

    def get(self, request, discrepancy_id: int):
        try:
            disc = Discrepancy.objects.select_related("run", "run__batch").get(id=discrepancy_id)
        except Discrepancy.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        if disc.run.batch.user_id != request.user.id:
            return Response({"detail": "Not found."}, status=404)

        batch = disc.run.batch
        order = (
            Order.objects.filter(batch=batch, normalized_id=disc.order_ref)
            .values(
                "order_id",
                "order_date",
                "customer_email",
                "currency",
                "gross_amount",
                "discount",
                "net_amount",
                "status",
            )
            .first()
        )
        payments = list(
            Payment.objects.filter(batch=batch, normalized_order_ref=disc.order_ref).values(
                "transaction_ref",
                "processed_at",
                "currency",
                "amount",
                "fee",
                "net_settled",
                "type",
                "status",
            )
        )
        # Orphan charges have no order; payments are keyed by the same ref either way
        if disc.type == "orphan_charge":
            payments = list(
                Payment.objects.filter(batch=batch, normalized_order_ref=disc.order_ref).values(
                    "transaction_ref",
                    "processed_at",
                    "currency",
                    "amount",
                    "fee",
                    "net_settled",
                    "type",
                    "status",
                )
            )

        return Response(
            {
                **DiscrepancySerializer(disc).data,
                "explanation": disc.explanation,
                "order": order,
                "payments": payments,
            }
        )
