#!/usr/bin/env python3
"""
Tushare Pro 技术验证脚本
验证内容：
1. OHLC 日线数据（免费 tier，120积分）
2. 新闻数据（看结构和延迟）
3. 股票基本信息（A+H 代码格式）

用法：
  python tushare_check.py <YOUR_TOKEN>
  或
  TUSHARE_TOKEN=xxx python tushare_check.py
"""

import os
import sys
import json
from datetime import datetime, timedelta

try:
    import tushare as ts
except ImportError:
    print("ERROR: tushare 未安装。运行: pip install tushare")
    sys.exit(1)

# ── 1. 初始化 ──────────────────────────────────────────────
token = os.environ.get("TUSHARE_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not token:
    print("ERROR: 请提供 Tushare token:")
    print("  python tushare_check.py <YOUR_TOKEN>")
    print("  或设置环境变量 TUSHARE_TOKEN=<YOUR_TOKEN>")
    print("\n去 https://tushare.pro/register 注册获取免费 token")
    sys.exit(1)

pro = ts.pro_api(token)
print(f"\n{'='*60}")
print(f"  涨讯技术验证  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"{'='*60}\n")

# ── 2. 股票基本信息 ────────────────────────────────────────
print("## 1. 股票基本信息")
print("   测试股票: 贵州茅台 600519.SH (A 股)")

try:
    df_basic = pro.stock_basic(
        ts_code="600519.SH",
        fields="ts_code,symbol,name,area,industry,list_date,market"
    )
    print(f"\n  结果:")
    print(df_basic.to_string(index=False))
except Exception as e:
    print(f"  ERROR: {e}")

# ── 3. OHLC 日线数据 ───────────────────────────────────────
print(f"\n{'─'*60}")
print("## 2. OHLC 日线数据（最近 5 个交易日）")
print("   免费 tier: 120积分, 50次/分钟, 日线数据")

end_date = datetime.now().strftime("%Y%m%d")
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

try:
    df_ohlc = pro.pro_bar(
        ts_code="600519.SH",
        start_date=start_date,
        end_date=end_date,
        freq="D"
    )
    recent = df_ohlc.head(5)
    print(f"\n  最新 5 条:")
    print(f"  {'日期':<12} {'开盘':>8} {'最高':>8} {'最低':>8} {'收盘':>8} {'涨跌幅':>8}")
    print(f"  {'─'*12} {'─'*8} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
    for _, row in recent.iterrows():
        chg = f"{row['pct_chg']:+.2f}%" if 'pct_chg' in row and row['pct_chg'] is not None else "N/A"
        print(f"  {str(row['trade_date']):<12} {row['open']:>8.2f} {row['high']:>8.2f} {row['low']:>8.2f} {row['close']:>8.2f} {chg:>8}")
    print(f"\n  共获取 {len(df_ohlc)} 条数据")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 4. 涨跌停记录 ──────────────────────────────────────────
print(f"\n{'─'*60}")
print("## 3. 涨跌停记录（验证 A 股特色数据）")
print("   注意: 此 API 可能需要付费权限")

try:
    df_limit = pro.limit_list_d(
        trade_date=(datetime.now() - timedelta(days=1)).strftime("%Y%m%d"),
        limit_type="U",  # U=涨停, D=跌停
    )
    if df_limit is not None and len(df_limit) > 0:
        print(f"\n  昨日涨停股票 ({len(df_limit)} 只):")
        print(df_limit.head(10).to_string(index=False))
    else:
        print("  (无数据，可能需要更高权限)")
except Exception as e:
    print(f"  INFO: 涨跌停数据需要付费权限 - {e}")

# ── 5. 新闻数据 ────────────────────────────────────────────
print(f"\n{'─'*60}")
print("## 4. 新闻数据（最关键的验证项）")
print("   付费: ¥1,000/月 新闻权限; 免费: 可能无数据")

# 测试不同新闻 API
news_results = {}

# 5a. news API (主流财经新闻)
print("\n  [a] pro.news() - 财经新闻流")
try:
    df_news = pro.news(start_date=(datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S"),
                       end_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    if df_news is not None and len(df_news) > 0:
        print(f"      获取到 {len(df_news)} 条新闻")
        print(f"      字段: {list(df_news.columns)}")
        print(f"\n      最新 3 条:")
        for _, row in df_news.head(3).iterrows():
            dt = row.get('datetime', 'N/A')
            src = row.get('src', 'N/A')
            title = row.get('title', '')[:60]
            print(f"      {dt} [{src}] {title}")
        news_results['news'] = len(df_news)
    else:
        print("      返回空数据")
        news_results['news'] = 0
except Exception as e:
    print(f"      ERROR: {e}")
    news_results['news'] = f"ERROR: {e}"

# 5b. 公告 API (公司公告)
print("\n  [b] pro.anns_d() - 公司公告 (茅台近7天)")
try:
    df_anns = pro.anns_d(
        ts_code="600519.SH",
        start_date=(datetime.now() - timedelta(days=7)).strftime("%Y%m%d"),
        end_date=end_date,
    )
    if df_anns is not None and len(df_anns) > 0:
        print(f"      获取到 {len(df_anns)} 条公告")
        print(f"      字段: {list(df_anns.columns)}")
        print(f"\n      最新 3 条:")
        for _, row in df_anns.head(3).iterrows():
            ann_date = row.get('ann_date', 'N/A')
            title = row.get('title', '')[:60]
            print(f"      {ann_date}  {title}")
        news_results['anns'] = len(df_anns)
    else:
        print("      返回空数据")
        news_results['anns'] = 0
except Exception as e:
    print(f"      ERROR: {e}")
    news_results['anns'] = f"ERROR: {e}"

# ── 6. 港股数据（腾讯 00700.HK）─────────────────────────────
print(f"\n{'─'*60}")
print("## 5. 港股数据（腾讯 00700.HK）")
print("   港股日线数据可能需要单独付费")

try:
    df_hk = pro.pro_bar(
        ts_code="00700.HK",
        start_date=start_date,
        end_date=end_date,
        freq="D"
    )
    if df_hk is not None and len(df_hk) > 0:
        recent_hk = df_hk.head(3)
        print(f"\n  最新 3 条:")
        for _, row in recent_hk.iterrows():
            chg = f"{row['pct_chg']:+.2f}%" if 'pct_chg' in row and row['pct_chg'] is not None else "N/A"
            print(f"  {row['trade_date']}  {row['close']:>8.2f}  {chg}")
    else:
        print("  返回空数据 (可能需要港股数据权限)")
except Exception as e:
    print(f"  ERROR: {e}")

# ── 7. 北向资金（A股特色）───────────────────────────────────
print(f"\n{'─'*60}")
print("## 6. 北向资金数据（沪深港通）")
print("   验证是否有 A 股特有特色数据")

try:
    df_hsgt = pro.hk_hold(
        ts_code="600519.SH",
        trade_date=(datetime.now() - timedelta(days=5)).strftime("%Y%m%d"),
    )
    if df_hsgt is not None and len(df_hsgt) > 0:
        print(f"  获取到 {len(df_hsgt)} 条北向持股记录")
        print(df_hsgt.head(5).to_string(index=False))
    else:
        print("  暂无数据（正常，可能是权限或日期原因）")
except Exception as e:
    print(f"  INFO: {e}")

# ── 总结 ───────────────────────────────────────────────────
print(f"\n{'='*60}")
print("  验证结果总结")
print(f"{'='*60}")
print(f"  OHLC 日线: {'✓ 可用' if 'df_ohlc' in dir() and df_ohlc is not None else '✗ 失败'}")
print(f"  新闻数据:  {news_results.get('news', 'N/A')}")
print(f"  公告数据:  {news_results.get('anns', 'N/A')}")
print(f"  港股数据:  {'待验证' if 'df_hk' not in dir() else '✓ 可用'}")
print()
print("  下一步建议:")
print("  - 如果 OHLC 可用但新闻为空 → 需要购买新闻权限(¥1,000/月)")
print("  - 如果都想用 → 建议去 tushare.pro 购买新闻+公告权限")
print(f"  - Token 权限积分查询: pro.user_info()['coins']")
print()
