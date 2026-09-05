"""Ingestion serializers."""
from rest_framework import serializers

from .models import ImportBatch


class ImportBatchSerializer(serializers.ModelSerializer):
    run_id = serializers.SerializerMethodField()

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

    def get_run_id(self, obj: ImportBatch) -> int | None:
        return obj.runs.order_by("-created_at").values_list("id", flat=True).first()
