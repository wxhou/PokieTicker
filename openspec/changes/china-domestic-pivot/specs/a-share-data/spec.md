## ADDED Requirements

### Requirement: AKShare data client with retry and fallback

The system SHALL provide a unified data client that fetches A-share OHLC, news, and limit-up/down data from AKShare, with automatic retry on connection errors and graceful fallback to cached data.

#### Scenario: OHLC data fetched successfully
- **WHEN** user or pipeline requests daily OHLC for a stock
- **THEN** system fetches from AKShare `stock_zh_a_hist()`, retries up to 3 times on `RemoteDisconnected`, and returns pandas DataFrame with columns: 日期, 开盘, 收盘, 最高, 最低, 涨跌幅, 成交额

#### Scenario: AKShare rate-limited
- **WHEN** AKShare returns `RemoteDisconnected` after 3 retries
- **THEN** system returns cached data from local SQLite `ohlc_cache` table (TTL: 1 day), and logs warning

#### Scenario: News fetched with latency metadata
- **WHEN** user requests news for a stock
- **THEN** system fetches from AKShare `stock_news_em()`, returns articles with: 关键词, 新闻标题, 新闻内容, 发布时间, 文章来源, 新闻链接
- **AND** stores news in `news_raw` table with `source='akshare'` and `fetched_at` timestamp

### Requirement: Limit-up/down tagging on trading days

The system SHALL mark each trading day as limit-up, limit-down, or normal based on AKShare `stock_zt_pool_em()` data.

#### Scenario: Limit-up day detected
- **WHEN** a stock's daily price change >= 9.5% (or exchange-specific threshold)
- **THEN** system stores `limit_up=True, limit_down=False` in `news_aligned` or a `trading_days` table

#### Scenario: Limit-down day detected
- **WHEN** a stock's daily price change <= -9.5%
- **THEN** system stores `limit_up=False, limit_down=True`

#### Scenario: Normal trading day
- **WHEN** daily change is between -9.5% and 9.5%
- **THEN** system stores `limit_up=False, limit_down=False`

### Requirement: News-to-trading-day alignment

The system SHALL align news articles to the nearest trading day using the existing `alignment.py` logic, computing forward returns ret_t0, ret_t1, ret_t3, ret_t5, ret_t10.

#### Scenario: News aligned to correct trading day
- **WHEN** a news article is published on a non-trading day (weekend/holiday)
- **THEN** system aligns it to the next trading day

#### Scenario: Forward returns computed correctly
- **WHEN** news is aligned to a trading day
- **THEN** system computes ret_t0 (prev close → trade-day close), ret_t1 (trade-day close → next close), etc.

### Requirement: Local caching layer

The system SHALL cache fetched data in SQLite to reduce AKShare API calls and handle rate limits.

#### Scenario: OHLC cache hit
- **WHEN** cached OHLC data exists for a stock/date with TTL <= 1 day
- **THEN** system returns cached data without calling AKShare

#### Scenario: News cache hit
- **WHEN** cached news exists for a stock with TTL <= 10 minutes
- **THEN** system returns cached news without calling AKShare
