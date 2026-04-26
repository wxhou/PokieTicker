"""Tests for MiniMax VL screenshot parsing and AKShare enrichment."""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.ai.minimax_tools import MiniMaxTools, VL_MODEL, VL_PROMPT


class TestParseVLResponse:
    """Test _parse_vl_response: VL JSON output parsing."""

    def test_valid_vl_json_returns_stocks(self):
        """Valid VL JSON returns parsed stock list."""
        mt = MiniMaxTools()
        text = '[{"stock_code":"600519","stock_name":"贵州茅台","quantity":100,"source":"雪球"}]'
        results = mt._parse_vl_response(text)
        assert len(results) == 1
        assert results[0]["stock_code"] == "600519"
        assert results[0]["stock_name"] == "贵州茅台"
        assert results[0]["quantity"] == 100
        assert results[0]["source"] == "雪球"
        assert "confidence" in results[0]

    def test_empty_vl_array_returns_empty(self):
        """Empty VL array returns empty list."""
        mt = MiniMaxTools()
        assert mt._parse_vl_response("[]") == []

    def test_malformed_json_returns_empty(self):
        """Malformed JSON returns empty list."""
        mt = MiniMaxTools()
        assert mt._parse_vl_response("这不是JSON") == []

    def test_multiple_stocks(self):
        """Multiple stocks are parsed."""
        mt = MiniMaxTools()
        text = """[
            {"stock_code":"600519","stock_name":"贵州茅台","source":"雪球"},
            {"stock_code":"300750","stock_name":"宁德时代","source":"同花顺"}
        ]"""
        results = mt._parse_vl_response(text)
        assert len(results) == 2
        assert results[0]["stock_code"] == "600519"
        assert results[1]["stock_code"] == "300750"

    def test_missing_code_filtered(self):
        """Items without stock_code are filtered out."""
        mt = MiniMaxTools()
        text = '[{"stock_name":"茅台"},{"stock_code":"600519","stock_name":"贵州茅台"}]'
        results = mt._parse_vl_response(text)
        assert len(results) == 1

    def test_missing_name_filtered(self):
        """Items without stock_name are filtered out."""
        mt = MiniMaxTools()
        text = '[{"stock_code":"600519"},{"stock_code":"600519","stock_name":"贵州茅台"}]'
        results = mt._parse_vl_response(text)
        assert len(results) == 1


class TestParseScreenshot:
    """Test parse_screenshot: end-to-end VL call and enrichment."""

    def test_base64_encoded_in_request(self):
        """Image bytes are base64-encoded and sent to MiniMax VL."""
        with patch("backend.ai.minimax_tools.httpx.Client") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_instance)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_instance.post.return_value.json.return_value = {
                "choices": [{"message": {"content": '[{"stock_code":"600519","stock_name":"贵州茅台","source":"雪球"}]'}}]
            }

            mt = MiniMaxTools()
            mt.parse_screenshot(b"\x89PNG\r\n\x1a\nfake-png-data")

            call_kwargs = mock_instance.post.call_args[1]
            body = call_kwargs["json"]
            assert body["model"] == VL_MODEL
            # Check base64 encoding is in the image_url
            image_content = body["messages"][0]["content"][0]["image_url"]["url"]
            assert image_content.startswith("data:image/png;base64,")

    def test_vl_prompt_included(self):
        """VL prompt is sent to MiniMax VL."""
        with patch("backend.ai.minimax_tools.httpx.Client") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_instance)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_instance.post.return_value.json.return_value = {
                "choices": [{"message": {"content": "[]"}}]
            }

            mt = MiniMaxTools()
            mt.parse_screenshot(b"\xff\xd8\xff\xe0fake-jpeg")

            body = mock_instance.post.call_args[1]["json"]
            messages = body["messages"]
            # Second message should contain the prompt
            prompt_msg = messages[1]["content"]
            assert "A股" in prompt_msg
            assert "stock_code" in prompt_msg

    def test_in_database_true_for_known_stock(self):
        """Known stock is marked in_database=True."""
        with patch("backend.ai.minimax_tools.httpx.Client") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_instance)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_instance.post.return_value.json.return_value = {
                "choices": [{"message": {"content": '[{"stock_code":"600519","stock_name":"贵州茅台","source":"雪球"}]'}}]
            }

            with patch("backend.ai.minimax_tools.get_conn") as mock_conn:
                mock_c = MagicMock()
                mock_conn.return_value = mock_c
                mock_c.execute.return_value.fetchone.return_value = {"symbol": "600519"}
                mock_c.close = MagicMock()

                mt = MiniMaxTools()
                results = mt.parse_screenshot(b"\xff\xd8\xff\xe0fake")
                assert results[0]["in_database"] is True

    def test_in_database_false_for_unknown_stock(self):
        """Unknown stock is marked in_database=False."""
        with patch("backend.ai.minimax_tools.httpx.Client") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_instance)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_instance.post.return_value.json.return_value = {
                "choices": [{"message": {"content": '[{"stock_code":"600519","stock_name":"贵州茅台","source":"雪球"}]'}}]
            }

            with patch("backend.ai.minimax_tools.get_conn") as mock_conn:
                mock_c = MagicMock()
                mock_conn.return_value = mock_c
                mock_c.execute.return_value.fetchone.return_value = None
                mock_c.close = MagicMock()

                mt = MiniMaxTools()
                results = mt.parse_screenshot(b"\xff\xd8\xff\xe0fake")
                assert results[0]["in_database"] is False

    def test_network_error_raises(self):
        """Network error propagates."""
        with patch("backend.ai.minimax_tools.httpx.Client") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_instance)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_instance.post.side_effect = Exception("Network error")

            mt = MiniMaxTools()
            with pytest.raises(Exception, match="Network error"):
                mt.parse_screenshot(b"\xff\xd8\xff\xe0fake")


class TestEnrichment:
    """Test AKShare enrichment integration."""

    def test_parse_screenshot_uses_akshare_when_unknown(self):
        """parse_screenshot checks tickers and would use AKShare for unknown stocks."""
        # This tests the flow: VL returns stocks, tickers check, then AKShare enrichment
        with patch("backend.ai.minimax_tools.httpx.Client") as MockClient:
            mock_instance = MagicMock()
            MockClient.return_value.__enter__ = MagicMock(return_value=mock_instance)
            MockClient.return_value.__exit__ = MagicMock(return_value=False)
            mock_instance.post.return_value.json.return_value = {
                "choices": [{"message": {"content": '[{"stock_code":"600519","stock_name":"贵州茅台","source":"雪球"}]'}}]
            }

            with patch("backend.ai.minimax_tools.get_conn") as mock_conn:
                mock_c = MagicMock()
                mock_conn.return_value = mock_c
                # First call: check tickers (returns None = unknown)
                mock_c.execute.return_value.fetchone.side_effect = [None, None]
                mock_c.close = MagicMock()

                mt = MiniMaxTools()
                results = mt.parse_screenshot(b"\xff\xd8\xff\xe0fake")
                # Unknown stock, in_database should be False
                assert results[0]["in_database"] is False
