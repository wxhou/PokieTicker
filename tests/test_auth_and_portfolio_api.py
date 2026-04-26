"""Tests for auth register/login API and portfolio CRUD API."""

import sys
import os
import sqlite3
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient


def _tmp_db(tmp_path):
    """Create a temp DB with required schema for auth+portfolio tests."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS portfolios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS portfolio_holdings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        portfolio_id INTEGER NOT NULL,
        stock_code TEXT NOT NULL,
        added_at TEXT NOT NULL DEFAULT (datetime('now')),
        source TEXT DEFAULT 'manual',
        FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS tickers (
        symbol TEXT PRIMARY KEY,
        name TEXT
    )""")
    conn.commit()
    conn.close()
    return db_path


# ── Auth tests ──

def test_register_success(tmp_path):
    """Register a new user returns 201 with user data."""
    db_path = _tmp_db(tmp_path)
    from backend.api.main import app

    with patch("backend.database.settings") as mock_settings:
        mock_settings.database_path = db_path
        with patch("backend.api.routers.auth.settings"):
            client = TestClient(app)
            resp = client.post("/api/auth/register", json={
                "email": "test@example.com",
                "password": "Password1!",
            })

    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "test@example.com"
    assert "id" in data


def test_register_duplicate_email(tmp_path):
    """Registering an existing email returns 409."""
    db_path = _tmp_db(tmp_path)
    from backend.api.main import app

    with patch("backend.database.settings") as mock_settings:
        mock_settings.database_path = db_path
        with patch("backend.api.routers.auth.settings"):
            client = TestClient(app)
            client.post("/api/auth/register", json={
                "email": "dup@example.com",
                "password": "Password1!",
            })
            resp = client.post("/api/auth/register", json={
                "email": "dup@example.com",
                "password": "Password2!",
            })

    assert resp.status_code == 409
    assert "已被注册" in resp.json()["detail"]


def test_login_success(tmp_path):
    """Login with correct credentials returns access_token."""
    db_path = _tmp_db(tmp_path)
    from backend.api.main import app

    with patch("backend.database.settings") as mock_settings:
        mock_settings.database_path = db_path
        with patch("backend.api.routers.auth.settings"):
            client = TestClient(app)
            client.post("/api/auth/register", json={
                "email": "login@example.com",
                "password": "Password1!",
            })
            resp = client.post("/api/auth/login", json={
                "email": "login@example.com",
                "password": "Password1!",
            })

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(tmp_path):
    """Login with wrong password returns 401."""
    db_path = _tmp_db(tmp_path)
    from backend.api.main import app

    with patch("backend.database.settings") as mock_settings:
        mock_settings.database_path = db_path
        with patch("backend.api.routers.auth.settings"):
            client = TestClient(app)
            client.post("/api/auth/register", json={
                "email": "wrong@example.com",
                "password": "Password1!",
            })
            resp = client.post("/api/auth/login", json={
                "email": "wrong@example.com",
                "password": "WrongPassword!",
            })

    assert resp.status_code == 401


# ── Portfolio tests ──

def test_portfolio_list_empty(tmp_path):
    """New user has no portfolios."""
    db_path = _tmp_db(tmp_path)
    from backend.api.main import app

    with patch("backend.database.settings") as mock_settings:
        mock_settings.database_path = db_path
        with patch("backend.api.routers.auth.settings"):
            client = TestClient(app)
            reg = client.post("/api/auth/register", json={
                "email": "port@example.com", "password": "Password1!",
            })
            token = client.post("/api/auth/login", json={
                "email": "port@example.com", "password": "Password1!",
            }).json()["access_token"]
            resp = client.get("/api/portfolio", headers={
                "Authorization": f"Bearer {token}",
            })

    assert resp.status_code == 200
    assert resp.json() == []


def test_portfolio_create_and_list(tmp_path):
    """Create a portfolio and list it back."""
    db_path = _tmp_db(tmp_path)
    from backend.api.main import app

    with patch("backend.database.settings") as mock_settings:
        mock_settings.database_path = db_path
        with patch("backend.api.routers.auth.settings"):
            client = TestClient(app)
            client.post("/api/auth/register", json={
                "email": "port2@example.com", "password": "Password1!",
            })
            token = client.post("/api/auth/login", json={
                "email": "port2@example.com", "password": "Password1!",
            }).json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Create
            resp = client.post("/api/portfolio", json={"name": "科技股"}, headers=headers)
            assert resp.status_code in (200, 201)
            created = resp.json()
            assert created["name"] == "科技股"

            # List
            resp = client.get("/api/portfolio", headers=headers)
            assert resp.status_code == 200
            portfolios = resp.json()
            assert len(portfolios) == 1
            assert portfolios[0]["name"] == "科技股"


def test_portfolio_unauthorized():
    """Accessing portfolio without token returns 401/403."""
    from backend.api.main import app
    client = TestClient(app)
    resp = client.get("/api/portfolio")
    assert resp.status_code in (401, 403)


# ── Predict API tests ──

def test_predict_no_model_returns_200():
    """Predict endpoint returns 200 with available=false when no model exists."""
    from backend.api.main import app
    client = TestClient(app)
    mock_predict = MagicMock(return_value={"error": "No trained model for AAPL"})
    mock_module = MagicMock(predict=mock_predict)
    with patch.dict("sys.modules", {"backend.ml.model": mock_module}):
        resp = client.get("/api/predict/AAPL?horizon=t1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False
    assert "error" in data


def test_forecast_no_model_returns_200():
    """Forecast endpoint returns 200 with available=false when no model exists."""
    from backend.api.main import app
    client = TestClient(app)
    mock_forecast = MagicMock(return_value={"error": "No trained model for AAPL"})
    mock_module = MagicMock(generate_forecast=mock_forecast)
    with patch.dict("sys.modules", {"backend.ml.inference": mock_module}):
        resp = client.get("/api/predict/AAPL/forecast?window=7")

    assert resp.status_code == 200
    data = resp.json()
    assert data["available"] is False