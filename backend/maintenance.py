"""One-shot data-quality backfills.

Run from project root:
    python -m backend.maintenance reclassify_events
    python -m backend.maintenance backfill_limit_flags
    python -m backend.maintenance compute_contradictions
    python -m backend.maintenance all

Each step is idempotent — safe to re-run after a partial failure.

Why these exist
---------------
The original scheduler backfill was too narrow:

1. `events.category` ended up 100% "policy" because:
   - `news_raw.source_type` was always "news" (AKShare client defaulted to it),
     so `_backfill_events` never produced notice/flash events,
   - and its fallback matched any title containing buyback/dividend/IPO keywords
     as "policy", misclassifying company-action news.

2. `news_aligned.limit_up / limit_down` are 0 on every row because the threshold
   flag was added to `align_news_for_symbol` after all 10K+ rows had already
   been written. The flag is computed correctly for new alignments, but a
   one-shot UPDATE is needed for the historical set.

3. There is no signal for "positive news + negative price" or vice versa —
   which is exactly the case where the attribution answer is most useful
   ("the news was good, why did it drop?"). A `contradiction` flag is
   written on `news_aligned` and surfaced via the attribution API.
"""

import logging
import sqlite3
import sys

from backend.database import get_conn, init_db

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# True policy: macro / regulator actions.
_POLICY_KEYWORDS = (
    "央行|降准|降息|加息|证监会|国务院|发改委|财政部|人民银行|"
    "银保监|外汇局|货币政策|财政政策|国企改革|混改|碳中和|"
    "碳达峰|新质生产力|数字经济|注册制|退市"
)

# Company-level actions that should be 'notice', not 'policy'.
_NOTICE_KEYWORDS = (
    "回购|分红|减持|增持|再融资|中标|合同|收购|合并|重组|"
    "辞职|聘任|董事长|总经理|副总|高管|业绩预增|业绩预减|"
    "盈利|亏损|净利"
)


def reclassify_events() -> dict:
    """Re-categorize the 792 'policy' events that are actually company actions.

    Returns: {"reclassified_to_notice": N, "reclassified_to_news": M, ...}
    """
    init_db()
    conn = get_conn()

    # Load ticker name → symbol map for name-based linking.
    ticker_rows = conn.execute(
        "SELECT symbol, name FROM tickers WHERE last_ohlc_fetch IS NOT NULL"
    ).fetchall()
    names_map = {
        r["name"]: r["symbol"]
        for r in ticker_rows
        if r["name"] and len(r["name"]) >= 3
    }

    # Build subqueries using LIKE — pragmatic, no FTS setup required.
    # Split the title by event_id prefix "evt_<news_id>" to join back to news_raw.
    rows = conn.execute(
        "SELECT id, title, description FROM events WHERE category = 'policy'"
    ).fetchall()

    to_notice, to_news, keep_policy, links_added = 0, 0, 0, 0
    for r in rows:
        title = r["title"] or ""
        if any(kw in title for kw in _POLICY_KEYWORDS.split("|")):
            keep_policy += 1
            continue
        if any(kw in title for kw in _NOTICE_KEYWORDS.split("|")):
            target = "notice"
            to_notice += 1
        else:
            target = "news"
            to_news += 1
        conn.execute(
            "UPDATE events SET category = ? WHERE id = ?",
            (target, r["id"]),
        )

        # Link events to tickers. Two strategies:
        #   1. news_ticker join (works for 'news' which originated from news)
        #   2. name match against active ticker names (works for 'notice'
        #      events that came from policy regex but mention a specific ticker)
        news_id = r["id"].replace("evt_", "", 1)
        nt = conn.execute(
            "SELECT symbol FROM news_ticker WHERE news_id = ? LIMIT 1",
            (news_id,),
        ).fetchone()
        if nt:
            conn.execute(
                "INSERT OR IGNORE INTO event_stock (event_id, symbol) VALUES (?, ?)",
                (r["id"], nt["symbol"]),
            )
            links_added += 1
        else:
            # Name match fallback for company-action 'notice' events.
            text = (r["title"] or "") + " " + (r["description"] or "")
            for name, symbol in names_map.items():
                if name in text:
                    conn.execute(
                        "INSERT OR IGNORE INTO event_stock (event_id, symbol) VALUES (?, ?)",
                        (r["id"], symbol),
                    )
                    links_added += 1

    conn.commit()
    conn.close()

    result = {
        "total": len(rows),
        "kept_policy": keep_policy,
        "reclassified_to_notice": to_notice,
        "reclassified_to_news": to_news,
        "links_added": links_added,
    }
    logger.info("reclassify_events: %s", result)
    return result


def backfill_limit_flags() -> dict:
    """Populate limit_up / limit_down on existing news_aligned rows.

    A股涨跌停阈值: 9.5% (主板); ST 股 4.5%; 创业板/科创板 19.5%.
    Conservative threshold = 9.5%.
    """
    init_db()
    conn = get_conn()

    cur = conn.execute(
        """UPDATE news_aligned
           SET limit_up = CASE
               WHEN (SELECT pct_chg FROM ohlc
                     WHERE ohlc.symbol = news_aligned.symbol
                     AND ohlc.date = news_aligned.trade_date) >= 9.5
               THEN 1 ELSE 0 END,
               limit_down = CASE
               WHEN (SELECT pct_chg FROM ohlc
                     WHERE ohlc.symbol = news_aligned.symbol
                     AND ohlc.date = news_aligned.trade_date) <= -9.5
               THEN 1 ELSE 0 END"""
    )
    updated = cur.rowcount

    # Stats
    up = conn.execute(
        "SELECT COUNT(*) FROM news_aligned WHERE limit_up = 1"
    ).fetchone()[0]
    down = conn.execute(
        "SELECT COUNT(*) FROM news_aligned WHERE limit_down = 1"
    ).fetchone()[0]

    conn.commit()
    conn.close()

    result = {"updated": updated, "limit_up": up, "limit_down": down}
    logger.info("backfill_limit_flags: %s", result)
    return result


def compute_contradictions() -> dict:
    """Flag news where sentiment and T+1 direction disagree (|ret_t1|>2%).

    A contradiction is a useful prompt for the AI explainer: "the news was
    positive, why did the stock drop?" We do NOT exclude these from
    attribution — they are surfaced as 'warning' reasons instead.

    Cases flagged:
      sentiment='positive' AND ret_t1 < -2%  (利好但跌)
      sentiment='negative' AND ret_t1 > +2%  (利空但涨)

    Neutral sentiment is ignored — too noisy.
    """
    init_db()
    conn = get_conn()

    cur = conn.execute(
        """UPDATE news_aligned
           SET contradiction = CASE
               WHEN EXISTS (
                   SELECT 1 FROM layer1_results l1
                   WHERE l1.news_id = news_aligned.news_id
                     AND l1.sentiment = 'positive'
                     AND news_aligned.ret_t1 < -0.02
               ) THEN 1
               WHEN EXISTS (
                   SELECT 1 FROM layer1_results l1
                   WHERE l1.news_id = news_aligned.news_id
                     AND l1.sentiment = 'negative'
                     AND news_aligned.ret_t1 > 0.02
               ) THEN 1
               ELSE 0
           END
           WHERE news_id IN (SELECT news_id FROM layer1_results)
             AND ret_t1 IS NOT NULL"""
    )
    updated = cur.rowcount

    flagged = conn.execute(
        "SELECT COUNT(*) FROM news_aligned WHERE contradiction = 1"
    ).fetchone()[0]

    conn.commit()
    conn.close()

    result = {"updated_rows": updated, "contradictions": flagged}
    logger.info("compute_contradictions: %s", result)
    return result


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "reclassify_events":
        reclassify_events()
    elif cmd == "backfill_limit_flags":
        backfill_limit_flags()
    elif cmd == "compute_contradictions":
        compute_contradictions()
    elif cmd == "all":
        reclassify_events()
        backfill_limit_flags()
        compute_contradictions()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()