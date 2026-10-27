import httpx
import pytest

from app.core.config import get_settings
from tests.conftest import auth, register

CLIENT_ID = "123-teste.apps.googleusercontent.com"
URL = "/api/v1/auth/google"
TOKEN = "token-de-teste-assinado"
# Capturado uma vez: o patch troca httpx.AsyncClient no próprio módulo httpx.
REAL_CLIENT = httpx.AsyncClient


def google_says(monkeypatch, status=200, **overrides):
    """Simula o tokeninfo do Google (nenhuma chamada real)."""
    info = {
        "aud": CLIENT_ID,
        "iss": "https://accounts.google.com",
        "email": "Pessoa@Gmail.com",
        "email_verified": "true",
        "name": "Pessoa Teste",
        "sub": "1098",
        **overrides,
    }
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json=info if status == 200 else {"error": "invalid"})

    monkeypatch.setattr(
        "app.services.google_auth.httpx.AsyncClient",
        lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw),
    )
    return calls


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", CLIENT_ID)


async def test_first_login_requires_terms_then_creates_account(client, monkeypatch):
    calls = google_says(monkeypatch)
    r = await client.post(URL, json={"id_token": TOKEN})
    assert r.status_code == 400 and "termos" in r.json()["detail"]

    r = await client.post(URL, json={"id_token": TOKEN, "accept_terms": True})
    assert r.status_code == 200
    me = (await client.get("/api/v1/me", headers=auth(r.json()))).json()
    assert me["email"] == "pessoa@gmail.com" and me["auth_provider"] == "google"
    assert me["name"] == "Pessoa Teste"
    assert calls[-1].url.params["id_token"] == TOKEN

    # segundo acesso: entra direto, sem pedir os termos de novo
    again = await client.post(URL, json={"id_token": TOKEN})
    assert again.status_code == 200


async def test_existing_email_account_logs_in_with_google(client, monkeypatch):
    tokens = await register(client, email="pessoa@gmail.com")
    original = (await client.get("/api/v1/me", headers=auth(tokens))).json()
    google_says(monkeypatch)
    r = await client.post(URL, json={"id_token": TOKEN})
    assert r.status_code == 200
    me = (await client.get("/api/v1/me", headers=auth(r.json()))).json()
    assert me["id"] == original["id"]  # mesma conta, não duplica


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": "outro-app.apps.googleusercontent.com"},
        {"iss": "https://evil.example.com"},
        {"email_verified": "false"},
        {"email": ""},
    ],
)
async def test_rejects_untrusted_tokens(client, monkeypatch, overrides):
    google_says(monkeypatch, **overrides)
    r = await client.post(URL, json={"id_token": TOKEN, "accept_terms": True})
    assert r.status_code == 401


async def test_invalid_token_and_google_down(client, monkeypatch):
    google_says(monkeypatch, status=400)
    assert (await client.post(URL, json={"id_token": TOKEN})).status_code == 401
    google_says(monkeypatch, status=503)
    assert (await client.post(URL, json={"id_token": TOKEN})).status_code == 503


async def test_not_configured(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_client_id", "")
    assert (await client.post(URL, json={"id_token": TOKEN})).status_code == 501
