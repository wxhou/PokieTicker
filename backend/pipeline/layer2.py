"""Layer 2: On-demand deep analysis.

Triggered when user clicks a news article. Cached in layer2_results.
Uses MiniMax M2.5 via Anthropic SDK.
"""

import json
import re
import logging
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from backend.config import settings
from backend.database import get_conn
from backend.ai.provider import UnifiedSentimentProvider
from backend.ai.minimax import _get_client, _extract_text_from_response

logger = logging.getLogger(__name__)


# Sentinel news_id used to cache the per-day attribution summary in layer2_results.
# Using a synthetic id lets us reuse the existing cache table instead of adding
# a new schema for one column.
_ATTRIBUTION_SUMMARY_PREFIX = "_attr_summary:"


def get_attribution_summary(
    symbol: str,
    trade_date: str,
    evidence: list[dict],
    price_change_pct: Optional[float],
    contradictions: list[dict],
) -> Dict[str, Any]:
    """Generate a 2-3 sentence AI narrative explaining why the stock moved today.

    Args:
        symbol: stock symbol, e.g. "600519.SH"
        trade_date: YYYY-MM-DD
        evidence: top 3 reasons from get_attribution (title, sentiment, source_type, contradiction)
        price_change_pct: today's pct change (decimal, e.g. 0.027 = +2.7%)
        contradictions: subset of evidence where sentiment disagrees with price direction

    Returns:
        {"summary": "2-3 sentence narrative", "cached": bool, "model": "MiniMax-M2.5"}

    The narrative is grounded in the evidence chain so the user can verify
    every claim by clicking the source news. If MiniMax is unavailable, returns
    a graceful fallback pointing the user to the evidence list instead of
    hallucinating a story.
    """
    summary_key = f"{_ATTRIBUTION_SUMMARY_PREFIX}{trade_date}"

    # Check cache
    conn = get_conn()
    cached = conn.execute(
        "SELECT discussion, growth_reasons FROM layer2_results WHERE news_id = ? AND symbol = ?",
        (summary_key, symbol),
    ).fetchone()
    conn.close()

    if cached and cached["discussion"]:
        return {
            "summary": cached["discussion"],
            "model": "MiniMax-M2.5",
            "cached": True,
        }

    # Build prompt — keep it short so the model focuses on evidence-grounded synthesis.
    direction = "上涨" if (price_change_pct or 0) > 0 else "下跌"
    pct_str = f"{abs((price_change_pct or 0)) * 100:.2f}%"

    lines = []
    sent_label = {"positive": "利好", "negative": "利空", "neutral": "中性"}
    for i, ev in enumerate(evidence, 1):
        sentiment = ev.get("sentiment")
        sent = sent_label.get(sentiment or "", "中性")
        contradicts = bool(ev.get("contradiction"))
        flag = " ⚠️(与价格方向相反)" if contradicts else ""
        title = ev.get("title") or ""
        lines.append(f"{i}. [{sent}{flag}] {title}")

    prompt = f"""基于以下今日 {symbol} 的相关新闻，写 2-3 句话总结今日股价{direction} {pct_str} 的主要原因。

要求：
1. 严格根据提供的新闻信息总结，不引入未列出的事件或数据
2. 如果新闻与价格方向矛盾（如利好但跌），明确指出"市场反应与新闻方向不一致"
3. 如果新闻不足以判断涨跌原因，直接说"现有新闻不足以判断"
4. 用中文，简洁自然，像财经编辑写的一句话摘要
5. 不要使用"根据以上新闻""综合来看"等套话

新闻：
{chr(10).join(lines)}

只返回摘要文本，不要 JSON 或其他格式。"""

    summary_text = ""
    try:
        client = _get_client()
        response = client.messages.create(
            model="MiniMax-M2.5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        summary_text = _extract_text_from_response(response).strip()
        # Strip any leading labels the model might prepend.
        for prefix in ["摘要:", "总结:", "分析:", "Summary:", "Analysis:"]:
            if summary_text.startswith(prefix):
                summary_text = summary_text[len(prefix):].strip()
    except Exception as e:
        logger.warning("summarize_attribution failed for %s on %s: %s", symbol, trade_date, e)
        # Graceful fallback: don't hallucinate. Point the user to the evidence.
        if evidence:
            summary_text = (
                f"AI 总结暂不可用 ({type(e).__name__})，请参考下方证据链。"
                if not contradictions
                else f"今日新闻与价格方向存在矛盾（{len(contradictions)} 条），详见下方标注 ⚠️ 的条目。"
            )
        else:
            summary_text = "暂无相关新闻，AI 无法生成总结。"

    # Cache in layer2_results using the synthetic key.
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO layer2_results
           (news_id, symbol, discussion, growth_reasons, decrease_reasons, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            summary_key,
            symbol,
            summary_text,
            "",  # unused for summary
            "",
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    return {
        "summary": summary_text,
        "model": "MiniMax-M2.5",
        "cached": False,
    }


def get_cached(news_id: str, symbol: str) -> Optional[Dict[str, Any]]:
    """Check if a deep analysis is already cached."""
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM layer2_results WHERE news_id = ? AND symbol = ?",
        (news_id, symbol),
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def analyze_article(news_id: str, symbol: str) -> Dict[str, Any]:
    """Run deep analysis on a single article. Returns cached if available."""
    cached = get_cached(news_id, symbol)
    if cached:
        return cached

    # Fetch article data
    conn = get_conn()
    article = conn.execute(
        "SELECT title, description, content FROM news_raw WHERE id = ?",
        (news_id,),
    ).fetchone()
    conn.close()

    if not article:
        return {"error": "Article not found"}

    title = article["title"] or ""
    desc = article["description"] or article["content"] or ""

    # Try AI analysis first
    provider = UnifiedSentimentProvider()
    articles = [{
        "id": news_id,
        "title": title,
        "description": desc,
    }]

    discussion, growth_reasons, decrease_reasons = "", "", ""

    try:
        # Try batch-style analysis first
        results = provider.analyze(articles, symbol)
        if results and results[0].is_relevant:
            discussion = results[0].key_discussion
            growth_reasons = results[0].reason_growth
            decrease_reasons = results[0].reason_decrease
        elif results:
            # Not relevant, still use what we got
            discussion = results[0].key_discussion or ""
    except Exception as e:
        logger.warning("Batch analysis failed, trying detailed analysis: %s", e)

    # If no meaningful result, generate detailed analysis
    if not discussion and title:
        try:
            discussion, growth_reasons, decrease_reasons = _generate_analysis(
                title, desc, symbol
            )
        except Exception as e:
            logger.error("Layer2 analysis failed for %s: %s", news_id, e)

    # Cache result
    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO layer2_results
           (news_id, symbol, discussion, growth_reasons, decrease_reasons, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            news_id,
            symbol,
            discussion,
            growth_reasons,
            decrease_reasons,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    return {
        "news_id": news_id,
        "symbol": symbol,
        "discussion": discussion,
        "growth_reasons": growth_reasons,
        "decrease_reasons": decrease_reasons,
    }


def _generate_analysis(title: str, desc: str, symbol: str) -> tuple:
    """Generate detailed analysis using Anthropic SDK + MiniMax."""
    prompt = f"""分析以下新闻对股票 {symbol} 的影响，以JSON格式返回详细分析。

新闻标题：{title}
新闻内容：{desc[:2000]}

JSON格式：
{{
  "discussion": "详细分析该新闻对{symbol}的影响（100-200字）",
  "growth_reasons": "利好因素：具体说明为何该消息可能推动{symbol}上涨",
  "decrease_reasons": "利空因素：具体说明为何该消息可能给{symbol}带来下行压力"
}}

只返回JSON，不要包含任何其他文字。"""

    try:
        results = _call_analysis(prompt, symbol)
    except Exception as e:
        logger.error("Analysis call failed in layer2: %s", e)
        return ("分析生成失败，请稍后重试。", "", "")

    return (
        results.get("discussion", ""),
        results.get("growth_reasons", ""),
        results.get("decrease_reasons", ""),
    )


def _call_analysis(prompt: str, symbol: str) -> Dict[str, Any]:
    """Call MiniMax M2.5 via Anthropic SDK with a custom prompt."""
    client = _get_client()
    response = client.messages.create(
        model="MiniMax-M2.5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    text = _extract_text_from_response(response)
    return _robust_json_parse(text)


def _robust_json_parse(text: str) -> Dict[str, Any]:
    """Parse JSON with robustness for extra backticks, trailing commas, missing fields."""
    text = text.strip()
    # Remove markdown code fences
    text = re.sub(r"```(?:json)?", "", text)
    text = text.strip()

    # Find first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        # Fallback: try to find any JSON-like content
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                items = json.loads(text[start:end + 1])
                if isinstance(items, list) and items:
                    return items[0]
            except Exception:
                pass
        raise ValueError(f"Cannot find JSON in response: {text[:200]}")

    json_str = text[start:end + 1]

    # Remove trailing commas using a state-machine that respects string boundaries
    json_str = _strip_trailing_commas(json_str)

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.error("JSON parse error: %s, raw: %s", e, json_str[:500])
        return {
            "discussion": text[:200],
            "growth_reasons": "",
            "decrease_reasons": "",
        }


def _strip_trailing_commas(s: str) -> str:
    """Remove trailing commas before } or ] while respecting string boundaries."""
    result = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '"':
            # String start — copy until closing quote
            result.append(c)
            i += 1
            while i < n:
                c2 = s[i]
                result.append(c2)
                if c2 == '"':
                    i += 1
                    break
                if c2 == "\\" and i + 1 < n:
                    result.append(s[i + 1])
                    i += 2
                else:
                    i += 1
        elif c == ",":
            # Check if this comma is followed by whitespace and then } or ]
            j = i + 1
            while j < n and s[j] in " \t\n\r":
                j += 1
            if j < n and s[j] in "}]":
                # Trailing comma — skip it
                i = j
            else:
                result.append(c)
                i += 1
        else:
            result.append(c)
            i += 1
    return "".join(result)


def generate_story(symbol: str, csv_content: str) -> str:
    """Generate an AI story about stock price movements."""
    prompt = f"""根据以下{symbol}的OHLC数据和相关新闻，生成一份有吸引力的投资故事。

数据摘要：
{csv_content[-30000:]}

要求：
1. 讲述股价从开始到结束的完整旅程，突出关键转折点
2. 结合新闻事件分析底层业务和经济因素
3. 以1-2句话的概况开头
4. 分析市场情绪变化和投资机会
5. 用HTML格式输出，使用<h3>标题、<p>段落、<strong>强调标签
6. 约500-1000字，使用生动叙述性语言
7. 关注：价格大幅波动时期及时间线、关键新闻事件影响、与竞争对比、监管和政策影响

请直接返回HTML内容。"""

    try:
        client = _get_client()
        response = client.messages.create(
            model="MiniMax-M2.5",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        return _extract_text_from_response(response)
    except Exception as e:
        logger.error("generate_story failed: %s", e)
        return f"<p>故事生成失败，请稍后重试。</p><p>错误: {e}</p>"


def analyze_range(
    symbol: str, start_date: str, end_date: str, question: Optional[str] = None
) -> Dict[str, Any]:
    """Analyze what drove price movement in a date range using AI."""
    conn = get_conn()

    # Get OHLC data for range
    ohlc_rows = conn.execute(
        """SELECT date, open, high, low, close, volume, pct_chg
           FROM ohlc WHERE symbol = ? AND date >= ? AND date <= ? ORDER BY date ASC""",
        (symbol, start_date, end_date),
    ).fetchall()

    if not ohlc_rows:
        conn.close()
        return {"error": "No OHLC data for this range"}

    open_price = ohlc_rows[0]["open"]
    close_price = ohlc_rows[-1]["close"]
    high_price = max(r["high"] for r in ohlc_rows)
    low_price = min(r["low"] for r in ohlc_rows)
    price_change_pct = round((close_price - open_price) / open_price * 100, 2)

    # Get news in range, prioritize by impact
    news_rows = conn.execute(
        """SELECT nr.title, l1.key_discussion,
                  l1.sentiment, l1.reason_growth, l1.reason_decrease,
                  na.trade_date, na.ret_t0
           FROM news_aligned na
           JOIN layer1_results l1 ON na.news_id = l1.news_id AND l1.symbol = na.symbol
           JOIN news_raw nr ON na.news_id = nr.id
           WHERE na.symbol = ? AND na.trade_date >= ? AND na.trade_date <= ?
             AND l1.relevance = 'relevant'
           ORDER BY ABS(COALESCE(na.ret_t0, 0)) DESC
           LIMIT 30""",
        (symbol, start_date, end_date),
    ).fetchall()
    conn.close()

    news_count = len(news_rows)

    # Build news context
    news_context = ""
    for i, row in enumerate(news_rows[:30], 1):
        ret = f"当日涨跌: {row['ret_t0']*100:.2f}%" if row["ret_t0"] else ""
        news_context += f"\n{i}. [{row['trade_date']}] {row['title']}\n"
        if row["key_discussion"]:
            news_context += f"   摘要: {row['key_discussion']}\n"
        if ret:
            news_context += f"   {ret}\n"

    ohlc_summary = (
        f"开盘: {open_price:.2f}, 收盘: {close_price:.2f}, "
        f"最高: {high_price:.2f}, 最低: {low_price:.2f}, "
        f"涨跌幅: {price_change_pct:+.2f}%, 交易日: {len(ohlc_rows)}天"
    )

    question_part = f"用户问题: {question}\n\n" if question else ""

    prompt = f"""分析{symbol}在{start_date}至{end_date}期间的股价变动原因。

价格数据：
{ohlc_summary}

相关新闻（共{news_count}篇）：
{news_context if news_context else "该期间无相关新闻"}

{question_part}请以JSON格式返回分析结果：
{{
  "summary": "1-2句话概况",
  "key_events": ["关键事件1", "关键事件2", ...],
  "bullish_factors": ["利好因素1", ...],
  "bearish_factors": ["利空因素1", ...],
  "trend_analysis": "详细趋势分析（100-150字）"
}}

只返回JSON。"""

    try:
        results = _call_analysis(prompt, symbol)
    except Exception as e:
        logger.error("analyze_range failed: %s", e)
        results = {
            "summary": f"分析{symbol}期间股价变动",
            "key_events": [],
            "bullish_factors": [],
            "bearish_factors": [],
            "trend_analysis": f"数据加载失败: {e}",
        }

    return {
        "symbol": symbol,
        "start_date": start_date,
        "end_date": end_date,
        "price_change_pct": price_change_pct,
        "open_price": open_price,
        "close_price": close_price,
        "high_price": high_price,
        "low_price": low_price,
        "news_count": news_count,
        "trading_days": len(ohlc_rows),
        "analysis": results,
    }