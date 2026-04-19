## ADDED Requirements

### Requirement: Unified AI provider interface

The system SHALL provide an abstract `SentimentProvider` interface that supports multiple AI backends (MiniMax primary, DeepSeek fallback), with automatic failover on errors.

#### Scenario: MiniMax returns successfully
- **WHEN** AI analysis request is sent with MiniMax as primary
- **THEN** system returns sentiment, key_discussion, reason_growth, reason_decrease from MiniMax M2.5

#### Scenario: MiniMax fails, DeepSeek fallback
- **WHEN** MiniMax returns error or times out (>10s)
- **THEN** system retries with DeepSeek and returns results if successful
- **AND** logs the fallback event

#### Scenario: Both models fail
- **WHEN** both MiniMax and DeepSeek return errors
- **THEN** system returns `null` for AI analysis fields and logs error
- **AND** the news is shown without AI interpretation (graceful degradation)

### Requirement: A-share financial sentiment analysis

The AI layer SHALL analyze Chinese A-share news and produce structured output: sentiment (利好/利空/中性), key discussion point, growth reasons, decrease reasons.

#### Scenario: Positive news correctly identified
- **WHEN** news contains 分红, 业绩增长, 订单, 政策利好
- **THEN** AI SHALL return `sentiment='利好'` with growth_reasons explaining the positive factors

#### Scenario: Negative news correctly identified
- **WHEN** news contains 净利润下降, 减持, 监管, 竞争加剧
- **THEN** AI SHALL return `sentiment='利空'` with decrease_reasons explaining the negative factors

#### Scenario: Neutral/mixed news handled
- **WHEN** news contains both positive and negative elements (e.g., 业绩下降 but 高分红)
- **THEN** AI SHALL return `sentiment='中性'` and list both growth and decrease factors

### Requirement: Causal attribution output

The AI layer SHALL produce a causal attribution summary explaining WHY a stock moved based on news + price data.

#### Scenario: Attribution ties news to price movement
- **WHEN** AI analyzes a stock with news and price change
- **THEN** output SHALL explicitly tie specific news items to the price movement
- **AND** use neutral language (avoid absolute terms like 必涨, 暴跌, 必将)

### Requirement: Neutral tone enforcement

The AI output SHALL use neutral, objective language suitable for a financial analysis tool.

#### Scenario: Absolute language avoided
- **WHEN** AI generates analysis
- **THEN** output SHALL NOT contain: 必涨, 必跌, 必将, 暴跌, 狂涨, 强烈建议, 一定
- **AND** output SHALL use hedging language: 可能, 倾向于, 历史上, 通常

### Requirement: JSON parsing robustness

The AI provider SHALL handle malformed JSON responses gracefully when parsing LLM output.

#### Scenario: JSON with trailing commas
- **WHEN** LLM returns JSON with trailing commas (e.g., `"key": "value",}`)
- **THEN** parser SHALL strip trailing commas before JSON.loads()

#### Scenario: JSON wrapped in markdown code fences
- **WHEN** LLM returns JSON wrapped in ```json ... ``` or ``` ... ```
- **THEN** parser SHALL extract content between first `{` and last `}`

#### Scenario: JSON with missing required fields
- **WHEN** parsed JSON is missing required fields (e.g., no `sentiment`)
- **THEN** parser SHALL return null for missing fields rather than raising exception
- **AND** log the malformed response for debugging

#### Scenario: Empty or null LLM response
- **WHEN** LLM returns empty string or null
- **THEN** provider SHALL return null and NOT raise exception

### Requirement: Batch sentiment analysis

Layer 1 SHALL process up to 50 articles per API call (MiniMax batch), computing sentiment for each.

#### Scenario: Batch processed successfully
- **WHEN** layer 1 receives 30 news articles for a stock
- **THEN** system sends one batch request to MiniMax with all 30 articles
- **AND** stores individual sentiment results in `layer1_results` table
