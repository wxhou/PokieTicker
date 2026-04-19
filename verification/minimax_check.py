#!/usr/bin/env python3
"""
MiniMax 中文财经理解能力验证
测试内容：
1. A 股特有术语理解（涨停、跌停、T+1、龙虎榜、主力、北向资金）
2. 情感分析（利好/利空判断）
3. 因果归因（新闻 → 涨跌原因）
4. 腾讯/茅台新闻的深度解读

用法：
  python minimax_check.py <YOUR_MINIMAX_API_KEY>
  或
  MINIMAX_API_KEY=xxx python minimax_check.py
"""

import os
import sys
import json
import time
from datetime import datetime

try:
    import openai
except ImportError:
    print("ERROR: openai SDK 未安装。运行: pip install openai")
    sys.exit(1)

# ── 初始化 ──────────────────────────────────────────────
api_key = os.environ.get("MINIMAX_API_KEY") or (sys.argv[1] if len(sys.argv) > 1 else None)
if not api_key:
    print("ERROR: 请提供 MiniMax API key:")
    print("  python minimax_check.py <YOUR_API_KEY>")
    print("  或设置环境变量 MINIMAX_API_KEY=<YOUR_API_KEY>")
    print("\n去 https://platform.minimax.io 注册获取 API key")
    sys.exit(1)

# MiniMax OpenAI-compatible endpoint
# 海外用户用 api.minimax.io，中国大陆用户用 api.minimaxi.com
client = openai.OpenAI(
    api_key=api_key,
    base_url="https://api.minimaxi.com/v1"  # 中国大陆版
)

MODEL = "MiniMax-M2.5"
MAX_TOKENS = 500

def ask(prompt, model=MODEL, temp=0.3):
    """发送请求到 MiniMax，返回文本响应"""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_TOKENS,
            temperature=temp,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"ERROR: {e}"

def divider(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

# ── 测试新闻数据（来自 AKShare 真实数据）───────────────────
MOUTAI_NEWS = """以下是一组贵州茅台(600519.SH)的真实新闻，发布时间为2026年4月16日-17日：

[新闻1] 2026-04-16 22:50 财联社
标题：贵州茅台：2025年度净利润823.20亿元 同比下降4.53%
内容：贵州茅台(600519.SH)发布2025年年度报告，实现营业收入1688.38亿元，同比下降1.21%；归属于上市公司股东的净利润为823.20亿元，同比下降4.53%。拟向全体股东每股派发现金红利27.993元（含税）。

[新闻2] 2026-04-16 22:57 财联社
标题：贵州茅台：2025年拟每股派现27.993元 合计约350.33亿元
内容：公告称，公司拟实施2025年年度利润分配，向全体股东每股派发现金红利27.993元(含税)。以总股本计算，合计派发现金红利约350.33亿元。

[新闻3] 2026-04-17 09:19 财中社
标题：贵州茅台拟每股派发现金红利27.993元
内容：4月16日，贵州茅台（600519）发布公告，公司拟向全体股东每股派发现金红利27.993元（含税），预计总派发金额为350.33亿元。

[新闻4] 2026-04-14 19:21 每日经济新闻
标题：贵州茅台：聘任余思明为财务总监并代行董秘职责
内容：4月14日公告，董事会决定，聘任余思明为公司财务总监，并指定余思明代行董事会秘书职责。

已知：贵州茅台4月17日收盘1407.24元，当日跌幅3.80%，成交额136亿元，主力资金净流出9.87亿元（占比-7.24%）。"""

print(f"\n{'='*60}")
print(f"  涨讯 · MiniMax AI 验证  |  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  模型: {MODEL}")
print(f"{'='*60}\n")

# ── 测试 1：A 股术语理解 ─────────────────────────────────
divider("测试1：A 股特有术语理解")
print()

print("[1a] 什么是'主力'？什么是'北向资金'？")
p1 = "请用一段话解释A股中'主力'和'北向资金'的含义，不要用英文缩写，简洁易懂。"
r1 = ask(p1)
print(f"  问题: {p1}")
print(f"  回答: {r1}")
time.sleep(1)

print()
print("[1b] 什么是'涨停'和'一字板'？这对散户意味着什么？")
p2 = "请解释A股'涨停'和'一字板'的含义，以及这对散户投资者意味着什么风险或机会。"
r2 = ask(p2)
print(f"  回答: {r2}")
time.sleep(1)

print()
print("[1c] 'T+1'制度是什么？为什么A股要T+1？")
p3 = "请解释A股T+1交易制度的含义，以及为什么中国A股采用T+1而不是T+0。"
r3 = ask(p3)
print(f"  回答: {r3}")

# ── 测试 2：情感分析 ─────────────────────────────────────
divider("测试2：情感分析（利好/利空）")
print()

p4 = f"""{MOUTAI_NEWS}

问题：以上新闻对贵州茅台股价来说，哪些是利好消息，哪些是利空消息？请逐条分析并说明理由。"""
r4 = ask(p4)
print(f"  回答:\n{r4}")

# ── 测试 3：因果归因 ─────────────────────────────────────
divider("测试3：因果归因（核心测试）")
print()

p5 = f"""{MOUTAI_NEWS}

问题：结合以上所有信息，分析贵州茅台4月17日下跌3.80%的主要原因是什么？哪些新闻是下跌的驱动因素？请给出因果分析（不要猜测，给出有逻辑支撑的推断）。"""
r5 = ask(p5)
print(f"  回答:\n{r5}")

# ── 测试 4：主力资金解读 ─────────────────────────────────
divider("测试4：主力资金解读")
print()

p6 = """已知：贵州茅台4月17日主力资金净流出9.87亿元，占当日成交额的7.24%。
问题：'主力资金净流出'是什么意思？这种规模的主力流出对股价后续走势有什么参考意义？请给出客观分析。"""
r6 = ask(p6)
print(f"  回答:\n{r6}")

# ── 测试 5：综合结论 ─────────────────────────────────────
divider("测试5：综合结论输出")
print()

p7 = f"""{MOUTAI_NEWS}

问题：作为普通散户投资者，看到以上信息后，应该如何客观理解茅台今天的涨跌？请用200字以内的中性语言总结（不要给出具体投资建议）。"""
r7 = ask(p7)
print(f"  回答:\n{r7}")

# ── 测试 6：中文语义质量 ─────────────────────────────────
divider("测试6：中文语义理解质量评估")
print()

p8 = """请分析以下这段财经文本中的专业术语和关键数据表述是否清晰准确：

"2025年度，贵州茅台实现营业收入1688.38亿元，同比下降1.21%；归母净利润823.20亿元，同比下降4.53%。拟向全体股东每股派发现金红利27.993元(含税)，合计派发350.33亿元。"

问题：这段文字表述是否清晰？有哪些可能引起普通投资者困惑的地方？"""
r8 = ask(p8)
print(f"  回答:\n{r8}")

# ── 总结 ─────────────────────────────────────────────────
divider("验证结论")
print()
print("请人工评估以上输出质量，重点关注：")
print("  1. A股术语理解是否正确（主力、涨停、T+1等）")
print("  2. 情感分析是否合理（利好/利空判断）")
print("  3. 因果归因是否有逻辑（新闻 → 涨跌）")
print("  4. 语言是否流畅自然（无明显翻译腔）")
print("  5. 语气是否客观中性（不过度乐观/悲观）")
print()
