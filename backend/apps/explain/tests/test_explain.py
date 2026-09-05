"""Explain-layer tests: fallbacks, caching, ownership, and mocked service calls.

The AI layer now runs in a separate FastAPI microservice; the Django side only
makes HTTP calls via apps.explain.client. Tests mock the client (hermetic —
no network, no LLM) and verify the view behavior around it.
"""
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.explain import client
from apps.ingestion.tests.test_upload_api import SAMPLE_DIR, auth_client  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def loaded_client(auth_client):  # noqa: F801
    with open(SAMPLE_DIR / "orders.csv", "rb") as o, open(SAMPLE_DIR / "payments.csv", "rb") as p:
        resp = auth_client.post(
            "/api/imports/", {"orders_file": o, "payments_file": p}, format="multipart"
        )
    auth_client.run_id = resp.json()["run_id"]
    return auth_client


def _first_disc_id(client_, type_="missing_payment"):
    resp = client_.get(f"/api/runs/{client_.run_id}/discrepancies/", {"type": type_})
    return resp.json()["results"][0]["id"]


def test_explain_without_service_returns_fallback(loaded_client):
    """AI service not configured → deterministic fallback, flagged degraded."""
    disc_id = _first_disc_id(loaded_client)
    with patch.object(client, "is_configured", return_value=False):
        resp = loaded_client.post(f"/api/discrepancies/{disc_id}/explain/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert "ORD-12" in body["summary"]
    assert "engine" in body["likely_cause"]


def test_explain_caches_result(loaded_client):
    disc_id = _first_disc_id(loaded_client)
    with patch.object(client, "is_configured", return_value=False):
        r1 = loaded_client.post(f"/api/discrepancies/{disc_id}/explain/")
        r2 = loaded_client.post(f"/api/discrepancies/{disc_id}/explain/")
    assert r1.json() == r2.json()


def test_explain_ownership(loaded_client):
    other = APIClient()
    other.post("/api/auth/signup/", {"email": "z@z.zz", "password": "Sup3rSecret!x"}, format="json")
    login = other.post("/api/auth/login/", {"email": "z@z.zz", "password": "Sup3rSecret!x"}, format="json").json()
    other.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    disc_id = _first_disc_id(loaded_client)
    assert other.post(f"/api/discrepancies/{disc_id}/explain/").status_code == 404


def test_explain_with_mocked_service(loaded_client):
    """Service healthy → its structured output is returned, degraded False."""
    disc_id = _first_disc_id(loaded_client)
    fake = {
        "summary": "Order shows completed but no payment exists.",
        "likely_cause": "The checkout succeeded while the processor webhook failed.",
        "recommended_action": "Contact the payment processor with the order id.",
        "urgency": "high",
    }

    def fake_explain(payload):
        assert payload["discrepancy_type"] == "missing_payment"
        assert "\n" not in payload["order_reference"]  # sanitized
        return dict(fake)

    with patch.object(client, "is_configured", return_value=True), \
         patch.object(client, "explain_discrepancy", side_effect=fake_explain):
        resp = loaded_client.post(f"/api/discrepancies/{disc_id}/explain/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is False
    assert body["urgency"] == "high"
    assert body["summary"].startswith("Order shows completed")


def test_explain_service_failure_falls_back(loaded_client):
    """Service configured but unreachable → deterministic fallback, still 200."""
    disc_id = _first_disc_id(loaded_client, "orphan_charge")

    def boom(payload):
        raise client.AIServiceError("AI service unreachable: ConnectError")

    with patch.object(client, "is_configured", return_value=True), \
         patch.object(client, "explain_discrepancy", side_effect=boom):
        resp = loaded_client.post(f"/api/discrepancies/{disc_id}/explain/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True


def test_summarize_without_service(loaded_client):
    with patch.object(client, "is_configured", return_value=False):
        resp = loaded_client.post(f"/api/runs/{loaded_client.run_id}/summarize/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert any("missing_payment" in p for p in body["top_priorities"])


def test_summarize_with_mocked_service(loaded_client):
    fake = {
        "executive_summary": "Reconciliation is mostly clean with a handful of material issues.",
        "top_priorities": ["Refund the double charges", "Chase the four unpaid orders"],
        "recommended_actions": ["Issue refunds for duplicate charges first"],
    }

    def fake_summarize(payload):
        assert "breakdown_by_type" in payload
        return dict(fake)

    with patch.object(client, "is_configured", return_value=True), \
         patch.object(client, "summarize_findings", side_effect=fake_summarize):
        resp = loaded_client.post(f"/api/runs/{loaded_client.run_id}/summarize/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is False
    assert body["top_priorities"] == fake["top_priorities"]


def test_service_client_retries_transport_errors():
    """The httpx client retries connect errors (the DNS-blip class) with backoff."""
    calls = {"n": 0}

    def flaky_post(url, **kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            import httpx

            raise httpx.ConnectError("DNS blip")
        return type("R", (), {"status_code": 200, "json": lambda self: {"ok": True}})()

    with patch.object(client.httpx, "post", side_effect=flaky_post), \
         patch.object(client, "is_configured", return_value=True):
        result = client.explain_discrepancy({"x": 1})
    assert result == {"ok": True}
    assert calls["n"] == 3  # initial + 2 retries


def test_service_client_no_retry_on_auth_error():
    """401 from the service is a config error — must NOT be retried."""
    calls = {"n": 0}

    def rejecting_post(url, **kwargs):
        calls["n"] += 1
        return type("R", (), {"status_code": 401, "json": lambda self: {}})()

    with patch.object(client.httpx, "post", side_effect=rejecting_post):
        with pytest.raises(client.AIServiceError):
            client.explain_discrepancy({"x": 1})
    assert calls["n"] == 1
