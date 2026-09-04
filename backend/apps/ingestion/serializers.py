"""Ingestion serializers."""
from rest_framework import serializers

from .models import ImportBatch


class ImportBatchSerializer(serializers.ModelSerializer):
    run_id = serializers.IntegerField(source="latest_run.id", read_only=True, default=None)

    class Meta:
        model = ImportBatch
        fields = (
            "id",
            "created_at",
            "orders_file_name",
            "payments_file_name",
            "order_row_count",
            "payment_row_count",
            "warnings",
            "run_id",
        )
