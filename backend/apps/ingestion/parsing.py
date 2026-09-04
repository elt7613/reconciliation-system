"""CSV parsing and normalization.

Raw values are preserved wherever the source is messy (dirty refs, empty fields);
normalized fields are what the engine matches on. Parsing rules are data-driven:

- Order refs and payment order-refs are normalized via strip().upper() — resolves
  the ' ord-1801 ' / 'ord-1802' dirty-reference rows.
- Payment dates use DD/MM/YYYY (day-first) — verified against the dataset
  (116 unambiguous day-first rows; the remaining ambiguous ones are consistent).
- Empty discount → Decimal("0"); empty email / processed_at → NULL.
- Exact-duplicate order rows (same normalized id + identical fields) are dropped,
  with a data-quality warning recorded on the batch.
- All money parsed via Decimal (never float).
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

def _utc(dt: datetime) -> datetime:
    """Both files are naive local exports; treat them as UTC for storage."""
    return dt.replace(tzinfo=timezone.utc)

ORDER_FIELDS = [
    "order_id",
    "order_date",
    "customer_email",
    "currency",
    "gross_amount",
    "discount",
    "net_amount",
    "status",
]

PAYMENT_FIELDS = [
    "transaction_ref",
    "processed_at",
    "order_reference",
    "currency",
    "amount",
    "fee",
    "net_settled",
    "type",
    "status",
]


@dataclass
class ParsedOrder:
    raw: dict
    normalized_id: str
    order_date: datetime
    customer_email: str | None
    currency: str
    gross_amount: Decimal
    discount: Decimal
    net_amount: Decimal
    status: str


@dataclass
class ParsedPayment:
    raw: dict
    transaction_ref: str
    normalized_order_ref: str
    processed_at: datetime | None
    currency: str
    amount: Decimal
    fee: Decimal
    net_settled: Decimal
    type: str
    status: str


@dataclass
class ParseResult:
    orders: list[ParsedOrder] = field(default_factory=list)
    payments: list[ParsedPayment] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)

    @property
    def duplicate_order_rows(self) -> int:
        return sum(1 for w in self.warnings if w["code"] == "duplicate_order_row")


class ParseError(ValueError):
    """Raised for structural problems that make the file unusable."""


def _to_decimal(value: str, *, context: str) -> Decimal:
    text = (value or "").strip()
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ParseError(f"Invalid amount {value!r} in {context}") from exc


def _empty_to_none(value: str | None) -> str | None:
    text = (value or "").strip()
    return text or None


def parse_orders_csv(text: str) -> tuple[list[ParsedOrder], list[dict]]:
    """Parse orders CSV content. Returns (orders, warnings).

    Exact duplicate rows (all fields identical) are dropped with a warning — they
    are export artifacts, not real orders. Non-identical rows sharing an order id
    are a genuine problem and are surfaced as a conflict warning; the first row wins.
    """
    import csv
    import io

    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [f for f in ORDER_FIELDS if f not in header]
    if missing:
        raise ParseError(f"orders.csv missing columns: {', '.join(missing)}")

    orders: list[ParsedOrder] = []
    warnings: list[dict] = []
    seen: dict[str, tuple[ParsedOrder, str]] = {}

    for line_no, row in enumerate(reader, start=2):
        raw = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        order_id_raw = raw.get("order_id", "")
        if not order_id_raw:
            warnings.append({"code": "missing_order_id", "row": line_no})
            continue
        normalized = order_id_raw.strip().upper()
        fingerprint = str(dict(sorted(raw.items())))

        if normalized in seen:
            existing, existing_fp = seen[normalized]
            if fingerprint == existing_fp:
                warnings.append({"code": "duplicate_order_row", "order_id": order_id_raw, "row": line_no})
                continue
            warnings.append(
                {
                    "code": "conflicting_duplicate_order",
                    "order_id": order_id_raw,
                    "row": line_no,
                }
            )
            continue

        try:
            order_date = _utc(datetime.strptime(raw["order_date"], "%Y-%m-%d %H:%M:%S"))
        except (KeyError, ValueError) as exc:
            raise ParseError(f"Invalid order_date at row {line_no}: {raw.get('order_date')!r}") from exc

        order = ParsedOrder(
            raw=raw,
            normalized_id=normalized,
            order_date=order_date,
            customer_email=_empty_to_none(raw.get("customer_email")),
            currency=(raw.get("currency") or "").strip().upper(),
            gross_amount=_to_decimal(raw.get("gross_amount"), context=f"orders row {line_no} gross_amount"),
            discount=_to_decimal(raw.get("discount"), context=f"orders row {line_no} discount"),
            net_amount=_to_decimal(raw.get("net_amount"), context=f"orders row {line_no} net_amount"),
            status=(raw.get("status") or "").strip().lower(),
        )
        orders.append(order)
        seen[normalized] = (order, fingerprint)

    return orders, warnings


def parse_payments_csv(text: str) -> tuple[list[ParsedPayment], list[dict]]:
    """Parse payments CSV content. Returns (payments, warnings).

    Payment dates are DD/MM/YYYY HH:MM (day-first) — this format was verified
    against the dataset: 116 rows are unambiguous day-first, and the remaining
    70 ambiguous rows are all consistent with day-first parsing.
    """
    import csv
    import io

    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [f for f in PAYMENT_FIELDS if f not in header]
    if missing:
        raise ParseError(f"payments.csv missing columns: {', '.join(missing)}")

    payments: list[ParsedPayment] = []
    warnings: list[dict] = []
    seen_txn: set[str] = set()

    for line_no, row in enumerate(reader, start=2):
        raw = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        txn_raw = raw.get("transaction_ref", "")
        if not txn_raw:
            warnings.append({"code": "missing_transaction_ref", "row": line_no})
            continue
        if txn_raw in seen_txn:
            warnings.append({"code": "duplicate_transaction_row", "transaction_ref": txn_raw, "row": line_no})
            continue
        seen_txn.add(txn_raw)

        order_ref_raw = raw.get("order_reference", "") or ""
        normalized_ref = order_ref_raw.strip().upper()
        if order_ref_raw != normalized_ref:
            warnings.append(
                {
                    "code": "normalized_order_reference",
                    "transaction_ref": txn_raw,
                    "raw": order_ref_raw,
                    "normalized": normalized_ref,
                }
            )

        processed_at: datetime | None = None
        date_text = (raw.get("processed_at") or "").strip()
        if date_text:
            try:
                processed_at = _utc(datetime.strptime(date_text, "%d/%m/%Y %H:%M"))
            except ValueError as exc:
                warnings.append(
                    {"code": "unparseable_date", "transaction_ref": txn_raw, "value": date_text}
                )
        else:
            warnings.append({"code": "missing_processed_at", "transaction_ref": txn_raw})

        payment = ParsedPayment(
            raw=raw,
            transaction_ref=txn_raw,
            normalized_order_ref=normalized_ref,
            processed_at=processed_at,
            currency=(raw.get("currency") or "").strip().upper(),
            amount=_to_decimal(raw.get("amount"), context=f"payments row {line_no} amount"),
            fee=_to_decimal(raw.get("fee"), context=f"payments row {line_no} fee"),
            net_settled=_to_decimal(raw.get("net_settled"), context=f"payments row {line_no} net_settled"),
            type=(raw.get("type") or "").strip().lower(),
            status=(raw.get("status") or "").strip().lower(),
        )
        payments.append(payment)

    return payments, warnings
