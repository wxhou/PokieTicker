## Why

国内散户炒 A 股/港股，面临一个根本性问题：新闻很多，但不知道哪些真正影响了今天的股价。同花顺、东方财富、雪球解决了信息获取的问题，但没有解决"信息优先级"和"因果归因"的问题。用户看了 20 条新闻，关掉软件还是不知道今天为什么涨了。

技术验证已完成：AKShare 数据全通（A股日线、新闻、涨跌停、龙虎榜、主力资金），MiniMax M2.5 中文财经理解能力通过验证（术语、情感、因果归因全部合格）。可以在此基础上快速构建 MVP。

## What Changes

**数据层**
- 替换 Polygon.io → AKShare（A 股日线、新闻、资金流）
- AKShare 限流：加本地缓存层 + 限速 + 备用源
- Tushare Pro 作为付费备选（账号积分涨上来后切换）

**AI 层**
- 替换 Anthropic Claude → MiniMax M2.5（主力）+ DeepSeek（备选）
- 新增中文分词：jieba 提取关键词，替换英文 TICKER_KEYWORDS
- 抽象接入层：统一 SentimentProvider，支持双模型降级

**数据库**
- 新增 users / portfolios / portfolio_holdings 三张表
- alignment.py 加涨跌停标记

**前端**
- 品牌名切换：PokieTicker → 涨讯
- 颜色反转：up=red / down=green（A 股习惯）
- 中文本地化：字体 PingFang SC，所有 UI 文字翻译
- Skeleton 骨架屏复用
- 默认展示：localStorage 记住用户上次查看的股票
- 免责声明固定在预测面板底部
- ML 预测面板降级：保留展示但不做为主推（v1.1 重训后再主推）

**合规**
- 全局 Disclaimer 文本（工具属性定位，无投顾资质风险）

**品牌候选**
- 当前选定：涨讯
- 待出候选 list（3-5 个），参考：涨跌通、股讯通、事件眼、因果投

**废弃**
- 删除 layer1.py 中 Anthropic Batch API dead code（约130行）
- pipeline.py 清理已删除函数的 import
- JSON 解析健壮性：layer2.py 的 MiniMax/DeepSeek 返回处理

## Capabilities

### New Capabilities

- `a-share-data`: AKShare 数据接入层，支持 A 股日线、新闻、涨跌停、龙虎榜、资金流。加缓存和限流。
- `chinese-ai-analysis`: MiniMax M2.5 情感分析 + DeepSeek 备选。抽象 Provider 接口，支持双模型降级。
- `chinese-keywords`: jieba 中文分词提取新闻关键词，替换英文关键词逻辑。
- `user-auth`: JWT 账户体系（注册、登录、token）。支持完整用户体系。
- `portfolio-tracking`: 单用户持仓组合管理（3-10 只股），加仓/减仓/查看。
- `chinese-localization`: 涨讯品牌、本地化 UI、颜色反转、中文字体、免责声明。
- `a-share-rules`: alignment.py 涨跌停标记，T+1 对齐规则。

### Modified Capabilities

（无现有 spec 需修改，specs/ 目录为空，直接创建新 capability spec）

## Impact

**后端**
- `backend/polygon/client.py` → 改为 `backend/akshare/client.py`（重试模板复用）
- `backend/pipeline/layer0.py` → jieba 关键词提取
- `backend/pipeline/layer1.py` → 替换 Claude → MiniMax，删除 Anthropic Batch API dead code
- `backend/pipeline/layer2.py` → 替换 Claude → MiniMax/DeepSeek
- `backend/database.py` → 新增 3 表（users, portfolios, portfolio_holdings）
- `backend/api/routers/stocks.py` → 数据源切换
- `backend/api/routers/pipeline.py` → import 清理
- `backend/pipeline/alignment.py` → 加涨跌停标记

**前端**
- `frontend/src/App.tsx` → 本地化、品牌切换
- `frontend/src/App.css` → 颜色反转、中文字体
- `frontend/src/components/PredictionPanel.tsx` → ML 降级 + 免责声明
- `frontend/src/components/StockSelector.tsx` → 持仓分组下拉
- 新增 `frontend/src/pages/Portfolio.tsx` → /portfolio 路由

**依赖**
- `requirements.txt` → 新增 jieba、python-jose（JWT）、passlib
- 新增 `.env`（TUSHARE_TOKEN, MINIMAX_API_KEY, DEEPSEEK_API_KEY）

**测试**
- pytest 新增后端测试
- Playwright E2E 新增中文 UI 测试
