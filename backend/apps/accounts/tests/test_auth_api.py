"""Auth API smoke tests: signup, login, me, isolation."""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


def test_signup_returns_tokens(client):
    resp = client.post(
        "/api/auth/signup/",
        {"email": "a@b.co", "password": "Sup3rSecret!x"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["tokens"]["access"]


def test_signup_rejects_duplicate_email(client):
    client.post("/api/auth/signup/", {"email": "a@b.co", "password": "Sup3rSecret!x"}, format="json")
    resp = client.post(
        "/api/auth/signup/", {"email": "a@b.co", "password": "Sup3rSecret!x"}, format="json"
    )
    assert resp.status_code == 400


def test_signup_rejects_weak_password(client):
    resp = client.post("/api/auth/signup/", {"email": "a@b.co", "password": "123"}, format="json")
    assert resp.status_code == 400


def test_login_returns_token_pair(client):
    client.post("/api/auth/signup/", {"email": "a@b.co", "password": "Sup3rSecret!x"}, format="json")
    resp = client.post("/api/auth/login/", {"email": "a@b.co", "password": "Sup3rSecret!x"}, format="json")
    assert resp.status_code == 200
    assert "access" in resp.json() and "refresh" in resp.json()


def test_login_wrong_password_fails(client):
    client.post("/api/auth/signup/", {"email": "a@b.co", "password": "Sup3rSecret!x"}, format="json")
    resp = client.post("/api/auth/login/", {"email": "a@b.co", "password": "nope"}, format="json")
    assert resp.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/auth/me/").status_code == 401


def test_me_with_token(client):
    client.post("/api/auth/signup/", {"email": "a@b.co", "password": "Sup3rSecret!x"}, format="json")
    login = client.post("/api/auth/login/", {"email": "a@b.co", "password": "Sup3rSecret!x"}, format="json").json()
    resp = client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@b.co"


def test_refresh_returns_new_access_token(client):
    client.post("/api/auth/signup/", {"email": "a@b.co", "password": "Sup3rSecret!x"}, format="json")
    login = client.post("/api/auth/login/", {"email": "a@b.co", "password": "Sup3rSecret!x"}, format="json").json()
    resp = client.post("/api/auth/refresh/", {"refresh": login["refresh"]}, format="json")
    assert resp.status_code == 200
    assert "access" in resp.json()
    # The new access token actually authenticates
    resp2 = client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")
    assert resp2.status_code == 200


def test_refresh_with_garbage_token_fails(client):
    resp = client.post("/api/auth/refresh/", {"refresh": "not-a-token"}, format="json")
    assert resp.status_code == 401


def test_health_endpoint_is_public(client):
    resp = client.get("/api/health/")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
