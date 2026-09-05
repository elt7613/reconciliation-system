"""End-to-end ingestion API tests: upload real CSVs → batch + run created."""
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.ingestion.models import ImportBatch
from apps.reconciliation.models import Discrepancy, ReconciliationRun

User = get_user_model()
SAMPLE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sample_data"
pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client():
    client = APIClient()
    client.post(
        "/api/auth/signup/", {"email": "e2e@test.dev", "password": "Sup3rSecret!x"}, format="json"
    )
    login = client.post(
        "/api/auth/login/", {"email": "e2e@test.dev", "password": "Sup3rSecret!x"}, format="json"
    ).json()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    return client


def _upload(client):
    with open(SAMPLE_DIR / "orders.csv", "rb") as o, open(SAMPLE_DIR / "payments.csv", "rb") as p:
        return client.post(
            "/api/imports/",
            {"orders_file": o, "payments_file": p},
            format="multipart",
        )


def test_upload_requires_auth():
    resp = APIClient().post("/api/imports/", {})
    assert resp.status_code == 401


def test_upload_bad_headers_rejected(auth_client):
    import io

    bad = io.StringIO("wrong,columns,here\n1,2,3\n")
    resp = auth_client.post(
        "/api/imports/",
        {
            "orders_file": bad,
            "payments_file": io.StringIO("also,wrong\n1,2\n"),
        },
        format="multipart",
    )
    assert resp.status_code == 400
    assert "missing columns" in resp.json()["detail"]


def test_sample_endpoint_creates_run(auth_client):
    resp = auth_client.post("/api/imports/sample/")
    assert resp.status_code == 201, resp.content
    data = resp.json()
    assert data["batch"]["order_row_count"] == 184
    assert data["batch"]["payment_row_count"] == 187
    assert ReconciliationRun.objects.filter(id=data["run_id"]).exists()


def test_batches_lists_run_id(auth_client):
    with open(SAMPLE_DIR / "orders.csv", "rb") as o, open(SAMPLE_DIR / "payments.csv", "rb") as p:
        resp = auth_client.post(
            "/api/imports/", {"orders_file": o, "payments_file": p}, format="multipart"
        )
    run_id = resp.json()["run_id"]
    batches = auth_client.get("/api/batches/").json()["results"]
    assert len(batches) == 1
    assert batches[0]["run_id"] == run_id


def test_upload_creates_batch_and_run(auth_client):
    resp = _upload(auth_client)
    assert resp.status_code == 201, resp.content
    data = resp.json()
    assert data["batch"]["order_row_count"] == 184
    assert data["batch"]["payment_row_count"] == 187
    # Warnings recorded: 1 duplicate order row + 2 dirty refs + 1 missing email/discount
    # + 1 missing processed_at
    codes = [w["code"] for w in data["batch"]["warnings"]]
    assert codes.count("duplicate_order_row") == 1
    assert codes.count("normalized_order_reference") == 2
    assert codes.count("missing_processed_at") == 1

    run = ReconciliationRun.objects.get(id=data["run_id"])
    assert run.total_orders == 184
    assert run.total_payments == 187
    assert str(run.money_at_risk) == "1296.43"
    assert run.discrepancies.count() == 23  # 20 material + 3 rounding


def test_rerun_is_deterministic(auth_client):
    _upload(auth_client)
    # Second run over the same batch must produce identical results
    resp = auth_client.post("/api/runs/")
    assert resp.status_code == 201
    runs = ReconciliationRun.objects.all()
    assert runs.count() == 2
    a, b = runs.order_by("id")
    assert a.breakdown == b.breakdown
    assert str(a.value_in_dispute) == str(b.value_in_dispute)


def test_users_only_see_own_batches(auth_client):
    _upload(auth_client)
    other = APIClient()
    other.post("/api/auth/signup/", {"email": "other@test.dev", "password": "Sup3rSecret!x"}, format="json")
    login = other.post(
        "/api/auth/login/", {"email": "other@test.dev", "password": "Sup3rSecret!x"}, format="json"
    ).json()
    other.credentials(HTTP_AUTHORIZATION=f"Bearer {login['access']}")

    resp = other.get("/api/batches/")
    assert resp.status_code == 200
    assert resp.json()["results"] == []

    # Other user's run list is empty; direct run access must 404
    resp = other.get("/api/runs/1/")
    assert resp.status_code == 404

    # Other user cannot upload into first user's context — their own upload is isolated
    with open(SAMPLE_DIR / "orders.csv", "rb") as o, open(SAMPLE_DIR / "payments.csv", "rb") as p:
        resp = other.post("/api/imports/", {"orders_file": o, "payments_file": p}, format="multipart")
    assert resp.status_code == 201
    batch_ids = set(ImportBatch.objects.values_list("id", flat=True))
    user_ids = dict(ImportBatch.objects.values_list("id", "user_id"))
    # two batches, two distinct users
    assert len(batch_ids) == 2
    assert len(set(user_ids.values())) == 2
