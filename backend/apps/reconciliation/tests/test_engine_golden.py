"""Golden tests: the engine's exact output on the provided CSVs.

Expected numbers were derived by independent analysis of the two files before the
engine was written (see README 'What we found in the data').
"""
from decimal import Decimal
from pathlib import Path

import pytest

from apps.ingestion.parsing import parse_orders_csv, parse_payments_csv
from apps.reconciliation.engine import AMOUNT_TOLERANCE, reconcile

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sample_data"


@pytest.fixture(scope="module")
def golden():
    orders, _ = parse_orders_csv((SAMPLE_DIR / "orders.csv").read_text())
    payments, _ = parse_payments_csv((SAMPLE_DIR / "payments.csv").read_text())
    return reconcile(orders, payments)


def by_type(findings, type_):
    return [f for f in findings if f.type == type_]


class TestGoldenCounts:
    def test_missing_payment(self, golden):
        findings, _ = golden
        rows = by_type(findings, "missing_payment")
        assert sorted(f.order_ref for f in rows) == ["ORD-1201", "ORD-1202", "ORD-1203", "ORD-1204"]
        assert sum(f.amount_at_risk for f in rows) == Decimal("392.35")

    def test_orphan_charge(self, golden):
        findings, _ = golden
        rows = by_type(findings, "orphan_charge")
        assert sorted(f.order_ref for f in rows) == ["ORD-1301", "ORD-1302", "ORD-1303"]
        assert sum(f.amount_at_risk for f in rows) == Decimal("308.00")

    def test_duplicate_charge(self, golden):
        findings, _ = golden
        rows = by_type(findings, "duplicate_charge")
        assert sorted(f.order_ref for f in rows) == ["ORD-1501", "ORD-1502"]
        # Extra charges: 119.84 + 128.74
        assert sum(f.amount_at_risk for f in rows) == Decimal("248.58")

    def test_amount_mismatch(self, golden):
        findings, _ = golden
        rows = by_type(findings, "amount_mismatch")
        assert sorted(f.order_ref for f in rows) == ["ORD-1401", "ORD-1402", "ORD-1403"]
        assert sum(f.amount_at_risk for f in rows) == Decimal("103.50")

    def test_amount_mismatch_directions(self, golden):
        findings, _ = golden
        by_ref = {f.order_ref: f for f in by_type(findings, "amount_mismatch")}
        assert by_ref["ORD-1401"].detail["direction"] == "overcharged"
        assert by_ref["ORD-1401"].amount_at_risk == Decimal("25.00")
        assert by_ref["ORD-1402"].detail["direction"] == "undercharged"
        assert by_ref["ORD-1402"].amount_at_risk == Decimal("18.50")
        assert by_ref["ORD-1403"].detail["direction"] == "overcharged"
        assert by_ref["ORD-1403"].amount_at_risk == Decimal("60.00")

    def test_charged_after_cancellation(self, golden):
        findings, _ = golden
        rows = by_type(findings, "charged_after_cancellation")
        assert [f.order_ref for f in rows] == ["ORD-1701"]
        assert rows[0].amount_at_risk == Decimal("175.00")

    def test_partial_refund(self, golden):
        findings, _ = golden
        rows = by_type(findings, "partial_refund")
        assert [f.order_ref for f in rows] == ["ORD-1702"]
        assert rows[0].amount_at_risk == Decimal("120.00")  # charged 240, refunded 120

    def test_refund_of_completed_order(self, golden):
        findings, _ = golden
        rows = by_type(findings, "refund_of_completed_order")
        assert [f.order_ref for f in rows] == ["ORD-1703"]
        assert rows[0].amount_at_risk == Decimal("99.00")

    def test_currency_mismatch(self, golden):
        findings, _ = golden
        rows = by_type(findings, "currency_mismatch")
        assert sorted(f.order_ref for f in rows) == ["ORD-1601", "ORD-1602"]

    def test_failed_and_pending(self, golden):
        findings, _ = golden
        failed = by_type(findings, "failed_payment")
        pending = by_type(findings, "pending_payment")
        assert [f.order_ref for f in failed] == ["ORD-2001"]
        assert failed[0].amount_at_risk == Decimal("310.00")
        assert [f.order_ref for f in pending] == ["ORD-2002"]
        assert pending[0].amount_at_risk == Decimal("67.00")

    def test_late_settlement(self, golden):
        findings, _ = golden
        rows = by_type(findings, "late_settlement")
        assert [f.order_ref for f in rows] == ["ORD-2101"]
        assert rows[0].detail["days_late"] >= 28

    def test_rounding_variance_within_tolerance(self, golden):
        findings, _ = golden
        rows = by_type(findings, "rounding_variance")
        assert sorted(f.order_ref for f in rows) == ["ORD-1901", "ORD-1902", "ORD-1903"]
        # Rounding variances never count as risk
        assert sum(f.amount_at_risk for f in rows) == Decimal("0")

    def test_tolerance_boundary(self, golden):
        # 0.05 exactly is tolerated; anything above is material.
        assert AMOUNT_TOLERANCE == Decimal("0.05")


class TestGoldenStats:
    def test_totals(self, golden):
        _, stats = golden
        assert stats.total_orders == 184  # 185 rows − 1 exact duplicate
        assert stats.total_payments == 187
        # 182 completed unique orders − 4 unpaid − 2 double-charged − 2 unsettled-only
        assert stats.matched_pairs == 174

    def test_value_reconciled(self, golden):
        _, stats = golden
        # All matched pairs within amount tolerance and same currency.
        # Cross-check: 41854.65 (completed net after dedup) − 392.35 (missing) −
        # 419.44 (mismatch orders' nets) − 355 (currency swaps) − 377 (failed/pending) −
        # 248.58 (dup orders counted once) = 40062.28
        assert stats.value_reconciled == Decimal("40062.28")

    def test_value_in_dispute(self, golden):
        _, stats = golden
        # high+medium: 392.35 + 308.00 + 248.58 + 103.50 + 175.00 + 120.00 + 99.00
        # + 210 + 145 (currency) + 310 (failed) + 67 (pending) = 2178.43
        assert stats.value_in_dispute == Decimal("2178.43")

    def test_risk_buckets(self, golden):
        _, stats = golden
        # uncollected: 392.35 (missing) + 18.50 (undercharged) + 310 (failed) + 67 (pending)
        assert stats.uncollected_revenue == Decimal("787.85")
        # refund obligations: 248.58 (dups) + 85 (overcharged) + 175 (cancelled)
        assert stats.refund_obligations == Decimal("508.58")
        # investigation: 308 (orphans) + 120 (partial refund) + 99 (refund completed) + 355 (currency)
        assert stats.needs_investigation == Decimal("882.00")
        assert stats.money_at_risk == Decimal("1296.43")


class TestDeterminism:
    def test_same_input_same_output(self):
        orders, _ = parse_orders_csv((SAMPLE_DIR / "orders.csv").read_text())
        payments, _ = parse_payments_csv((SAMPLE_DIR / "payments.csv").read_text())
        f1, s1 = reconcile(orders, payments)
        f2, s2 = reconcile(orders, payments)
        assert [(f.type, f.order_ref, str(f.amount_at_risk)) for f in f1] == [
            (f.type, f.order_ref, str(f.amount_at_risk)) for f in f2
        ]
        assert s1.breakdown == s2.breakdown

    def test_dirty_refs_still_match(self):
        """The 18xx trap: ' ord-1801 ' and 'ord-1802' must match their orders."""
        orders, _ = parse_orders_csv((SAMPLE_DIR / "orders.csv").read_text())
        payments, _ = parse_payments_csv((SAMPLE_DIR / "payments.csv").read_text())
        findings, _ = reconcile(orders, payments)
        # Neither order may appear as missing_payment
        missing = {f.order_ref for f in findings if f.type == "missing_payment"}
        assert "ORD-1801" not in missing and "ORD-1802" not in missing
