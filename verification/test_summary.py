"""Test get_attribution_summary on multiple cases (contradiction + normal + no-news)."""
from backend.pipeline.layer2 import get_attribution_summary

cases = [
    {
        "name": "茅台 04-16: 利好但跌 (高分红 + ret_t1=-3.8%)",
        "symbol": "600519.SH",
        "trade_date": "2026-04-16",
        "price_change_pct": -0.038,
        "evidence": [
            {
                "news_id": "600519_2026-04-16 22:57:53",
                "title": "贵州茅台：2025年拟每股派现27.993元 合计拟派发现金红利约350.33亿元",
                "sentiment": "positive",
                "source_type": "notice",
                "contradiction": True,
                "ret_t1": -0.038,
            },
            {
                "news_id": "600519_2026-04-16 18:30:00",
                "title": 'A股超万亿"红包"来袭，近八成公司拟分红',
                "sentiment": "neutral",
                "source_type": "news",
                "contradiction": False,
                "ret_t1": -0.038,
            },
        ],
    },
    {
        "name": "中国石化 02-27: 利空但涨 (高管辞职 + ret_t1=+10%)",
        "symbol": "600028.SH",
        "trade_date": "2026-02-27",
        "price_change_pct": 0.101,
        "evidence": [
            {
                "news_id": "600028_2026-02-27 16:30:00",
                "title": "中国石化：总地质师因年龄原因辞职",
                "sentiment": "negative",
                "source_type": "notice",
                "contradiction": True,
                "ret_t1": 0.101,
            },
            {
                "news_id": "600028_2026-02-27 14:00:00",
                "title": "三桶油集体大涨，受益于国际油价上行",
                "sentiment": "positive",
                "source_type": "news",
                "contradiction": False,
                "ret_t1": 0.101,
            },
        ],
    },
    {
        "name": "宁德时代 04-02: 多条利好但跌 (-3.67%)",
        "symbol": "300750.SZ",
        "trade_date": "2026-04-02",
        "price_change_pct": -0.0367,
        "evidence": [
            {
                "news_id": "300750_2026-04-02 19:56:00",
                "title": "宁德时代已回购1599万股 金额达43.86亿元",
                "sentiment": "positive",
                "source_type": "notice",
                "contradiction": True,
                "ret_t1": -0.0367,
            },
            {
                "news_id": "300750_2026-04-02 18:36:00",
                "title": "券商4月金股出炉：通信板块增配居前 中际旭创热度第一",
                "sentiment": "positive",
                "source_type": "news",
                "contradiction": True,
                "ret_t1": -0.0367,
            },
        ],
    },
]

for c in cases:
    print("=" * 70)
    print(f"CASE: {c['name']}")
    print("=" * 70)
    result = get_attribution_summary(
        symbol=c["symbol"],
        trade_date=c["trade_date"],
        evidence=c["evidence"],
        price_change_pct=c["price_change_pct"],
        contradictions=[e for e in c["evidence"] if e["contradiction"]],
    )
    print(f"summary: {result['summary']}")
    print(f"cached:  {result['cached']}")
    print()