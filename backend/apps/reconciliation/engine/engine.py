"""Reconciliation engine — pure, deterministic, no Django imports.

Given parsed orders and payments (see apps.ingestion.parsing dataclasses) it
classifies every disagreement between the two systems. Same input → same output,
always: inputs are sorted by stable keys before matching.

Design decisions (defensible, documented in README):
- Join key: normalized order reference (strip().upper()).
- Grouping: per order, payments split by type (charge/refund) and status.
- One primary classification per order-payment cluster (prevents double-counting
  money in headline figures); data-quality notes can coexist.
- Amount tolerance: |delta| <= 0.05 → rounding_variance (info), not a dispute.
  Rationale: real processor rounding is 1-2c; flagging it as a dispute would
  invent false problems. The variance is still surfaced so totals tie out.
- Settlement window: > 7 days after order date → late_settlement (low).
  Normal card settlement is 1-3 days; 7 avoids false positives.
- Currency: exact match required. No cross-currency matching even when amounts
  are numerically equal (ORD-1601/1602 are deliberately swapped).
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

AMOUNT_TOLERANCE = Decimal("0.05")
SETTLEMENT_WINDOW_DAYS = 7


@dataclass
class Finding:
    type: str
    severity: str
    risk_bucket: str  # uncollected | refund_obligation | investigation | ""
    order_ref: str
    transaction_refs: list[str]
    amount_at_risk: Decimal
    detail: dict = field(default_factory=dict)


@dataclass
class Stats:
    total_orders: int
    total_payments: int
    matched_pairs: int
    value_reconciled: Decimal
    value_in_dispute: Decimal
    money_at_risk: Decimal
    uncollected_revenue: Decimal
    refund_obligations: Decimal
    needs_investigation: Decimal
    breakdown: dict  # {type: {count, amount, severity}}


def _abs(value: Decimal) -> Decimal:
    return value if value >= 0 else -value


def reconcile(orders: list, payments: list) -> tuple[list[Finding], Stats]:
    """Run the full reconciliation. `orders`/`payments` are ParsedOrder/ParsedPayment."""
    orders_sorted = sorted(orders, key=lambda o: o.normalized_id)
    payments_sorted = sorted(payments, key=lambda p: (p.normalized_order_ref, p.transaction_ref))

    payments_by_ref: dict[str, list] = {}
    for p in payments_sorted:
        payments_by_ref.setdefault(p.normalized_order_ref, []).append(p)

    order_ids = {o.normalized_id for o in orders_sorted}
    findings: list[Finding] = []

    matched_pairs = 0
    value_reconciled = Decimal("0")

    # --- Pass 1: per-order analysis ---
    for order in orders_sorted:
        group = payments_by_ref.get(order.normalized_id, [])
        charges = [p for p in group if p.type == "charge"]
        refunds = [p for p in group if p.type == "refund"]
        settled_charges = [p for p in charges if p.status == "settled"]

        if not group:
            if order.status == "completed":
                findings.append(
                    Finding(
                        type="missing_payment",
                        severity="high",
                        risk_bucket="uncollected",
                        order_ref=order.normalized_id,
                        transaction_refs=[],
                        amount_at_risk=order.net_amount,
                        detail={"order_net": str(order.net_amount), "order_date": str(order.order_date)},
                    )
                )
            continue

        if order.status == "cancelled" and settled_charges:
            # Cancelled but money moved — the highest-priority refund obligation.
            total = sum((p.amount for p in settled_charges), Decimal("0"))
            findings.append(
                Finding(
                    type="charged_after_cancellation",
                    severity="high",
                    risk_bucket="refund_obligation",
                    order_ref=order.normalized_id,
                    transaction_refs=[p.transaction_ref for p in settled_charges],
                    amount_at_risk=total,
                    detail={"order_net": str(order.net_amount), "charged": str(total)},
                )
            )
            continue

        if order.status == "refunded":
            total_charged = sum((p.amount for p in settled_charges), Decimal("0"))
            total_refunded = sum((p.amount for p in refunds if p.status == "settled"), Decimal("0"))
            if total_refunded < total_charged:
                findings.append(
                    Finding(
                        type="partial_refund",
                        severity="medium",
                        risk_bucket="investigation",
                        order_ref=order.normalized_id,
                        transaction_refs=[p.transaction_ref for p in group],
                        amount_at_risk=total_charged - total_refunded,
                        detail={"charged": str(total_charged), "refunded": str(total_refunded)},
                    )
                )
            elif total_refunded > total_charged:
                findings.append(
                    Finding(
                        type="partial_refund",
                        severity="medium",
                        risk_bucket="investigation",
                        order_ref=order.normalized_id,
                        transaction_refs=[p.transaction_ref for p in group],
                        amount_at_risk=total_refunded - total_charged,
                        detail={"charged": str(total_charged), "refunded": str(total_refunded), "over_refund": True},
                    )
                )
            continue

        if order.status != "completed":
            continue

        # Order is completed from here on.
        if len(settled_charges) > 1:
            # Multiple settled charges: the customer paid extra times.
            extra = sum((p.amount for p in settled_charges[1:]), Decimal("0"))
            findings.append(
                Finding(
                    type="duplicate_charge",
                    severity="high",
                    risk_bucket="refund_obligation",
                    order_ref=order.normalized_id,
                    transaction_refs=[p.transaction_ref for p in settled_charges],
                    amount_at_risk=extra,
                    detail={
                        "order_net": str(order.net_amount),
                        "charged_each": str(settled_charges[0].amount),
                        "times_charged": len(settled_charges),
                        "duplicate_txns": [p.transaction_ref for p in settled_charges[1:]],
                    },
                )
            )
            continue

        if len(settled_charges) == 1:
            charge = settled_charges[0]
            matched_pairs += 1

            # Currency gate before amount comparison.
            if charge.currency != order.currency:
                findings.append(
                    Finding(
                        type="currency_mismatch",
                        severity="medium",
                        risk_bucket="investigation",
                        order_ref=order.normalized_id,
                        transaction_refs=[charge.transaction_ref],
                        amount_at_risk=charge.amount,
                        detail={
                            "order_currency": order.currency,
                            "charge_currency": charge.currency,
                            "amount": str(charge.amount),
                        },
                    )
                )
                continue

            delta = charge.amount - order.net_amount
            if _abs(delta) > AMOUNT_TOLERANCE:
                # Material amount mismatch: over- or under-charged.
                bucket = "refund_obligation" if delta > 0 else "uncollected"
                findings.append(
                    Finding(
                        type="amount_mismatch",
                        severity="high",
                        risk_bucket=bucket,
                        order_ref=order.normalized_id,
                        transaction_refs=[charge.transaction_ref],
                        amount_at_risk=_abs(delta),
                        detail={
                            "order_net": str(order.net_amount),
                            "charged": str(charge.amount),
                            "delta": str(delta),
                            "direction": "overcharged" if delta > 0 else "undercharged",
                        },
                    )
                )
            else:
                # Within tolerance → genuinely reconciled money.
                value_reconciled += order.net_amount
                if delta != 0:
                    findings.append(
                        Finding(
                            type="rounding_variance",
                            severity="info",
                            risk_bucket="",
                            order_ref=order.normalized_id,
                            transaction_refs=[charge.transaction_ref],
                            amount_at_risk=Decimal("0"),
                            detail={"delta": str(delta)},
                        )
                    )

                # Refund against a completed order with no refund status — suspicious.
                settled_refunds = [p for p in refunds if p.status == "settled"]
                if settled_refunds:
                    refunded = sum((p.amount for p in settled_refunds), Decimal("0"))
                    findings.append(
                        Finding(
                            type="refund_of_completed_order",
                            severity="medium",
                            risk_bucket="investigation",
                            order_ref=order.normalized_id,
                            transaction_refs=[p.transaction_ref for p in settled_refunds],
                            amount_at_risk=refunded,
                            detail={"refunded": str(refunded), "order_net": str(order.net_amount)},
                        )
                    )

                # Late settlement (only meaningful when we have both timestamps).
                if charge.processed_at and (charge.processed_at - order.order_date) > timedelta(
                    days=SETTLEMENT_WINDOW_DAYS
                ):
                    findings.append(
                        Finding(
                            type="late_settlement",
                            severity="low",
                            risk_bucket="",
                            order_ref=order.normalized_id,
                            transaction_refs=[charge.transaction_ref],
                            amount_at_risk=Decimal("0"),
                            detail={
                                "order_date": str(order.order_date),
                                "settled_at": str(charge.processed_at),
                                "days_late": int((charge.processed_at - order.order_date).days),
                            },
                        )
                    )
            continue

        # Completed order, no settled charge — but charge attempts exist.
        if charges and not settled_charges:
            attempt = charges[0]
            if attempt.status == "pending":
                findings.append(
                    Finding(
                        type="pending_payment",
                        severity="medium",
                        risk_bucket="uncollected",
                        order_ref=order.normalized_id,
                        transaction_refs=[attempt.transaction_ref],
                        amount_at_risk=attempt.amount,
                        detail={"amount": str(attempt.amount), "status": "pending"},
                    )
                )
            elif attempt.status == "failed":
                findings.append(
                    Finding(
                        type="failed_payment",
                        severity="medium",
                        risk_bucket="uncollected",
                        order_ref=order.normalized_id,
                        transaction_refs=[attempt.transaction_ref],
                        amount_at_risk=attempt.amount,
                        detail={"amount": str(attempt.amount), "status": "failed"},
                    )
                )

    # --- Pass 2: payments with no order ---
    for ref, group in payments_by_ref.items():
        if ref in order_ids:
            continue
        settled = [p for p in group if p.status == "settled" and p.type == "charge"]
        if settled:
            total = sum((p.amount for p in settled), Decimal("0"))
            findings.append(
                Finding(
                    type="orphan_charge",
                    severity="high",
                    risk_bucket="investigation",
                    order_ref=ref,
                    transaction_refs=[p.transaction_ref for p in settled],
                    amount_at_risk=total,
                    detail={"charged": str(total), "txns": [p.transaction_ref for p in settled]},
                )
            )

    # --- Stats ---
    material = [f for f in findings if f.severity in ("high", "medium")]
    value_in_dispute = sum((f.amount_at_risk for f in material), Decimal("0"))
    uncollected = sum((f.amount_at_risk for f in material if f.risk_bucket == "uncollected"), Decimal("0"))
    refund_obligations = sum(
        (f.amount_at_risk for f in material if f.risk_bucket == "refund_obligation"), Decimal("0")
    )
    investigation = sum(
        (f.amount_at_risk for f in material if f.risk_bucket == "investigation"), Decimal("0")
    )
    breakdown: dict = {}
    for f in findings:
        entry = breakdown.setdefault(f.type, {"count": 0, "amount": Decimal("0"), "severity": f.severity})
        entry["count"] += 1
        entry["amount"] += f.amount_at_risk
    breakdown = {k: {**v, "amount": str(v["amount"])} for k, v in sorted(breakdown.items())}

    stats = Stats(
        total_orders=len(orders_sorted),
        total_payments=len(payments_sorted),
        matched_pairs=matched_pairs,
        value_reconciled=value_reconciled,
        value_in_dispute=value_in_dispute,
        money_at_risk=uncollected + refund_obligations,
        uncollected_revenue=uncollected,
        refund_obligations=refund_obligations,
        needs_investigation=investigation,
        breakdown=breakdown,
    )
    return findings, stats
