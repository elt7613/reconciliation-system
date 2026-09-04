"""Ingestion models: an ImportBatch owns its orders and payments (append-only)."""
from django.conf import settings
from django.db import models


class ImportBatch(models.Model):
    """One upload of an orders CSV + payments CSV pair. Nothing is ever deleted."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="import_batches"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    orders_file_name = models.CharField(max_length=255)
    payments_file_name = models.CharField(max_length=255)
    order_row_count = models.PositiveIntegerField(default=0)
    payment_row_count = models.PositiveIntegerField(default=0)
    warnings = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Batch #{self.pk} by {self.user_id} at {self.created_at:%Y-%m-%d %H:%M}"


class Order(models.Model):
    """A single row from orders.csv. Raw values preserved; normalized fields used for matching."""

    class Status(models.TextChoices):
        COMPLETED = "completed"
        CANCELLED = "cancelled"
        REFUNDED = "refunded"

    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="orders")
    order_id = models.CharField(max_length=64, db_index=True)  # raw value
    normalized_id = models.CharField(max_length=64, db_index=True)  # strip().upper()
    order_date = models.DateTimeField()
    customer_email = models.EmailField(null=True, blank=True)  # empty → NULL (data quality)
    currency = models.CharField(max_length=3)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=16, choices=Status.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "normalized_id"],
                name="uniq_order_per_batch",
            )
        ]
        indexes = [
            models.Index(fields=["batch", "normalized_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.normalized_id} ({self.status})"


class Payment(models.Model):
    """A single row from payments.csv. Raw values preserved; normalized fields used for matching."""

    class Type(models.TextChoices):
        CHARGE = "charge"
        REFUND = "refund"

    class Status(models.TextChoices):
        SETTLED = "settled"
        PENDING = "pending"
        FAILED = "failed"

    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="payments")
    transaction_ref = models.CharField(max_length=64, db_index=True)  # raw value
    normalized_order_ref = models.CharField(max_length=64, db_index=True)  # strip().upper()
    processed_at = models.DateTimeField(null=True, blank=True)  # empty → NULL (data quality)
    currency = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    net_settled = models.DecimalField(max_digits=12, decimal_places=2)
    type = models.CharField(max_length=16, choices=Type.choices)
    status = models.CharField(max_length=16, choices=Status.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "transaction_ref"],
                name="uniq_txn_per_batch",
            )
        ]
        indexes = [
            models.Index(fields=["batch", "normalized_order_ref"]),
        ]

    def __str__(self) -> str:
        return f"{self.transaction_ref} → {self.normalized_order_ref}"
