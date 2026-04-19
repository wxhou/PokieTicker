"""Tests for AKShare client SQLite TTL cache behavior (ohlc_cache, news_cache)."""

import pytest
import json
import time
import sqlite3
import tempfile
import sys
import os
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for cache testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ohlc_cache (
            key_col    TEXT PRIMARY KEY,
            data_json  TEXT,
            fetched_at TEXT
        );
        CREATE TABLE IF NOT EXISTS news_cache (
            key_col    TEXT PRIMARY KEY,
            data_json  TEXT,
            fetched_at TEXT
        );
        CREATE TABLE IF NOT EXISTS limit_cache (
            key_col    TEXT PRIMARY KEY,
            data_json  TEXT,
            fetched_at TEXT
        );
    """)
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


def _temp_conn(temp_path: str) -> sqlite3.Connection:
    """Create a connection to temp_path with Row factory set."""
    conn = sqlite3.connect(temp_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


class TestAkShareCache:
    """Test _cache_get and _cache_set TTL behavior."""

    def test_cache_get_returns_fresh_data(self, temp_db):
        """_cache_get returns data when within TTL."""
        from backend.akshare import client as akshare_client

        with patch.object(akshare_client.settings, "database_path", temp_db), \
             patch.object(akshare_client, "_cache_conn", lambda: _temp_conn(temp_db)):
            now = datetime.now().isoformat()
            conn = _temp_conn(temp_db)
            conn.execute(
                "INSERT OR REPLACE INTO ohlc_cache (key_col, data_json, fetched_at) VALUES (?, ?, ?)",
                ("600519.SH,20260401,20260418", json.dumps([{"close": 1850.0}]), now),
            )
            conn.commit()
            conn.close()

            result = akshare_client._cache_get("ohlc", "600519.SH,20260401,20260418")
            assert result == [{"close": 1850.0}]

    def test_cache_get_returns_none_when_expired(self, temp_db):
        """_cache_get returns None when TTL has passed."""
        from backend.akshare import client as akshare_client

        with patch.object(akshare_client.settings, "database_path", temp_db), \
             patch.object(akshare_client, "_cache_conn", lambda: _temp_conn(temp_db)):
            old_time = (datetime.now() - timedelta(days=2)).isoformat()
            conn = _temp_conn(temp_db)
            conn.execute(
                "INSERT OR REPLACE INTO ohlc_cache (key_col, data_json, fetched_at) VALUES (?, ?, ?)",
                ("600519.SH,20260401,20260418", json.dumps([{"close": 1850.0}]), old_time),
            )
            conn.commit()
            conn.close()

            result = akshare_client._cache_get("ohlc", "600519.SH,20260401,20260418")
            assert result is None

    def test_cache_get_returns_none_when_missing(self, temp_db):
        """_cache_get returns None when key does not exist."""
        from backend.akshare import client as akshare_client

        with patch.object(akshare_client.settings, "database_path", temp_db), \
             patch.object(akshare_client, "_cache_conn", lambda: _temp_conn(temp_db)):
            result = akshare_client._cache_get("ohlc", "nonexistent.key")
            assert result is None

    def test_cache_set_stores_data(self, temp_db):
        """_cache_set stores data with correct fetched_at timestamp."""
        from backend.akshare import client as akshare_client

        with patch.object(akshare_client.settings, "database_path", temp_db), \
             patch.object(akshare_client, "_cache_conn", lambda: _temp_conn(temp_db)):
            test_data = [{"symbol": "000001", "close": 12.5}]
            akshare_client._cache_set("news", "000001,recent", test_data)

            conn = _temp_conn(temp_db)
            row = conn.execute(
                "SELECT data_json, fetched_at FROM news_cache WHERE key_col = ?",
                ("000001,recent",),
            ).fetchone()
            conn.close()

            assert row is not None
            assert json.loads(row["data_json"]) == test_data
            datetime.fromisoformat(row["fetched_at"])

    def test_cache_set_replaces_existing(self, temp_db):
        """_cache_set replaces existing entry for the same key."""
        from backend.akshare import client as akshare_client

        with patch.object(akshare_client.settings, "database_path", temp_db), \
             patch.object(akshare_client, "_cache_conn", lambda: _temp_conn(temp_db)):
            akshare_client._cache_set("ohlc", "testkey", [{"v": 1}])
            akshare_client._cache_set("ohlc", "testkey", [{"v": 2}])

            conn = _temp_conn(temp_db)
            row = conn.execute(
                "SELECT data_json FROM ohlc_cache WHERE key_col = ?",
                ("testkey",),
            ).fetchone()
            conn.close()

            assert json.loads(row["data_json"]) == [{"v": 2}]

    def test_news_cache_ttl_10_minutes(self, temp_db):
        """news_cache has 10-minute TTL (600 seconds)."""
        from backend.akshare import client as akshare_client

        with patch.object(akshare_client.settings, "database_path", temp_db), \
             patch.object(akshare_client, "_cache_conn", lambda: _temp_conn(temp_db)):
            old_time = (datetime.now() - timedelta(minutes=15)).isoformat()
            conn = _temp_conn(temp_db)
            conn.execute(
                "INSERT OR REPLACE INTO news_cache (key_col, data_json, fetched_at) VALUES (?, ?, ?)",
                ("600519,20260418", json.dumps([{"title": "test"}]), old_time),
            )
            conn.commit()
            conn.close()

            result = akshare_client._cache_get("news", "600519,20260418")
            assert result is None

    def test_ohlc_cache_ttl_1_day(self, temp_db):
        """ohlc_cache has 1-day TTL (86400 seconds)."""
        from backend.akshare import client as akshare_client

        with patch.object(akshare_client.settings, "database_path", temp_db), \
             patch.object(akshare_client, "_cache_conn", lambda: _temp_conn(temp_db)):
            old_time = (datetime.now() - timedelta(hours=25)).isoformat()
            conn = _temp_conn(temp_db)
            conn.execute(
                "INSERT OR REPLACE INTO ohlc_cache (key_col, data_json, fetched_at) VALUES (?, ?, ?)",
                ("600519.SH,20260401,20260418", json.dumps([{"close": 1850.0}]), old_time),
            )
            conn.commit()
            conn.close()

            result = akshare_client._cache_get("ohlc", "600519.SH,20260401,20260418")
            assert result is None

    def test_cache_close_handles_connection(self, temp_db):
        """_cache_get/_cache_set properly close connections (no leakage)."""
        from backend.akshare import client as akshare_client

        with patch.object(akshare_client.settings, "database_path", temp_db), \
             patch.object(akshare_client, "_cache_conn", lambda: _temp_conn(temp_db)):
            akshare_client._cache_set("news", "leak_test", [{"data": "x"}])

            results = []
            for _ in range(5):
                results.append(akshare_client._cache_get("news", "leak_test"))

            assert all(r == [{"data": "x"}] for r in results)
