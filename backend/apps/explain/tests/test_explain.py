"""Explain-layer tests: fallbacks, caching, ownership, and mocked LLM behavior."""
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.explain.agents import Explanation, Summary
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


def _first_disc_id(client, type_="missing_payment"):
    resp = client.get(f"/api/runs/{client.run_id}/discrepancies/", {"type": type_})
    return resp.json()["results"][0]["id"]


def test_explain_without_llm_returns_fallback(loaded_client):
    """No OPENROUTER_API_KEY set → deterministic fallback, flagged degraded."""
    disc_id = _first_disc_id(loaded_client)
    resp = loaded_client.post(f"/api/discrepancies/{disc_id}/explain/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert "ORD-12" in body["summary"]
    assert "engine" in body["likely_cause"]


def test_explain_caches_result(loaded_client):
    disc_id = _first_disc_id(loaded_client)
    r1 = loaded_client.post(f"/api/discrepancies/{disc_id}/explain/")
    # Second call must come from cache (no LLM either way), same content
    r2 = loaded_client.post(f"/api/discrepancies/{disc_id}/explain/")
    assert r1.json() == r2.json()


def test_explain_ownership(loaded_client):
    other = APIClient()
    other.post("/api/auth/signup/", {"email": "z@z.zz", "password": "Sup3rSecret!x"}, format="json")
    login = other.post("/api/auth/login/", {"email": "z@z.zz", "password": "Sup3rSecret!x"}, format="json").json()
    other.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    disc_id = _first_disc_id(loaded_client)
    assert other.post(f"/api/discrepancies/{disc_id}/explain/").status_code == 404


def test_explain_with_mocked_llm(loaded_client):
    """When the LLM is configured and succeeds, its structured output is returned."""
    disc_id = _first_disc_id(loaded_client)
    fake = Explanation(
        summary="Order shows completed but no payment exists.",
        likely_cause="The checkout may have succeeded while the processor webhook failed.",
        recommended_action="Contact the payment processor support with the order id.",
        urgency="high",
    )

    async def fake_explain(payload):
        assert payload["discrepancy_type"] == "missing_payment"
        return fake

    with patch("apps.explain.views.llm_available", return_value=True), \
         patch("apps.explain.views.explain_discrepancy_async", fake_explain):
        resp = loaded_client.post(f"/api/discrepancies/{disc_id}/explain/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is False
    assert body["urgency"] == "high"
    assert body["summary"].startswith("Order shows completed")


def test_explain_llm_failure_falls_back(loaded_client):
    """LLM configured but raises → deterministic fallback, still 200."""
    disc_id = _first_disc_id(loaded_client, "orphan_charge")

    async def boom(payload):
        raise RuntimeError("provider down")

    with patch("apps.explain.views.llm_available", return_value=True), \
         patch("apps.explain.views.explain_discrepancy_async", boom):
        resp = loaded_client.post(f"/api/discrepancies/{disc_id}/explain/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True


def test_summarize_without_llm(loaded_client):
    resp = loaded_client.post(f"/api/runs/{loaded_client.run_id}/summarize/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is True
    assert any("missing_payment" in p for p in body["top_priorities"])


def test_summarize_with_mocked_llm(loaded_client):
    fake = Summary(
        executive_summary="Reconciliation is mostly clean with a handful of material issues.",
        top_priorities=["Refund the double charges", "Chase the four unpaid orders"],
        recommended_actions=["Issue refunds for duplicate charges first"],
    )

    async def fake_summarize(payload):
        assert "breakdown_by_type" in payload
        return fake

    with patch("apps.explain.views.llm_available", return_value=True), \
         patch("apps.explain.views.summarize_findings_async", fake_summarize):
        resp = loaded_client.post(f"/api/runs/{loaded_client.run_id}/summarize/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["degraded"] is False
    assert body["top_priorities"] == fake.top_priorities
