"""Drill-down API tests: filters, search, pagination, ownership."""
import pytest
from rest_framework.test import APIClient

from apps.ingestion.tests.test_upload_api import SAMPLE_DIR, auth_client  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def loaded_client(auth_client):  # noqa: F801
    """Authenticated client that has uploaded the sample data; sets run_id attr."""
    with open(SAMPLE_DIR / "orders.csv", "rb") as o, open(SAMPLE_DIR / "payments.csv", "rb") as p:
        resp = auth_client.post(
            "/api/imports/", {"orders_file": o, "payments_file": p}, format="multipart"
        )
    assert resp.status_code == 201
    auth_client.run_id = resp.json()["run_id"]
    return auth_client


def test_discrepancies_pagination(loaded_client):
    resp = loaded_client.get(f"/api/runs/{loaded_client.run_id}/discrepancies/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 23
    assert len(body["results"]) == 23  # under page size 25


def test_filter_by_type(loaded_client):
    resp = loaded_client.get(f"/api/runs/{loaded_client.run_id}/discrepancies/", {"type": "missing_payment"})
    body = resp.json()
    assert body["count"] == 4
    assert all(r["type"] == "missing_payment" for r in body["results"])


def test_filter_by_severity(loaded_client):
    resp = loaded_client.get(f"/api/runs/{loaded_client.run_id}/discrepancies/", {"severity": "high"})
    body = resp.json()
    # missing 4 + orphan 3 + duplicate 2 + amount 3 + cancelled 1 = 13
    assert body["count"] == 13


def test_search_by_order_ref(loaded_client):
    resp = loaded_client.get(f"/api/runs/{loaded_client.run_id}/discrepancies/", {"search": "ORD-1501"})
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["order_ref"] == "ORD-1501"


def test_search_by_transaction_ref(loaded_client):
    resp = loaded_client.get(f"/api/runs/{loaded_client.run_id}/discrepancies/", {"search": "TXN700164"})
    body = resp.json()
    assert body["count"] == 1
    assert body["results"][0]["order_ref"] == "ORD-1401"


def test_detail_includes_raw_records(loaded_client):
    list_resp = loaded_client.get(f"/api/runs/{loaded_client.run_id}/discrepancies/", {"type": "amount_mismatch"})
    disc_id = list_resp.json()["results"][0]["id"]
    resp = loaded_client.get(f"/api/discrepancies/{disc_id}/")
    body = resp.json()
    assert body["order"] is not None
    assert body["order"]["order_id"].upper().startswith("ORD-14")
    assert isinstance(body["payments"], list) and body["payments"]


def test_detail_orphan_charge_has_no_order(loaded_client):
    list_resp = loaded_client.get(f"/api/runs/{loaded_client.run_id}/discrepancies/", {"type": "orphan_charge"})
    disc_id = list_resp.json()["results"][0]["id"]
    resp = loaded_client.get(f"/api/discrepancies/{disc_id}/")
    body = resp.json()
    assert body["order"] is None
    assert len(body["payments"]) == 1


def test_run_detail_ownership(loaded_client):
    # A different user must get 404 on this run
    other = APIClient()
    other.post("/api/auth/signup/", {"email": "x@y.zz", "password": "Sup3rSecret!x"}, format="json")
    login = other.post("/api/auth/login/", {"email": "x@y.zz", "password": "Sup3rSecret!x"}, format="json").json()
    other.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    assert other.get(f"/api/runs/{loaded_client.run_id}/").status_code == 404
    assert other.get(f"/api/runs/{loaded_client.run_id}/discrepancies/").status_code == 404


def test_run_list_only_own(loaded_client):
    resp = loaded_client.get("/api/runs/")
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 1
