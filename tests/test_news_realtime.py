"""Tests for GET /api/news/{symbol}/realtime endpoint."""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient


class TestRealtimeNewsEndpoint:
    """Tests for GET /api/news/{symbol}/realtime."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset module-level imports to avoid state pollution."""
        # Force reload to reset router state
        import importlib
        import backend.api.routers.news as news_module
        importlib.reload(news_module)

    def _make_mock_conn(self, news_sources_row=None, stock_row=None):
        """Create a mock DB connection."""
        mock_conn = MagicMock()

        # news_sources table
        news_sources_data = []
        if news_sources_row is not None:
            news_sources_data.append(news_sources_row)

        # stocks table
        stock_data = []
        if stock_row is not None:
            stock_data.append(stock_row)

        mock_conn.execute.side_effect = lambda q, *a, **kw: (
            MagicMock(fetchone=lambda: news_sources_row, fetchall=lambda: news_sources_data)
            if "news_sources" in q
            else (
                MagicMock(fetchone=lambda: stock_row, fetchall=lambda: stock_data)
                if "tickers" in q
                else MagicMock(fetchall=lambda: [], fetchone=lambda: None)
            )
        )
        return mock_conn

    def test_realtime_returns_structured_response(self):
        """API returns {supplemented, cached, count} structure."""
        from backend.api.main import app
        client = TestClient(app)

        with patch("backend.ai.minimax_tools.get_conn") as mock_get_conn:
            mock_get_conn.return_value = self._make_mock_conn(
                news_sources_row=None, stock_row=("贵州茅台",)
            )
            with patch("backend.ai.minimax_tools.httpx.Client") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": "[]"}}]
                }
                mock_resp.raise_for_status = MagicMock()
                mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

                resp = client.get("/api/news/600519/realtime")

        assert resp.status_code == 200
        data = resp.json()
        assert "supplemented" in data
        assert "cached" in data
        assert "count" in data

    def test_realtime_error_returns_graceful_response(self):
        """MiniMax API error returns {supplemented: [], error, count: 0}."""
        from backend.api.main import app
        client = TestClient(app)

        with patch("backend.ai.minimax_tools.get_conn") as mock_get_conn:
            mock_get_conn.return_value = self._make_mock_conn(
                news_sources_row=None, stock_row=("贵州茅台",)
            )
            with patch("backend.ai.minimax_tools.httpx.Client") as mock_client_cls:
                mock_client_cls.return_value.__enter__.return_value.post.side_effect = (
                    Exception("API unavailable")
                )

                resp = client.get("/api/news/600519/realtime")

        assert resp.status_code == 200
        data = resp.json()
        assert data["supplemented"] == []
        assert data["count"] == 0
        assert "error" in data

    def test_realtime_stock_not_found_returns_empty(self):
        """Stock not in DB returns empty supplemented list."""
        from backend.api.main import app
        client = TestClient(app)

        with patch("backend.ai.minimax_tools.get_conn") as mock_get_conn:
            mock_get_conn.return_value = self._make_mock_conn(
                news_sources_row=None, stock_row=None
            )

            resp = client.get("/api/news/999999/realtime")

        assert resp.status_code == 200
        data = resp.json()
        assert data["supplemented"] == []
        assert data["count"] == 0

    def test_realtime_days_parameter(self):
        """days query parameter is accepted."""
        from backend.api.main import app
        client = TestClient(app)

        with patch("backend.ai.minimax_tools.get_conn") as mock_get_conn:
            mock_get_conn.return_value = self._make_mock_conn(
                news_sources_row=None, stock_row=("贵州茅台",)
            )
            with patch("backend.ai.minimax_tools.httpx.Client") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "choices": [{"message": {"content": "[]"}}]
                }
                mock_resp.raise_for_status = MagicMock()
                mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

                resp = client.get("/api/news/600519/realtime?days=14")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0

    def test_realtime_days_out_of_range(self):
        """days outside 1-30 range returns 422."""
        from backend.api.main import app
        client = TestClient(app)

        resp = client.get("/api/news/600519/realtime?days=100")
        assert resp.status_code == 422

    def test_realtime_response_contains_news_fields(self):
        """Successful response contains title, snippet, date, url in each item."""
        from backend.api.main import app
        client = TestClient(app)

        with patch("backend.ai.minimax_tools.get_conn") as mock_get_conn:
            mock_get_conn.return_value = self._make_mock_conn(
                news_sources_row=None, stock_row=("贵州茅台",)
            )
            with patch("backend.ai.minimax_tools.httpx.Client") as mock_client_cls:
                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "choices": [
                        {
                            "message": {
                                "content": '[{"title":"茅台业绩","snippet":"营收增长","date":"2026-04-20","url":"https://x.cn/1"}]'
                            }
                        }
                    ]
                }
                mock_resp.raise_for_status = MagicMock()
                mock_client_cls.return_value.__enter__.return_value.post.return_value = mock_resp

                resp = client.get("/api/news/600519/realtime")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["supplemented"]) == 1
        item = data["supplemented"][0]
        assert "title" in item
        assert "snippet" in item
        assert "date" in item
        assert "url" in item
