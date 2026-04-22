"""Tests for backend/ai/minimax_tools.py."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.ai.minimax_tools import (
    _compute_simhash,
    _hamming_distance,
    _parse_json_robust,
    MiniMaxTools,
)


class TestComputeSimhash:
    """Test _compute_simhash: 64-bit SimHash computation."""

    def test_same_text_produces_same_hash(self):
        """Identical text produces the same hash."""
        h1 = _compute_simhash("贵州茅台业绩公告")
        h2 = _compute_simhash("贵州茅台业绩公告")
        assert h1 == h2
        assert len(h1) == 16  # 64-bit hex string

    def test_different_text_produces_different_hash(self):
        """Different text produces different hashes."""
        h1 = _compute_simhash("贵州茅台业绩公告")
        h2 = _compute_simhash("宁德时代业绩公告")
        assert h1 != h2

    def test_chinese_text(self):
        """Chinese text is handled correctly."""
        h = _compute_simhash("A股市场今日上涨，贵州茅台领涨")
        assert len(h) == 16
        assert h.isalnum()

    def test_empty_string(self):
        """Empty string produces a valid hash."""
        h = _compute_simhash("")
        assert len(h) == 16

    def test_single_character(self):
        """Single character is handled."""
        h = _compute_simhash("涨")
        assert len(h) == 16


class TestHammingDistance:
    """Test _hamming_distance: bitwise XOR + popcount."""

    def test_equal_hashes_distance_zero(self):
        """Same hash has distance 0."""
        h = "0123456789abcdef"
        assert _hamming_distance(h, h) == 0

    def test_known_distance(self):
        """Known Hamming distance."""
        # 0x0000 vs 0x0001 differs by 1 bit
        assert _hamming_distance("0000000000000000", "0000000000000001") == 1
        # 0x0000 vs 0x0003 differs by 2 bits
        assert _hamming_distance("0000000000000000", "0000000000000003") == 2

    def test_completely_different_hashes(self):
        """Completely different hashes have high distance."""
        h1 = "0000000000000000"
        h2 = "ffffffffffffffff"
        assert _hamming_distance(h1, h2) == 64


class TestParseJsonRobust:
    """Test _parse_json_robust: robust JSON array parsing."""

    def test_direct_array(self):
        """Direct JSON array parses correctly."""
        items = _parse_json_robust('[{"title": "茅台", "snippet": "公告"}]')
        assert len(items) == 1
        assert items[0]["title"] == "茅台"

    def test_nested_data_key(self):
        """Nested {"data": [...]} is extracted."""
        items = _parse_json_robust('{"data": [{"title": "茅台", "snippet": "公告"}]}')
        assert len(items) == 1
        assert items[0]["title"] == "茅台"

    def test_nested_results_key(self):
        """Nested {"results": [...]} is extracted."""
        items = _parse_json_robust('{"results": [{"title": "test"}]}')
        assert len(items) == 1

    def test_markdown_fence(self):
        """JSON inside ``` fences is extracted."""
        items = _parse_json_robust('```json\n[{"title": "茅台"}]\n```')
        assert len(items) == 1
        assert items[0]["title"] == "茅台"

    def test_empty_array(self):
        """Empty array returns empty list."""
        assert _parse_json_robust("[]") == []
        assert _parse_json_robust("") == []

    def test_invalid_json(self):
        """Invalid JSON returns empty list."""
        assert _parse_json_robust("这不是JSON") == []

    def test_mixed_text(self):
        """JSON with surrounding text is extracted."""
        items = _parse_json_robust(
            '以下是新闻结果：\n[{"title": "茅台", "snippet": "公告"}]\n请注意'
        )
        assert len(items) == 1
        assert items[0]["title"] == "茅台"

    def test_partial_match_fallback(self):
        """Fallback bracket extraction finds array in text."""
        items = _parse_json_robust(
            '没有JSON前缀 [{"title": "茅台", "snippet": "公告"}] 后缀'
        )
        assert len(items) == 1


class TestMiniMaxToolsParsing:
    """Test MiniMaxTools._parse_search_response and _deduplicate_by_simhash."""

    def test_parse_valid_response(self):
        """Valid search response is parsed with simhash."""
        text = '[{"title": "贵州茅台业绩","snippet":"营收增长","date":"2026-04-20","url":"https://x.cn/1"}]'
        mt = MiniMaxTools()
        results = mt._parse_search_response(text, "600519")
        assert len(results) == 1
        assert results[0]["title"] == "贵州茅台业绩"
        assert results[0]["snippet"] == "营收增长"
        assert results[0]["date"] == "2026-04-20"
        assert results[0]["url"] == "https://x.cn/1"
        assert results[0]["symbol"] == "600519"
        assert len(results[0]["simhash"]) == 16

    def test_parse_missing_fields_filtered(self):
        """Items missing title or snippet are filtered out."""
        # None, empty string, and missing fields all get filtered
        text = '[{"title": "有标题"}, {"snippet": "有摘要"}, {"title": "", "snippet": "x"}]'
        mt = MiniMaxTools()
        results = mt._parse_search_response(text, "600519")
        # All three have either missing/empty title or missing/empty snippet
        assert len(results) == 0

    def test_parse_both_fields_needed(self):
        """Only items with both title AND snippet pass."""
        text = '[{"title": "茅台公告"}, {"title": "公告", "snippet": ""}]'
        mt = MiniMaxTools()
        results = mt._parse_search_response(text, "600519")
        assert len(results) == 0

    def test_parse_empty_response(self):
        """Empty JSON returns empty list."""
        mt = MiniMaxTools()
        results = mt._parse_search_response("[]", "600519")
        assert results == []
