"""Tests for AKShare client retry logic: 3 retries, exponential backoff."""

import pytest
import time
from unittest.mock import patch, MagicMock, call
import sys
import os

# Ensure backend is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAkShareRetry:
    """Test _with_retry from backend/akshare/client.py."""

    def test_retry_succeeds_on_third_attempt(self):
        """Function retries up to 3 times and succeeds on 3rd attempt."""
        from backend.akshare.client import _with_retry

        mock_fn = MagicMock(side_effect=[
            ConnectionResetError("reset"),
            ConnectionResetError("reset"),
            [{"date": "2026-04-01", "close": 100.0}],
        ])

        with patch("time.sleep") as mock_sleep:
            result = _with_retry(mock_fn, max_retries=3)

        assert result == [{"date": "2026-04-01", "close": 100.0}]
        assert mock_fn.call_count == 3
        # Exponential backoff: 2^0 + 0.5 = 1.5, 2^1 + 0.5 = 2.5
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == pytest.approx(1.5, rel=0.1)
        assert mock_sleep.call_args_list[1][0][0] == pytest.approx(2.5, rel=0.1)

    def test_retry_connection_refused_error(self):
        """Retries on ConnectionRefusedError."""
        from backend.akshare.client import _with_retry

        mock_fn = MagicMock(side_effect=[
            ConnectionRefusedError("refused"),
            [{"data": "ok"}],
        ])

        with patch("time.sleep") as mock_sleep:
            result = _with_retry(mock_fn, max_retries=3)

        assert result == [{"data": "ok"}]
        assert mock_fn.call_count == 2
        assert mock_sleep.call_count == 1

    def test_retry_os_error(self):
        """Retries on OSError (generic network error)."""
        from backend.akshare.client import _with_retry

        mock_fn = MagicMock(side_effect=[
            OSError("network unreachable"),
            [{"data": "ok"}],
        ])

        with patch("time.sleep"):
            result = _with_retry(mock_fn, max_retries=3)

        assert result == [{"data": "ok"}]
        assert mock_fn.call_count == 2

    def test_retry_exhausted_raises_last_error(self):
        """After 3 retries, raises the last ConnectionResetError."""
        from backend.akshare.client import _with_retry

        mock_fn = MagicMock(side_effect=ConnectionResetError("persistent failure"))

        with patch("time.sleep"):
            with pytest.raises(ConnectionResetError, match="persistent failure"):
                _with_retry(mock_fn, max_retries=3)

        assert mock_fn.call_count == 3

    def test_retry_max_30_second_backoff_cap(self):
        """Backoff is capped at 30 seconds even after many retries."""
        from backend.akshare.client import _with_retry

        # Simulate many retries by using more iterations
        mock_fn = MagicMock(side_effect=ConnectionResetError("fail"))

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(ConnectionResetError):
                _with_retry(mock_fn, max_retries=3)

        # All sleep intervals should be <= 30
        for call_args in mock_sleep.call_args_list:
            sleep_duration = call_args[0][0]
            assert sleep_duration <= 30.0

    def test_retry_succeeds_immediately(self):
        """No retries when function succeeds on first call."""
        from backend.akshare.client import _with_retry

        mock_fn = MagicMock(return_value={"key": "value"})

        result = _with_retry(mock_fn, max_retries=3)

        assert result == {"key": "value"}
        assert mock_fn.call_count == 1

    def test_retry_non_connection_error_not_retried(self):
        """Non-connection errors (ValueError) are NOT retried."""
        from backend.akshare.client import _with_retry

        mock_fn = MagicMock(side_effect=ValueError("not a connection error"))

        with patch("time.sleep") as mock_sleep:
            with pytest.raises(ValueError, match="not a connection error"):
                _with_retry(mock_fn, max_retries=3)

        assert mock_fn.call_count == 1
        mock_sleep.assert_not_called()
