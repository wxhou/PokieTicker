"""Tests for T+1 alignment and limit_up/limit_down marking."""

import pytest
import sys
import os
import sqlite3
import tempfile
from unittest.mock import patch
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def temp_align_db():
    """Create a temp DB with ohlc, news_raw, news_ticker, news_aligned tables."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS ohlc (
            symbol TEXT NOT NULL, date TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            volume REAL, pct_chg REAL DEFAULT 0,
            PRIMARY KEY (symbol, date)
        );
        CREATE TABLE IF NOT EXISTS news_raw (
            id TEXT PRIMARY KEY, title TEXT, description TEXT,
            published_utc TEXT
        );
        CREATE TABLE IF NOT EXISTS news_ticker (
            news_id TEXT NOT NULL, symbol TEXT NOT NULL,
            PRIMARY KEY (news_id, symbol)
        );
        CREATE TABLE IF NOT EXISTS news_aligned (
            news_id TEXT NOT NULL, symbol TEXT NOT NULL,
            trade_date TEXT NOT NULL, published_utc TEXT,
            ret_t0 REAL, ret_t1 REAL, ret_t3 REAL, ret_t5 REAL, ret_t10 REAL,
            limit_up INTEGER DEFAULT 0, limit_down INTEGER DEFAULT 0,
            PRIMARY KEY (news_id, symbol)
        );
    """)
    conn.commit()
    conn.close()
    yield path
    os.unlink(path)


def make_align_conn(path: str) -> sqlite3.Connection:
    """Create a connection with Row factory like the real get_conn."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


class TestAlignmentT1:
    """Test T+1 alignment and limit_up/limit_down marking."""

    def test_to_iso_date_valid(self):
        """_to_iso_date correctly parses Z-suffixed and timezone ISO strings."""
        from backend.pipeline.alignment import _to_iso_date

        assert _to_iso_date("2026-04-18T09:30:00Z") == "2026-04-18"
        assert _to_iso_date("2026-04-18T14:30:00+08:00") == "2026-04-18"
        assert _to_iso_date("2026-04-18") == "2026-04-18"
        assert _to_iso_date(None) is None
        assert _to_iso_date("") is None
        assert _to_iso_date("invalid") is None

    def test_shift_to_trade_day(self):
        """_shift_to_trade_day finds the next trading day within 7 days."""
        from backend.pipeline.alignment import _shift_to_trade_day

        # Trading days: 04-15 (Wed), 04-16 (Thu), 04-17 (Fri)
        idx = {
            "2026-04-15": 0,
            "2026-04-16": 1,
            "2026-04-17": 2,
        }

        # Same day is a trading day
        assert _shift_to_trade_day("2026-04-15", idx) == "2026-04-15"
        # Saturday -> next Wednesday (search forward up to 7 days)
        # 04-18(Sat) -> 04-19(Sun) -> 04-20(Mon) -> 04-21(Tue) -> 04-22(Wed)
        # Actually only 15, 16, 17 are in idx, so 04-18 -> 04-19 -> 04-20 -> 04-21 -> 04-22 -> NOT FOUND
        # The function searches for up to 7 days forward
        # 04-18 +1=04-19, +2=04-20, +3=04-21, +4=04-22, +5=04-23, +6=04-24, +7=04-25, NOT FOUND -> None
        assert _shift_to_trade_day("2026-04-18", idx) is None  # Not in idx, not found within 7 days
        # Monday -> if Mon not in idx, searches forward
        # Let's verify the function searches forward (not backward)
        result = _shift_to_trade_day("2026-04-14", idx)
        assert result == "2026-04-15"  # Tue -> Wed

    def test_pct_calculation(self):
        """_pct correctly computes percentage return."""
        from backend.pipeline.alignment import _pct

        assert _pct(100.0, 105.0) == pytest.approx(0.05)
        assert _pct(100.0, 95.0) == pytest.approx(-0.05)
        assert _pct(50.0, 100.0) == pytest.approx(1.0)
        assert _pct(None, 100.0) is None
        assert _pct(100.0, None) is None
        assert _pct(0.0, 100.0) is None

    def test_align_news_shifts_to_trade_day(self, temp_align_db):
        """align_news_for_symbol shifts published_utc to nearest trading day."""
        from backend.pipeline.alignment import align_news_for_symbol

        conn = make_align_conn(temp_align_db)
        conn.execute("INSERT INTO news_raw (id, published_utc) VALUES (?, ?)",
                     ("n1", "2026-04-17T10:00:00Z"))  # Friday - trading day
        conn.execute("INSERT INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                     ("n1", "600519"))
        conn.execute("INSERT INTO ohlc (symbol, date, close, pct_chg) VALUES (?, ?, ?, ?)",
                     ("600519", "2026-04-17", 1850.0, 2.5))
        conn.commit()
        conn.close()

        with patch("backend.pipeline.alignment.get_conn") as mock_get_conn:
            mock_get_conn.return_value = make_align_conn(temp_align_db)

            result = align_news_for_symbol("600519")

        assert result["aligned"] == 1
        assert result["total_news"] == 1

    def test_limit_up_threshold(self, temp_align_db):
        """limit_up=1 when pct_chg >= 9.5%."""
        from backend.pipeline.alignment import align_news_for_symbol

        conn = make_align_conn(temp_align_db)
        conn.execute("INSERT INTO news_raw (id, published_utc) VALUES (?, ?)",
                     ("n_limitup", "2026-04-17T09:00:00Z"))
        conn.execute("INSERT INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                     ("n_limitup", "600519"))
        conn.execute("INSERT INTO ohlc (symbol, date, close, pct_chg) VALUES (?, ?, ?, ?)",
                     ("600519", "2026-04-17", 1850.0, 10.0))
        conn.commit()
        conn.close()

        with patch("backend.pipeline.alignment.get_conn") as mock_get_conn:
            mock_get_conn.return_value = make_align_conn(temp_align_db)

            align_news_for_symbol("600519")

        conn = make_align_conn(temp_align_db)
        row = conn.execute(
            "SELECT limit_up, limit_down FROM news_aligned WHERE news_id = ?",
            ("n_limitup",),
        ).fetchone()
        conn.close()
        assert row["limit_up"] == 1
        assert row["limit_down"] == 0

    def test_limit_down_threshold(self, temp_align_db):
        """limit_down=1 when pct_chg <= -9.5%."""
        from backend.pipeline.alignment import align_news_for_symbol

        conn = make_align_conn(temp_align_db)
        conn.execute("INSERT INTO news_raw (id, published_utc) VALUES (?, ?)",
                     ("n_limitdown", "2026-04-17T09:00:00Z"))
        conn.execute("INSERT INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                     ("n_limitdown", "000001"))
        conn.execute("INSERT INTO ohlc (symbol, date, close, pct_chg) VALUES (?, ?, ?, ?)",
                     ("000001", "2026-04-17", 12.5, -10.2))
        conn.commit()
        conn.close()

        with patch("backend.pipeline.alignment.get_conn") as mock_get_conn:
            mock_get_conn.return_value = make_align_conn(temp_align_db)

            align_news_for_symbol("000001")

        conn = make_align_conn(temp_align_db)
        row = conn.execute(
            "SELECT limit_up, limit_down FROM news_aligned WHERE news_id = ?",
            ("n_limitdown",),
        ).fetchone()
        conn.close()
        assert row["limit_up"] == 0
        assert row["limit_down"] == 1

    def test_limit_boundary_9_5_percent(self, temp_align_db):
        """At exactly 9.5% pct_chg, limit_up=1."""
        from backend.pipeline.alignment import align_news_for_symbol

        conn = make_align_conn(temp_align_db)
        conn.execute("INSERT INTO news_raw (id, published_utc) VALUES (?, ?)",
                     ("n_boundary", "2026-04-17T09:00:00Z"))
        conn.execute("INSERT INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                     ("n_boundary", "600519"))
        # Exactly 9.5% -> limit up
        conn.execute("INSERT INTO ohlc (symbol, date, close, pct_chg) VALUES (?, ?, ?, ?)",
                     ("600519", "2026-04-17", 1850.0, 9.5))
        conn.commit()
        conn.close()

        with patch("backend.pipeline.alignment.get_conn") as mock_get_conn:
            mock_get_conn.return_value = make_align_conn(temp_align_db)

            align_news_for_symbol("600519")

        conn = make_align_conn(temp_align_db)
        row = conn.execute(
            "SELECT limit_up FROM news_aligned WHERE news_id = ?",
            ("n_boundary",),
        ).fetchone()
        conn.close()
        assert row["limit_up"] == 1

    def test_no_ohlc_data_returns_error(self, temp_align_db):
        """align_news_for_symbol returns error when no OHLC data exists."""
        from backend.pipeline.alignment import align_news_for_symbol

        with patch("backend.pipeline.alignment.get_conn") as mock_get_conn:
            mock_get_conn.return_value = make_align_conn(temp_align_db)

            result = align_news_for_symbol("NONEXIST")

        assert "error" in result
        assert result["aligned"] == 0

    def test_t_plus_returns_calculation(self, temp_align_db):
        """T+1/T+3 return is computed from trade_date to subsequent trading days."""
        from backend.pipeline.alignment import align_news_for_symbol

        conn = make_align_conn(temp_align_db)
        conn.execute("INSERT INTO news_raw (id, published_utc) VALUES (?, ?)",
                     ("n_t1", "2026-04-15T10:00:00Z"))
        conn.execute("INSERT INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                     ("n_t1", "600519"))
        # 3 consecutive trading days
        conn.execute("INSERT INTO ohlc (symbol, date, close, pct_chg) VALUES (?, ?, ?, ?)",
                     ("600519", "2026-04-15", 100.0, 1.0))
        conn.execute("INSERT INTO ohlc (symbol, date, close, pct_chg) VALUES (?, ?, ?, ?)",
                     ("600519", "2026-04-16", 102.0, 2.0))
        conn.execute("INSERT INTO ohlc (symbol, date, close, pct_chg) VALUES (?, ?, ?, ?)",
                     ("600519", "2026-04-17", 105.0, 3.0))
        conn.commit()
        conn.close()

        with patch("backend.pipeline.alignment.get_conn") as mock_get_conn:
            mock_get_conn.return_value = make_align_conn(temp_align_db)

            align_news_for_symbol("600519")

        conn = make_align_conn(temp_align_db)
        row = conn.execute(
            "SELECT ret_t0, ret_t1, ret_t3, ret_t5, ret_t10 FROM news_aligned WHERE news_id = ?",
            ("n_t1",),
        ).fetchone()
        conn.close()

        # ret_t0: previous day close → current day close. prev is None for first day → None
        assert row["ret_t0"] is None
        # ret_t1: close(04-16) / close(04-15) - 1 = (102 - 100) / 100 = 0.02
        assert row["ret_t1"] == pytest.approx(0.02)
        # ret_t3: j=0+3=3, len(dates)=3 → out of bounds → None
        assert row["ret_t3"] is None

    def test_already_aligned_not_duplicated(self, temp_align_db):
        """News already aligned is not re-aligned (INSERT OR IGNORE)."""
        from backend.pipeline.alignment import align_news_for_symbol

        conn = make_align_conn(temp_align_db)
        # News with Saturday timestamp
        conn.execute("INSERT INTO news_raw (id, published_utc) VALUES (?, ?)",
                     ("n_dup", "2026-04-18T10:00:00Z"))
        conn.execute("INSERT INTO news_ticker (news_id, symbol) VALUES (?, ?)",
                     ("n_dup", "600519"))
        conn.execute("INSERT INTO ohlc (symbol, date, close, pct_chg) VALUES (?, ?, ?, ?)",
                     ("600519", "2026-04-17", 100.0, 1.0))
        # Pre-insert into news_aligned (already aligned for same news)
        conn.execute("INSERT INTO news_aligned (news_id, symbol, trade_date, published_utc) VALUES (?, ?, ?, ?)",
                     ("n_dup", "600519", "2026-04-17", "2026-04-18T10:00:00Z"))
        conn.commit()
        conn.close()

        with patch("backend.pipeline.alignment.get_conn") as mock_get_conn:
            mock_get_conn.return_value = make_align_conn(temp_align_db)

            result = align_news_for_symbol("600519")

        # aligned=0 because n_dup was already in news_aligned (excluded from query)
        assert result["aligned"] == 0
