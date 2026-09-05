"""AI service tests — mocked agents, hermetic (no network, no LLM)."""
import pytest
from fastapi.testclient import TestClient

from app import agents
from app.config import settings
from app.main import app

client = TestClient(app)

EXPLAIN_PAYLOAD = {
    "discrepancy_type": "duplicate_charge",
    "severity": "high",
    "risk_bucket": "refund_obligation",
    "order_reference": "ORD-1501",
    "transaction_refs": ["TXN700167", "TXN700168"],
    "amount_at_risk": "119.84",
    "engine_facts": {"order_net": "119.84", "times_charged": 2},
}

SUMMARIZE_PAYLOAD = {
    "headline": {"total_orders": 184, "money_at_risk": "1296.43"},
    "breakdown_by_type": {"missing_payment": {"count": 4, "amount": "392.35"}},
}


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    """Every test runs with a known service key + LLM marked available."""
    monkeypatch.setattr(settings, "ai_service_api_key", "test-key", raising=False)
    monkeypatch.setattr(agents, "llm_available", lambda: True)
    yield


def _auth():
    return {"X-API-Key": "test-key"}


def test_health_public():
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_reports_config():
    body = client.get("/ready").json()
    assert body["status"] in ("ok", "degraded")
    assert "model" in body


def test_explain_rejects_missing_key():
    assert client.post("/explain", json=EXPLAIN_PAYLOAD).status_code == 401


def test_explain_rejects_wrong_key():
    assert client.post("/explain", json=EXPLAIN_PAYLOAD, headers={"X-API-Key": "nope"}).status_code == 401


def test_explain_rejects_malformed_payload():
    resp = client.post("/explain", json={"garbage": True}, headers=_auth())
    assert resp.status_code == 422


def test_explain_happy_path(monkeypatch):
    from app.schemas import Explanation

    fake = Explanation(
        summary="Charged twice.",
        likely_cause="Double submit.",
        recommended_action="Refund the duplicate.",
        urgency="high",
    )

    async def fake_explain(payload):
        assert payload["order_reference"] == "ORD-1501"
        return fake

    monkeypatch.setattr(agents, "explain_discrepancy", fake_explain)
    resp = client.post("/explain", json=EXPLAIN_PAYLOAD, headers=_auth())
    assert resp.status_code == 200
    body = resp.json()
    assert body["urgency"] == "high" and body["summary"] == "Charged twice."


def test_explain_maps_provider_failure_to_502(monkeypatch):
    async def boom(payload):
        raise RuntimeError("provider down")

    monkeypatch.setattr(agents, "explain_discrepancy", boom)
    resp = client.post("/explain", json=EXPLAIN_PAYLOAD, headers=_auth())
    assert resp.status_code == 502


def test_summarize_happy_path(monkeypatch):
    from app.schemas import Summary

    fake = Summary(
        executive_summary="Mostly clean, some issues.",
        top_priorities=["Refund duplicates"],
        recommended_actions=["Issue refunds first"],
    )

    async def fake_summarize(payload):
        assert "breakdown_by_type" in payload
        return fake

    monkeypatch.setattr(agents, "summarize_findings", fake_summarize)
    resp = client.post("/summarize", json=SUMMARIZE_PAYLOAD, headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["top_priorities"] == ["Refund duplicates"]


def test_unconfigured_llm_is_503(monkeypatch):
    monkeypatch.setattr(agents, "llm_available", lambda: False)
    resp = client.post("/explain", json=EXPLAIN_PAYLOAD, headers=_auth())
    assert resp.status_code == 503


def test_service_key_fails_closed_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "ai_service_api_key", "", raising=False)
    resp = client.post("/explain", json=EXPLAIN_PAYLOAD, headers={"X-API-Key": ""})
    assert resp.status_code in (401, 503)
