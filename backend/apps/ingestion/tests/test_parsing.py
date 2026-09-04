"""Parser tests — run against the real provided CSVs (golden behavior)."""
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from apps.ingestion.parsing import (
    ParseError,
    parse_orders_csv,
    parse_payments_csv,
)

SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sample_data"


@pytest.fixture(scope="module")
def orders_text():
    return (SAMPLE_DIR / "orders.csv").read_text()


@pytest.fixture(scope="module")
def payments_text():
    return (SAMPLE_DIR / "payments.csv").read_text()


def test_orders_parse_count_and_fields(orders_text):
    orders, warnings = parse_orders_csv(orders_text)
    # 185 raw rows, 1 exact duplicate (ORD-1004) → 184 unique
    assert len(orders) == 184
    assert any(w["code"] == "duplicate_order_row" and w["order_id"] == "ORD-1004" for w in warnings)


def test_orders_empty_email_becomes_none(orders_text):
    orders, _ = parse_orders_csv(orders_text)
    o2201 = next(o for o in orders if o.normalized_id == "ORD-2201")
    assert o2201.customer_email is None
    # empty discount → 0
    o2201 and None
    assert o2201.discount == Decimal("0")


def test_orders_normalization_uppercases_ids(orders_text):
    orders, _ = parse_orders_csv(orders_text)
    assert all(o.normalized_id == o.normalized_id.strip().upper() for o in orders)


def test_orders_bad_date_raises():
    with pytest.raises(ParseError):
        parse_orders_csv("order_id,order_date,customer_email,currency,gross_amount,discount,net_amount,status\n"
                         "ORD-1,not-a-date,x@y.co,USD,10,0,10,completed\n")


def test_payments_parse_count(payments_text):
    payments, _ = parse_payments_csv(payments_text)
    assert len(payments) == 187


def _utc(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


def test_payments_dayfirst_dates(payments_text):
    payments, _ = parse_payments_csv(payments_text)
    # TXN700003: 03/05/2025 20:24 → May 3rd (day-first)
    txn = next(p for p in payments if p.transaction_ref == "TXN700003")
    assert txn.processed_at == _utc(2025, 5, 3, 20, 24)
    # A day >12 row proves day-first: 28/04/2025 → April 28
    txn2 = next(p for p in payments if p.transaction_ref == "TXN700167")
    assert txn2.processed_at == _utc(2025, 4, 28, 0, 12)


def test_payments_dirty_refs_normalized(payments_text):
    payments, warnings = parse_payments_csv(payments_text)
    txn = next(p for p in payments if p.transaction_ref == "TXN700178")
    assert txn.normalized_order_ref == "ORD-1801"
    txn2 = next(p for p in payments if p.transaction_ref == "TXN700179")
    assert txn2.normalized_order_ref == "ORD-1802"
    norm_warnings = [w for w in warnings if w["code"] == "normalized_order_reference"]
    assert len(norm_warnings) == 2


def test_payments_missing_processed_at_flagged(payments_text):
    payments, warnings = parse_payments_csv(payments_text)
    txn = next(p for p in payments if p.transaction_ref == "TXN700187")
    assert txn.processed_at is None
    assert any(w["code"] == "missing_processed_at" and w["transaction_ref"] == "TXN700187" for w in warnings)


def test_payments_decimal_amounts(payments_text):
    payments, _ = parse_payments_csv(payments_text)
    txn = next(p for p in payments if p.transaction_ref == "TXN700171")
    assert isinstance(txn.amount, Decimal)
    assert txn.amount == Decimal("210.00")
