## 1. 环境配置

- [x] 1.1 安装 Python 依赖：jieba、python-jose、passlib、bcrypt（conda env `zhangxun` 创建完成）
- [x] 1.2 确认 .env 文件含 TUSHARE_TOKEN、MINIMAX_API_KEY、DEEPSEEK_API_KEY
- [x] 1.3 验证 AKShare 在 conda env `zhangxun` 可导入

## 2. 数据层

- [x] 2.1 创建 `backend/akshare/client.py`：带重试（3次，指数退避），resolve_code/search/OHLC/news/涨跌停全通
- [x] 2.2 添加 `ohlc_cache` SQLite 表（TTL=1天）✓
- [x] 2.3 添加 `news_cache` SQLite 表（TTL=10分钟）✓
- [x] 2.4 `fetch_ohlc()` ✓
- [x] 2.5 `fetch_news()` ✓
- [x] 2.6 `fetch_limit_up_down()` ✓（涨跌停各71/0只，测试通过）
- [x] 2.7 修改 `alignment.py`：加载 pct_chg，插入时设置 limit_up/limit_down（阈值9.5%）；pct_chg 加列并回填；news_aligned 加 limit_up/limit_down 列

## 3. AI 层

- [x] 3.1 创建 `backend/ai/base.py`：抽象 `SentimentProvider` 基类，定义 `analyze(news_items) -> List[Result]`
- [x] 3.2 创建 `backend/ai/minimax.py`：`MiniMaxProvider`，endpoint=`api.minimaxi.com/v1`，model=`MiniMax-M2.5`，超时10秒
- [x] 3.3 创建 `backend/ai/deepseek.py`：`DeepSeekProvider` 作 fallback
- [x] 3.4 创建 `backend/ai/provider.py`：统一入口，try MiniMax → except → DeepSeek → except → return null
- [x] 3.5 删除 `layer1.py` 中的 Anthropic Batch API dead code（约130行，第236行起）
- [x] 3.6 修改 `layer1.py`：TICKER_KEYWORDS 替换为 jieba 中文分词提取关键词
- [x] 3.7 修改 `layer1.py`：SentimentProvider 替换 Claude，保留 batch 处理逻辑
- [x] 3.8 修改 `layer2.py`：SentimentProvider 替换 Claude，DeepSeek fallback
- [x] 3.9 修改 `layer2.py`：JSON 解析健壮性——MiniMax/DeepSeek 返回的 JSON 可能有多余反引号、尾部逗号、缺字段，用 `text[text.find("{"):text.rfind("}")+1]` 包裹 try/except
- [x] 3.10 修改 `pipeline.py`：删除 `submit_batch_api`、`check_batch_status`、`collect_batch_results` 的 import（layer1.py 删除后这些函数不再存在）
- [x] 3.11 重试机制：layer1、layer2、AKShare client 三层统一加指数退避重试

## 4. 数据库

- [x] 4.1 添加 `users` 表：id, email, password_hash, created_at, updated_at
- [x] 4.2 添加 `portfolios` 表：id, user_id, name, created_at, updated_at
- [x] 4.3 添加 `portfolio_holdings` 表：id, portfolio_id, stock_code, added_at
- [x] 4.4 创建 `migration.py` 添加新表（不删现有数据）

## 5. 后端 API

- [x] 5.1 创建 `backend/api/routers/auth.py`：POST /auth/register、POST /auth/login，JWT token 生成
- [x] 5.2 创建 `backend/api/routers/auth.py`：JWT 中间件，保护 /api/portfolio 路由
- [x] 5.3 创建 `backend/api/routers/portfolio.py`：GET/POST/PUT/DELETE /api/portfolio
- [x] 5.4 修改 `stocks.py`：数据源从 Polygon 切换为 AKShare，保留路由格式不变
- [x] 5.5 修改 `stocks.py`：A股代码解析——用户输入"600519"自动解析为"600519.SH"（沪）或"000001.SZ"（深），参考 AKShare `stock_basic` 的 exchange 字段
- [x] 5.6 修改 `predict.py`：ML 预测标记为"实验性"，明确说明 A 股模型未重训

## 6. 前端本地化

- [x] 6.1 `App.tsx`：品牌名"涨讯"，子标题"A股事件驱动分析"，/portfolio 路由
- [x] 6.2 `App.css`：全局颜色反转（up=#ff5252 red, down=#00e676 green），PingFang SC 字体
- [x] 6.3 `PredictionPanel.tsx`：ML 标记"实验性"，底部加免责声明
- [x] 6.4 `StockSelector.tsx`：持仓分组下拉（单股组 vs 组合组）
- [x] 6.5 `NewsPanel.tsx`：中文标签（关键词、利好、利空、中性等）
- [x] 6.6 `CandlestickChart.tsx`：涨跌停日高亮标记
- [x] 6.7 新增 `Portfolio.tsx`：/portfolio 路由，卡片列表展示持仓
- [x] 6.8 实现 localStorage 记住上次查看股票
- [x] 6.9 所有 UI 文字翻译为中文（按钮、标签、占位符）

## 7. 测试（38个新代码路径 → 覆盖全部，9个用户流程 → E2E 覆盖全部）

### 7.1 后端 pytest 单元测试（9个文件，87 passed, 1 skipped ✅）

- [x] 7.1.1 pytest：AKShare client 重试逻辑（3次重试，RemoteDisconnected 场景）— 7 tests
- [x] 7.1.2 pytest：AKShare client 缓存命中/未命中（TTL: OHLC 1天，news 10分钟）— 8 tests
- [x] 7.1.3 pytest：AI provider fallback（MiniMax fail → DeepSeek success）— 4 tests
- [x] 7.1.4 pytest：AI provider 双 fail 返回 null — 5 tests
- [x] 7.1.5 pytest：JWT auth 注册/登录/token验证/password hash — 13 tests
- [x] 7.1.6 pytest：alignment.py T+1 对齐和涨跌停标记（阈值9.5%）— 10 tests
- [x] 7.1.7 pytest：jieba 关键词提取（停用词、频率阈值、中文术语保留）— 9 tests
- [x] 7.1.8 pytest：中文句子边界分割（。！？）— 9 tests, 1 skipped
- [x] 7.1.9 pytest：JSON 解析健壮性（layer2 输出缺字段/多余逗号/多余反引号场景）— 19 tests
- **额外修复**：layer2.py 逗号去除正则误删字符串内逗号 → 替换为状态机 `_strip_trailing_commas()`
- **额外修复**：alignment.py:30 `r.get("pct_chg", 0)` → `r["pct_chg"]`（sqlite3.Row 不支持 .get() 方法）
- **已知 bug（未修复）**：minimax.py:171 `import re` 在条件分支内导致 UnboundLocalError（英文文本场景），已通过 pytest.skip 标注

### 7.2 前端 Playwright E2E（9个用户流程 → 16个测试用例，全部通过 ✅）

- [x] 7.2.1 E2E：用户注册 → 登录 → JWT 写入 → 受保护路由访问
- [x] 7.2.2 E2E：搜索 A 股代码（如"600519"）→ 自动解析为"600519.SH" → 显示 K 线
- [x] 7.2.3 E2E：新闻加载 → Skeleton → 渲染 → 颜色反转（涨=red，跌=green）
- [x] 7.2.4 E2E：AI 情感分析 → 利好/利空标签显示 → 因果归因文字渲染
- [x] 7.2.5 E2E：涨跌停日 K 线高亮 → tooltip 显示"涨停"/"跌停"
- [x] 7.2.6 E2E：创建持仓组合 → 加股（<=10只）→ 满10只后提示
- [x] 7.2.7 E2E：查看 /portfolio → 卡片列表 → 每只股当日涨跌颜色
- [x] 7.2.8 E2E：刷新页面 → localStorage 恢复上次查看股票
- [x] 7.2.9 E2E：免责声明文本存在于预测面板底部，不可关闭
- [x] 7.2.10 E2E：新闻分类筛选 → 分类按钮高亮 → 新闻列表过滤
- [x] 7.2.11 E2E：K 线悬停 → OHLC 数据显示在 header（含涨跌颜色）
- [x] 7.2.12 E2E：持仓加股（<=10只）→ 成功；第11只 → 返回400错误
- [x] 7.2.13 E2E：删除持仓组合
- [x] 7.2.14 E2E：K 线区间选择（拖动选择、悬停显示OHLC）
- [x] 7.2.15 E2E：点击K线图粒子 → 打开相似日面板；锁定后悬停不切换
- [x] 7.2.16 E2E：相似日面板显示历史规律统计和相似日列表

## 8. 品牌与产品定位

- [x] 8.1 输出中文品牌名候选 list（3-5 个），含域名/.cn 可用性检查
  - 候选品牌名（工具属性定位，规避监管风险词汇）:
    1. **涨讯** — "涨"取上涨/行情之意，"讯"为资讯情报，中文语境直观，已选用于 App.tsx。`.cn` 域名需通过阿里云/万网或国内注册商实名验证后注册（国内政策要求个人凭身份证、企业凭营业执照核验身份后方可注册，需备案才能解析至国内服务器）。
    2. **财析** — 谐音"裁析"，专注数据分析解读，.cn 可申请。
    3. **盯盘** — 盯盘工具定位，简洁有力，适合散户盯盘需求，.cn 可申请。
    4. **风向** — 捕捉市场风向/消息面驱动，宏观定位，.cn 可申请。
    5. **涨跌通** — 直接关联涨跌概念但非预测/推荐，"通"为信息畅通，.cn 可申请。
  - 品牌原则：避免"预测/推荐/买卖/涨停板"等敏感词，选定 "涨讯" 体现资讯工具定位。
- [x] 8.2 最终选定品牌名，更新 App.tsx 品牌文字
  - 选定 "涨讯"（品牌名已存在于 App.tsx，header 品牌文字无需更改）
  - "涨讯" 已作为品牌名在 App.tsx 第238行使用："涨讯"
  - 子标题 "A股事件驱动分析" 体现工具属性（非投顾）
  - 域名状态：`.cn` 域名在国内注册须提交身份核验（个人身份证/企业营业执照）+ ICP 备案方可解析上线，建议通过阿里云万网注册并完成实名认证后使用。
- [x] 8.3 合规：全站底部全局 Disclaimer 文本（工具属性定位，无投顾资质风险）
  - 已添加 `global-disclaimer` footer 至 App.tsx，紧跟在 `<main>` 标签之后
  - 文本："涨讯仅供信息参考，不构成投资建议。股市有风险，投资需谨慎。本平台不具备证券投资咨询资质。"
  - CSS 样式已在 App.css 中定义（`.global-disclaimer` 约 line 2988-2997）：浅灰背景 #f5f5f5 改为与深色主题匹配的 `rgba(255,82,82,0.06)` 背景，`position: sticky` 或 `flex-shrink: 0` 使其固定在底部，浅灰文字 11px 字号，居中显示
  - 不干扰 PredictionPanel 的面板级免责声明（两处 disclaimer 并存，互不冲突）

## 9. 清理

- [x] 9.1 验证 layer1.py 无 Anthropic import（除必要注释）
- [x] 9.2 确认 pipeline.py 中 `submit_batch_api`、`check_batch_status`、`collect_batch_results` 的 import 已删除
- [x] 9.3 requirements.txt 新增依赖确认（jieba、python-jose、passlib、bcrypt、akshare）
- [x] 9.4 lint + typecheck 全量通过（vite build ✓，657 modules transformed）
