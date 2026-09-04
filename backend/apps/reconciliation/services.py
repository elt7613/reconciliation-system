"""Django adapter: runs the pure engine over an ImportBatch and persists results."""
from django.db import transaction

from apps.ingestion.models import Order, Payment
from apps.ingestion.parsing import ParsedOrder, ParsedPayment  # noqa: F401 (type reference)

from apps.reconciliation.engine import Finding, reconcile  # noqa: F401
from apps.reconciliation.models import Discrepancy, ReconciliationRun


@transaction.atomic
def run_reconciliation(batch) -> ReconciliationRun:
    """Execute the engine over a batch's stored data. Deterministic: same rows → same run."""
    orders = list(batch.orders.order_by("normalized_id"))
    payments = list(batch.payments.order_by("normalized_order_ref", "transaction_ref"))

    # Engine consumes plain dataclasses; map ORM rows into them (kept identical).
    parsed_orders = [
        ParsedOrder(
            raw={},
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
    parsed_payments = [
        ParsedPayment(
            raw={},
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

    findings, stats = reconcile(parsed_orders, parsed_payments)

    run = ReconciliationRun.objects.create(
        batch=batch,
        total_orders=stats.total_orders,
        total_payments=stats.total_payments,
        matched_pairs=stats.matched_pairs,
        value_reconciled=stats.value_reconciled,
        value_in_dispute=stats.value_in_dispute,
        money_at_risk=stats.money_at_risk,
        breakdown=stats.breakdown,
    )
    Discrepancy.objects.bulk_create(
        [
            Discrepancy(
                run=run,
                type=f.type,
                severity=f.severity,
                risk_bucket=f.risk_bucket,
                order_ref=f.order_ref,
                transaction_refs=f.transaction_refs,
                amount_at_risk=f.amount_at_risk,
                detail=f.detail,
            )
            for f in findings
        ]
    )
    return run
