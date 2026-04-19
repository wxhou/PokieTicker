"""Tests for robust JSON parsing from layer2.py."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.pipeline.layer2 import _robust_json_parse


class TestJSONParsing:
    """Test _robust_json_parse: backticks/fences, JSON bounds, fallback, missing fields."""

    def test_clean_json(self):
        """Clean JSON object parses correctly."""
        result = _robust_json_parse(
            '{"discussion": "茅台营收增长", "growth_reasons": "业绩超预期", "decrease_reasons": ""}'
        )
        assert result["discussion"] == "茅台营收增长"
        assert result["growth_reasons"] == "业绩超预期"
        assert result["decrease_reasons"] == ""

    def test_json_array_response(self):
        """JSON array response returns first element."""
        result = _robust_json_parse(
            '[{"discussion": "test", "growth_reasons": "u", "decrease_reasons": "d"}]'
        )
        assert result["discussion"] == "test"

    def test_clean_json_all_fields_present(self):
        """Clean JSON with all three fields parses correctly."""
        result = _robust_json_parse(
            '{"discussion": "茅台分析", "growth_reasons": "利好", "decrease_reasons": "利空"}'
        )
        assert result["discussion"] == "茅台分析"
        assert result["growth_reasons"] == "利好"
        assert result["decrease_reasons"] == "利空"

    def test_single_trailing_comma_brace(self):
        """A single trailing comma before } is stripped by the regex."""
        result = _robust_json_parse(
            '{"discussion": "test", "growth_reasons": "u", "decrease_reasons": "",}'
        )
        assert result["discussion"] == "test"

    def test_single_trailing_comma_bracket(self):
        """A single trailing comma before ] is stripped by the regex."""
        result = _robust_json_parse(
            '[{"discussion": "test", "growth_reasons": "u",},]'
        )
        assert result["discussion"] == "test"

    def test_markdown_code_fence_triple_backtick(self):
        """JSON wrapped in markdown ``` is extracted correctly."""
        result = _robust_json_parse(
            '```json\n{"discussion": "茅台分析", "growth_reasons": "利好", "decrease_reasons": ""}\n```'
        )
        assert result["discussion"] == "茅台分析"

    def test_markdown_code_fence_no_lang(self):
        """JSON wrapped in plain ``` without language spec is extracted."""
        result = _robust_json_parse(
            '```\n{"discussion": "plain code fence", "growth_reasons": "u", "decrease_reasons": ""}\n```'
        )
        assert result["discussion"] == "plain code fence"

    def test_backtick_only_prefix(self):
        """Single backtick prefix is stripped."""
        result = _robust_json_parse(
            '`{"discussion": "backtick prefix", "growth_reasons": "u", "decrease_reasons": ""}`'
        )
        assert result["discussion"] == "backtick prefix"

    def test_extra_text_around_json(self):
        """Extra text before/after JSON is stripped."""
        result = _robust_json_parse(
            '以下是分析结果：\n{"discussion": "带前缀后缀", "growth_reasons": "u", "decrease_reasons": ""}\n请注意以上内容'
        )
        assert result["discussion"] == "带前缀后缀"

    def test_no_json_found_raises(self):
        """If no JSON-like content found, raises ValueError."""
        with pytest.raises(ValueError, match="Cannot find JSON"):
            _robust_json_parse("这不是JSON内容，没有任何花括号")

    def test_whitespace_only_response(self):
        """Whitespace-only response raises ValueError (no JSON found)."""
        with pytest.raises(ValueError, match="Cannot find JSON"):
            _robust_json_parse("   \n\n  ")

    def test_mixed_backticks_and_text(self):
        """JSON with mixed backticks and surrounding text."""
        result = _robust_json_parse(
            '根据分析，```json\n{"discussion": "混合格式", "growth_reasons": "u", "decrease_reasons": ""}\n```'
            '是正确的结果'
        )
        assert result["discussion"] == "混合格式"

    def test_unicode_characters_in_json(self):
        """Unicode Chinese characters in JSON are parsed correctly."""
        result = _robust_json_parse(
            '{"discussion": "茅台股价持续上涨创历史新高", "growth_reasons": "业绩超预期、品牌溢价", "decrease_reasons": "成本上升"}'
        )
        assert "茅台" in result["discussion"]
        assert "业绩超预期" in result["growth_reasons"]

    def test_empty_json_object(self):
        """Empty JSON object {} parses without raising."""
        result = _robust_json_parse("{}")
        assert isinstance(result, dict)

    def test_nested_json_parses(self):
        """Nested JSON with extra fields parses successfully."""
        result = _robust_json_parse(
            '{"discussion": "test", "nested": {"inner": "value"}, "growth_reasons": "u", "decrease_reasons": ""}'
        )
        assert result["discussion"] == "test"
        assert result["growth_reasons"] == "u"

    def test_leading_whitespace_stripped(self):
        """Leading whitespace is stripped before parsing."""
        result = _robust_json_parse(
            '   \n   {"discussion": "去空格", "growth_reasons": "u", "decrease_reasons": ""}'
        )
        assert result["discussion"] == "去空格"

    def test_json_extracts_from_middle_of_text(self):
        """JSON boundaries are found by first { and last }."""
        result = _robust_json_parse(
            'Some prefix text {"discussion": "middle json", "growth_reasons": "u", "decrease_reasons": ""} some suffix'
        )
        assert result["discussion"] == "middle json"

    def test_object_not_array_falls_back_to_array_parse(self):
        """If {} not found, falls back to trying [] for array extraction."""
        result = _robust_json_parse(
            '[{"discussion": "array item", "growth_reasons": "u", "decrease_reasons": ""}]'
        )
        assert result["discussion"] == "array item"

    def test_truncated_json_raises_value_error(self):
        """Truncated JSON that can't be parsed raises ValueError."""
        with pytest.raises(ValueError, match="Cannot find JSON"):
            _robust_json_parse('{"discussion": "partial", "growth_reasons":')
