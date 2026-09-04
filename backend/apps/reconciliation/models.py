"""Reconciliation models: a ReconciliationRun owns its Discrepancies (append-only)."""
from django.conf import settings
from django.db import models

from apps.ingestion.models import ImportBatch


class ReconciliationRun(models.Model):
    """One execution of the deterministic engine over one ImportBatch. Immutable once created."""

    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="runs")
    created_at = models.DateTimeField(auto_now_add=True)
    total_orders = models.PositiveIntegerField(default=0)
    total_payments = models.PositiveIntegerField(default=0)
    matched_pairs = models.PositiveIntegerField(default=0)
    value_reconciled = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    value_in_dispute = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    money_at_risk = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    uncollected_revenue = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    refund_obligations = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    needs_investigation = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    breakdown = models.JSONField(default=dict)  # {type: {count, amount, severity}}

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Run #{self.pk} on batch {self.batch_id}"


class Discrepancy(models.Model):
    """A single finding from the engine. Classification is ground truth; LLM only explains."""

    class Type(models.TextChoices):
        MISSING_PAYMENT = "missing_payment"
        ORPHAN_CHARGE = "orphan_charge"
        DUPLICATE_CHARGE = "duplicate_charge"
        AMOUNT_MISMATCH = "amount_mismatch"
        CHARGED_AFTER_CANCELLATION = "charged_after_cancellation"
        FAILED_PAYMENT = "failed_payment"
        PENDING_PAYMENT = "pending_payment"
        PARTIAL_REFUND = "partial_refund"
        REFUND_OF_COMPLETED_ORDER = "refund_of_completed_order"
        CURRENCY_MISMATCH = "currency_mismatch"
        LATE_SETTLEMENT = "late_settlement"
        ROUNDING_VARIANCE = "rounding_variance"
        DATA_QUALITY = "data_quality"

    class Severity(models.TextChoices):
        HIGH = "high"
        MEDIUM = "medium"
        LOW = "low"
        INFO = "info"

    run = models.ForeignKey(ReconciliationRun, on_delete=models.PROTECT, related_name="discrepancies")
    type = models.CharField(max_length=32, choices=Type.choices, db_index=True)
    severity = models.CharField(max_length=8, choices=Severity.choices)
    risk_bucket = models.CharField(max_length=32, default="", blank=True)  # uncollected | refund_obligation | investigation | ""
    order_ref = models.CharField(max_length=64, db_index=True)  # normalized order id
    transaction_refs = models.JSONField(default=list)  # involved TXNs
    amount_at_risk = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    detail = models.JSONField(default=dict)  # type-specific facts (deltas, statuses, dates)
    explanation = models.JSONField(null=True, blank=True)  # cached LLM explanation
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["type", "order_ref"]
        indexes = [
            models.Index(fields=["run", "type"]),
            models.Index(fields=["run", "severity"]),
        ]

    def __str__(self) -> str:
        return f"{self.type}:{self.order_ref}"
