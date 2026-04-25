"""Tests for POST /api/portfolio/screenshot endpoint."""

import pytest
import sys
import os
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from backend.api.routers.portfolio import get_current_user, get_conn as portfolio_get_conn
import backend.api.routers.portfolio as portfolio_module


def make_test_db(path: str):
    """Init a test DB with schema."""
    conn = sqlite3.connect(path)
    conn.executescript("""
        PRAGMA journal_mode=WAL;
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS tickers (
            symbol TEXT PRIMARY KEY, name TEXT, sector TEXT,
            last_ohlc_fetch TEXT, last_news_fetch TEXT
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL, name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS portfolio_holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id INTEGER NOT NULL, stock_code TEXT NOT NULL,
            added_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            source TEXT NOT NULL DEFAULT 'manual',
            FOREIGN KEY (portfolio_id) REFERENCES portfolios(id) ON DELETE CASCADE,
            UNIQUE(portfolio_id, stock_code)
        );
        INSERT INTO users (id, email, password_hash, created_at) VALUES (1, 'test@example.com', '$2b$12$dummy', datetime('now'));
        INSERT INTO portfolios (id, user_id, name, created_at) VALUES (1, 1, '我的持仓', datetime('now'));
        INSERT INTO tickers (symbol, name) VALUES ('600519', '贵州茅台');
    """)
    conn.commit()
    conn.close()


@pytest.fixture
def temp_portfolio_db():
    """Create a temp DB with portfolio schema and test user."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    make_test_db(path)
    yield path
    os.unlink(path)


@pytest.fixture
def client(temp_portfolio_db):
    """Create FastAPI test client with overridden DB. Used by test_no_auth_returns_401."""
    from backend.api.main import app
    from backend.api.routers.portfolio import get_current_user

    def _override_get_conn():
        conn = sqlite3.connect(temp_portfolio_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    try:
        with patch("backend.api.main.init_db"):
            with patch.object(portfolio_module, "get_conn", side_effect=_override_get_conn):
                with TestClient(app) as c:
                    yield c
    finally:
        app.dependency_overrides.clear()


def make_authenticated_client(temp_portfolio_db, user_override=None):
    """Create a TestClient with auth mock and custom DB."""
    from backend.api.main import app
    from backend.database import get_conn

    def _override_get_conn():
        conn = sqlite3.connect(temp_portfolio_db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    app.dependency_overrides[get_conn] = _override_get_conn
    user = user_override or {"id": 1, "email": "test@example.com"}
    app.dependency_overrides[__import__("backend.api.routers.portfolio", fromlist=["get_current_user"]).get_current_user] = lambda: user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


class TestBatchImport:
    """Tests for POST /api/portfolio/import."""

    def test_no_auth_returns_401(self, client):
        """No token returns 401."""
        r = client.post("/api/portfolio/import", json={"stock_codes": ["600519"]})
        assert r.status_code == 401

    def test_empty_stock_codes_returns_400(self, temp_portfolio_db):
        """Empty array returns 400."""
        from backend.api.main import app
        from backend.api.routers.auth import create_access_token

        def _override_get_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_override_get_conn):
                    with TestClient(app) as c:
                        r = c.post(
                            "/api/portfolio/import",
                            json={"stock_codes": []},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        assert r.status_code == 400
                        assert "至少选择一个股票" in r.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_valid_codes_return_200(self, temp_portfolio_db):
        """Valid stock codes return 200 with imported count."""
        from backend.api.main import app
        from backend.api.routers.auth import create_access_token

        def _make_test_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_make_test_conn):
                    with TestClient(app) as c:
                        r = c.post(
                            "/api/portfolio/import",
                            json={"stock_codes": ["600519"]},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        assert r.status_code == 200
                        data = r.json()
                        assert data["imported"] == 1
                        assert data["skipped"] == 0
                        assert data["not_found"] == []
        finally:
            app.dependency_overrides.clear()

    def test_duplicate_codes_are_skipped(self, temp_portfolio_db):
        """Duplicate codes are skipped via INSERT OR IGNORE."""
        # Pre-insert a different holding (not in the import list)
        conn = sqlite3.connect(temp_portfolio_db)
        conn.execute("INSERT OR IGNORE INTO portfolio_holdings (portfolio_id, stock_code) VALUES (1, '000001')")
        conn.commit()
        conn.close()

        from backend.api.main import app
        from backend.api.routers.auth import create_access_token

        def _make_test_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_make_test_conn):
                    with TestClient(app) as c:
                        # Import 600519 twice - first should succeed, second skipped
                        r = c.post(
                            "/api/portfolio/import",
                            json={"stock_codes": ["600519", "600519"]},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        assert r.status_code == 200
                        data = r.json()
                        # First 600519 is inserted, second is skipped (duplicate input)
                        assert data["imported"] == 1
                        assert data["skipped"] == 1
                        assert data["not_found"] == []
        finally:
            app.dependency_overrides.clear()

    def test_portfolio_full_returns_400(self, temp_portfolio_db):
        """Portfolio at limit returns 400."""
        # Fill portfolio to limit
        conn = sqlite3.connect(temp_portfolio_db)
        for i in range(10):
            conn.execute(
                "INSERT OR IGNORE INTO portfolio_holdings (portfolio_id, stock_code) VALUES (1, ?)",
                (f"60000{i}",),
            )
        conn.commit()
        conn.close()

        from backend.api.main import app
        from backend.api.routers.auth import create_access_token

        def _make_test_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_make_test_conn):
                    with TestClient(app) as c:
                        r = c.post(
                            "/api/portfolio/import",
                            json={"stock_codes": ["600519"]},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        assert r.status_code == 400
                        assert "已满" in r.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_invalid_codes_tracked_in_not_found(self, temp_portfolio_db):
        """Invalid stock codes returned in not_found array."""
        from backend.api.main import app
        from backend.api.routers.auth import create_access_token

        def _make_test_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_make_test_conn):
                    with TestClient(app) as c:
                        r = c.post(
                            "/api/portfolio/import",
                            json={"stock_codes": ["600519", "999999"]},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        assert r.status_code == 200
                        data = r.json()
                        assert data["imported"] == 1
                        assert "999999" in data["not_found"]
        finally:
            app.dependency_overrides.clear()


class TestScreenshotEndpoint:
    """Tests for POST /api/portfolio/screenshot."""

    def test_no_auth_returns_401(self, client):
        """No token returns 401."""
        r = client.post("/api/portfolio/screenshot", files={"file": ("x.jpg", b"fake", "image/jpeg")})
        assert r.status_code == 401

    def test_non_image_file_returns_422(self, temp_portfolio_db):
        """Uploading .txt file returns 422."""
        from backend.api.main import app
        from backend.api.routers.auth import create_access_token
        from backend.api.routers.portfolio import get_current_user

        def _override_get_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_override_get_conn):
                    with TestClient(app) as c:
                        r = c.post(
                            "/api/portfolio/screenshot",
                            files={"file": ("x.txt", b"not an image", "text/plain")},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        assert r.status_code == 422
                        assert "仅支持" in r.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_file_too_large_returns_413(self, temp_portfolio_db):
        """File >10MB returns 413."""
        from backend.api.main import app
        from backend.api.routers.auth import create_access_token
        from backend.api.routers.portfolio import get_current_user

        def _override_get_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_override_get_conn):
                    with TestClient(app) as c:
                        large_content = b"\x00" * (10 * 1024 * 1024 + 1)
                        r = c.post(
                            "/api/portfolio/screenshot",
                            files={"file": ("x.jpg", large_content, "image/jpeg")},
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        assert r.status_code == 413
        finally:
            app.dependency_overrides.clear()

    def test_happy_path_returns_200(self, temp_portfolio_db):
        """Mock MiniMax VL returns 200 with holdings."""
        from backend.api.main import app
        from backend.api.routers.auth import create_access_token
        from backend.api.routers.portfolio import get_current_user

        def _make_test_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_make_test_conn):
                    with patch.object(portfolio_module, "MiniMaxTools") as MockMT:
                        instance = MagicMock()
                        instance.parse_screenshot.return_value = [
                            {"stock_code": "600519", "stock_name": "贵州茅台", "quantity": None, "source": "雪球", "confidence": 0.95, "in_database": True},
                            {"stock_code": "300750", "stock_name": "宁德时代", "quantity": 50, "source": "同花顺", "confidence": 0.9, "in_database": True},
                        ]
                        MockMT.return_value = instance
                        with TestClient(app) as c:
                            r = c.post(
                                "/api/portfolio/screenshot",
                                files={"file": ("x.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
                            data = r.json()
                            assert len(data["holdings"]) == 2
                            assert data["message"] == "识别成功"
                            assert "portfolio_id" in data
        finally:
            app.dependency_overrides.clear()

    def test_empty_result_returns_empty_holdings(self, temp_portfolio_db):
        """MiniMax returns [] → empty holdings + message."""
        from backend.api.main import app
        from backend.api.routers.auth import create_access_token
        from backend.api.routers.portfolio import get_current_user

        def _make_test_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_make_test_conn):
                    with patch.object(portfolio_module, "MiniMaxTools") as MockMT:
                        instance = MagicMock()
                        instance.parse_screenshot.return_value = []
                        MockMT.return_value = instance
                        with TestClient(app) as c:
                            r = c.post(
                                "/api/portfolio/screenshot",
                                files={"file": ("x.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            assert r.status_code == 200
                            data = r.json()
                            assert data["holdings"] == []
                            assert "未能识别" in data["message"]
        finally:
            app.dependency_overrides.clear()

    def test_insert_or_ignore_duplicate(self, temp_portfolio_db):
        """Duplicate stock in portfolio is skipped."""
        conn = sqlite3.connect(temp_portfolio_db)
        conn.execute("INSERT OR IGNORE INTO portfolio_holdings (portfolio_id, stock_code) VALUES (1, '600519')")
        conn.commit()
        conn.close()

        from backend.api.main import app
        from backend.api.routers.auth import create_access_token
        from backend.api.routers.portfolio import get_current_user

        def _make_test_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_make_test_conn):
                    with patch.object(portfolio_module, "MiniMaxTools") as MockMT:
                        instance = MagicMock()
                        instance.parse_screenshot.return_value = [
                            {"stock_code": "600519", "stock_name": "贵州茅台", "quantity": None, "source": "雪球", "confidence": 0.95, "in_database": True},
                        ]
                        MockMT.return_value = instance
                        with TestClient(app) as c:
                            r = c.post(
                                "/api/portfolio/screenshot",
                                files={"file": ("x.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            assert r.status_code == 200
                            conn2 = sqlite3.connect(temp_portfolio_db)
                            conn2.row_factory = sqlite3.Row
                            count = conn2.execute("SELECT COUNT(*) FROM portfolio_holdings WHERE stock_code='600519' AND portfolio_id=1").fetchone()[0]
                            conn2.close()
                            assert count == 1
        finally:
            app.dependency_overrides.clear()

    def test_no_portfolio_creates_default(self, temp_portfolio_db):
        """User with no portfolios → creates '我的持仓'."""
        conn = sqlite3.connect(temp_portfolio_db)
        conn.execute("DELETE FROM portfolio_holdings")
        conn.execute("DELETE FROM portfolios")
        conn.commit()
        conn.close()

        from backend.api.main import app
        from backend.api.routers.auth import create_access_token
        from backend.api.routers.portfolio import get_current_user

        def _make_test_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_make_test_conn):
                    with patch.object(portfolio_module, "MiniMaxTools") as MockMT:
                        instance = MagicMock()
                        instance.parse_screenshot.return_value = [
                            {"stock_code": "600519", "stock_name": "贵州茅台", "quantity": None, "source": "雪球", "confidence": 0.95, "in_database": True},
                        ]
                        MockMT.return_value = instance
                        with TestClient(app) as c:
                            r = c.post(
                                "/api/portfolio/screenshot",
                                files={"file": ("x.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
                            conn2 = sqlite3.connect(temp_portfolio_db)
                            conn2.row_factory = sqlite3.Row
                            exists = conn2.execute("SELECT 1 FROM portfolios WHERE user_id=1 AND name='我的持仓'").fetchone()
                            conn2.close()
                            assert exists is not None
        finally:
            app.dependency_overrides.clear()

    def test_source_field_is_screenshot(self, temp_portfolio_db):
        """Inserted holdings have source='screenshot'."""
        from backend.api.main import app
        from backend.api.routers.auth import create_access_token
        from backend.api.routers.portfolio import get_current_user

        def _make_test_conn():
            conn = sqlite3.connect(temp_portfolio_db)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn

        try:
            app.dependency_overrides[get_current_user] = lambda: {"id": 1, "email": "test@example.com"}
            token = create_access_token(user_id=1, email="test@example.com")
            with patch("backend.api.main.init_db"):
                with patch.object(portfolio_module, "get_conn", side_effect=_make_test_conn):
                    with patch.object(portfolio_module, "MiniMaxTools") as MockMT:
                        instance = MagicMock()
                        instance.parse_screenshot.return_value = [
                            {"stock_code": "600519", "stock_name": "贵州茅台", "quantity": None, "source": "雪球", "confidence": 0.95, "in_database": True},
                        ]
                        MockMT.return_value = instance
                        with TestClient(app) as c:
                            r = c.post(
                                "/api/portfolio/screenshot",
                                files={"file": ("x.jpg", b"\xff\xd8\xff\xe0fake", "image/jpeg")},
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            assert r.status_code == 200, f"Got {r.status_code}: {r.text}"
                            conn2 = sqlite3.connect(temp_portfolio_db)
                            conn2.row_factory = sqlite3.Row
                            source = conn2.execute("SELECT source FROM portfolio_holdings WHERE stock_code='600519'").fetchone()
                            conn2.close()
                            assert source["source"] == "screenshot"
        finally:
            app.dependency_overrides.clear()
