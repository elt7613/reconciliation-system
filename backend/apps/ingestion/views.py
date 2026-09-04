"""Upload endpoint: parse both CSVs, store the batch, trigger reconciliation."""
from pathlib import Path

from django.core.files.base import File
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reconciliation.services import run_reconciliation

from .models import ImportBatch, Order, Payment
from .parsing import ParseError, parse_orders_csv, parse_payments_csv
from .serializers import ImportBatchSerializer

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB — CSV exports, not data dumps


class UploadView(APIView):
    """POST multipart with `orders_file` + `payments_file`. Returns batch + run summary."""

    parser_classes = (FormParser, MultiPartParser)

    def post(self, request):
        orders_file: File | None = request.FILES.get("orders_file")
        payments_file: File | None = request.FILES.get("payments_file")
        if not orders_file or not payments_file:
            return Response(
                {"detail": "Both orders_file and payments_file are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for f in (orders_file, payments_file):
            if f.size > MAX_FILE_BYTES:
                return Response(
                    {"detail": f"{f.name} exceeds 5 MB limit."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            orders, order_warnings = parse_orders_csv(orders_file.read().decode("utf-8-sig"))
            payments, payment_warnings = parse_payments_csv(payments_file.read().decode("utf-8-sig"))
        except (UnicodeDecodeError, ParseError) as exc:
            return Response(
                {"detail": f"Could not parse files: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch = ImportBatch.objects.create(
            user=request.user,
            orders_file_name=orders_file.name,
            payments_file_name=payments_file.name,
            order_row_count=len(orders),
            payment_row_count=len(payments),
            warnings=order_warnings + payment_warnings,
        )
        Order.objects.bulk_create(
            [
                Order(
                    batch=batch,
                    order_id=o.raw.get("order_id", ""),
                    normalized_id=o.normalized_id,
                    order_date=o.order_date,
                    customer_email=o.customer_email,
                    currency=o.currency,
                    gross_amount=o.gross_amount,
                    discount=o.discount,
                    net_amount=o.net_amount,
                    status=o.status,
                )
                for o in orders
            ]
        )
        Payment.objects.bulk_create(
            [
                Payment(
                    batch=batch,
                    transaction_ref=p.transaction_ref,
                    normalized_order_ref=p.normalized_order_ref,
                    processed_at=p.processed_at,
                    currency=p.currency,
                    amount=p.amount,
                    fee=p.fee,
                    net_settled=p.net_settled,
                    type=p.type,
                    status=p.status,
                )
                for p in payments
            ]
        )

        run = run_reconciliation(batch)

        return Response(
            {"batch": ImportBatchSerializer(batch).data, "run_id": run.id},
            status=status.HTTP_201_CREATED,
        )


class SampleDataView(APIView):
    """POST: import the bundled sample CSVs (same flow as upload, zero clicks)."""

    def post(self, request):
        sample_dir = Path(__file__).resolve().parent.parent.parent / "sample_data"
        orders_path = sample_dir / "orders.csv"
        payments_path = sample_dir / "payments.csv"
        if not orders_path.exists() or not payments_path.exists():
            return Response(
                {"detail": "Sample data files are not bundled in this deployment."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            orders, order_warnings = parse_orders_csv(orders_path.read_text(encoding="utf-8-sig"))
            payments, payment_warnings = parse_payments_csv(payments_path.read_text(encoding="utf-8-sig"))
        except ParseError as exc:
            return Response(
                {"detail": f"Could not parse sample files: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        batch = ImportBatch.objects.create(
            user=request.user,
            orders_file_name="sample-orders.csv",
            payments_file_name="sample-payments.csv",
            order_row_count=len(orders),
            payment_row_count=len(payments),
            warnings=order_warnings + payment_warnings,
        )
        Order.objects.bulk_create(
            [
                Order(
                    batch=batch,
                    order_id=o.raw.get("order_id", ""),
                    normalized_id=o.normalized_id,
                    order_date=o.order_date,
                    customer_email=o.customer_email,
                    currency=o.currency,
                    gross_amount=o.gross_amount,
                    discount=o.discount,
                    net_amount=o.net_amount,
                    status=o.status,
                )
                for o in orders
            ]
        )
        Payment.objects.bulk_create(
            [
                Payment(
                    batch=batch,
                    transaction_ref=p.transaction_ref,
                    normalized_order_ref=p.normalized_order_ref,
                    processed_at=p.processed_at,
                    currency=p.currency,
                    amount=p.amount,
                    fee=p.fee,
                    net_settled=p.net_settled,
                    type=p.type,
                    status=p.status,
                )
                for p in payments
            ]
        )
        run = run_reconciliation(batch)
        return Response(
            {"batch": ImportBatchSerializer(batch).data, "run_id": run.id},
            status=status.HTTP_201_CREATED,
        )


class BatchListView(APIView):
    """GET the current user's import history (append-only — nothing is ever removed)."""

    def get(self, request):
        batches = ImportBatch.objects.filter(user=request.user).order_by("-created_at")
        return Response({"results": ImportBatchSerializer(batches, many=True).data})
