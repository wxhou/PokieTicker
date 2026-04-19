## Context

**当前状态**：PokieTicker 是面向美股的事件驱动分析工具，Polygon.io + Claude Haiku/Sonnet + XGBoost ML 预测。

**目标**：国内版 涨讯，A 股散户因果归因工具。品类定位：不是选股工具，不是行情软件，是因果归因引擎。

**约束**：
- AKShare 依赖 East Money 数据源，高频调用会被限流（`RemoteDisconnected`）
- MiniMax API key 是中国区格式（`sk-cp-`），endpoint 用 `api.minimaxi.com`
- Tushare token 积分几乎为零，核心 API 不可用，先用 AKShare
- ML 模型（A 股）未重训，预测面板降级为辅助展示
- 合规：Disclaimer 必须，无投顾资质风险

**利益相关方**：A 股 1-5 年股龄散户用户

## Goals / Non-Goals

**Goals:**
- 4 周内全链路跑通（A 股日线 + 新闻 + AI 归因），可演示
- 中文品牌、本地化 UI、A 股颜色习惯
- 完整账户体系（注册/登录/持仓管理）
- 涨跌停标记、T+1 对齐

**Non-Goals:**
- ML 模型 A 股重训（v1.1）
- 港股实时行情（v1.1）
- 微信小程序（H5 先跑）
- 微信/支付宝支付
- ICP 备案（技术验证后）
- 美股版本

## Decisions

### D1: 数据层用 AKShare，Tushare 作为付费升级路径

**决定**：AKShare 先行，Tushare 等积分涨上来后切换。

**理由**：
- AKShare 免费、无注册、零配置，验证结果全通（A 股日线/新闻/涨跌停/资金流）
- Tushare 新账号积分几乎为零，核心 API（日线/基本信息）全部权限不足
- AKShare 限流问题通过缓存层缓解：新闻缓存 10 分钟，日线缓存 1 天
- Tushare 新闻权限 ¥1,000/月太贵，等账号有积分再迁

**替代方案**：
- 自建爬虫：维护成本高，被封风险大，放弃
- 专业终端（Wind/iFinD）：¥3,000+/月起步，MVP 阶段不可接受

### D2: AI 层用 MiniMax M2.5，DeepSeek 作备选

**决定**：MiniMax M2.5（主力）+ DeepSeek（备选），统一抽象 Provider 接口。

**理由**：
- MiniMax M2.5 中文财经理解能力通过验证（术语/情感/因果归因全部合格）
- 成本是 Claude 的 1/16，便宜很多
- endpoint 用 `api.minimaxi.com`（中国大陆区）
- DeepSeek 作为 fallback：模型差一些但稳定、便宜

**备选方案**：
- 纯 DeepSeek：中文能力比 MiniMax 弱，暂作备选
- Claude：中国用户访问不稳定，成本高

### D3: 前端完全复用现有架构，只做本地化

**决定**：不改架构，只做颜色/文字/品牌切换。

**理由**：
- React 组件树结构合理（CandlestickChart/NewsPanel/PredictionPanel 等）
- 现有 Skeleton shimmer 动画可直接复用
- App.css 已有完整 dark theme，只需变量替换

**备选方案**：
- 重新设计前端：时间太长，Approach A 的目的就是快速验证

### D4: ML 预测降级为辅助展示

**决定**：PredictionPanel 保留但不作为主推功能，标注"实验性"。

**理由**：
- XGBoost 模型未在 A 股重训，用美股模型预测 A 股不准确
- 展示错误预测比不展示更危险（用户可能据此交易）
- v1.1 重训后再主推

### D5: JWT 账户体系，不用设备 ID

**决定**：完整注册/登录/JWT token，不用设备 ID。

**理由**：
- 国内用户习惯账号体系（vs 美股版设备 ID）
- 持仓管理需要用户身份
- 支持未来多设备登录

### D6: 涨跌停标记在 alignment.py，不在前端

**决定**：涨跌停信息存在数据库，前端读取展示。

**理由**：
- alignment.py 已有 `news_aligned` 表，加一个 `limit_up` / `limit_down` 字段
- 前端只需要读字段渲染，不需要再算
- 涨跌停数据来自 AKShare `stock_zt_pool_em`

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| AKShare 被限流/不稳定 | 本地缓存 + 每日凌晨全量更新 + 备用数据源（AKShare 不同 API）|
| MiniMax API 不可用 | DeepSeek fallback；双失败 → 静默降级（返回原始数据无 AI 解读）|
| ML 预测误导用户 | 降级为"实验性"标签 + 强 Disclaimer |
| A 股特有术语理解不够 | 监控 bad case，用户反馈驱动 prompt 迭代 |
| 数据延迟（新闻 10-20 分钟）| 产品定位为"次日早盘解读"，明确告知用户 |

## Open Questions

1. **港股数据**：AKShare 港股 K 线调用被限流，v1.1 需要单独方案
2. **港股实时**：日线先行，v1.1 再接入富途 OpenAPI
3. **AKShare 稳定性**：生产环境需要做每日数据预缓存，防止早上高峰限流
4. **AI prompt 迭代**：上线后监控 AI 归因质量，收集 bad case 持续优化
5. **品牌名候选**：CEO plan 候选 list 待出，暂定"涨讯"
