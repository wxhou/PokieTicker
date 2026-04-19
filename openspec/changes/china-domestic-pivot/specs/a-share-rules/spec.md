## ADDED Requirements

### Requirement: T+1 trading alignment

The system SHALL apply T+1 trading rules when computing and displaying returns.

#### Scenario: News published on T day, return shown on T+1
- **WHEN** news is published and stock moves on day T
- **THEN** system SHALL show ret_t1 (next trading day's return) as the primary forward return
- **AND** ret_t0 SHALL show same-day return from previous close to current close

#### Scenario: Stock bought today cannot be sold today
- **WHEN** displaying trading advice context
- **THEN** system SHALL note that A shares follow T+1 (cannot sell same day as buy)

### Requirement: Limit-up/down markers on chart

The system SHALL visually mark limit-up and limit-down days on the candlestick chart.

#### Scenario: Limit-up day rendered
- **WHEN** a trading day is marked limit_up=True
- **THEN** candlestick SHALL be highlighted with a distinct color (e.g., red border)
- **AND** a marker/label "涨停" SHALL appear at that price point

#### Scenario: Limit-down day rendered
- **WHEN** a trading day is marked limit_down=True
- **THEN** candlestick SHALL be highlighted with green border
- **AND** a marker/label "跌停" SHALL appear

### Requirement: Stock code format support

The system SHALL handle A-share and HK-stock code formats correctly.

#### Scenario: A-share code parsed
- **WHEN** user searches or adds "600519"
- **THEN** system SHALL resolve to "600519.SH" (Shanghai) or "000001.SZ" (Shenzhen)
- **AND** all data fetches SHALL use the exchange-qualified code

#### Scenario: HK stock code parsed
- **WHEN** user searches or adds "00700"
- **THEN** system SHALL resolve to "00700.HK"
- **AND** fetch HK-specific data (v1.1, deferred)
